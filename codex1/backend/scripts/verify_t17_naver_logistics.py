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
    def __init__(self, page):
        self.page = page
        self.feed_calls = 0
        self.detail_calls = []
    def validate(self, **_kwargs): raise AssertionError("not used")
    def read_products(self, *_args, **_kwargs): raise AssertionError("not used")
    def read_orders(self, *_args, **_kwargs):
        self.feed_calls += 1
        raise AssertionError("T17 logistics must not call the order feed")
    def read_logistics(self, _context, *, product_order_ids):
        self.detail_calls.append(list(product_order_ids))
        return self.page


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

        # Exact legacy placeholder upgrade is idempotent; unrelated blocks stay blocked.
        legacy_checkpoint = SyncCheckpoint(
            store_id=store.id, platform="naver", sync_type="naver_automatic_logistics",
            automatic_read_enabled=False, status="blocked", notes="not_supported", next_run_at=None,
        )
        unrelated_checkpoint = SyncCheckpoint(
            store_id=other.id, platform="naver", sync_type="naver_automatic_logistics",
            automatic_read_enabled=False, status="blocked", notes="manual_review", next_run_at=None,
        )
        db.add_all((legacy_checkpoint, unrelated_checkpoint)); db.commit()
        automatic_read_sync_service.ensure_automatic_read_schedule(db, store_id=store.id, now=NOW)
        db.refresh(legacy_checkpoint); db.refresh(unrelated_checkpoint)
        assert legacy_checkpoint.status == "idle" and legacy_checkpoint.automatic_read_enabled is True
        legacy_next_run = legacy_checkpoint.next_run_at
        assert legacy_next_run is not None
        if legacy_next_run.tzinfo is None:
            legacy_next_run = legacy_next_run.replace(tzinfo=timezone.utc)
        assert legacy_checkpoint.notes is None and legacy_next_run == NOW
        automatic_read_sync_service.ensure_automatic_read_schedule(db, store_id=store.id, now=NOW)
        db.refresh(legacy_checkpoint); db.refresh(unrelated_checkpoint)
        assert legacy_checkpoint.status == "idle" and legacy_checkpoint.notes is None
        assert unrelated_checkpoint.status == "blocked" and unrelated_checkpoint.automatic_read_enabled is False

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
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "wrong-order")], now=NOW)
            raise AssertionError("external order mismatch must block")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_external_order_id_mismatch"
            db.rollback()
        for excluded_detail in (detail("po-old", "o-old"), detail("po-test", "o-test")):
            try:
                pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[excluded_detail], now=NOW)
                raise AssertionError("non-candidate association must block")
            except ApiError as exc:
                assert exc.error_code == "naver_logistics_order_association_invalid"
                db.rollback()
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", delivery="CANCELLED")], now=NOW)["skipped"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-history", "o-history")], now=NOW, scope="historical")["saved"] == 1
        db.commit()

        # Idempotence, stale source protection, same-version conflict, and terminal non-regression.
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary")], now=NOW)["saved"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", changed=NOW - timedelta(minutes=1), tracking="OLD")], now=NOW)["skipped"] == 1
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary", tracking="CONFLICT")], now=NOW)
            raise AssertionError("same-version conflict must block")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_same_version_conflict"
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

        # The scheduler reads only local candidates and the detail endpoint.
        automatic_read_sync_service.ensure_automatic_read_schedule(db, store_id=store.id, now=NOW)
        checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store.id, SyncCheckpoint.sync_type == "naver_automatic_logistics"))
        assert checkpoint and checkpoint.automatic_read_enabled and checkpoint.status == "idle"
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["interval"] == timedelta(minutes=30)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["lease"] == timedelta(minutes=20)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["freshness"] == timedelta(minutes=75)
        assert "logistics" in automatic_read_sync_service.RECOVERABLE_RESOURCES
        checkpoint.next_run_at = NOW; db.commit()
        reader = Reader([detail("po-second", "o-shared", changed=NOW + timedelta(minutes=3), delivery="DELIVERING", tracking="T17-SECOND")])
        assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=checkpoint.id, now=NOW, reader=reader) == "success"
        assert reader.feed_calls == 0 and reader.detail_calls == [["po-second"]]
        fresh_until = db.scalar(select(SyncCheckpoint.fresh_until).where(SyncCheckpoint.id == checkpoint.id))
        assert fresh_until is not None and fresh_until.replace(tzinfo=timezone.utc) >= NOW + timedelta(minutes=75)
        assert db.query(OrderStatusEvent).filter_by(order_id=primary.id).count() >= 2
        assert db.query(PxgNaverReadonlyLogisticsRecord).count() >= 2

        # Stable non-retryable detail failures roll the page back without advancing its local cursor.
        for bad_detail, code in (
            (detail("po-second", "wrong-order", changed=NOW + timedelta(minutes=4)), "naver_logistics_external_order_id_mismatch"),
            ({**detail("po-second", "o-shared", changed=NOW + timedelta(minutes=4)), "last_changed_at": "not-a-time"}, "naver_logistics_source_time_invalid"),
            (detail("po-second", "o-shared", changed=NOW + timedelta(minutes=3), tracking="same-version-conflict"), "naver_logistics_same_version_conflict"),
        ):
            checkpoint.status = "idle"; checkpoint.automatic_read_enabled = True; checkpoint.next_run_at = NOW
            checkpoint.cursor_value = None; checkpoint.lease_token = None; checkpoint.lease_expires_at = None
            db.commit()
            assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=checkpoint.id, now=NOW, reader=Reader([bad_detail])) == "failed"
            db.refresh(checkpoint)
            assert checkpoint.cursor_value is None and checkpoint.last_error_code == code and checkpoint.status == "blocked"

        duplicate = seed_order(db, store, "po-duplicate", "o-duplicate")
        duplicate_second = seed_order(db, store, "po-duplicate", "o-duplicate-second")
        db.commit()
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-duplicate", "o-duplicate")], now=NOW)
            raise AssertionError("ambiguous product-order association must block")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_order_association_invalid"
            db.rollback()
    print("verify_t17_naver_logistics: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)
