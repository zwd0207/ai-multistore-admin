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
from app.models.pxg_naver_readonly import (
    PxgNaverReadonlyCleanupStatus,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
)
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.services import automatic_read_sync_service, customer_inquiry_service, order_service, pxg_naver_readonly_persistence_service
from app.services.encryption import encrypt_value
from app.services.store_onboarding_service import NaverReadPage, _canonical_orders


NOW = datetime.now(timezone.utc).replace(microsecond=0)
TRACKING = "T17-TRACKING-99887766"


def detail(product_order_id, order_id, *, changed=NOW, delivery="DELIVERING", tracking=TRACKING, carrier="CJ", order_hash=None, product_order_hash=None):
    return {
        "external_product_order_id": product_order_id,
        "external_order_id_full": order_id,
        "external_order_id_hash": order_hash,
        "external_product_order_id_hash": product_order_hash,
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


class BatchReader:
    def __init__(self, order_ids, *, fail_on_second=False):
        self.order_ids = order_ids
        self.fail_on_second = fail_on_second
        self.detail_calls = []
    def validate(self, **_kwargs): raise AssertionError("not used")
    def read_products(self, *_args, **_kwargs): raise AssertionError("not used")
    def read_orders(self, *_args, **_kwargs): raise AssertionError("T17 logistics must not call the order feed")
    def read_logistics(self, _context, *, product_order_ids):
        self.detail_calls.append(list(product_order_ids))
        if self.fail_on_second and len(self.detail_calls) == 2:
            from app.services.store_onboarding_service import NaverReadFailure
            raise NaverReadFailure("network_timeout", retryable=True)
        return [detail(product_order_id, self.order_ids[product_order_id], delivery="DELIVERED") for product_order_id in product_order_ids]


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
        later_id = seed_order(db, other, "po-ordering-late", "o-ordering-late", ordered_at=NOW - timedelta(days=20))
        earlier_id = seed_order(db, other, "po-ordering-early", "o-ordering-early", ordered_at=NOW - timedelta(days=2))
        db.commit()
        ordered_candidates = automatic_read_sync_service._t17_logistics_candidates(db, store_id=other.id, now=NOW)
        assert [row.id for row in ordered_candidates] == sorted(row.id for row in ordered_candidates)
        assert later_id.id < earlier_id.id and ordered_candidates[-2:] == [later_id, earlier_id]

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
        unavailable = detail("po-second", "o-shared", changed=NOW + timedelta(minutes=1), tracking=None, carrier=None, delivery=None)
        unavailable.pop("shipped_at")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[unavailable], now=NOW)["not_available"] == 1
        db.commit()
        db.refresh(missing_record)
        assert missing_record.is_stale is True
        assert missing_record.encrypted_tracking_number == missing_record.tracking_number_hash == missing_record.tracking_number_masked == ""
        assert missing_record.shipment_status == "not_available"
        unavailable_payload = order_service.serialize_order(second, db=db)
        _, unavailable_context = customer_inquiry_service._order_context(db, second)
        assert unavailable_payload["logistics_stale"] is True and not unavailable_payload["tracking_number"]
        assert unavailable_context["is_stale"] is True and not unavailable_context["tracking_number_masked"]

        # Naver may omit change/shipping/payment time for an unshipped order.
        # Its platform order time is a stable baseline until a newer shipment
        # timestamp appears.
        fallback_order = seed_order(db, store, "po-time-fallback", "o-time-fallback")
        db.commit()
        fallback_time = NOW - timedelta(days=1)
        fallback_detail = detail(
            "po-time-fallback",
            "o-time-fallback",
            tracking=None,
            carrier=None,
            delivery=None,
        )
        fallback_detail.pop("shipped_at")
        fallback_detail["last_changed_at"] = None
        fallback_detail["paid_at"] = None
        fallback_detail["ordered_at"] = fallback_time.isoformat()
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db,
            store_id=store.id,
            details=[fallback_detail],
            now=NOW,
        )["not_available"] == 1
        db.commit()
        fallback_record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == fallback_order.id,
        ))
        assert fallback_record is None
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db,
            store_id=store.id,
            details=[detail(
                "po-time-fallback",
                "o-time-fallback",
                changed=NOW,
                delivery="DELIVERING",
            )],
            now=NOW,
        )["saved"] == 1
        db.commit()
        fallback_record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == fallback_order.id,
        ))
        assert fallback_record is not None
        assert fallback_record.shipment_status == "DELIVERING"
        fallback_order.order_status = "CANCELLED"
        db.commit()

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
        hash_order = seed_order(db, store, "po-hash", "id-hash-t13")
        hash_history = seed_order(db, store, "po-hash-history", "id-hash-history", ordered_at=NOW - timedelta(days=61), source_type="naver_historical_backfill")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db, store_id=store.id, details=[detail("po-hash", "full-order-id-must-not-persist", order_hash="id-hash-t13")], now=NOW,
        )["saved"] == 1
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db, store_id=store.id, details=[detail("po-hash-history", "full-history-id-must-not-persist", order_hash="id-hash-history")], now=NOW, scope="historical",
        )["saved"] == 1
        db.commit()
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
                db, store_id=store.id, details=[detail("po-hash", "full-order-id-must-not-persist", order_hash="wrong-hash")], now=NOW,
            )
            raise AssertionError("T13 canonical hash mismatch must block")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_external_order_id_mismatch"
            db.rollback()
        legacy_hash_order = seed_order(db, store, "po-legacy-hash", "legacy-product-order-hash")
        assert pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db,
            store_id=store.id,
            details=[detail(
                "po-legacy-hash",
                "full-legacy-order-id",
                order_hash="correct-order-hash",
                product_order_hash="legacy-product-order-hash",
            )],
            now=NOW,
        )["saved"] == 1
        db.commit()

        # The caller owns the page transaction. If a later detail fails, its
        # rollback must remove records and events flushed for earlier details.
        batch_first = seed_order(
            db,
            store,
            "po-atomic-batch-first",
            "atomic-batch-first-order",
        )
        batch_second = seed_order(
            db,
            store,
            "po-atomic-batch-second",
            "atomic-batch-second-order",
        )
        db.commit()
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
                db,
                store_id=store.id,
                details=[
                    detail(
                        "po-atomic-batch-first",
                        "atomic-batch-first-order",
                        changed=NOW + timedelta(minutes=2),
                    ),
                    detail(
                        "po-atomic-batch-second",
                        "wrong-atomic-batch-second-order",
                        changed=NOW + timedelta(minutes=2),
                    ),
                ],
                now=NOW,
            )
            raise AssertionError("a later invalid batch detail must fail the page")
        except ApiError as exc:
            assert exc.error_code == "naver_logistics_external_order_id_mismatch"
            db.rollback()
        assert db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == batch_first.id,
        )) is None
        assert db.query(OrderStatusEvent).filter_by(order_id=batch_first.id).count() == 0
        assert db.scalar(select(PxgNaverReadonlyRecordState).where(
            PxgNaverReadonlyRecordState.store_id == store.id,
            PxgNaverReadonlyRecordState.resource_type == "logistics",
            PxgNaverReadonlyRecordState.source_key_hash
            == pxg_naver_readonly_persistence_service._hash(f"logistics:{batch_first.id}"),
        )) is None

        atomic_store = Store(name="T17 Atomic Runner", platform="naver", status="active")
        db.add(atomic_store)
        db.flush()
        db.add_all((
            PxgNaverReadonlyCleanupStatus(
                store_id=atomic_store.id,
                platform="naver",
                status="healthy",
                last_success_at=NOW,
            ),
            ApiCredential(
                store_id=atomic_store.id,
                platform="naver",
                credential_name="T17 Atomic",
                client_id="t17-atomic",
                encrypted_secret_key=encrypt_value("t17-atomic-secret"),
                auth_status="test_passed",
                status="active",
                extra_config={"channel_no": "atomic"},
            ),
        ))
        runner_first = seed_order(
            db, atomic_store, "po-runner-first", "runner-first-order"
        )
        runner_second = seed_order(
            db, atomic_store, "po-runner-second", "runner-second-order"
        )
        db.commit()
        automatic_read_sync_service.ensure_automatic_read_schedule(
            db, store_id=atomic_store.id, now=NOW
        )
        runner_checkpoint = db.scalar(select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == atomic_store.id,
            SyncCheckpoint.sync_type == "naver_automatic_logistics",
        ))
        runner_orders = db.scalar(select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == atomic_store.id,
            SyncCheckpoint.sync_type == "naver_automatic_orders",
        ))
        runner_orders.status = "success"
        runner_orders.last_synced_at = NOW
        runner_orders.fresh_until = NOW + timedelta(minutes=25)
        runner_orders.last_error_code = None
        runner_checkpoint.status = "idle"
        runner_checkpoint.next_run_at = NOW
        db.commit()
        runner_reader = Reader([
            detail("po-runner-first", "runner-first-order"),
            detail("po-runner-second", "wrong-runner-second-order"),
        ])
        assert automatic_read_sync_service.run_automatic_checkpoint(
            db,
            checkpoint_id=runner_checkpoint.id,
            now=NOW,
            reader=runner_reader,
        ) == "failed"
        db.refresh(runner_checkpoint)
        assert runner_checkpoint.status == "blocked"
        assert runner_checkpoint.last_error_code == "naver_logistics_external_order_id_mismatch"
        assert db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == runner_first.id,
        )) is None
        assert db.query(OrderStatusEvent).filter_by(order_id=runner_first.id).count() == 0
        assert db.scalar(select(PxgNaverReadonlyRecordState).where(
            PxgNaverReadonlyRecordState.store_id == atomic_store.id,
            PxgNaverReadonlyRecordState.resource_type == "logistics",
            PxgNaverReadonlyRecordState.source_key_hash
            == pxg_naver_readonly_persistence_service._hash(f"logistics:{runner_first.id}"),
        )) is None
        runner_first.order_status = "CANCELLED"
        runner_second.order_status = "CANCELLED"
        db.commit()

        batch_first.order_status = "CANCELLED"
        batch_second.order_status = "CANCELLED"
        db.commit()

        canonical = _canonical_orders([{
            "external_product_order_id": "po-canonical",
            "external_product_order_id_hash": "product-order-hash",
            "external_order_id_hash": "order-hash",
            "product_name": "Canonical product",
            "ordered_at": NOW.isoformat(),
            "order_status": {"raw": "PAYED"},
        }], "automatic_incremental")
        assert canonical[0]["external_order_id"] == "order-hash"
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
        assert payload["logistics_updated_at"] and payload["logistics_stale"] is False
        assert payload["delivery_status"] == "DELIVERED"
        assert timeline["tracking_source"] == "pxg_naver_readonly_logistics"
        assert timeline["logistics_updated_at"] and timeline["realtime_tracking_open"] is False
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        record.is_stale = False
        db.commit()
        expired_payload = order_service.serialize_order(primary, db=db)
        _, expired_context = customer_inquiry_service._order_context(db, primary)
        assert expired_payload["logistics_stale"] is True and not expired_payload["tracking_number"]
        assert expired_context["is_stale"] is True and not expired_context["tracking_number_masked"]

        cleanup = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(PxgNaverReadonlyCleanupStatus.store_id == store.id))
        cleanup.status = "failed"; db.commit()
        try:
            pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(db, store_id=store.id, details=[detail("po-primary", "o-primary")], now=NOW)
            raise AssertionError("cleanup failure must block writes")
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_failed"
        cleanup.status = "healthy"; cleanup.last_success_at = NOW; db.commit()

        # The scheduler reads only local candidates and the detail endpoint.
        for logistics in db.scalars(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.store_id == store.id,
            PxgNaverReadonlyLogisticsRecord.order_id != second.id,
        )).all():
            logistics.shipment_status = "DELIVERED"
        db.commit()
        automatic_read_sync_service.ensure_automatic_read_schedule(db, store_id=store.id, now=NOW)
        checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store.id, SyncCheckpoint.sync_type == "naver_automatic_logistics"))
        orders_checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store.id, SyncCheckpoint.sync_type == "naver_automatic_orders"))
        assert checkpoint and checkpoint.automatic_read_enabled and checkpoint.status == "idle"
        assert orders_checkpoint and orders_checkpoint.automatic_read_enabled
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["interval"] == timedelta(minutes=30)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["lease"] == timedelta(minutes=20)
        assert automatic_read_sync_service.RESOURCE_CONFIG["logistics"]["freshness"] == timedelta(minutes=75)
        assert "logistics" in automatic_read_sync_service.RECOVERABLE_RESOURCES
        orders_checkpoint.status = "retry_wait"
        orders_checkpoint.last_synced_at = None
        orders_checkpoint.fresh_until = None
        orders_checkpoint.next_run_at = NOW + timedelta(minutes=4)
        checkpoint.next_run_at = NOW
        db.commit()
        dependency_reader = Reader([detail("po-second", "o-shared", changed=NOW + timedelta(minutes=3), delivery="DELIVERING", tracking="T17-SECOND")])
        assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=checkpoint.id, now=NOW, reader=dependency_reader) == "not_due"
        db.refresh(checkpoint)
        assert checkpoint.status == "retry_wait" and checkpoint.automatic_read_enabled is True
        assert checkpoint.last_error_code == "orders_dependency_not_ready"
        assert checkpoint.next_run_at.replace(tzinfo=timezone.utc) == NOW + timedelta(minutes=4)
        assert checkpoint.lease_token is None and checkpoint.retry_count == 0
        assert dependency_reader.feed_calls == 0 and dependency_reader.detail_calls == []

        orders_checkpoint.status = "success"
        orders_checkpoint.last_synced_at = NOW
        orders_checkpoint.fresh_until = NOW + timedelta(minutes=25)
        orders_checkpoint.next_run_at = NOW + timedelta(minutes=10)
        checkpoint.next_run_at = NOW
        db.commit()
        reader = Reader([detail("po-second", "o-shared", changed=NOW + timedelta(minutes=3), delivery="DELIVERING", tracking="T17-SECOND")])
        assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=checkpoint.id, now=NOW, reader=reader) == "success"
        assert reader.feed_calls == 0 and reader.detail_calls == [["po-second"]]
        fresh_until = db.scalar(select(SyncCheckpoint.fresh_until).where(SyncCheckpoint.id == checkpoint.id))
        assert fresh_until is not None and fresh_until.replace(tzinfo=timezone.utc) >= NOW + timedelta(minutes=75)
        assert db.query(OrderStatusEvent).filter_by(order_id=primary.id).count() >= 2
        assert db.query(PxgNaverReadonlyLogisticsRecord).count() >= 2

        # The durable cursor is the last local Order.id, not a changing candidate-array offset.
        for logistics in db.scalars(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.store_id == store.id,
        )).all():
            logistics.shipment_status = "DELIVERED"
        db.commit()
        paged_orders = {f"po-page-{index}": f"o-page-{index}" for index in range(21)}
        for product_order_id, order_id in paged_orders.items():
            seed_order(db, store, product_order_id, order_id)
        checkpoint.status = "idle"; checkpoint.automatic_read_enabled = True; checkpoint.next_run_at = NOW
        checkpoint.cursor_value = None; checkpoint.lease_token = None; checkpoint.lease_expires_at = None
        db.commit()
        interrupted_reader = BatchReader(paged_orders, fail_on_second=True)
        page_sleeps = []
        assert automatic_read_sync_service.run_automatic_checkpoint(
            db,
            checkpoint_id=checkpoint.id,
            now=NOW,
            reader=interrupted_reader,
            sleep_fn=page_sleeps.append,
        ) == "failed"
        assert page_sleeps == [1.0]
        db.refresh(checkpoint)
        first_page_last_id = db.scalar(select(Order.id).where(Order.store_id == store.id, Order.external_product_order_id == "po-page-19"))
        assert checkpoint.cursor_value == f"logistics-local-id:{first_page_last_id}"
        resumed_reader = BatchReader(paged_orders)
        checkpoint.next_run_at = NOW; checkpoint.status = "retry_wait"; checkpoint.automatic_read_enabled = True
        db.commit()
        resumed_sleeps = []
        assert automatic_read_sync_service.run_automatic_checkpoint(
            db,
            checkpoint_id=checkpoint.id,
            now=NOW,
            reader=resumed_reader,
            sleep_fn=resumed_sleeps.append,
        ) == "success"
        assert resumed_reader.detail_calls == [["po-page-20"]]
        assert resumed_sleeps == []

        duplicate_checkpoint = checkpoint
        scheduler_dup_a = seed_order(db, store, "po-scheduler-duplicate", "o-scheduler-duplicate-a")
        scheduler_dup_b = seed_order(db, store, "po-scheduler-duplicate", "o-scheduler-duplicate-b")
        duplicate_checkpoint.status = "idle"; duplicate_checkpoint.automatic_read_enabled = True; duplicate_checkpoint.next_run_at = NOW
        duplicate_checkpoint.cursor_value = None; db.commit()
        assert automatic_read_sync_service.run_automatic_checkpoint(db, checkpoint_id=duplicate_checkpoint.id, now=NOW, reader=BatchReader({})) == "failed"
        db.refresh(duplicate_checkpoint)
        assert duplicate_checkpoint.cursor_value is None and duplicate_checkpoint.last_error_code == "naver_logistics_duplicate_product_order_id"
        scheduler_dup_a.source_type = "mock_sync"
        scheduler_dup_b.source_type = "mock_sync"
        second_record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == second.id,
        ))
        assert second_record is not None
        second_record.shipment_status = "DELIVERING"
        db.commit()

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
