"""Fictional-data contract for T09-R2 sync backup and rollback safety."""

import os
import sys
import tempfile
import subprocess
import getpass
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly-sync-safety.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEMP_DB.as_posix()}",
    "APP_ENV": "test",
    "ALLOW_DEV_AUTH": "true",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "PXG_NAVER_LOCAL_READ_BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "OPERATOR_TRIAL_ENABLED": "true",
    "OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY": "true",
    "OPERATOR_TRIAL_REAL_READ_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED": "true",
    "PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED": "true",
})

from app.config import get_settings
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.models.order import Order
from app.models.operation_audit_log import OperationAuditLog
from app.models.pxg_naver_readonly import PxgNaverReadonlySyncBackup, PxgNaverReadonlySyncBatch, PxgNaverReadonlySyncControl
from app.models.shipping import WarehouseShippingApprovalGrant, WarehouseShippingBatch, WarehouseShippingBatchOrder
from app.models.store import Store
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operator_trial_service import TRIAL_STORE_NAME
from app.services.pxg_naver_readonly_sync_safety_service import (
    cleanup_expired_pxg_naver_backups,
    assert_pxg_naver_sync_open,
    prepare_fictional_first_sync,
    rollback_pxg_naver_sync_batch,
    run_pxg_naver_restore_drill,
    _privacy_backup_expiry,
)


def fictional_batch(store_id: int, suffix: str) -> PxgNaverReadonlyAdapterBatch:
    return PxgNaverReadonlyAdapterBatch.model_validate({
        "store_id": store_id, "platform": "naver", "source_mode": "fictional_test",
        "products": [{"external_product_id": f"product-{suffix}", "name": "PXG Fictional Bag", "price": "1000", "currency": "KRW", "stock_quantity": 1, "source_updated_at": "2026-07-12T00:00:00+00:00"}],
        "orders": [{"external_order_id": f"order-{suffix}", "external_product_order_id": f"product-order-{suffix}", "product_name": "PXG Fictional Bag", "quantity": 1, "order_amount": "1000", "currency": "KRW", "order_status": "PAYED", "ordered_at": "2026-07-12T00:00:00+00:00", "source_updated_at": "2026-07-12T00:00:00+00:00"}],
        "logistics": [], "customer_inquiries": [],
    })


