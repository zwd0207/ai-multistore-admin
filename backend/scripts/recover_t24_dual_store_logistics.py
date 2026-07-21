from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings
from app.core.timezone import get_utc_now
from app.database import SessionLocal
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from scripts.prepare_t24_dual_store_automatic_read import (
    PreparationBlocked,
    StoreSpec,
    _parse_store_spec,
    _validate_specs,
)


APPROVAL_VALUE = "owner-approved-dual-store-logistics-recovery"
APPROVAL_ENV = "T24_DUAL_STORE_LOGISTICS_RECOVERY_APPROVAL"
APPROVED_STORE_IDS_ENV = "T24_DUAL_STORE_LOGISTICS_RECOVERY_STORE_IDS"
RECOVERY_SERVICE_STOPPED_VALUE = "api-service-confirmed-stopped"
RECOVERY_SERVICE_STOPPED_ENV = "T24_DUAL_STORE_LOGISTICS_RECOVERY_SERVICE_STATE"
RECOVERY_SYNC_TYPE = "t24_dual_store_logistics_recovery"
CLOSE_APPROVAL_VALUE = "owner-approved-dual-store-logistics-close"
CLOSE_APPROVAL_ENV = "T24_DUAL_STORE_LOGISTICS_CLOSE_APPROVAL"
CLOSE_SERVICE_STOPPED_VALUE = "api-service-confirmed-stopped"
CLOSE_SERVICE_STOPPED_ENV = "T24_DUAL_STORE_LOGISTICS_CLOSE_SERVICE_STATE"
CLOSE_SYNC_TYPE = "t24_dual_store_logistics_close"
CLOSE_ERROR_CODE = "t24_logistics_rollback_closed"
REOPEN_APPROVAL_VALUE = "owner-approved-dual-store-logistics-reopen"
REOPEN_APPROVAL_ENV = "T24_DUAL_STORE_LOGISTICS_REOPEN_APPROVAL"
REOPEN_SYNC_TYPE = "t24_dual_store_logistics_reopen"
RECLOSE_SYNC_TYPE = "t24_dual_store_logistics_reclose"
API_SYSTEMD_UNIT = "ai-multistore-api.service"
ORDERS_SYNC_TYPE = "naver_automatic_orders"
LOGISTICS_SYNC_TYPE = "naver_automatic_logistics"
RECOVERABLE_ERROR_CODE = "naver_logistics_external_order_id_mismatch"
FIRST_RUN_SPACING = timedelta(minutes=1)


