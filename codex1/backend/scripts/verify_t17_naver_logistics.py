import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t17-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "APP_ENV": "test",
    "AUTOMATIC_READ_SYNC_ENABLED": "true",
    "PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED": "true",
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
})

from sqlalchemy import select

from app.core.exceptions import ApiError
from app.database import SessionLocal, engine, init_db
from app.models.api_credential import ApiCredential
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyLogisticsRecord
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.services import automatic_read_sync_service, order_service, pxg_naver_readonly_persistence_service
from app.services.encryption import encrypt_value
from app.services.store_onboarding_service import NaverReadPage


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
TRACKING = "T17-TRACKING-99887766"


def detail(product_order_id, order_id, *, changed=NOW, delivery="DELIVERING", tracking=TRACKING, carrier="CJ"):
    return {
        "external_product_order_id": product_order_id,
        "external_order_id_full": order_id,
        "last_changed_at": changed.isoformat(),
        "delivery_status": {"raw": delivery, "derived_from_order_status": False} if delivery else None,
        "tracking_number": tracking,
        "delivery_company": carrier,
        "shipped_at": (changed - timedelta(minutes=10)).isoformat(),
    }


class Reader:
    def __init__(self, page): self.page = page
    def validate(self, **_kwargs): raise AssertionError("not used")
    def read_products(self, *_args, **_kwargs): raise AssertionError("not used")
    def read_orders(self, *_args, **_kwargs): return NaverReadPage(self.page)


def seed_order(db, store, product_order_id, order_id, *, ordered_at=NOW - timedelta(days=1), source_type="naver_onboarding_sync"):
    row = Order(
        store_id=store.id, platform="naver", external_order_id=order_id,
        external_product_order_id=product_order_id, product_name="T17 Product", quantity=1,
        order_amount=1, currency="KRW", order_status="PAID", ordered_at=ordered_at,
        source_type=source_type, last_synced_at=NOW, raw_data={"raw_response_saved": False},
    )
    db.add(row)
    db.flush()
    return row


