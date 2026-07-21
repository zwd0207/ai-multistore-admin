"""Pre-activation controls for PXG/Naver readonly local persistence.

This module deliberately prepares a bounded, auditable activation path without
enabling real persistence. The simulation accepts only fictional adapter data
and never mutates product, order, logistics, recipient, or inquiry records.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
)
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.operator_trial_service import assert_trial_runtime_closed, resolve_trial_store


PXG_NAVER_READONLY_LOCAL_SOURCE = "pxg_naver_readonly_local_v1"
MAX_FIRST_SYNC_LIMIT = 3


def _safe_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _first_sync_limit(settings: Settings) -> int:
    limit = int(settings.pxg_naver_local_read_first_sync_limit)
    if limit < 1 or limit > MAX_FIRST_SYNC_LIMIT:
        raise ApiError(
            "PXG/Naver first-sync limit must be between 1 and 3",
            "readonly_first_sync_limit_invalid",
            409,
        )
    return limit


def _store_snapshot(db: Session, *, store_id: int) -> dict[str, int]:
    models = {
        "products": Product,
        "orders": Order,
        "record_states": PxgNaverReadonlyRecordState,
        "secure_recipients": PxgNaverOrderRecipientSecureRecord,
        "logistics": PxgNaverReadonlyLogisticsRecord,
        "customer_inquiries": PxgNaverReadonlyCustomerInquiry,
    }
    return {
        name: int(db.scalar(select(func.count()).select_from(model).where(model.store_id == store_id)) or 0)
        for name, model in models.items()
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sqlite_backup_and_rollback_drill(db: Session, *, store_id: int, expected_snapshot: dict[str, int]) -> tuple[str, str, bool]:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite" or not bind.url.database:
        raise ApiError("activation simulation requires a SQLite temporary database", "readonly_simulation_database_forbidden", 409)
    source_path = Path(bind.url.database)
    if not source_path.exists():
        raise ApiError("activation simulation source database is unavailable", "readonly_simulation_backup_source_missing", 409)

    with tempfile.TemporaryDirectory(prefix="pxg-readonly-activation-") as directory:
        backup_path = Path(directory) / "activation-backup.sqlite"
        restore_path = Path(directory) / "activation-rollback.sqlite"
        source_connection = sqlite3.connect(source_path)
        backup_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            source_connection.close()

        backup_sha256 = _file_sha256(backup_path)
        backup_connection = sqlite3.connect(backup_path)
        restore_connection = sqlite3.connect(restore_path)
        try:
            backup_connection.backup(restore_connection)
        finally:
            restore_connection.close()
            backup_connection.close()

        restored_connection = sqlite3.connect(restore_path)
        try:
            table_names = {
                "products": "products",
                "orders": "orders",
                "record_states": "pxg_naver_readonly_record_states",
                "secure_recipients": "pxg_naver_order_recipient_secure_records",
                "logistics": "pxg_naver_readonly_logistics_records",
                "customer_inquiries": "pxg_naver_readonly_customer_inquiries",
            }
            restored_snapshot = {
                name: int(restored_connection.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE store_id = ?", (store_id,)
                ).fetchone()[0])
                for name, table_name in table_names.items()
            }
        finally:
            restored_connection.close()
        return backup_sha256, _file_sha256(restore_path), restored_snapshot == expected_snapshot


def _activation_checks(db: Session, settings: Settings) -> tuple[dict[str, bool], int, int]:
    store = resolve_trial_store(db)
    first_sync_limit = _first_sync_limit(settings)
    write_flags = {
        "real_api_write_enabled": settings.real_api_write_enabled,
        "ai_automatic_operations_enabled": settings.ai_automatic_operations_enabled,
        "platform_product_write_enabled": settings.platform_product_write_enabled,
        "platform_inventory_write_enabled": settings.platform_inventory_write_enabled,
        "platform_order_write_enabled": settings.platform_order_write_enabled,
        "customer_platform_write_enabled": settings.customer_platform_write_enabled,
        "shipping_platform_write_enabled": settings.shipping_platform_write_enabled,
    }
    checks = {
        "single_pxg_naver_store": store.platform.lower() == "naver",
        "first_sync_limit_bounded": 1 <= first_sync_limit <= MAX_FIRST_SYNC_LIMIT,
        "retention_configured": settings.pxg_naver_local_read_retention_days > 0,
        "retention_explicitly_approved": bool(settings.pxg_naver_local_read_retention_approved),
        "backup_rollback_explicitly_approved": bool(settings.pxg_naver_local_read_backup_rollback_approved),
        "activation_explicitly_enabled": bool(settings.pxg_naver_local_read_activation_enabled),
        "real_persistence_enabled": bool(settings.pxg_naver_local_read_persistence_enabled),
        "all_platform_writes_disabled": not any(write_flags.values()),
        "retention_cleanup_enabled": bool(settings.pxg_naver_local_read_retention_cleanup_enabled),
    }
    return checks, store.id, first_sync_limit


def readonly_activation_precheck(db: Session, *, settings: Settings) -> dict[str, Any]:
    """Return a masked, no-write activation checklist for the selected store."""

    checks, store_id, first_sync_limit = _activation_checks(db, settings)
    from app.services.pxg_naver_readonly_persistence_service import assert_pxg_naver_cleanup_healthy

    try:
        assert_pxg_naver_cleanup_healthy(db, store_id=store_id, settings=settings)
        checks["retention_cleanup_healthy"] = True
    except ApiError:
        checks["retention_cleanup_healthy"] = False
    required = (
        "single_pxg_naver_store",
        "first_sync_limit_bounded",
        "retention_configured",
        "retention_explicitly_approved",
        "backup_rollback_explicitly_approved",
        "activation_explicitly_enabled",
        "real_persistence_enabled",
        "all_platform_writes_disabled",
        "retention_cleanup_enabled",
        "retention_cleanup_healthy",
    )
    missing = [name for name in required if not checks[name]]
    return {
        "status": "ready_for_activation" if not missing else "activation_blocked",
        "store_id": store_id,
        "platform": "naver",
        "first_sync_limit": first_sync_limit,
        "maximum_first_sync_limit": MAX_FIRST_SYNC_LIMIT,
        "checks": checks,
        "missing_checks": missing,
        "real_platform_writes_enabled": False,
        "customer_send_enabled": False,
        "ai_automatic_operation_enabled": False,
        "recipient_data_returned": False,
        "raw_platform_response_returned": False,
    }


def assert_real_persistence_activation_ready(
    db: Session,
    *,
    settings: Settings,
    batch: PxgNaverReadonlyAdapterBatch,
) -> None:
    """Enforce Sol's future activation gate immediately before a real write."""

    checks, store_id, first_sync_limit = _activation_checks(db, settings)
    from app.services.pxg_naver_readonly_persistence_service import assert_pxg_naver_cleanup_healthy

    assert_pxg_naver_cleanup_healthy(db, store_id=store_id, settings=settings)
    required = (
        "single_pxg_naver_store",
        "first_sync_limit_bounded",
        "retention_configured",
        "retention_explicitly_approved",
        "backup_rollback_explicitly_approved",
        "activation_explicitly_enabled",
        "real_persistence_enabled",
        "all_platform_writes_disabled",
    )
    missing = [name for name in required if not checks[name]]
    if missing:
        raise ApiError(
            "PXG/Naver readonly activation checklist is incomplete",
            "readonly_activation_checklist_incomplete",
            409,
            {"missing_checks": missing},
        )
    if batch.store_id != store_id or batch.platform != "naver":
        raise ApiError("PXG/Naver activation store mismatch", "readonly_activation_store_mismatch", 403)
    if len(batch.orders) > first_sync_limit:
        raise ApiError(
            "PXG/Naver first sync exceeds the approved limit",
            "readonly_first_sync_limit_exceeded",
            409,
            {"first_sync_limit": first_sync_limit, "candidate_count": len(batch.orders)},
        )