class LogisticsRecoveryBlocked(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalized_specs(specs: list[StoreSpec]) -> list[StoreSpec]:
    try:
        return _validate_specs(specs)
    except PreparationBlocked as exc:
        raise LogisticsRecoveryBlocked(exc.error_code) from exc


def _require_process_approval(specs: list[StoreSpec]) -> None:
    if os.environ.get(APPROVAL_ENV) != APPROVAL_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_owner_approval_missing")
    try:
        raw_ids = [
            int(value.strip())
            for value in os.environ.get(APPROVED_STORE_IDS_ENV, "").split(",")
            if value.strip()
        ]
    except ValueError as exc:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_approved_ids_invalid") from exc
    if len(raw_ids) != len(set(raw_ids)):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_approved_ids_duplicate")
    if sorted(raw_ids) != [spec.store_id for spec in specs]:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_approved_ids_mismatch")


def _require_recovery_process_approval(specs: list[StoreSpec]) -> None:
    _require_process_approval(specs)
    if os.environ.get(RECOVERY_SERVICE_STOPPED_ENV) != RECOVERY_SERVICE_STOPPED_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_service_stop_unconfirmed")


def _assert_write_gates_closed(settings: Settings) -> None:
    write_flags = (
        settings.real_api_write_enabled,
        settings.platform_product_write_enabled,
        settings.platform_inventory_write_enabled,
        settings.platform_order_write_enabled,
        settings.customer_platform_write_enabled,
        settings.shipping_platform_write_enabled,
        settings.pxg_naver_shipping_pilot_enabled,
        settings.ai_automatic_operations_enabled,
    )
    if any(write_flags):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_write_gate_open")


def _assert_runtime_approved(settings: Settings) -> None:
    if settings.app_env != "production":
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_production_required")
    if settings.real_api_test_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_parallel_real_test_enabled")
    if not settings.automatic_read_sync_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_automatic_read_disabled")
    if not settings.lifecycle_schedulers_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_lifecycle_scheduler_disabled")
    if not settings.naver_readonly_inquiry_real_read_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_inquiry_runtime_disabled")
    if not settings.pxg_naver_local_read_retention_cleanup_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_cleanup_disabled")
    if not settings.credential_encryption_key:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_encryption_key_missing")
    _assert_write_gates_closed(settings)


def _require_close_process_approval(specs: list[StoreSpec]) -> None:
    if os.environ.get(CLOSE_APPROVAL_ENV) != CLOSE_APPROVAL_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_close_owner_approval_missing")
    if os.environ.get(CLOSE_SERVICE_STOPPED_ENV) != CLOSE_SERVICE_STOPPED_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_close_service_stop_unconfirmed")
    _require_process_approval(specs)


def _assert_close_runtime(settings: Settings, *, target_ids: list[int]) -> None:
    if settings.app_env != "production":
        raise LogisticsRecoveryBlocked("t24_logistics_close_production_required")
    if settings.real_api_test_enabled:
        raise LogisticsRecoveryBlocked("t24_logistics_close_parallel_real_test_enabled")
    if settings.naver_readonly_inquiry_approved_store_id_set != frozenset(target_ids):
        raise LogisticsRecoveryBlocked("t24_logistics_close_allowlist_mismatch")
    _assert_write_gates_closed(settings)


def _require_reopen_process_approval(specs: list[StoreSpec]) -> None:
    if os.environ.get(REOPEN_APPROVAL_ENV) != REOPEN_APPROVAL_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_owner_approval_missing")
    if os.environ.get(CLOSE_SERVICE_STOPPED_ENV) != CLOSE_SERVICE_STOPPED_VALUE:
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_service_stop_unconfirmed")
    _require_process_approval(specs)


def _api_service_is_inactive() -> bool:
    try:
        result = subprocess.run(
            (
                "systemctl",
                "show",
                API_SYSTEMD_UNIT,
                "--property=ActiveState",
                "--value",
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "inactive"


def _active_or_uncleared_lease(checkpoint: SyncCheckpoint, now: datetime) -> bool:
    return bool(
        checkpoint.lease_token
        or (
            checkpoint.lease_expires_at is not None
            and _utc(checkpoint.lease_expires_at) > now
        )
    )


def _checkpoint_by_scope(
    rows: list[SyncCheckpoint],
    *,
    store_id: int,
    sync_type: str,
) -> SyncCheckpoint:
    matches = [
        row
        for row in rows
        if row.store_id == store_id and row.sync_type == sync_type
    ]
    if len(matches) != 1:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_checkpoint_incomplete")
    return matches[0]


def _lock_and_validate_stores(
    db: Session,
    *,
    specs: list[StoreSpec],
    target_ids: list[int],
) -> None:
    stores = db.scalars(
        select(Store)
        .where(Store.id.in_(target_ids))
        .order_by(Store.id.asc())
        .with_for_update()
    ).all()
    if [store.id for store in stores] != target_ids:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_missing")
    stores_by_id = {store.id: store for store in stores}
    for spec in specs:
        store = stores_by_id[spec.store_id]
        if store.status != "active" or str(store.platform).strip().lower() != "naver":
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_ineligible")
        if hashlib.sha256(store.name.encode("utf-8")).hexdigest() != spec.name_sha256:
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_name_mismatch")


def recover_dual_store_logistics(
    db: Session,
    *,
    specs: list[StoreSpec],
    settings: Settings,
    now: datetime | None = None,
    service_stopped_probe: Callable[[], bool] | None = None,
) -> dict[str, object]:
    normalized_specs = _normalized_specs(specs)
    _require_recovery_process_approval(normalized_specs)
    _assert_runtime_approved(settings)
    current = _utc(now or get_utc_now())
    target_ids = [spec.store_id for spec in normalized_specs]
    if settings.naver_readonly_inquiry_approved_store_id_set != frozenset(target_ids):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_allowlist_mismatch")
    if not (service_stopped_probe or _api_service_is_inactive)():
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_service_not_inactive")

    _lock_and_validate_stores(
        db,
        specs=normalized_specs,
        target_ids=target_ids,
    )

    checkpoints = db.scalars(
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.store_id.in_(target_ids),
            SyncCheckpoint.platform == "naver",
        )
        .order_by(SyncCheckpoint.store_id.asc(), SyncCheckpoint.id.asc())
        .with_for_update()
    ).all()
    if any(_active_or_uncleared_lease(row, current) for row in checkpoints):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_active_lease_present")

    logistics_by_store: dict[int, SyncCheckpoint] = {}
    for store_id in target_ids:
        orders = _checkpoint_by_scope(
            checkpoints,
            store_id=store_id,
            sync_type=ORDERS_SYNC_TYPE,
        )
        logistics = _checkpoint_by_scope(
            checkpoints,
            store_id=store_id,
            sync_type=LOGISTICS_SYNC_TYPE,
        )
        if (
            orders.status != "success"
            or not orders.automatic_read_enabled
            or orders.last_synced_at is None
            or orders.fresh_until is None
            or _utc(orders.fresh_until) <= current
            or orders.last_error_code is not None
        ):
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_orders_not_fresh")
        logistics_by_store[store_id] = logistics

    recovery_markers = db.scalars(
        select(SyncLog)
        .where(
            SyncLog.store_id.in_(target_ids),
            SyncLog.platform == "naver",
            SyncLog.sync_type == RECOVERY_SYNC_TYPE,
            SyncLog.status == "success",
        )
        .order_by(SyncLog.store_id.asc(), SyncLog.id.asc())
        .with_for_update()
    ).all()
    if recovery_markers:
        marker_store_ids = {marker.store_id for marker in recovery_markers}
        if marker_store_ids == set(target_ids):
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_already_applied")
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_marker_incomplete")

    logistics_rows = [logistics_by_store[store_id] for store_id in target_ids]
    if all(
        row.status == "idle"
        and row.automatic_read_enabled
        and row.last_error_code is None
        and row.next_run_at is not None
        for row in logistics_rows
    ):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_already_applied")
    if any(
        row.status != "blocked"
        or row.automatic_read_enabled
        or row.last_error_code != RECOVERABLE_ERROR_CODE
        or row.next_run_at is not None
        for row in logistics_rows
    ):
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_checkpoint_state_invalid")

    schedules: list[dict[str, object]] = []
    try:
        for index, store_id in enumerate(target_ids):
            checkpoint = logistics_by_store[store_id]
            next_run_at = current + FIRST_RUN_SPACING * index
            checkpoint.status = "idle"
            checkpoint.automatic_read_enabled = True
            checkpoint.next_run_at = next_run_at
            checkpoint.retry_count = 0
            checkpoint.last_error_code = None
            checkpoint.lease_token = None
            checkpoint.lease_expires_at = None
            db.add(SyncLog(
                store_id=store_id,
                platform="naver",
                sync_type=RECOVERY_SYNC_TYPE,
                status="success",
                started_at=current,
                finished_at=current,
                message="Guarded logistics checkpoint recovery scheduled",
                raw_summary={
                    "status": "scheduled",
                    "resource": "logistics",
                    "recovered_error_code": RECOVERABLE_ERROR_CODE,
                    "first_run_offset_seconds": int((FIRST_RUN_SPACING * index).total_seconds()),
                    "platform_write": False,
                    "network_called": False,
                },
            ))
            schedules.append({
                "store_id": store_id,
                "next_run_at": next_run_at.isoformat(),
            })
        result = {
            "status": "scheduled",
            "store_ids": target_ids,
            "checkpoint_count": len(logistics_rows),
            "first_run_spacing_seconds": int(FIRST_RUN_SPACING.total_seconds()),
            "schedules": schedules,
            "platform_write": False,
            "network_called": False,
        }
        _validate_cli_result("recover", result)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def close_dual_store_logistics(
    db: Session,
    *,
    specs: list[StoreSpec],
    settings: Settings,
    now: datetime | None = None,
    service_stopped_probe: Callable[[], bool] | None = None,
) -> dict[str, object]:
    normalized_specs = _normalized_specs(specs)
    _require_close_process_approval(normalized_specs)
    current = _utc(now or get_utc_now())
    target_ids = [spec.store_id for spec in normalized_specs]
    _assert_close_runtime(settings, target_ids=target_ids)
    if not (service_stopped_probe or _api_service_is_inactive)():
        raise LogisticsRecoveryBlocked("t24_logistics_close_service_not_inactive")
    _lock_and_validate_stores(
        db,
        specs=normalized_specs,
        target_ids=target_ids,
    )

    checkpoints = db.scalars(
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.store_id.in_(target_ids),
            SyncCheckpoint.platform == "naver",
        )
        .order_by(SyncCheckpoint.store_id.asc(), SyncCheckpoint.id.asc())
        .with_for_update()
    ).all()
    logistics_rows = [
        _checkpoint_by_scope(
            checkpoints,
            store_id=store_id,
            sync_type=LOGISTICS_SYNC_TYPE,
        )
        for store_id in target_ids
    ]

    recovery_markers = db.scalars(select(SyncLog).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == RECOVERY_SYNC_TYPE,
        SyncLog.status == "success",
    ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc()).with_for_update()).all()
    if len(recovery_markers) != len(target_ids) or {
        marker.store_id for marker in recovery_markers
    } != set(target_ids):
        raise LogisticsRecoveryBlocked("t24_logistics_close_recovery_marker_incomplete")

    close_markers = db.scalars(select(SyncLog).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == CLOSE_SYNC_TYPE,
        SyncLog.status == "success",
    ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc()).with_for_update()).all()
    reopen_markers = db.scalars(select(SyncLog).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == REOPEN_SYNC_TYPE,
        SyncLog.status == "success",
    ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc()).with_for_update()).all()
    reclose_markers = db.scalars(select(SyncLog).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == RECLOSE_SYNC_TYPE,
        SyncLog.status == "success",
    ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc()).with_for_update()).all()

    def complete_markers(markers: list[SyncLog]) -> bool:
        return len(markers) == len(target_ids) and {
            marker.store_id for marker in markers
        } == set(target_ids)

    for markers in (close_markers, reopen_markers, reclose_markers):
        if markers and not complete_markers(markers):
            raise LogisticsRecoveryBlocked("t24_logistics_close_marker_incomplete")

    already_closed = all(
        not row.automatic_read_enabled
        and row.status == "blocked"
        and row.last_error_code == CLOSE_ERROR_CODE
        and row.next_run_at is None
        and row.lease_token is None
        and row.lease_expires_at is None
        for row in logistics_rows
    )
    if close_markers and already_closed:
        raise LogisticsRecoveryBlocked("t24_logistics_close_already_applied")
    if not close_markers:
        if reopen_markers or reclose_markers:
            raise LogisticsRecoveryBlocked("t24_logistics_close_marker_incomplete")
        close_sync_type = CLOSE_SYNC_TYPE
    else:
        if not complete_markers(reopen_markers) or reclose_markers:
            raise LogisticsRecoveryBlocked("t24_logistics_close_marker_incomplete")
        close_sync_type = RECLOSE_SYNC_TYPE

    try:
        for row in logistics_rows:
            row.automatic_read_enabled = False
            row.status = "blocked"
            row.next_run_at = None
            row.fresh_until = current
            row.retry_count = 0
            row.last_error_code = CLOSE_ERROR_CODE
            row.lease_token = None
            row.lease_expires_at = None
            db.add(SyncLog(
                store_id=row.store_id,
                platform="naver",
                sync_type=close_sync_type,
                status="success",
                started_at=current,
                finished_at=current,
                message="Guarded logistics checkpoint closure applied",
                raw_summary={
                    "status": "closed",
                    "resource": "logistics",
                    "platform_write": False,
                    "network_called": False,
                    "records_deleted": False,
                },
            ))
        result = {
            "status": "closed",
            "store_ids": target_ids,
            "checkpoint_count": len(logistics_rows),
            "platform_write": False,
            "network_called": False,
            "records_deleted": False,
        }
        _validate_cli_result("close", result)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def reopen_closed_dual_store_logistics(
    db: Session,
    *,
    specs: list[StoreSpec],
    settings: Settings,
    now: datetime | None = None,
    service_stopped_probe: Callable[[], bool] | None = None,
) -> dict[str, object]:
    normalized_specs = _normalized_specs(specs)
    _require_reopen_process_approval(normalized_specs)
    _assert_runtime_approved(settings)
    current = _utc(now or get_utc_now())
    target_ids = [spec.store_id for spec in normalized_specs]
    if settings.naver_readonly_inquiry_approved_store_id_set != frozenset(target_ids):
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_allowlist_mismatch")
    if not (service_stopped_probe or _api_service_is_inactive)():
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_service_not_inactive")
    _lock_and_validate_stores(
        db,
        specs=normalized_specs,
        target_ids=target_ids,
    )

    checkpoints = db.scalars(
        select(SyncCheckpoint)
        .where(
            SyncCheckpoint.store_id.in_(target_ids),
            SyncCheckpoint.platform == "naver",
        )
        .order_by(SyncCheckpoint.store_id.asc(), SyncCheckpoint.id.asc())
        .with_for_update()
    ).all()
    if any(_active_or_uncleared_lease(row, current) for row in checkpoints):
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_active_lease_present")

    logistics_rows: list[SyncCheckpoint] = []
    for store_id in target_ids:
        orders = _checkpoint_by_scope(
            checkpoints,
            store_id=store_id,
            sync_type=ORDERS_SYNC_TYPE,
        )
        if (
            orders.status != "success"
            or not orders.automatic_read_enabled
            or orders.last_synced_at is None
            or orders.fresh_until is None
            or _utc(orders.fresh_until) <= current
            or orders.last_error_code is not None
        ):
            raise LogisticsRecoveryBlocked("t24_logistics_reopen_orders_not_fresh")
        logistics_rows.append(_checkpoint_by_scope(
            checkpoints,
            store_id=store_id,
            sync_type=LOGISTICS_SYNC_TYPE,
        ))

    def locked_markers(sync_type: str) -> list[SyncLog]:
        return db.scalars(select(SyncLog).where(
            SyncLog.store_id.in_(target_ids),
            SyncLog.platform == "naver",
            SyncLog.sync_type == sync_type,
            SyncLog.status == "success",
        ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc()).with_for_update()).all()

    for sync_type, error_code in (
        (RECOVERY_SYNC_TYPE, "t24_logistics_reopen_recovery_marker_incomplete"),
        (CLOSE_SYNC_TYPE, "t24_logistics_reopen_close_marker_incomplete"),
    ):
        markers = locked_markers(sync_type)
        if len(markers) != len(target_ids) or {
            marker.store_id for marker in markers
        } != set(target_ids):
            raise LogisticsRecoveryBlocked(error_code)

    reopen_markers = locked_markers(REOPEN_SYNC_TYPE)
    if reopen_markers:
        if len(reopen_markers) == len(target_ids) and {
            marker.store_id for marker in reopen_markers
        } == set(target_ids):
            raise LogisticsRecoveryBlocked("t24_logistics_reopen_already_applied")
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_marker_incomplete")
    if locked_markers(RECLOSE_SYNC_TYPE):
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_reclose_marker_present")

    if any(
        row.status != "blocked"
        or row.automatic_read_enabled
        or row.last_error_code != CLOSE_ERROR_CODE
        or row.next_run_at is not None
        or row.lease_token is not None
        or row.lease_expires_at is not None
        for row in logistics_rows
    ):
        raise LogisticsRecoveryBlocked("t24_logistics_reopen_checkpoint_state_invalid")

    schedules: list[dict[str, object]] = []
    try:
        for index, row in enumerate(logistics_rows):
            next_run_at = current + FIRST_RUN_SPACING * index
            row.status = "idle"
            row.automatic_read_enabled = True
            row.next_run_at = next_run_at
            row.retry_count = 0
            row.last_error_code = None
            row.lease_token = None
            row.lease_expires_at = None
            db.add(SyncLog(
                store_id=row.store_id,
                platform="naver",
                sync_type=REOPEN_SYNC_TYPE,
                status="success",
                started_at=current,
                finished_at=current,
                message="Guarded logistics checkpoint reopen scheduled",
                raw_summary={
                    "status": "scheduled",
                    "resource": "logistics",
                    "first_run_offset_seconds": int((FIRST_RUN_SPACING * index).total_seconds()),
                    "platform_write": False,
                    "network_called": False,
                    "records_deleted": False,
                },
            ))
            schedules.append({
                "store_id": row.store_id,
                "next_run_at": next_run_at.isoformat(),
            })
        result = {
            "status": "scheduled",
            "store_ids": target_ids,
            "checkpoint_count": len(logistics_rows),
            "first_run_spacing_seconds": int(FIRST_RUN_SPACING.total_seconds()),
            "schedules": schedules,
            "platform_write": False,
            "network_called": False,
            "records_deleted": False,
        }
        _validate_cli_result("reopen", result)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def _validate_cli_result(mode: str, result: dict[str, object]) -> None:
    if result.get("status") != ("closed" if mode == "close" else "scheduled"):
        raise ValueError("invalid T24 logistics action status")
    store_ids = result.get("store_ids")
    if (
        not isinstance(store_ids, list)
        or len(store_ids) != 2
        or any(not isinstance(store_id, int) or store_id <= 0 for store_id in store_ids)
        or len(set(store_ids)) != 2
        or result.get("checkpoint_count") != 2
        or result.get("platform_write") is not False
        or result.get("network_called") is not False
    ):
        raise ValueError("invalid T24 logistics action safety contract")
    if mode in {"close", "reopen"} and result.get("records_deleted") is not False:
        raise ValueError("invalid T24 logistics record-retention contract")
    if mode != "close":
        schedules = result.get("schedules")
        if (
            result.get("first_run_spacing_seconds") != int(FIRST_RUN_SPACING.total_seconds())
            or not isinstance(schedules, list)
            or len(schedules) != 2
            or [item.get("store_id") for item in schedules if isinstance(item, dict)] != store_ids
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("next_run_at"), str)
                or not item["next_run_at"]
                for item in schedules
            )
        ):
            raise ValueError("invalid T24 logistics schedule contract")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover exactly two guarded T24 Naver logistics checkpoints"
    )
    parser.add_argument("--mode", choices=("recover", "close", "reopen"), required=True)
    parser.add_argument("--store", action="append", required=True, type=_parse_store_spec)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            actions = {
                "recover": recover_dual_store_logistics,
                "close": close_dual_store_logistics,
                "reopen": reopen_closed_dual_store_logistics,
            }
            action = actions[args.mode]
            result = action(db, specs=args.store, settings=get_settings())
            _validate_cli_result(args.mode, result)
    except LogisticsRecoveryBlocked as exc:
        print(json.dumps({"status": "blocked", "error_code": exc.error_code}), file=sys.stderr)
        return 2
    except Exception:
        print(
            json.dumps({"status": "failed", "error_code": "t24_logistics_recovery_failed"}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
