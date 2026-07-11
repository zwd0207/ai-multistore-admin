"""T09-R2 encrypted backup, first-sync batch, rollback, and restore drill.

This service is deliberately limited to fictional test batches while real local
persistence remains disabled. It never calls a marketplace write endpoint.
"""

from __future__ import annotations

import hashlib
import json
import getpass
import os
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
    PxgNaverReadonlySyncBackup,
    PxgNaverReadonlySyncBatch,
    PxgNaverReadonlySyncControl,
)
from app.models.shipping import WarehouseShippingApprovalGrant, WarehouseShippingBatch, WarehouseShippingBatchOrder
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operator_trial_service import resolve_trial_store
from app.services.pxg_naver_readonly_persistence_service import (
    PXG_NAVER_READONLY_LOCAL_SOURCE,
    persist_pxg_naver_readonly_adapter_batch,
)
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local


BACKUP_RETENTION_DAYS = 30
FIRST_SYNC_LIMITS = {"products": 3, "orders": 3, "logistics": 3, "customer_inquiries": 10}


def _utc(value: datetime | None = None) -> datetime:
    value = value or get_utc_now()
    return value if value.tzinfo is not None else value.replace(tzinfo=get_utc_now().tzinfo)


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _control(db: Session, *, store_id: int) -> PxgNaverReadonlySyncControl:
    row = db.scalar(select(PxgNaverReadonlySyncControl).where(
        PxgNaverReadonlySyncControl.store_id == store_id,
        PxgNaverReadonlySyncControl.platform == "naver",
    ))
    if row is None:
        row = PxgNaverReadonlySyncControl(store_id=store_id, platform="naver")
        db.add(row)
        db.flush()
    return row


def assert_pxg_naver_sync_open(db: Session, *, store_id: int) -> None:
    row = db.scalar(select(PxgNaverReadonlySyncControl).where(
        PxgNaverReadonlySyncControl.store_id == store_id,
        PxgNaverReadonlySyncControl.platform == "naver",
    ))
    if row is not None and (row.write_and_refresh_blocked or row.backup_retention_failed):
        raise ApiError("PXG/Naver sync safety control is blocking operation", "readonly_sync_safety_blocked", 409)


def _snapshot_ids(db: Session, *, store_id: int) -> dict[str, set[int]]:
    return {
        "products": set(db.scalars(select(Product.id).where(Product.store_id == store_id, Product.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)).all()),
        "orders": set(db.scalars(select(Order.id).where(Order.store_id == store_id, Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)).all()),
        "record_states": set(db.scalars(select(PxgNaverReadonlyRecordState.id).where(PxgNaverReadonlyRecordState.store_id == store_id)).all()),
        "recipients": set(db.scalars(select(PxgNaverOrderRecipientSecureRecord.id).where(PxgNaverOrderRecipientSecureRecord.store_id == store_id)).all()),
        "logistics": set(db.scalars(select(PxgNaverReadonlyLogisticsRecord.id).where(PxgNaverReadonlyLogisticsRecord.store_id == store_id)).all()),
        "inquiries": set(db.scalars(select(PxgNaverReadonlyCustomerInquiry.id).where(PxgNaverReadonlyCustomerInquiry.store_id == store_id)).all()),
    }


def _schema_version(connection: sqlite3.Connection) -> str:
    return str(connection.execute("PRAGMA user_version").fetchone()[0])


def _backup_root(settings: Settings, requested_root: Path) -> Path:
    if not settings.pxg_naver_local_read_backup_root:
        raise ApiError("PXG/Naver designated backup directory is not configured", "readonly_backup_root_missing", 409)
    root = Path(settings.pxg_naver_local_read_backup_root).resolve()
    if requested_root.resolve() != root:
        raise ApiError("PXG/Naver backup directory is outside the designated root", "readonly_backup_path_forbidden", 403)
    root.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["icacls", str(root), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(OI)(CI)F"],
                capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                raise OSError("icacls failed")
        else:
            root.chmod(0o700)
    except OSError as exc:
        raise ApiError("PXG/Naver backup directory permissions cannot be set", "readonly_backup_acl_failed", 409) from exc
    _verify_windows_acl(root)
    return root


def _verify_windows_acl(path: Path) -> None:
    if os.name != "nt":
        return
    result = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=False)
    output = result.stdout.lower()
    if result.returncode != 0 or "(i)" in output or any(group in output for group in ("everyone:", "builtin\\users:", "authenticated users:")):
        raise ApiError("PXG/Naver backup ACL verification failed", "readonly_backup_acl_failed", 409)


