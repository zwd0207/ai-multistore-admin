from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.database import SessionLocal
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import automatic_read_sync_service, naver_readonly_inquiry_service


APPROVAL_VALUE = "owner-approved-dual-store-readonly"
PREPARATION_SYNC_TYPE = naver_readonly_inquiry_service.DUAL_STORE_PREPARATION_SYNC_TYPE
RESOURCE_ORDER = automatic_read_sync_service.PREPARED_ACTIVATION_RESOURCE_ORDER
FIRST_RUN_SPACING = timedelta(minutes=1)
ORDER_INITIAL_LOOKBACK = timedelta(days=30)
MIN_ACTIVATION_LEAD = timedelta(minutes=5)
MAX_ACTIVATION_LEAD = timedelta(hours=1)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PreparationBlocked(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class StoreSpec:
    store_id: int
    name_sha256: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_specs(specs: list[StoreSpec]) -> list[StoreSpec]:
    if len(specs) != 2:
        raise PreparationBlocked("t24_exactly_two_stores_required")
    store_ids = [spec.store_id for spec in specs]
    if any(type(store_id) is not int or store_id <= 0 for store_id in store_ids):
        raise PreparationBlocked("t24_store_id_invalid")
    if len(set(store_ids)) != len(store_ids):
        raise PreparationBlocked("t24_store_id_duplicate")
    normalized = []
    for spec in specs:
        name_hash = spec.name_sha256.strip().lower()
        if not SHA256_PATTERN.fullmatch(name_hash):
            raise PreparationBlocked("t24_store_name_hash_invalid")
        normalized.append(StoreSpec(store_id=spec.store_id, name_sha256=name_hash))
    return sorted(normalized, key=lambda item: item.store_id)


def _require_process_approval(specs: list[StoreSpec]) -> None:
    if os.environ.get("T24_DUAL_STORE_PREPARATION_APPROVAL") != APPROVAL_VALUE:
        raise PreparationBlocked("t24_dual_store_owner_approval_missing")
    try:
        raw_approved_ids = [
            int(value.strip())
            for value in os.environ.get("T24_DUAL_STORE_PREPARATION_STORE_IDS", "").split(",")
            if value.strip()
        ]
    except ValueError as exc:
        raise PreparationBlocked("t24_dual_store_approved_ids_invalid") from exc
    if len(raw_approved_ids) != len(set(raw_approved_ids)):
        raise PreparationBlocked("t24_dual_store_approved_ids_duplicate")
    approved_ids = sorted(raw_approved_ids)
    if approved_ids != [spec.store_id for spec in specs]:
        raise PreparationBlocked("t24_dual_store_approved_ids_mismatch")


def _assert_runtime_closed(settings: Settings) -> None:
    if settings.app_env != "production":
        raise PreparationBlocked("t24_production_runtime_required")
    if settings.real_api_test_enabled:
        raise PreparationBlocked("t24_parallel_real_test_enabled")
    if settings.automatic_read_sync_enabled:
        raise PreparationBlocked("t24_automatic_read_must_remain_disabled")
    if settings.naver_readonly_inquiry_real_read_enabled:
        raise PreparationBlocked("t24_persistent_inquiry_gate_must_remain_disabled")
    if settings.lifecycle_schedulers_enabled:
        raise PreparationBlocked("t24_lifecycle_scheduler_must_remain_disabled")
    if not settings.pxg_naver_local_read_retention_cleanup_enabled:
        raise PreparationBlocked("t24_readonly_retention_cleanup_required")
    if not settings.credential_encryption_key:
        raise PreparationBlocked("t24_credential_encryption_key_missing")
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
        raise PreparationBlocked("t24_platform_write_gate_open")


def _validate_activation_at(*, now: datetime, activation_at: datetime) -> datetime:
    normalized = _utc(activation_at)
    if normalized < now + MIN_ACTIVATION_LEAD:
        raise PreparationBlocked("t24_activation_time_too_soon")
    if normalized > now + MAX_ACTIVATION_LEAD:
        raise PreparationBlocked("t24_activation_time_too_far")
    return normalized


def _safe_manual_resume_log(db: Session, *, store_id: int) -> SyncLog:
    rows = db.scalars(select(SyncLog).where(
        SyncLog.store_id == store_id,
        SyncLog.platform == "naver",
        SyncLog.sync_type == "manual_batch_sync",
        SyncLog.status == "success",
    ).order_by(SyncLog.finished_at.desc(), SyncLog.id.desc())).all()
    for row in rows:
        summary = row.raw_summary if isinstance(row.raw_summary, dict) else {}
        if summary.get("status") != "success" or summary.get("platform_write") is not False:
            continue
        items = summary.get("items") if isinstance(summary.get("items"), list) else []
        by_resource = {
            str(item.get("resource")): item
            for item in items
            if isinstance(item, dict) and item.get("platform") in {None, "naver"}
        }
        if all(
            isinstance(by_resource.get(resource), dict)
            and by_resource[resource].get("status") == "success"
            and by_resource[resource].get("platform_write") is False
            for resource in ("orders", "products")
        ):
            return row
    raise PreparationBlocked("t24_safe_manual_resume_log_missing")


def _assert_store_ready(
    db: Session,
    *,
    spec: StoreSpec,
    settings: Settings,
    now: datetime,
) -> tuple[ApiCredential, SyncLog]:
    store = db.get(Store, spec.store_id)
    if store is None or store.status != "active" or str(store.platform).strip().lower() != "naver":
        raise PreparationBlocked("t24_store_ineligible")
    if hashlib.sha256(store.name.encode("utf-8")).hexdigest() != spec.name_sha256:
        raise PreparationBlocked("t24_store_name_mismatch")
    try:
        credential = naver_readonly_inquiry_service._approved_inquiry_credential(
            db,
            store_id=store.id,
        )
    except ApiError as exc:
        raise PreparationBlocked(str(exc.error_code or "t24_inquiry_credential_not_ready")) from exc
    try:
        from app.services.encryption import decrypt_value

        secret = decrypt_value(credential.encrypted_secret_key)
    except ApiError as exc:
        raise PreparationBlocked("t24_credential_decrypt_failed") from exc
    if not secret:
        raise PreparationBlocked("t24_credential_decrypt_failed")
    try:
        naver_readonly_inquiry_service.assert_naver_inquiry_cleanup_healthy(
            db,
            store_id=store.id,
            settings=settings,
            now=now,
        )
    except ApiError as exc:
        raise PreparationBlocked(str(exc.error_code or "t24_cleanup_health_blocked")) from exc
    return credential, _safe_manual_resume_log(db, store_id=store.id)


def _prepared_checkpoint_is_pristine(
    checkpoint: SyncCheckpoint,
    *,
    manual_resume_at: datetime,
    order_resume_at: datetime,
    expected_next_run_at: datetime,
) -> bool:
    resource = automatic_read_sync_service._resource_for_checkpoint(checkpoint)
    expected_resume = (
        order_resume_at
        if resource == "orders"
        else manual_resume_at if resource == "products" else None
    )
    actual_resume = _utc(checkpoint.last_synced_at) if checkpoint.last_synced_at else None
    return bool(
        checkpoint.automatic_read_enabled
        and checkpoint.status == "idle"
        and checkpoint.next_run_at is not None
        and _utc(checkpoint.next_run_at) == expected_next_run_at
        and checkpoint.fresh_until is None
        and checkpoint.retry_count == 0
        and checkpoint.last_error_code is None
        and checkpoint.last_attempt_at is None
        and checkpoint.lease_token is None
        and checkpoint.lease_expires_at is None
        and checkpoint.cursor_value is None
        and checkpoint.window_start_at is None
        and checkpoint.window_end_at is None
        and actual_resume == expected_resume
    )


def _valid_preparation_markers(
    db: Session,
    *,
    target_ids: list[int],
    ready: dict[int, tuple[ApiCredential, SyncLog]],
    activation_at: datetime,
) -> bool:
    markers = db.scalars(select(SyncLog).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == PREPARATION_SYNC_TYPE,
        SyncLog.status == "success",
    ).order_by(SyncLog.store_id.asc(), SyncLog.id.asc())).all()
    if len(markers) != len(target_ids) or [marker.store_id for marker in markers] != target_ids:
        return False
    for store_index, marker in enumerate(markers):
        credential, resume_log = ready[marker.store_id]
        summary = marker.raw_summary if isinstance(marker.raw_summary, dict) else {}
        if summary != {
            "status": "success",
            "credential_id": credential.id,
            "resume_sync_log_id": resume_log.id,
            "resource_count": len(RESOURCE_ORDER),
            "activation_at": activation_at.isoformat(),
            "order_initial_lookback_days": ORDER_INITIAL_LOOKBACK.days,
            "first_run_offset_seconds": int(
                FIRST_RUN_SPACING.total_seconds() * len(RESOURCE_ORDER) * store_index
            ),
            "platform_write": False,
            "network_called": False,
        }:
            return False
    return True


