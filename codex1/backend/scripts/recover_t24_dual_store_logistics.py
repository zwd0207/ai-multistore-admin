from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
RECOVERY_SYNC_TYPE = "t24_dual_store_logistics_recovery"
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


def _assert_runtime_closed(settings: Settings) -> None:
    if settings.app_env != "production":
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_production_required")
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


def recover_dual_store_logistics(
    db: Session,
    *,
    specs: list[StoreSpec],
    settings: Settings,
    now: datetime | None = None,
) -> dict[str, object]:
    normalized_specs = _normalized_specs(specs)
    _require_process_approval(normalized_specs)
    _assert_runtime_closed(settings)
    current = _utc(now or get_utc_now())
    target_ids = [spec.store_id for spec in normalized_specs]

    stores = db.scalars(
        select(Store)
        .where(Store.id.in_(target_ids))
        .order_by(Store.id.asc())
        .with_for_update()
    ).all()
    if [store.id for store in stores] != target_ids:
        raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_missing")
    stores_by_id = {store.id: store for store in stores}
    for spec in normalized_specs:
        store = stores_by_id[spec.store_id]
        if store.status != "active" or str(store.platform).strip().lower() != "naver":
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_ineligible")
        if hashlib.sha256(store.name.encode("utf-8")).hexdigest() != spec.name_sha256:
            raise LogisticsRecoveryBlocked("t24_logistics_recovery_store_name_mismatch")

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
        if orders.fresh_until is None or _utc(orders.fresh_until) <= current:
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
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "status": "scheduled",
        "store_ids": target_ids,
        "checkpoint_count": len(logistics_rows),
        "first_run_spacing_seconds": int(FIRST_RUN_SPACING.total_seconds()),
        "schedules": schedules,
        "platform_write": False,
        "network_called": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover exactly two guarded T24 Naver logistics checkpoints"
    )
    parser.add_argument("--store", action="append", required=True, type=_parse_store_spec)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            result = recover_dual_store_logistics(
                db,
                specs=args.store,
                settings=get_settings(),
            )
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