def _restrict_backup_file(path: Path) -> None:
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                raise OSError("icacls failed")
        else:
            path.chmod(0o600)
    except OSError as exc:
        raise ApiError("PXG/Naver backup file permissions cannot be set", "readonly_backup_acl_failed", 409) from exc
    _verify_windows_acl(path)


def _assert_inside_root(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ApiError("PXG/Naver backup file is outside the designated root", "readonly_backup_path_forbidden", 403) from exc
    return resolved


def _baseline_manifest(connection: sqlite3.Connection, *, store_id: int) -> dict[str, Any]:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    def count(table: str, predicate: str = "") -> int:
        if table not in tables:
            return 0
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}{predicate}").fetchone()[0])
    indexes = sorted(row[1] for row in connection.execute("PRAGMA index_list(orders)").fetchall() if row[2])
    def structure_hash(query: str, params: tuple = ()) -> str:
        if not query.split(" FROM ", 1)[1].split()[0] in tables:
            return _hash([])
        rows = [tuple(row) for row in connection.execute(query, params).fetchall()]
        return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {
        "orders": count("orders"),
        "unique_order_indexes": indexes,
        "store_memberships": count("erp_store_memberships", f" WHERE store_id = {int(store_id)}"),
        "accounts": count("erp_users"),
        "sessions": count("erp_sessions"),
        "order_structure_hash": structure_hash("SELECT id, store_id, platform, external_order_id, external_product_order_id, order_status FROM orders ORDER BY id"),
        "membership_structure_hash": structure_hash("SELECT user_id, store_id, role_id, membership_status FROM erp_store_memberships WHERE store_id = ? ORDER BY user_id, role_id", (store_id,)),
        "account_structure_hash": structure_hash("SELECT id, user_key_hash, status FROM erp_users ORDER BY id"),
        "session_structure_hash": structure_hash("SELECT user_id, authn_level, revoked_at, idle_expires_at, absolute_expires_at FROM erp_sessions ORDER BY id"),
    }


def _privacy_backup_expiry(db: Session, *, store_id: int, now: datetime) -> datetime:
    deadlines = [now + timedelta(days=BACKUP_RETENTION_DAYS)]
    for record in db.scalars(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.store_id == store_id)).all():
        deadlines.append(_utc(record.source_observed_at) + timedelta(days=30))
        if record.terminal_confirmed_at is not None:
            deadlines.append(_utc(record.terminal_confirmed_at) + timedelta(days=7))
    for record in db.scalars(select(PxgNaverReadonlyLogisticsRecord).where(
        PxgNaverReadonlyLogisticsRecord.store_id == store_id,
        PxgNaverReadonlyLogisticsRecord.encrypted_tracking_number != "",
    )).all():
        deadlines.append(_utc(record.source_updated_at) + timedelta(days=30))
    expiry = min(deadlines)
    if expiry <= now:
        raise ApiError("PXG/Naver backup contains expired privacy data; cleanup is required", "readonly_backup_privacy_expired", 409)
    return expiry


def _write_backup_retention_audit(db: Session, *, store_id: int, status: str, reason_code: str, count: int) -> None:
    now = get_utc_now()
    write_operation_audit_log_local(db, {
        "created_at": now, "updated_at": now, "store_id": store_id, "platform": "naver", "environment": "local",
        "actor_type": "system", "actor_id": _hash("pxg-backup-retention"), "actor_label": "PXG backup retention",
        "actor_role": "system", "action": "pxg_naver_readonly_backup_retention", "operation_phase": "T09-R2",
        "correlation_id": f"pxg-backup-retention-{store_id}-{now:%Y%m%d%H%M%S%f}", "request_id": None,
        "status": status, "reason_code": reason_code, "target_type": "encrypted_backup", "target_id": None,
        "target_hash": _hash(f"pxg-backup-store:{store_id}"), "target_label": "PXG encrypted backup retention",
        "changed_field_names": ["backup_retention"], "before_summary": None, "after_summary": None,
        "counts_summary": {"backup_count": count}, "backup_sha256": None, "restore_source_sha256": None,
        "safety_flags": {"platform_write": False, "customer_send": False, "ai_automatic_operation": False},
        "sensitive_scan_passed": True, "raw_response_saved": False, "secrets_saved": False,
        "privacy_fields_redacted": True, "notes": "Encrypted backup retention outcome without backup paths or customer data.",
    }, write_enabled=True, manual_approval=True, local_write_scope=LOCAL_WRITER_SCOPE)