def prepare_dual_store_automatic_read(
    db: Session,
    *,
    specs: list[StoreSpec],
    settings: Settings,
    activation_at: datetime,
    now: datetime | None = None,
) -> dict[str, object]:
    normalized_specs = _validate_specs(specs)
    _assert_runtime_closed(settings)
    current = _utc(now or get_utc_now())
    scheduled_activation = _validate_activation_at(now=current, activation_at=activation_at)
    ready = {
        spec.store_id: _assert_store_ready(db, spec=spec, settings=settings, now=current)
        for spec in normalized_specs
    }
    target_ids = [spec.store_id for spec in normalized_specs]
    if settings.naver_readonly_inquiry_approved_store_id_set != frozenset(target_ids):
        raise PreparationBlocked("t24_runtime_allowlist_mismatch")
    if automatic_read_sync_service._eligible_store_ids(db) != target_ids:
        raise PreparationBlocked("t24_eligible_store_set_mismatch")

    sync_types = [config["sync_type"] for config in automatic_read_sync_service.RESOURCE_CONFIG.values()]
    checkpoints = db.scalars(select(SyncCheckpoint).where(
        SyncCheckpoint.platform == "naver",
        SyncCheckpoint.sync_type.in_(sync_types),
    ).order_by(SyncCheckpoint.store_id.asc(), SyncCheckpoint.id.asc())).all()
    if any(checkpoint.store_id not in target_ids for checkpoint in checkpoints):
        raise PreparationBlocked("t24_unapproved_automatic_checkpoint_present")
    if any(
        checkpoint.lease_token
        or (checkpoint.lease_expires_at and _utc(checkpoint.lease_expires_at) > current)
        for checkpoint in checkpoints
    ):
        raise PreparationBlocked("t24_active_automatic_lease_present")

    if checkpoints:
        if len(checkpoints) != len(target_ids) * len(RESOURCE_ORDER):
            raise PreparationBlocked("t24_partial_checkpoint_set_present")
        if any(_utc(checkpoint.next_run_at) <= current for checkpoint in checkpoints if checkpoint.next_run_at):
            raise PreparationBlocked("t24_activation_schedule_expired")
        expected_schedule: dict[tuple[int, str], datetime] = {}
        sequence = 0
        for store_id in target_ids:
            for resource in RESOURCE_ORDER:
                expected_schedule[(store_id, resource)] = scheduled_activation + FIRST_RUN_SPACING * sequence
                sequence += 1
        for checkpoint in checkpoints:
            resume_log = ready[checkpoint.store_id][1]
            manual_resume_at = _utc(resume_log.finished_at or resume_log.started_at)
            resource = automatic_read_sync_service._resource_for_checkpoint(checkpoint)
            if not _prepared_checkpoint_is_pristine(
                checkpoint,
                manual_resume_at=manual_resume_at,
                order_resume_at=scheduled_activation - ORDER_INITIAL_LOOKBACK,
                expected_next_run_at=expected_schedule[(checkpoint.store_id, resource)],
            ):
                raise PreparationBlocked("t24_checkpoint_not_pristine")
        if not _valid_preparation_markers(
            db,
            target_ids=target_ids,
            ready=ready,
            activation_at=scheduled_activation,
        ):
            raise PreparationBlocked("t24_preparation_marker_mismatch")
        return {
            "status": "already_prepared",
            "store_ids": target_ids,
            "checkpoint_count": len(checkpoints),
            "activation_at": scheduled_activation.isoformat(),
            "platform_write": False,
            "network_called": False,
        }

    existing_markers = db.scalar(select(SyncLog.id).where(
        SyncLog.store_id.in_(target_ids),
        SyncLog.platform == "naver",
        SyncLog.sync_type == PREPARATION_SYNC_TYPE,
    ).limit(1))
    if existing_markers is not None:
        raise PreparationBlocked("t24_orphaned_preparation_marker")

    created = []
    sequence = 0
    for store_index, spec in enumerate(normalized_specs):
        credential, resume_log = ready[spec.store_id]
        resume_at = _utc(resume_log.finished_at or resume_log.started_at)
        for resource in RESOURCE_ORDER:
            config = automatic_read_sync_service.RESOURCE_CONFIG[resource]
            checkpoint = SyncCheckpoint(
                store_id=spec.store_id,
                platform="naver",
                sync_type=config["sync_type"],
                automatic_read_enabled=True,
                status="idle",
                next_run_at=scheduled_activation + FIRST_RUN_SPACING * sequence,
                last_synced_at=(
                    scheduled_activation - ORDER_INITIAL_LOOKBACK
                    if resource == "orders"
                    else resume_at if resource == "products" else None
                ),
            )
            db.add(checkpoint)
            created.append((spec.store_id, resource, checkpoint))
            sequence += 1
        db.add(SyncLog(
            store_id=spec.store_id,
            platform="naver",
            sync_type=PREPARATION_SYNC_TYPE,
            status="success",
            started_at=current,
            finished_at=current,
            message="Dual-store automatic readonly activation prepared",
            raw_summary={
                "status": "success",
                "credential_id": credential.id,
                "resume_sync_log_id": resume_log.id,
                "resource_count": len(RESOURCE_ORDER),
                "activation_at": scheduled_activation.isoformat(),
                "order_initial_lookback_days": ORDER_INITIAL_LOOKBACK.days,
                "first_run_offset_seconds": int(
                    FIRST_RUN_SPACING.total_seconds() * len(RESOURCE_ORDER) * store_index
                ),
                "platform_write": False,
                "network_called": False,
            },
        ))
    db.commit()
    return {
        "status": "prepared",
        "store_ids": target_ids,
        "checkpoint_count": len(created),
        "first_run_spacing_seconds": int(FIRST_RUN_SPACING.total_seconds()),
        "activation_at": scheduled_activation.isoformat(),
        "platform_write": False,
        "network_called": False,
    }


def _parse_store_spec(value: str) -> StoreSpec:
    store_id, separator, name_hash = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("store must use STORE_ID:NAME_SHA256")
    try:
        parsed_id = int(store_id)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("store ID must be an integer") from exc
    return StoreSpec(parsed_id, name_hash)


def _parse_activation_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("activation time must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("activation time must include a timezone offset")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare two approved Naver stores for T24 automatic readonly sync")
    parser.add_argument("--store", action="append", required=True, type=_parse_store_spec)
    parser.add_argument("--activation-at", required=True, type=_parse_activation_at)
    args = parser.parse_args()
    try:
        specs = _validate_specs(args.store)
        _require_process_approval(specs)
        with SessionLocal() as db:
            result = prepare_dual_store_automatic_read(
                db,
                specs=specs,
                settings=get_settings(),
                activation_at=args.activation_at,
            )
    except PreparationBlocked as exc:
        print(json.dumps({"status": "blocked", "error_code": exc.error_code}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"status": "failed", "error_code": "t24_dual_store_preparation_failed"}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
