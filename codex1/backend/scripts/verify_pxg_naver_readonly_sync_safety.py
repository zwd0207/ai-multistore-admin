"""Fictional-data contract for T09-R2 sync backup and rollback safety."""

import os
import sys
import tempfile
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
    "PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED": "false",
    "PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED": "true",
})

from app.config import get_settings
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlySyncBackup, PxgNaverReadonlySyncControl
from app.models.store import Store
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operator_trial_service import TRIAL_STORE_NAME
from app.services.pxg_naver_readonly_sync_safety_service import (
    cleanup_expired_pxg_naver_backups,
    assert_pxg_naver_sync_open,
    prepare_fictional_first_sync,
    rollback_pxg_naver_sync_batch,
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
            assert db.query(Order).filter(Order.external_order_id == "baseline-order").count() == 1
            rollback = rollback_pxg_naver_sync_batch(db, settings=get_settings(), batch_id=result["batch_id"])
            assert rollback["status"] == "rolled_back" and rollback["write_and_refresh_blocked"] is True, rollback
            assert db.query(Order).filter(Order.external_order_id == "baseline-order").count() == 1
            assert db.query(Order).filter(Order.external_order_id == "order-one").count() == 0
            control = db.query(PxgNaverReadonlySyncControl).filter(PxgNaverReadonlySyncControl.store_id == store.id).one()
            assert control.write_and_refresh_blocked is True
            control.write_and_refresh_blocked = False
            control.reason_code = None
            db.commit()
            try:
                prepare_fictional_first_sync(
                    db, settings=get_settings(), adapter_batch=fictional_batch(store.id, "two"), actor_id="fictional-operator", backup_root=backup_root, force_failure_for_test=True,
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("resource failure must rollback the complete fictional batch")
            assert db.query(Order).filter(Order.external_order_id == "order-two").count() == 0
            expired = db.query(PxgNaverReadonlySyncBackup).filter(PxgNaverReadonlySyncBackup.deleted_at.is_(None)).first()
            assert expired is not None
            expired.expires_at = get_utc_now() - timedelta(seconds=1)
            db.commit()
            retention = cleanup_expired_pxg_naver_backups(db, force_failure_for_test=True)
            assert retention["status"] == "failed"
            assert control.backup_retention_failed is True and control.write_and_refresh_blocked is True
            try:
                assert_pxg_naver_sync_open(db, store_id=store.id)
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_sync_safety_blocked"
            else:
                raise AssertionError("backup-retention failure must block activation and refresh")
            control.backup_retention_failed = False
            control.write_and_refresh_blocked = False
            control.reason_code = None
            db.commit()
            retention_recovery = cleanup_expired_pxg_naver_backups(db)
            assert retention_recovery["status"] == "completed" and retention_recovery["deleted_count"] >= 1, retention_recovery
            db.refresh(expired)
            assert expired.deleted_at is not None and not Path(expired.encrypted_path).exists()
    finally:
        engine.dispose()
        if TEMP_DB.exists():
            TEMP_DB.unlink()
        for item in backup_root.glob("*"):
            item.unlink()
        backup_root.rmdir()
    print("verify_pxg_naver_readonly_sync_safety: ok")


if __name__ == "__main__":
    main()