def main() -> None:
    init_db()
    backup_root = Path(tempfile.mkdtemp(prefix="pxg-readonly-backups-"))
    outside_path = backup_root.parent / "outside.enc"
    os.environ["PXG_NAVER_LOCAL_READ_BACKUP_ROOT"] = str(backup_root)
    get_settings.cache_clear()
    try:
        with SessionLocal() as db:
            store = Store(name=TRIAL_STORE_NAME, platform="naver", status="active")
            baseline = Order(store=store, platform="naver", external_order_id="baseline-order", product_name="Baseline", quantity=1, order_amount=1, currency="KRW", order_status="PAYED", ordered_at=get_utc_now(), source_type="legacy")
            db.add_all([store, baseline])
            db.commit()
            result = prepare_fictional_first_sync(
                db, settings=get_settings(), adapter_batch=fictional_batch(store.id, "one"), actor_id="fictional-operator", backup_root=backup_root,
            )
            assert result["status"] == "completed" and result["restore_drill"]["status"] == "restore_drill_passed", result
            backup = db.get(PxgNaverReadonlySyncBackup, 1)
            assert backup is not None and Path(backup.encrypted_path).exists() and len(backup.checksum_sha256) == 64
            assert b"PXG Fictional Bag" not in Path(backup.encrypted_path).read_bytes()
            if os.name == "nt":
                acl = subprocess.run(["icacls", str(backup_root)], capture_output=True, text=True, check=False)
                output = acl.stdout.lower()
                assert acl.returncode == 0 and getpass.getuser().lower() in output and "(i)" not in output, acl.stdout
                assert all(group not in output for group in ("everyone:", "builtin\\users:", "authenticated users:")), acl.stdout
            original_ciphertext = Path(backup.encrypted_path).read_bytes()
            Path(backup.encrypted_path).write_bytes(original_ciphertext + b"tampered")
            try:
                run_pxg_naver_restore_drill(db, settings=get_settings(), backup=backup)
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_backup_checksum_mismatch"
            else:
                raise AssertionError("tampered encrypted backup must fail checksum validation")
            Path(backup.encrypted_path).write_bytes(original_ciphertext)
            original_manifest = dict(backup.baseline_manifest)
            backup.baseline_manifest = {"orders": 999}
            db.commit()
            try:
                run_pxg_naver_restore_drill(db, settings=get_settings(), backup=backup)
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_restore_drill_failed"
            else:
                raise AssertionError("baseline mismatch must block restore drill")
            backup.baseline_manifest = original_manifest
            outside_path.write_bytes(original_ciphertext)
            backup.encrypted_path = str(outside_path)
            db.commit()
            try:
                run_pxg_naver_restore_drill(db, settings=get_settings(), backup=backup)
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_backup_path_forbidden"
            else:
                raise AssertionError("backup path outside the designated root must be blocked")
            backup.encrypted_path = str(backup_root / f"{result['batch_no']}.sqlite.enc")
            db.commit()
            assert db.query(Order).filter(Order.external_order_id == "baseline-order").count() == 1
            synced_order = db.query(Order).filter(Order.external_order_id == "order-one").one()
            warehouse = WarehouseShippingBatch(batch_no="T09-R2-ROLLBACK", store_id=store.id, platform="naver", status="created")
            db.add(warehouse)
            db.flush()
            db.add(WarehouseShippingBatchOrder(batch_id=warehouse.id, local_order_id=synced_order.id, store_id=store.id, platform="naver", order_reference="order-one", product_name="PXG Fictional Bag", quantity=1))
            db.add(WarehouseShippingApprovalGrant(batch_id=warehouse.id, user_id=1, grant_scope="manifest", token_hash="a" * 128, batch_version=1, candidate_hash="b" * 128, expires_at=get_utc_now() + timedelta(minutes=10)))
            db.commit()
            rollback = rollback_pxg_naver_sync_batch(db, settings=get_settings(), batch_id=result["batch_id"])
            assert rollback["status"] == "rolled_back" and rollback["write_and_refresh_blocked"] is True, rollback
            assert rollback["revoked_approval_count"] == 1
            db.refresh(warehouse)
            assert warehouse.status == "cancelled"
            assert db.query(WarehouseShippingBatchOrder).filter(WarehouseShippingBatchOrder.batch_id == warehouse.id).count() == 0
            assert db.query(WarehouseShippingApprovalGrant).filter(WarehouseShippingApprovalGrant.batch_id == warehouse.id).count() == 0
            assert db.query(Order).filter(Order.external_order_id == "baseline-order").count() == 1
            assert db.query(Order).filter(Order.external_order_id == "order-one").count() == 0
            control = db.query(PxgNaverReadonlySyncControl).filter(PxgNaverReadonlySyncControl.store_id == store.id).one()
            assert control.write_and_refresh_blocked is True
            control.write_and_refresh_blocked = False
            control.reason_code = None
            db.commit()
            protected = prepare_fictional_first_sync(
                db, settings=get_settings(), adapter_batch=fictional_batch(store.id, "two"), actor_id="fictional-operator", backup_root=backup_root,
            )
            protected_order = db.query(Order).filter(Order.external_order_id == "order-two").one()
            from app.models.pxg_naver_readonly import PxgNaverOrderRecipientSecureRecord
            privacy_record = PxgNaverOrderRecipientSecureRecord(
                order_id=protected_order.id, store_id=store.id, platform="naver", encrypted_recipient_payload="ciphertext",
                recipient_payload_hash="a" * 64, source_updated_at=get_utc_now(),
                source_observed_at=get_utc_now(), expires_at=get_utc_now(), terminal_confirmed_at=get_utc_now() - timedelta(days=6), is_stale=True,
            )
            db.add(privacy_record)
            db.commit()
            assert _privacy_backup_expiry(db, store_id=store.id, now=get_utc_now()) < get_utc_now() + timedelta(days=2)
            sent_batch = WarehouseShippingBatch(batch_no="T09-R2-PROTECTED", store_id=store.id, platform="naver", status="warehouse_sent")
            db.add(sent_batch)
            db.flush()
            db.add(WarehouseShippingBatchOrder(batch_id=sent_batch.id, local_order_id=protected_order.id, store_id=store.id, platform="naver", order_reference="order-two", product_name="PXG Fictional Bag", quantity=1))
            db.commit()
            protected_rollback = rollback_pxg_naver_sync_batch(db, settings=get_settings(), batch_id=protected["batch_id"])
            assert protected_rollback["status"] == "manual_review_required"
            assert db.query(Order).filter(Order.external_order_id == "order-two").count() == 1
            control.write_and_refresh_blocked = False
            control.reason_code = None
            sent_batch.status = "completed"
            db.commit()
            try:
                prepare_fictional_first_sync(
                    db, settings=get_settings(), adapter_batch=fictional_batch(store.id, "three"), actor_id="fictional-operator", backup_root=backup_root, force_failure_for_test=True,
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("resource failure must rollback the complete fictional batch")
            assert db.query(Order).filter(Order.external_order_id == "order-three").count() == 0
            control.write_and_refresh_blocked = False
            control.reason_code = None
            db.commit()
            try:
                prepare_fictional_first_sync(
                    db, settings=get_settings(), adapter_batch=fictional_batch(store.id, "prewrite"), actor_id="fictional-operator", backup_root=backup_root,
                    force_prewrite_restore_failure_for_test=True,
                )
            except Exception:
                pass
            else:
                raise AssertionError("prewrite restore failure must abort the sync")
            assert db.query(Order).filter(Order.external_order_id == "order-prewrite").count() == 0
            failed_batch = db.query(PxgNaverReadonlySyncBatch).filter(
                PxgNaverReadonlySyncBatch.status == "failed",
            ).one()
            assert failed_batch.mutation_counts == {"failure": "prewrite_restore_drill_failed"}
            assert control.write_and_refresh_blocked is True
            expired = db.query(PxgNaverReadonlySyncBackup).filter(PxgNaverReadonlySyncBackup.deleted_at.is_(None)).first()
            assert expired is not None
            expired.expires_at = get_utc_now() - timedelta(seconds=1)
            db.commit()
            retention = cleanup_expired_pxg_naver_backups(db, settings=get_settings(), force_failure_for_test=True)
            assert retention["status"] == "failed"
            assert control.backup_retention_failed is True and control.write_and_refresh_blocked is True
            try:
                assert_pxg_naver_sync_open(db, store_id=store.id)
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_sync_safety_blocked"
            else:
                raise AssertionError("backup-retention failure must block activation and refresh")
            control.write_and_refresh_blocked = True
            control.reason_code = "sync_batch_rollback"
            db.commit()
            retention_recovery = cleanup_expired_pxg_naver_backups(db, settings=get_settings())
            assert retention_recovery["status"] == "completed" and retention_recovery["deleted_count"] >= 1, retention_recovery
            db.refresh(expired)
            assert expired.deleted_at is not None and not Path(expired.encrypted_path).exists()
            assert control.backup_retention_failed is False
            assert control.write_and_refresh_blocked is True and control.reason_code == "sync_batch_rollback"
            retention_audits = db.query(OperationAuditLog).filter(
                OperationAuditLog.action == "pxg_naver_readonly_backup_retention",
            ).all()
            assert {item.status for item in retention_audits} >= {"success", "failed"}
            assert "backup_root" not in str(retention_audits).lower() and "Fictional" not in str(retention_audits)
    finally:
        engine.dispose()
        if TEMP_DB.exists():
            TEMP_DB.unlink()
        for item in backup_root.glob("*"):
            item.unlink()
        backup_root.rmdir()
        outside_path.unlink(missing_ok=True)
    print("verify_pxg_naver_readonly_sync_safety: ok")


if __name__ == "__main__":
    main()