def _encrypted_backup(
    db: Session, *, settings: Settings, batch: PxgNaverReadonlySyncBatch, backup_root: Path, now: datetime,
) -> PxgNaverReadonlySyncBackup:
    if not settings.pxg_naver_local_read_backup_encryption_key:
        raise ApiError("PXG/Naver backup encryption key is not configured", "readonly_backup_key_missing", 409)
    try:
        fernet = Fernet(settings.pxg_naver_local_read_backup_encryption_key.encode("ascii"))
    except (TypeError, ValueError) as exc:
        raise ApiError("PXG/Naver backup encryption key is invalid", "readonly_backup_key_invalid", 409) from exc
    bind = db.get_bind()
    if bind.dialect.name != "sqlite" or not bind.url.database:
        raise ApiError("PXG/Naver sync safety tests require SQLite", "readonly_backup_database_forbidden", 409)
    source = Path(bind.url.database)
    backup_root = _backup_root(settings, backup_root)
    encrypted_path = backup_root / f"{batch.batch_no}.sqlite.enc"
    with tempfile.TemporaryDirectory(prefix="pxg-readonly-backup-") as directory:
        plain = Path(directory) / "backup.sqlite"
        with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(plain)) as backup_connection:
            source_connection.backup(backup_connection)
        with closing(sqlite3.connect(plain)) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ApiError("PXG/Naver backup integrity check failed", "readonly_backup_integrity_failed", 409)
            schema_version = _schema_version(check)
            baseline_manifest = _baseline_manifest(check, store_id=batch.store_id)
        encrypted_path.write_bytes(fernet.encrypt(plain.read_bytes()))
        _restrict_backup_file(encrypted_path)
    backup = PxgNaverReadonlySyncBackup(
        batch_id=batch.id, store_id=batch.store_id, platform="naver",
        backup_ref=f"backup-{batch.batch_no}", encrypted_path=str(encrypted_path),
        checksum_sha256=_file_hash(encrypted_path), schema_version=schema_version,
        actor_id_hash=batch.actor_id_hash, baseline_manifest=baseline_manifest,
        expires_at=_privacy_backup_expiry(db, store_id=batch.store_id, now=now),
    )
    db.add(backup)
    db.flush()
    return backup


