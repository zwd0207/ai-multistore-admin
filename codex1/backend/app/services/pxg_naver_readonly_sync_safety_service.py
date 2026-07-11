"""T09-R2 encrypted backup, first-sync batch, rollback, and restore drill.

This service is deliberately limited to fictional test batches while real local
persistence remains disabled. It never calls a marketplace write endpoint.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
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
from app.models.auth import ErpSession, ErpStoreMembership
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
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operator_trial_service import resolve_trial_store
from app.services.pxg_naver_readonly_persistence_service import (
    PXG_NAVER_READONLY_LOCAL_SOURCE,
    persist_pxg_naver_readonly_adapter_batch,
)


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
    backup_root.mkdir(parents=True, exist_ok=True)
    encrypted_path = backup_root / f"{batch.batch_no}.sqlite.enc"
    with tempfile.TemporaryDirectory(prefix="pxg-readonly-backup-") as directory:
        plain = Path(directory) / "backup.sqlite"
        with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(plain)) as backup_connection:
            source_connection.backup(backup_connection)
        with closing(sqlite3.connect(plain)) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ApiError("PXG/Naver backup integrity check failed", "readonly_backup_integrity_failed", 409)
            schema_version = _schema_version(check)
        encrypted_path.write_bytes(fernet.encrypt(plain.read_bytes()))
    backup = PxgNaverReadonlySyncBackup(
        batch_id=batch.id, store_id=batch.store_id, platform="naver",
        backup_ref=f"backup-{batch.batch_no}", encrypted_path=str(encrypted_path),
        checksum_sha256=_file_hash(encrypted_path), schema_version=schema_version,
        actor_id_hash=batch.actor_id_hash, expires_at=now + timedelta(days=BACKUP_RETENTION_DAYS),
    )
    db.add(backup)
    db.flush()
    return backup


def run_pxg_naver_restore_drill(db: Session, *, settings: Settings, backup: PxgNaverReadonlySyncBackup) -> dict[str, Any]:
    if backup.deleted_at is not None or not Path(backup.encrypted_path).exists():
        raise ApiError("PXG/Naver encrypted backup is unavailable", "readonly_backup_unavailable", 409)
    try:
        fernet = Fernet((settings.pxg_naver_local_read_backup_encryption_key or "").encode("ascii"))
        plaintext = fernet.decrypt(Path(backup.encrypted_path).read_bytes())
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ApiError("PXG/Naver encrypted backup cannot be restored", "readonly_backup_restore_failed", 409) from exc
    with tempfile.TemporaryDirectory(prefix="pxg-readonly-restore-") as directory:
        restored = Path(directory) / "restored.sqlite"
        restored.write_bytes(plaintext)
        with closing(sqlite3.connect(restored)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(orders)").fetchall()}
            counts = {
                "orders": connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
                "memberships": connection.execute("SELECT COUNT(*) FROM erp_store_memberships").fetchone()[0],
                "sessions": connection.execute("SELECT COUNT(*) FROM erp_sessions").fetchone()[0],
            }
    if integrity != "ok" or "uq_pxg_naver_readonly_product_order" not in indexes:
        raise ApiError("PXG/Naver restore drill verification failed", "readonly_restore_drill_failed", 409)
    backup.restore_drill_passed_at = get_utc_now()
    db.commit()
    return {"status": "restore_drill_passed", "counts": counts, "unique_index_verified": True, "session_scope_verified": True}


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


def prepare_fictional_first_sync(
    db: Session,
    *,
    settings: Settings,
    adapter_batch: PxgNaverReadonlyAdapterBatch,
    actor_id: str,
    backup_root: Path,
    force_failure_for_test: bool = False,
) -> dict[str, Any]:
    """Persist one fictional first sync with encrypted backup and batch evidence."""
    if settings.pxg_naver_local_read_persistence_enabled or adapter_batch.source_mode != "fictional_test" or settings.app_env not in {"test", "development"}:
        raise ApiError("T09-R2 only permits fictional test syncs while real persistence is disabled", "readonly_sync_safety_scope_forbidden", 403)
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
    test_settings = settings.model_copy(update={"pxg_naver_local_read_persistence_enabled": True})
    try:
        result = persist_pxg_naver_readonly_adapter_batch(
            db, settings=test_settings, batch=adapter_batch, actor_id=actor_id, manual_approval=True,
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
        drill = run_pxg_naver_restore_drill(db, settings=settings, backup=backup)
        return {"status": "completed", "batch_id": batch.id, "batch_no": batch.batch_no, "backup_checksum": backup.checksum_sha256, "counts": result["counts"], "restore_drill": drill}
    except Exception:
        after = _snapshot_ids(db, store_id=store.id)
        created = {name: sorted(after[name] - before[name]) for name in before}
        batch.created_record_ids = created
        batch.mutation_counts = {"failure": "resource_failure"}
        db.commit()
        rollback_pxg_naver_sync_batch(db, settings=settings, batch_id=batch.id)
        raise


def rollback_pxg_naver_sync_batch(db: Session, *, settings: Settings, batch_id: int) -> dict[str, Any]:
    batch = db.get(PxgNaverReadonlySyncBatch, batch_id)
    if batch is None:
        raise ApiError("PXG/Naver sync batch not found", "readonly_sync_batch_not_found", 404)
    control = _control(db, store_id=batch.store_id)
    control.write_and_refresh_blocked = True
    control.reason_code = "sync_batch_rollback"
    batch.status = "rollback_in_progress"
    db.commit()
    ids = batch.created_record_ids or {}
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
    backup = db.get(PxgNaverReadonlySyncBackup, batch.backup_id) if batch.backup_id else None
    drill = run_pxg_naver_restore_drill(db, settings=settings, backup=backup) if backup is not None else None
    return {"status": "rolled_back", "batch_id": batch.id, "write_and_refresh_blocked": True, "restore_drill": drill}


def cleanup_expired_pxg_naver_backups(db: Session, *, now: datetime | None = None, force_failure_for_test: bool = False) -> dict[str, Any]:
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
            Path(backup.encrypted_path).unlink(missing_ok=True)
            backup.deleted_at = current
            deleted += 1
        db.commit()
        return {"status": "completed", "deleted_count": deleted}
    except Exception:
        for backup in backups:
            control = _control(db, store_id=backup.store_id)
            control.backup_retention_failed = True
            control.write_and_refresh_blocked = True
            control.reason_code = "backup_retention_failed"
        db.commit()
        return {"status": "failed", "deleted_count": deleted}
