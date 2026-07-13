import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t15-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({"DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}", "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"), "APP_ENV": "test", "REAL_API_TEST_ENABLED": "false", "REAL_API_WRITE_ENABLED": "false"})

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.config import Settings
from app.models.api_credential import ApiCredential
from app.models.auth import ErpUser
from app.models.order import Order
from app.models.product import Product
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services.automatic_read_sync_service import RESOURCE_CONFIG, _eligible_store_ids, _stagger, automatic_read_status, ensure_onboarded_store_schedules, run_automatic_checkpoint
from app.services.encryption import encrypt_value
from app.services.store_onboarding_service import NaverReadFailure, NaverReadPage

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


class Reader:
    def __init__(self, fail=False, failure_code="network_timeout"): self.fail, self.failure_code = fail, failure_code
    def validate(self, **kwargs): raise AssertionError("not used")
    def read_products(self, context, *, start_at, end_at, cursor):
        if self.fail: raise NaverReadFailure(self.failure_code, retryable=True)
        return NaverReadPage([{"external_product_id": "p-1" if not cursor else "p-2", "name": "Product", "status": "active", "price": 1, "stock_quantity": 1}], "next" if not cursor else None)
    def read_orders(self, context, *, start_at, end_at, cursor):
        if self.fail: raise NaverReadFailure(self.failure_code, retryable=True)
        return NaverReadPage([{"external_order_id": "o-1", "external_product_order_id": "po-1", "product_name": "Product", "quantity": 1, "order_amount": 1, "currency": "KRW", "order_status": "PAID", "ordered_at": NOW.isoformat(), "paid_at": NOW.isoformat()}])


def checkpoint(db, store_id, resource):
    return db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store_id, SyncCheckpoint.sync_type == RESOURCE_CONFIG[resource]["sync_type"]))