def run_pxg_naver_restore_drill(db: Session, *, settings: Settings, backup: PxgNaverReadonlySyncBackup) -> dict[str, Any]:
    backup_path = _assert_inside_root(Path(backup.encrypted_path), _backup_root(settings, Path(settings.pxg_naver_local_read_backup_root or ".")))
    if backup.deleted_at is not None or not backup_path.exists():
        raise ApiError("PXG/Naver encrypted backup is unavailable", "readonly_backup_unavailable", 409)
    if _file_hash(backup_path) != backup.checksum_sha256:
        raise ApiError("PXG/Naver encrypted backup checksum does not match", "readonly_backup_checksum_mismatch", 409)
    try:
        fernet = Fernet((settings.pxg_naver_local_read_backup_encryption_key or "").encode("ascii"))
        plaintext = fernet.decrypt(backup_path.read_bytes())
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ApiError("PXG/Naver encrypted backup cannot be restored", "readonly_backup_restore_failed", 409) from exc
    with tempfile.TemporaryDirectory(prefix="pxg-readonly-restore-") as directory:
        restored = Path(directory) / "restored.sqlite"
        restored.write_bytes(plaintext)
        with closing(sqlite3.connect(restored)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            baseline = _baseline_manifest(connection, store_id=backup.store_id)
    if integrity != "ok" or baseline != (backup.baseline_manifest or {}):
        raise ApiError("PXG/Naver restore drill verification failed", "readonly_restore_drill_failed", 409)
    backup.restore_drill_passed_at = get_utc_now()
    db.commit()
    return {"status": "restore_drill_passed", "counts": baseline, "unique_index_verified": True, "session_scope_verified": True}


def _first_sync_precheck(db: Session, *, store_id: int, adapter_batch: PxgNaverReadonlyAdapterBatch) -> None:
    existing = db.scalar(select(func.count()).select_from(PxgNaverReadonlySyncBatch).where(
        PxgNaverReadonlySyncBatch.store_id == store_id,
        PxgNaverReadonlySyncBatch.status == "completed",
    ))
    if existing:
        raise ApiError("PXG/Naver first sync already completed", "readonly_first_sync_already_completed", 409)
    counts = {"products": len(adapter_batch.products), "orders": len(adapter_batch.orders), "logistics": len(adapter_batch.logistics), "customer_inquiries": len(adapter_batch.customer_inquiries)}
    if any(counts[name] > FIRST_SYNC_LIMITS[name] for name in counts):
        raise ApiError("PXG/Naver first sync limit exceeded", "readonly_first_sync_limit_exceeded", 409)
    if any(not item.external_product_order_id for item in adapter_batch.orders):
        raise ApiError("PXG/Naver product-order identifier is required", "readonly_first_sync_order_key_missing", 409)
    if db.scalar(select(Order.id).where(Order.store_id == store_id, Order.external_product_order_id.in_([item.external_product_order_id for item in adapter_batch.orders])).limit(1)):
        raise ApiError("PXG/Naver first sync cannot update existing orders", "readonly_first_sync_existing_record", 409)


def prepare_guarded_readonly_sync(
    db: Session,
    *,
    settings: Settings,
    adapter_batch: PxgNaverReadonlyAdapterBatch,
    actor_id: str,
    backup_root: Path,
    force_failure_for_test: bool = False,
    force_prewrite_restore_failure_for_test: bool = False,
    ) -> dict[str, Any]:
    """Persist one approved batch without changing its source or safety configuration."""
    if adapter_batch.source_mode not in {"fictional_test", "real_readonly"}:
        raise ApiError("PXG/Naver sync source is not allowed", "readonly_sync_safety_source_forbidden", 403)
    if adapter_batch.source_mode == "fictional_test" and (settings.app_env not in {"test", "development"} or not settings.operator_trial_artificial_data_only):
        raise ApiError("fictional PXG/Naver sync requires the artificial-data test scope", "readonly_sync_safety_scope_forbidden", 403)
    if not settings.pxg_naver_local_read_persistence_enabled:
        raise ApiError("PXG/Naver readonly local persistence is disabled", "readonly_local_persistence_disabled", 403)
    store = resolve_trial_store(db)
    if adapter_batch.store_id != store.id or adapter_batch.platform != "naver":
        raise ApiError("PXG/Naver sync store mismatch", "readonly_sync_safety_store_mismatch", 403)
    assert_pxg_naver_sync_open(db, store_id=store.id)
    _first_sync_precheck(db, store_id=store.id, adapter_batch=adapter_batch)
    now = get_utc_now()
    batch = PxgNaverReadonlySyncBatch(
        batch_no=f"PXG-READONLY-{store.id}-{now:%Y%m%d%H%M%S%f}", store_id=store.id, platform="naver",
        status="prepared", actor_id_hash=_hash(actor_id), baseline_counts={key: len(value) for key, value in _snapshot_ids(db, store_id=store.id).items()},
    )
    db.add(batch)
    db.commit()
    backup = _encrypted_backup(db, settings=settings, batch=batch, backup_root=backup_root, now=now)
    batch.backup_id = backup.id
    db.commit()
    before = _snapshot_ids(db, store_id=store.id)
    if force_prewrite_restore_failure_for_test:
        Path(backup.encrypted_path).write_bytes(b"invalid-encrypted-backup")
    # A restore copy must pass before any real local business record is saved.
    try:
        prewrite_drill = run_pxg_naver_restore_drill(db, settings=settings, backup=backup)
    except Exception:
        batch.status = "failed"
        batch.mutation_counts = {"failure": "prewrite_restore_drill_failed"}
        batch.created_record_ids = {name: [] for name in before}
        db.commit()
        rollback_pxg_naver_sync_batch(db, settings=settings, batch_id=batch.id, skip_restore_drill=True)
        batch.status = "failed"
        db.commit()
        raise
    try:
        result = persist_pxg_naver_readonly_adapter_batch(
            db, settings=settings, batch=adapter_batch, actor_id=actor_id, manual_approval=True,
        )
        if force_failure_for_test:
            raise RuntimeError("forced_resource_failure")
        if any(result["counts"][name].get("created", 0) != len(getattr(adapter_batch, name)) for name in result["counts"]):
            raise ApiError("PXG/Naver first sync has non-created records", "readonly_first_sync_mutation_mismatch", 409)
        after = _snapshot_ids(db, store_id=store.id)
        created = {name: sorted(after[name] - before[name]) for name in before}
        batch.mutation_counts = result["counts"]
        batch.created_record_ids = created
        batch.status = "completed"
        batch.completed_at = get_utc_now()
        db.commit()
        return {"status": "completed", "batch_id": batch.id, "batch_no": batch.batch_no, "backup_checksum": backup.checksum_sha256, "counts": result["counts"], "restore_drill": prewrite_drill}
    except Exception:
        after = _snapshot_ids(db, store_id=store.id)
        created = {name: sorted(after[name] - before[name]) for name in before}
        batch.created_record_ids = created
        batch.mutation_counts = {"failure": "resource_failure"}
        db.commit()
        rollback_pxg_naver_sync_batch(db, settings=settings, batch_id=batch.id)
        raise


def guarded_real_readonly_sync(*, settings: Settings) -> None:
    """Real refreshes have no direct-save path while activation remains blocked."""
    raise ApiError("PXG/Naver real readonly refresh remains disabled pending approved batch activation", "readonly_local_persistence_disabled", 403)


def run_guarded_readonly_sync(
    db: Session, *, settings: Settings, adapter_batch: PxgNaverReadonlyAdapterBatch, actor_id: str, backup_root: Path,
) -> dict[str, Any]:
    """The sole future real-save route: encrypted backup, batch, restore drill, persist, rollback."""
    if not settings.pxg_naver_local_read_persistence_enabled:
        guarded_real_readonly_sync(settings=settings)
    return prepare_guarded_readonly_sync(db, settings=settings, adapter_batch=adapter_batch, actor_id=actor_id, backup_root=backup_root)


# Backward-compatible test helper name; it never changes the source or settings.
prepare_fictional_first_sync = prepare_guarded_readonly_sync


def rollback_pxg_naver_sync_batch(db: Session, *, settings: Settings, batch_id: int, skip_restore_drill: bool = False) -> dict[str, Any]:
    batch = db.get(PxgNaverReadonlySyncBatch, batch_id)
    if batch is None:
        raise ApiError("PXG/Naver sync batch not found", "readonly_sync_batch_not_found", 404)
    control = _control(db, store_id=batch.store_id)
    control.write_and_refresh_blocked = True
    control.reason_code = "sync_batch_rollback"
    batch.status = "rollback_in_progress"
    db.commit()
    ids = batch.created_record_ids or {}
    order_ids = [int(record_id) for record_id in ids.get("orders", [])]
    warehouse_rows = db.scalars(select(WarehouseShippingBatchOrder).where(
        WarehouseShippingBatchOrder.local_order_id.in_(order_ids),
    )).all() if order_ids else []
    warehouse_batch_ids = {row.batch_id for row in warehouse_rows}
    protected_batches = db.scalars(select(WarehouseShippingBatch).where(
        WarehouseShippingBatch.id.in_(warehouse_batch_ids),
        WarehouseShippingBatch.status.in_({"warehouse_sent", "warehouse_returned", "ready_to_writeback", "writeback_partial", "completed"}),
    )).all() if warehouse_batch_ids else []
    used_grants = db.scalars(select(WarehouseShippingApprovalGrant).where(
        WarehouseShippingApprovalGrant.batch_id.in_(warehouse_batch_ids),
        WarehouseShippingApprovalGrant.used_at.is_not(None),
    )).all() if warehouse_batch_ids else []
    if protected_batches or used_grants:
        batch.status = "manual_review_required"
        control.reason_code = "warehouse_rollback_manual_review_required"
        db.commit()
        return {"status": "manual_review_required", "batch_id": batch.id, "write_and_refresh_blocked": True}
    revoked_approvals = 0
    if warehouse_batch_ids:
        for grant in db.scalars(select(WarehouseShippingApprovalGrant).where(
            WarehouseShippingApprovalGrant.batch_id.in_(warehouse_batch_ids),
            WarehouseShippingApprovalGrant.used_at.is_(None),
        )).all():
            db.delete(grant)
            revoked_approvals += 1
    for row in warehouse_rows:
        db.delete(row)
    db.flush()
    cancelled_batch_ids: list[int] = []
    for warehouse_batch_id in warehouse_batch_ids:
        remaining = db.scalar(select(func.count()).select_from(WarehouseShippingBatchOrder).where(
            WarehouseShippingBatchOrder.batch_id == warehouse_batch_id,
        ))
        if not remaining:
            warehouse_batch = db.get(WarehouseShippingBatch, warehouse_batch_id)
            if warehouse_batch is not None:
                warehouse_batch.status = "cancelled"
                cancelled_batch_ids.append(warehouse_batch_id)
    mapping = [
        (PxgNaverReadonlyCustomerInquiry, "inquiries"), (PxgNaverReadonlyRecordState, "record_states"),
        (PxgNaverOrderRecipientSecureRecord, "recipients"), (PxgNaverReadonlyLogisticsRecord, "logistics"),
        (Order, "orders"), (Product, "products"),
    ]
    for model, key in mapping:
        for record_id in ids.get(key, []):
            record = db.get(model, int(record_id))
            if record is not None:
                db.delete(record)
    batch.status = "rolled_back"
    batch.rolled_back_at = get_utc_now()
    db.commit()
    for warehouse_batch_id in cancelled_batch_ids:
        _write_backup_retention_audit(
            db, store_id=batch.store_id, status="success", reason_code="empty_warehouse_batch_cancelled", count=1,
        )
    backup = db.get(PxgNaverReadonlySyncBackup, batch.backup_id) if batch.backup_id else None
    drill = None if skip_restore_drill else (run_pxg_naver_restore_drill(db, settings=settings, backup=backup) if backup is not None else None)
    return {"status": "rolled_back", "batch_id": batch.id, "write_and_refresh_blocked": True, "revoked_approval_count": revoked_approvals, "restore_drill": drill}


def cleanup_expired_pxg_naver_backups(db: Session, *, settings: Settings, now: datetime | None = None, force_failure_for_test: bool = False) -> dict[str, Any]:
    current = _utc(now)
    backups = db.scalars(select(PxgNaverReadonlySyncBackup).where(
        PxgNaverReadonlySyncBackup.expires_at <= current,
        PxgNaverReadonlySyncBackup.deleted_at.is_(None),
    )).all()
    deleted = 0
    try:
        for backup in backups:
            if force_failure_for_test:
                raise OSError("forced_backup_retention_failure")
            root = _backup_root(settings, Path(settings.pxg_naver_local_read_backup_root or "."))
            _assert_inside_root(Path(backup.encrypted_path), root).unlink(missing_ok=True)
            backup.deleted_at = current
            deleted += 1
        db.commit()
        for store_id in {item.store_id for item in backups}:
            control = _control(db, store_id=store_id)
            control.backup_retention_failed = False
            if control.reason_code == "backup_retention_failed":
                control.write_and_refresh_blocked = False
                control.reason_code = None
            db.commit()
            _write_backup_retention_audit(db, store_id=store_id, status="success", reason_code="backup_retention_deleted", count=deleted)
        return {"status": "completed", "deleted_count": deleted}
    except Exception:
        for backup in backups:
            control = _control(db, store_id=backup.store_id)
            control.backup_retention_failed = True
            control.write_and_refresh_blocked = True
            control.reason_code = "backup_retention_failed"
        db.commit()
        for store_id in {item.store_id for item in backups}:
            _write_backup_retention_audit(db, store_id=store_id, status="failed", reason_code="backup_retention_failed", count=deleted)
        return {"status": "failed", "deleted_count": deleted}


def run_pxg_naver_daily_cleanup(db: Session, *, settings: Settings) -> dict[str, Any]:
    """Startup and 24-hour cleanup entrypoint. Failures leave the health gate closed."""
    from app.services.pxg_naver_readonly_persistence_service import run_pxg_naver_readonly_retention_cleanup

    store = resolve_trial_store(db)
    try:
        retention = run_pxg_naver_readonly_retention_cleanup(
            db, settings=settings, preview=False, manual_confirmation=True, actor_id="system-daily-cleanup",
        )
        backups = cleanup_expired_pxg_naver_backups(db, settings=settings)
        if retention.get("status") != "completed" or backups.get("status") != "completed":
            raise ApiError("PXG/Naver daily cleanup did not complete", "readonly_daily_cleanup_failed", 409)
        control = _control(db, store_id=store.id)
        if control.reason_code == "daily_cleanup_failed":
            control.write_and_refresh_blocked = False
            control.reason_code = None
            db.commit()
        return {"status": "completed", "store_id": store.id, "retention": retention, "backups": backups}
    except Exception:
        control = _control(db, store_id=store.id)
        control.write_and_refresh_blocked = True
        control.reason_code = "daily_cleanup_failed"
        db.commit()
        raise