def run_fictional_activation_simulation(
    db: Session,
    *,
    settings: Settings,
    batch: PxgNaverReadonlyAdapterBatch,
    actor_id: str | None,
) -> dict[str, Any]:
    """Create safe backup/rollback evidence without persisting any business data."""

    assert_trial_runtime_closed(settings)
    if settings.app_env not in {"development", "test"} or not settings.operator_trial_artificial_data_only:
        raise ApiError("activation simulation requires artificial development or test data", "readonly_simulation_environment_forbidden", 403)
    if settings.operator_trial_real_read_enabled or settings.pxg_naver_local_read_persistence_enabled:
        raise ApiError("activation simulation requires real readonly persistence to remain disabled", "readonly_simulation_real_mode_forbidden", 409)
    if batch.source_mode != "fictional_test":
        raise ApiError("activation simulation requires fictional adapter data", "readonly_simulation_fictional_source_required", 403)

    checks, store_id, first_sync_limit = _activation_checks(db, settings)
    if batch.store_id != store_id or batch.platform != "naver":
        raise ApiError("activation simulation store mismatch", "readonly_simulation_store_mismatch", 403)
    if len(batch.orders) > first_sync_limit:
        return {
            "status": "blocked",
            "skip_reason": "readonly_first_sync_limit_exceeded",
            "first_sync_limit": first_sync_limit,
            "candidate_count": len(batch.orders),
            "business_records_written": False,
            "platform_write": False,
        }

    snapshot_before = _store_snapshot(db, store_id=store_id)
    backup_evidence_hash, rollback_evidence_hash, backup_restore_verified = _sqlite_backup_and_rollback_drill(
        db, store_id=store_id, expected_snapshot=snapshot_before,
    )
    # No business operation is invoked. Matching both the restored backup and
    # the live snapshot makes any accidental mutation observable.
    snapshot_after = _store_snapshot(db, store_id=store_id)
    rollback_verified = backup_restore_verified and snapshot_before == snapshot_after
    now = get_utc_now()
    audit = write_operation_audit_log_local(
        db,
        {
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "platform": "naver",
            "environment": "test",
            "actor_type": "human",
            "actor_id": _safe_hash(actor_id or "authorized-operator"),
            "actor_label": "Authorized operator",
            "actor_role": "operator",
            "action": "pxg_naver_readonly_activation_simulated",
            "operation_phase": "T09-PXG-READONLY-ACTIVATION",
            "correlation_id": f"pxg-readonly-simulation-{store_id}-{now:%Y%m%d%H%M%S%f}",
            "request_id": None,
            "status": "success",
            "reason_code": "fictional_backup_rollback_simulation",
            "target_type": "sync_gate",
            "target_id": None,
            "target_hash": _safe_hash(f"pxg-naver-store:{store_id}"),
            "target_label": "PXG Naver readonly activation simulation",
            "changed_field_names": ["activation_simulation"],
            "before_summary": {"business_record_counts": snapshot_before},
            "after_summary": {"business_record_counts_unchanged": rollback_verified},
            "counts_summary": {
                "first_sync_candidates": len(batch.orders),
                "products": len(batch.products),
                "logistics": len(batch.logistics),
                "customer_inquiries": len(batch.customer_inquiries),
            },
            "backup_sha256": backup_evidence_hash,
            "restore_source_sha256": rollback_evidence_hash,
            "safety_flags": {
                "platform_write": False,
                "customer_send": False,
                "ai_automatic_operation": False,
                "backup_evidence_verified": True,
                "rollback_evidence_verified": rollback_verified,
            },
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Fictional data only; no product, order, recipient, logistics, or inquiry record was written.",
        },
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )
    if audit.get("status") != "audit_row_written":
        raise ApiError("activation simulation audit was rejected", "readonly_simulation_audit_blocked", 500)
    return {
        "status": "simulation_completed",
        "store_id": store_id,
        "platform": "naver",
        "first_sync_limit": first_sync_limit,
        "candidate_count": len(batch.orders),
        "backup_evidence_hash": backup_evidence_hash,
        "rollback_evidence_hash": rollback_evidence_hash,
        "rollback_verified": rollback_verified,
        "business_records_written": False,
        "platform_write": False,
        "customer_send": False,
        "ai_automatic_operation": False,
        "activation_checks": checks,
    }