def main():
    init_db()
    with SessionLocal() as db:
        user = ErpUser(user_key_hash="t15-owner", display_name="T15", status="active", auth_provider="api_operator")
        stores = [Store(name="T15 A", platform="naver", status="active"), Store(name="T15 B", platform="naver", status="active")]
        db.add_all([user, *stores]); db.flush()
        for store in stores:
            credential = ApiCredential(store_id=store.id, platform="naver", credential_name="T15", client_id="t15-client", encrypted_secret_key=encrypt_value("secret-never-in-log"), auth_status="test_passed", status="active", extra_config={"channel_no": "1"})
            db.add(credential); db.flush()
            db.add(StoreOnboarding(idempotency_key=f"t15-{store.id}", requested_store_name=store.name, creator_user_id=user.id, store_id=store.id, credential_id=credential.id, status="partially_synced"))
        db.commit()
        legacy_store = Store(name="T15 Legacy PXG", platform="naver", status="active")
        rejected_store = Store(name="T15 Fictional", platform="naver", status="active")
        db.add_all((legacy_store, rejected_store)); db.flush()
        db.add(ApiCredential(store_id=legacy_store.id, platform="naver", credential_name="T15 legacy", client_id="legacy-client", encrypted_secret_key=encrypt_value("legacy-secret-never-in-log"), auth_status="configured", status="active", extra_config={"channel_no": "1"}))
        db.add(SyncLog(store_id=legacy_store.id, platform="naver", sync_type="manual_batch_sync", status="success", message="approved legacy readonly sync", raw_summary={"status": "success", "platform_write": False}))
        db.commit()
        assert db.query(StoreOnboarding).filter_by(store_id=legacy_store.id).count() == 0
        assert _eligible_store_ids(db) == [stores[0].id, stores[1].id, legacy_store.id]
        assert db.query(SyncCheckpoint).filter_by(store_id=legacy_store.id).count() == 0
        assert ensure_onboarded_store_schedules(db, now=NOW) == 3
        assert db.query(StoreOnboarding).filter_by(store_id=legacy_store.id).count() == 0
        assert db.query(SyncCheckpoint).filter_by(store_id=legacy_store.id).count() == 4
        assert db.query(SyncCheckpoint).filter_by(store_id=rejected_store.id).count() == 0
        legacy_product_cp = checkpoint(db, legacy_store.id, "products")
        legacy_product_cp.next_run_at = NOW
        db.commit()
        assert run_automatic_checkpoint(db, checkpoint_id=legacy_product_cp.id, now=NOW, reader=Reader()) == "success"
        fictional_status = automatic_read_status(db, store_id=rejected_store.id, now=NOW)
        assert fictional_status["orders"]["status"] == "disabled" and fictional_status["orders"]["automatic_read_enabled"] is False
        assert checkpoint(db, stores[0].id, "logistics").status == "idle"
        contract_fields = {"status", "automatic_read_enabled", "last_success_at", "next_run_at", "data_fresh_until", "retry_count", "last_error_code", "safe_failure_reason", "is_stale", "last_attempt_at", "attention_state", "operator_message", "admin_action", "recovery_eligible", "action_path"}
        status = automatic_read_status(db, store_id=stores[0].id, now=NOW)
        assert set(status["logistics"]) == contract_fields and status["logistics"]["automatic_read_enabled"] is True
        assert Settings().automatic_read_sync_enabled is False
        assert RESOURCE_CONFIG["orders"]["lease"] == timedelta(minutes=15) and RESOURCE_CONFIG["products"]["lease"] == timedelta(minutes=30)
        assert abs(_stagger(stores[0].id, "orders", RESOURCE_CONFIG["orders"]["interval"]).total_seconds()) <= 60
        product_cp, order_cp, inquiry_cp = (checkpoint(db, stores[0].id, key) for key in ("products", "orders", "customer_inquiries"))
        for row in (product_cp, order_cp, inquiry_cp): row.next_run_at = NOW
        db.commit()
        assert run_automatic_checkpoint(db, checkpoint_id=product_cp.id, now=NOW, reader=Reader()) == "success"
        db.refresh(product_cp)
        assert product_cp.cursor_value is None and product_cp.retry_count == 0 and product_cp.fresh_until.replace(tzinfo=timezone.utc) > NOW
        status = automatic_read_status(db, store_id=stores[0].id, now=NOW)["products"]
        assert set(status) == contract_fields and status["status"] == "success" and status["is_stale"] is False
        product_cp.fresh_until = NOW - timedelta(seconds=1); db.commit()
        assert automatic_read_status(db, store_id=stores[0].id, now=NOW)["products"]["status"] == "stale"
        product_cp.fresh_until = NOW + timedelta(hours=4); product_cp.next_run_at = NOW; db.commit()
        assert automatic_read_status(db, store_id=stores[0].id, now=NOW)["products"]["status"] == "due"
        product_cp.next_run_at = NOW + timedelta(minutes=10); db.commit()
        assert db.query(Product).filter_by(store_id=stores[0].id).count() == 2
        assert run_automatic_checkpoint(db, checkpoint_id=product_cp.id, now=NOW, reader=Reader()) == "not_due"
        assert run_automatic_checkpoint(db, checkpoint_id=order_cp.id, now=NOW, reader=Reader()) == "success"
        assert db.query(Order).filter_by(store_id=stores[0].id).count() == 1 and db.query(Order).filter_by(store_id=stores[1].id).count() == 0
        assert run_automatic_checkpoint(db, checkpoint_id=inquiry_cp.id, now=NOW, inquiry_runner=lambda *args, **kwargs: {"created_count": 1, "updated_count": 0, "pages_read": 1}) == "success"
        product_cp.next_run_at, product_cp.lease_token, product_cp.lease_expires_at = NOW, "expired", NOW - timedelta(seconds=1)
        db.commit()
        assert run_automatic_checkpoint(db, checkpoint_id=product_cp.id, now=NOW, reader=Reader()) == "success"
        order_cp.next_run_at = NOW; db.commit()
        assert run_automatic_checkpoint(db, checkpoint_id=order_cp.id, now=NOW, reader=Reader(fail=True)) == "failed"
        db.refresh(order_cp)
        assert order_cp.status == "retry_wait" and order_cp.retry_count == 1 and order_cp.last_error_code == "network_timeout" and order_cp.next_run_at.replace(tzinfo=timezone.utc) > NOW and order_cp.lease_token is None
        assert (order_cp.next_run_at.replace(tzinfo=timezone.utc) - NOW) == timedelta(minutes=1)
        order_cp.next_run_at = NOW; db.commit()
        assert run_automatic_checkpoint(db, checkpoint_id=order_cp.id, now=NOW, reader=Reader(fail=True, failure_code="invalid_cursor")) == "failed"
        db.refresh(order_cp)
        assert order_cp.status == "blocked" and order_cp.automatic_read_enabled is False and order_cp.next_run_at is None
        assert "secret-never-in-log" not in str(automatic_read_status(db, store_id=stores[0].id))
        assert db.query(SyncCheckpoint).filter_by(store_id=stores[1].id).count() == 4
    print("verify_t15_automatic_read_sync: ok")


if __name__ == "__main__": main()