def main():
    init_db()
    with SessionLocal() as db:
        store = Store(name="T17 Naver", platform="naver", status="active")
        other = Store(name="T17 Other", platform="naver", status="active")
        fictional = Store(name="T17 Fictional", platform="naver", status="active")
        non_naver = Store(name="T17 Non Naver", platform="coupang", status="active")
        db.add_all((store, other, fictional, non_naver)); db.flush()
        for item in (store, other):
            db.add(PxgNaverReadonlyCleanupStatus(store_id=item.id, platform="naver", status="healthy", last_success_at=NOW))
        db.add(ApiCredential(store_id=store.id, platform="naver", credential_name="T17", client_id="t17", encrypted_secret_key=encrypt_value("t17-secret"), auth_status="test_passed", status="active", extra_config={"channel_no": "1"}))
        primary = seed_order(db, store, "po-primary", "o-primary")
        second = seed_order(db, store, "po-second", "o-shared")
        old = seed_order(db, store, "po-old", "o-old", ordered_at=NOW - timedelta(days=31))
        historical = seed_order(db, store, "po-history", "o-history", ordered_at=NOW - timedelta(days=61), source_type="naver_historical_backfill")
        test_order = seed_order(db, store, "po-test", "o-test", source_type="mock_sync")
        seed_order(db, other, "po-primary", "o-other")
        db.commit()

        # Permission/isolation and fictional stores fail closed before any record write.
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=fictional.id, details=[detail("po-primary", "o-primary")], now=NOW)
            raise AssertionError("fictional store must not pass the cleanup gate")
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_no_successful_run"
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=non_naver.id, details=[], now=NOW)
            raise AssertionError("non-Naver store must be rejected")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_store_unavailable"

        result = pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary")], now=NOW)
        assert result == {"saved": 1, "not_available": 0, "skipped": 0}
        db.commit()
        record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(PxgNaverReadonlyLogisticsRecord.order_id == primary.id))
        assert record and record.encrypted_tracking_number and record.tracking_number_hash and record.tracking_number_masked
        assert TRACKING not in str(record) and db.query(OrderStatusEvent).filter_by(order_id=primary.id).count() == 1

        # Missing tracking number is a successful snapshot with all sensitive fields empty.
        missing = detail("po-second", "o-shared", tracking=None, carrier="CJ", delivery="DELIVERING")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[missing], now=NOW)["saved"] == 1
        db.commit()
        missing_record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(PxgNaverReadonlyLogisticsRecord.order_id == second.id))
        assert missing_record and missing_record.encrypted_tracking_number == missing_record.tracking_number_hash == missing_record.tracking_number_masked == ""
        unavailable = detail("po-second", "o-shared", tracking=None, carrier=None, delivery=None)
        unavailable.pop("shipped_at")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[unavailable], now=NOW)["not_available"] == 1

        # Exact association, multi-product orders, candidate filters, terminal exclusion, and historical side-save.
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "wrong-order")], now=NOW)["skipped"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-old", "o-old")], now=NOW)["skipped"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-test", "o-test")], now=NOW)["skipped"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", delivery="CANCELLED")], now=NOW)["skipped"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-history", "o-history")], now=NOW, scope="historical")["saved"] == 1
        db.commit()

        # Idempotence, stale source protection, same-version conflict, and terminal non-regression.
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary")], now=NOW)["saved"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", changed=NOW - timedelta(minutes=1), tracking="OLD")], now=NOW)["skipped"] == 1
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", tracking="CONFLICT")], now=NOW)
            raise AssertionError("same-version conflict must block")
        except RuntimeError as exc:
            assert str(exc) == "logistics_same_version_conflict"
            db.rollback()
        delivered = detail("po-primary", "o-primary", changed=NOW + timedelta(minutes=1), delivery="DELIVERED")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[delivered], now=NOW)["saved"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", changed=NOW + timedelta(minutes=2), delivery="DELIVERING")], now=NOW)["skipped"] == 1
        db.commit(); db.refresh(record)
        assert record.shipment_status == "DELIVERED"

        payload = order_service.serialize_order(primary, db=db)
        timeline = order_service.get_order_logistics_timeline(db, store_id=store.id, order_id=primary.id)
        assert TRACKING not in str(payload) and TRACKING not in str(timeline)
        assert payload["tracking_number"] and "*" in payload["tracking_number"]

        cleanup = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(PxgNaverReadonlyCleanupStatus.store_id == store.id))
        cleanup.status = "failed"; db.commit()
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary")], now=NOW)
            raise AssertionError("cleanup failure must block writes")
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_failed"
        cleanup.status = "healthy"; cleanup.last_success_at = NOW; db.commit()

        automatic_read_sync_service.ensure_automatic_read_schedule(db, store_id=store.id, now=NOW)
        checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store.id, SyncCheckpoint.sync_type == "naver_automatic_logistics"))
        assert checkpoint and checkpoint.automatic_read_enabled and checkpoint.status == "idle"
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["interval"] == timedelta(minutes=30)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["lease"] == timedelta(minutes=20)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["freshness"] == timedelta(minutes=75)
        assert "logistics" in automatic_read_sync_service.RECOVERABLE_RESOURCES
        checkpoint.next_run_at = NOW; db.commit()
        assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=checkpoint.id, now=NOW, reader=Reader([detail("po-primary", "o-primary", changed=NOW + timedelta(minutes=3), delivery="DELIVERED")])) == "success"
        fresh_until = db.scalar(select(SyncCheckpoint.fresh_until).where(SyncCheckpoint.id == checkpoint.id))
        assert fresh_until is not None and fresh_until.replace(tzinfo=timezone.utc) >= NOW + timedelta(minutes=75)
        assert db.query(OrderStatusEvent).filter_by(order_id=primary.id).count() >= 2
        assert db.query(PxgNaverReadonlyLogisticsRecord).count() >= 2
    print("verify_t17_naver_logistics: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)
