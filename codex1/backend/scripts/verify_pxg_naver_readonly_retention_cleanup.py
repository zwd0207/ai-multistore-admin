import os
import sys
import tempfile
import gc
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import close_all_sessions, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly-retention-cleanup.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"
os.environ["OPERATOR_TRIAL_REAL_READ_ENABLED"] = "false"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED"] = "true"
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "true"
os.environ["AUTOMATIC_READ_SYNC_ENABLED"] = "false"
os.environ["LIFECYCLE_SCHEDULERS_ENABLED"] = "false"

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine, init_db
from app import models as _models  # noqa: F401 - register the complete schema
import app.main as app_main
from app.main import app
from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCleanupStatus,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
    PxgNaverReadonlySyncBackup,
    PxgNaverReadonlySyncBatch,
)
from app.models.shipping import WarehouseShippingBatch, WarehouseShippingBatchOrder
from app.models.store import Store
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from app.services.operator_trial_service import TRIAL_STORE_NAME
from app.services.pxg_naver_readonly_activation_service import readonly_activation_precheck
from app.services import warehouse_shipping_service
from app.services.encryption import encrypt_value
from app.services.pxg_naver_readonly_persistence_service import (
    PXG_NAVER_READONLY_LOCAL_SOURCE,
    TRACKING_RETENTION_FAILURE_CODE,
    assert_pxg_naver_cleanup_healthy,
    persist_pxg_naver_readonly_adapter_batch,
    recipient_contract_for_authorized_warehouse,
    readonly_local_summary,
    run_naver_logistics_tracking_retention_cleanup,
    run_pxg_naver_readonly_retention_cleanup,
    _recipient_due,
)


def fictional_batch(store_id: int) -> PxgNaverReadonlyAdapterBatch:
    return PxgNaverReadonlyAdapterBatch.model_validate({
        "store_id": store_id,
        "platform": "naver",
        "source_mode": "fictional_test",
        "products": [{
            "external_product_id": "cleanup-product", "name": "PXG Fictional Bag", "price": "1000",
            "currency": "KRW", "stock_quantity": 1, "source_updated_at": "2026-01-01T00:00:00+00:00",
        }],
        "orders": [{
            "external_order_id": "cleanup-order", "external_product_order_id": "cleanup-product-order",
            "product_name": "PXG Fictional Bag", "quantity": 1, "order_amount": "1000", "currency": "KRW",
            "order_status": "DELIVERED", "ordered_at": "2026-01-01T00:00:00+00:00",
            "source_updated_at": "2026-01-01T00:00:00+00:00",
            "recipient": {"receiver_name": "Fictional Recipient", "receiver_phone": "010-5555-1234", "receiver_address_full": "Fictional Address"},
        }],
        "logistics": [{
            "external_order_id": "cleanup-order", "external_product_order_id": "cleanup-product-order",
            "carrier": "CJ", "tracking_number": "TEST-CLEANUP-1234", "shipment_status": "DELIVERED",
            "shipped_at": "2026-01-01T00:00:00+00:00", "source_updated_at": "2026-01-01T00:00:00+00:00",
        }],
        "customer_inquiries": [{
            "external_inquiry_id": "cleanup-inquiry", "inquiry_type": "platform_message", "status": "closed",
            "customer_display_masked": "F***", "subject_category": "platform_message", "content_available": False,
            "source_updated_at": "2026-01-01T00:00:00+00:00",
        }],
    })


def verify_postgres_atomic_tracking_cleanup() -> None:
    postgres_url = os.environ.get("T22_TEST_POSTGRES_URL")
    if not postgres_url:
        print("verify_pxg_naver_readonly_retention_cleanup: PostgreSQL concurrency skipped")
        return
    schema = f"tracking_retention_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(postgres_url, future=True)
    isolated_engine = None
    worker: threading.Thread | None = None
    backend_pid: int | None = None
    cleanup_errors: list[str] = []
    now = get_utc_now()
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        isolated_engine = create_engine(
            postgres_url,
            future=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(isolated_engine)
        IsolatedSession = sessionmaker(
            bind=isolated_engine,
            expire_on_commit=False,
            future=True,
        )
        with IsolatedSession() as db:
            store = Store(id=1, name=TRIAL_STORE_NAME, platform="naver", status="active")
            db.add(store)
            db.flush()
            tracking_order = Order(
                store_id=store.id,
                platform="naver",
                external_order_id="tracking-retention-order",
                external_product_order_id="tracking-retention-product-order",
                product_name="Tracking retention product",
                quantity=1,
                order_amount=1,
                currency="KRW",
                order_status="DELIVERED",
                ordered_at=now - timedelta(days=40),
                source_type="naver_onboarding_sync",
                last_synced_at=now,
            )
            metadata_order = Order(
                store_id=store.id,
                platform="naver",
                external_order_id="metadata-retention-order",
                external_product_order_id="metadata-retention-product-order",
                product_name="Metadata retention product",
                quantity=1,
                order_amount=1,
                currency="KRW",
                order_status="SHIPPED",
                ordered_at=now - timedelta(days=100),
                source_type="naver_onboarding_sync",
                last_synced_at=now,
            )
            db.add_all((tracking_order, metadata_order))
            db.flush()
            tracking_record = PxgNaverReadonlyLogisticsRecord(
                order_id=tracking_order.id,
                store_id=store.id,
                platform="naver",
                carrier="CJ",
                encrypted_tracking_number="encrypted-before-refresh",
                tracking_number_hash="tracking-hash",
                tracking_number_masked="****1234",
                shipment_status="DELIVERY_COMPLETION",
                shipped_at=now - timedelta(days=40),
                source_updated_at=now - timedelta(days=40),
                source_observed_at=now - timedelta(days=31),
                expires_at=now + timedelta(days=1),
                is_stale=False,
            )
            metadata_record = PxgNaverReadonlyLogisticsRecord(
                order_id=metadata_order.id,
                store_id=store.id,
                platform="naver",
                carrier="CJ",
                encrypted_tracking_number="metadata-encrypted-before-refresh",
                tracking_number_hash="metadata-tracking-hash",
                tracking_number_masked="****5678",
                shipment_status="DELIVERING",
                shipped_at=now - timedelta(days=100),
                source_updated_at=now - timedelta(days=100),
                source_observed_at=now - timedelta(days=100),
                expires_at=now - timedelta(days=1),
                is_stale=True,
            )
            db.add_all((tracking_record, metadata_record))
            db.flush()
            db.add_all((
                PxgNaverReadonlyCleanupStatus(
                    store_id=store.id,
                    platform="naver",
                    status="healthy",
                    last_success_at=now,
                ),
                PxgNaverReadonlyRecordState(
                    store_id=store.id,
                    platform="naver",
                    resource_type="logistics",
                    source_key_hash="metadata-source-key-hash",
                    local_record_id=metadata_record.id,
                    content_fingerprint="metadata-content-fingerprint",
                    source_updated_at=now - timedelta(days=100),
                    source_observed_at=now - timedelta(days=91),
                    expires_at=now - timedelta(days=1),
                    retention_review_at=now - timedelta(days=1),
                    is_stale=True,
                ),
            ))
            db.commit()

        test_settings = Settings(
            database_url=postgres_url,
            credential_encryption_key=os.environ["CREDENTIAL_ENCRYPTION_KEY"],
            pxg_naver_local_read_retention_cleanup_enabled=True,
        )

        def start_blocked_cleanup(operation):
            nonlocal backend_pid
            result_holder: list[dict] = []
            errors: list[Exception] = []
            ready = threading.Event()

            def run_cleanup() -> None:
                nonlocal backend_pid
                with IsolatedSession() as db:
                    try:
                        db.execute(text("SET lock_timeout = '10s'"))
                        backend_pid = int(db.scalar(text("SELECT pg_backend_pid()")))
                        ready.set()
                        result_holder.append(operation(db))
                    except Exception as exc:  # pragma: no cover - reported below
                        errors.append(exc)

            current_worker = threading.Thread(target=run_cleanup, daemon=True)
            current_worker.start()
            assert ready.wait(timeout=5)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with admin_engine.connect() as connection:
                    waiting = bool(connection.scalar(text(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                        "WHERE pid = :pid AND wait_event_type = 'Lock')"
                    ), {"pid": backend_pid}))
                if waiting:
                    break
                time.sleep(0.05)
            assert waiting
            return current_worker, result_holder, errors

        with IsolatedSession() as refresh_db:
            record = refresh_db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
                PxgNaverReadonlyLogisticsRecord.tracking_number_hash == "tracking-hash",
            ).with_for_update())
            record.source_observed_at = now
            record.encrypted_tracking_number = "encrypted-after-refresh"
            refresh_db.flush()
            worker, result_holder, errors = start_blocked_cleanup(
                lambda db: run_naver_logistics_tracking_retention_cleanup(
                    db,
                    settings=test_settings,
                    now=now,
                    store_ids={1},
                )
            )
            refresh_db.commit()

        worker.join(timeout=15)
        assert not worker.is_alive()
        assert not errors, errors
        assert result_holder[0]["status"] == "completed"
        assert result_holder[0]["tracking_cleanup_count"] == 0
        with IsolatedSession() as db:
            record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
                PxgNaverReadonlyLogisticsRecord.tracking_number_hash == "tracking-hash",
            ))
            assert record.encrypted_tracking_number == "encrypted-after-refresh"
            assert record.is_stale is False

        with IsolatedSession() as refresh_db:
            record = refresh_db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
                PxgNaverReadonlyLogisticsRecord.tracking_number_hash == "metadata-tracking-hash",
            ).with_for_update())
            state = refresh_db.scalar(select(PxgNaverReadonlyRecordState).where(
                PxgNaverReadonlyRecordState.local_record_id == record.id,
                PxgNaverReadonlyRecordState.resource_type == "logistics",
            ).with_for_update())
            record.source_observed_at = now
            record.encrypted_tracking_number = "metadata-encrypted-after-refresh"
            record.is_stale = False
            state.source_observed_at = now
            state.is_stale = False
            refresh_db.flush()
            worker, result_holder, errors = start_blocked_cleanup(
                lambda db: run_pxg_naver_readonly_retention_cleanup(
                    db,
                    settings=test_settings,
                    preview=False,
                    manual_confirmation=True,
                    actor_id="postgres-concurrency-test",
                    now=now,
                )
            )
            refresh_db.commit()

        worker.join(timeout=15)
        assert not worker.is_alive()
        assert not errors, errors
        assert result_holder[0]["status"] == "completed"
        assert result_holder[0]["metadata_cleanup_count"] == 0
        with IsolatedSession() as db:
            record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
                PxgNaverReadonlyLogisticsRecord.tracking_number_hash == "metadata-tracking-hash",
            ))
            state = db.scalar(select(PxgNaverReadonlyRecordState).where(
                PxgNaverReadonlyRecordState.local_record_id == record.id,
                PxgNaverReadonlyRecordState.resource_type == "logistics",
            ))
            assert record.encrypted_tracking_number == "metadata-encrypted-after-refresh"
            assert record.is_stale is False
            assert state is not None and state.source_observed_at == now

        with IsolatedSession() as db:
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ))
            status.status = "failed"
            status.last_failure_code = TRACKING_RETENTION_FAILURE_CODE
            status.last_failure_at = now
            db.commit()

        with IsolatedSession() as status_db:
            status = status_db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ).with_for_update())
            status.status = "manual_review_required"
            status.last_failure_code = None
            status.manual_review_count = 2
            status_db.flush()
            worker, result_holder, errors = start_blocked_cleanup(
                lambda db: run_naver_logistics_tracking_retention_cleanup(
                    db,
                    settings=test_settings,
                    now=now,
                    store_ids={1},
                )
            )
            status_db.commit()

        worker.join(timeout=15)
        assert not worker.is_alive()
        assert not errors, errors
        assert result_holder[0]["status"] == "completed"
        with IsolatedSession() as db:
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ))
            assert status.status == "manual_review_required"
            assert status.manual_review_count == 2

        with IsolatedSession() as db:
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ))
            status.status = "healthy"
            status.last_failure_code = None
            status.manual_review_count = 0
            batch_race_order = Order(
                store_id=1,
                platform="naver",
                external_order_id="retention-batch-race-order",
                external_product_order_id="retention-batch-race-product-order",
                product_name="Retention batch race product",
                quantity=1,
                order_amount=1,
                currency="KRW",
                order_status="READY",
                ordered_at=now - timedelta(days=31),
                source_type=PXG_NAVER_READONLY_LOCAL_SOURCE,
                last_synced_at=now,
            )
            db.add(batch_race_order)
            db.flush()
            batch_race_recipient = PxgNaverOrderRecipientSecureRecord(
                order_id=batch_race_order.id,
                store_id=1,
                platform="naver",
                encrypted_recipient_payload="encrypted-recipient",
                recipient_payload_hash="batch-race-recipient-hash",
                source_updated_at=now - timedelta(days=31),
                source_observed_at=now - timedelta(days=31),
                expires_at=now - timedelta(days=1),
                is_stale=True,
            )
            db.add(batch_race_recipient)
            db.flush()
            db.add(PxgNaverReadonlyRecordState(
                store_id=1,
                platform="naver",
                resource_type="recipient",
                source_key_hash="batch-race-recipient-state",
                local_record_id=batch_race_recipient.id,
                content_fingerprint="batch-race-recipient-fingerprint",
                source_updated_at=now - timedelta(days=31),
                source_observed_at=now,
                expires_at=now + timedelta(days=1),
                retention_review_at=now + timedelta(days=1),
                is_stale=False,
            ))
            db.commit()
            batch_race_order_id = batch_race_order.id
            batch_race_recipient_id = batch_race_recipient.id

        with IsolatedSession() as batch_db:
            order = batch_db.scalar(select(Order).where(
                Order.id == batch_race_order_id,
            ).with_for_update())
            worker, result_holder, errors = start_blocked_cleanup(
                lambda db: run_pxg_naver_readonly_retention_cleanup(
                    db,
                    settings=test_settings,
                    preview=False,
                    manual_confirmation=True,
                    actor_id="postgres-batch-race-test",
                    now=now,
                )
            )
            batch = WarehouseShippingBatch(
                batch_no="POSTGRES-RETENTION-BATCH-RACE",
                store_id=1,
                platform="naver",
                status="created",
            )
            batch_db.add(batch)
            batch_db.flush()
            batch_db.add(WarehouseShippingBatchOrder(
                batch_id=batch.id,
                local_order_id=order.id,
                store_id=1,
                platform="naver",
                order_reference=order.external_order_id,
                product_order_reference=order.external_product_order_id,
                product_name=order.product_name,
                quantity=order.quantity,
                pre_batch_order_status=order.order_status,
                row_status="pending_export",
                is_active=True,
                active_lock="active",
            ))
            batch_db.commit()

        worker.join(timeout=15)
        assert not worker.is_alive()
        assert not errors, errors
        assert result_holder[0]["status"] == "completed"
        assert result_holder[0]["manual_review_frozen_count"] == 1
        with IsolatedSession() as db:
            assert db.get(PxgNaverOrderRecipientSecureRecord, batch_race_recipient_id) is not None
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ))
            assert status.status == "manual_review_required"
    finally:
        if worker is not None:
            worker.join(timeout=12)
        if worker is not None and worker.is_alive() and backend_pid is not None:
            with admin_engine.begin() as connection:
                connection.execute(text(
                    "SELECT pg_terminate_backend(:pid)"
                ), {"pid": backend_pid})
            worker.join(timeout=5)
        if worker is not None and worker.is_alive():
            cleanup_errors.append("tracking cleanup worker did not stop")
        if isolated_engine is not None:
            isolated_engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '10s'"))
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                if connection.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = :schema)"
                ), {"schema": schema}):
                    cleanup_errors.append("tracking cleanup schema still exists")
        except Exception as exc:  # pragma: no cover - reported below
            cleanup_errors.append(f"tracking cleanup schema cleanup failed: {type(exc).__name__}")
        finally:
            admin_engine.dispose()
        if cleanup_errors:
            raise AssertionError("; ".join(cleanup_errors))


def main() -> None:
    init_db()
    now = get_utc_now()
    with SessionLocal() as db:
        store = Store(name=TRIAL_STORE_NAME, platform="naver", status="active")
        db.add(store)
        db.commit()
        admin_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "admin"))
        assert admin_role is not None
        admin = ErpUser(user_key_hash="cleanup-admin", display_name="Cleanup Admin", status="active")
        db.add(admin)
        db.flush()
        db.add(ErpStoreMembership(user_id=admin.id, store_id=store.id, role_id=admin_role.id, membership_status="active"))
        db.commit()
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_no_successful_run"
        else:
            raise AssertionError("a missing cleanup record must block operations")
        no_status_activation = readonly_activation_precheck(db, settings=get_settings())
        assert no_status_activation["checks"]["retention_cleanup_healthy"] is False
        cleanup_disabled = Settings(pxg_naver_local_read_retention_cleanup_enabled=False)
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=cleanup_disabled)
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_disabled"
        else:
            raise AssertionError("a disabled cleanup switch must block operations")
        disabled_activation = readonly_activation_precheck(db, settings=cleanup_disabled)
        assert disabled_activation["checks"]["retention_cleanup_enabled"] is False
        with TestClient(app) as client:
            no_status_refresh = client.post(
                "/api/v1/pxg-naver-readonly/refresh",
                json={"manual_approval": True},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert no_status_refresh.status_code in {403, 409}, no_status_refresh.text
        persisted = persist_pxg_naver_readonly_adapter_batch(
            db, settings=get_settings(), batch=fictional_batch(store.id), actor_id="cleanup-test", manual_approval=True,
        )
        assert persisted["status"] == "completed", persisted

        order = db.scalar(select(Order).where(Order.store_id == store.id))
        recipient = db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.store_id == store.id))
        tracking = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(PxgNaverReadonlyLogisticsRecord.store_id == store.id))
        assert order is not None and recipient is not None and tracking is not None
        recipient.terminal_confirmed_at = now - timedelta(days=8)
        order.updated_at = now
        assert _recipient_due(recipient, order, now=now) is True
        recipient.terminal_confirmed_at = None
        recipient.source_observed_at = now - timedelta(days=31)
        assert _recipient_due(recipient, order, now=now) is True
        recipient.source_observed_at = now
        recipient.terminal_confirmed_at = now - timedelta(days=8)
        order.updated_at = now
        tracking.source_observed_at = now - timedelta(days=31)
        for state in db.scalars(select(PxgNaverReadonlyRecordState).where(PxgNaverReadonlyRecordState.store_id == store.id)).all():
            state.source_observed_at = now
            state.retention_review_at = now
        db.commit()

        preview = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=True, manual_confirmation=False, actor_id="cleanup-test", now=now,
        )
        assert preview["status"] == "preview", preview
        assert preview["recipient_cleanup_count"] == 1 and preview["tracking_cleanup_count"] == 1, preview
        assert preview["metadata_cleanup_count"] == 0, preview
        assert db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.id == recipient.id)) is not None

        completed = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
        )
        assert completed["status"] == "completed", completed
        assert db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.id == recipient.id)) is None
        retained_tracking = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(PxgNaverReadonlyLogisticsRecord.id == tracking.id))
        assert retained_tracking is not None and retained_tracking.encrypted_tracking_number == "" and retained_tracking.tracking_number_hash
        assert db.scalar(select(Product).where(Product.store_id == store.id, Product.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)) is not None
        assert db.scalar(select(Order).where(Order.store_id == store.id, Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)) is not None
        assert db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(PxgNaverReadonlyCustomerInquiry.store_id == store.id)) is not None

        second_store = Store(name="Retention second Naver", platform="naver", status="active")
        db.add(second_store)
        db.flush()
        second_order = Order(
            store_id=second_store.id,
            platform="naver",
            external_order_id="retention-second-order",
            external_product_order_id="retention-second-product-order",
            product_name="Retention product",
            quantity=1,
            order_amount=1,
            currency="KRW",
            order_status="DELIVERED",
            ordered_at=now - timedelta(days=10),
            source_type="naver_onboarding_sync",
            last_synced_at=now,
        )
        db.add(second_order)
        db.flush()
        second_tracking = PxgNaverReadonlyLogisticsRecord(
            order_id=second_order.id,
            store_id=second_store.id,
            platform="naver",
            carrier="CJ",
            encrypted_tracking_number=encrypt_value("SECOND-TRACKING-1234"),
            tracking_number_hash="second-tracking-hash",
            tracking_number_masked="****1234",
            shipment_status="DELIVERY_COMPLETION",
            shipped_at=now - timedelta(days=40),
            source_updated_at=now,
            source_observed_at=now - timedelta(days=29),
            expires_at=now + timedelta(days=1),
            is_stale=False,
        )
        stopped_order = Order(
            store_id=second_store.id,
            platform="naver",
            external_order_id="retention-stopped-order",
            external_product_order_id="retention-stopped-product-order",
            product_name="Stopped tracking product",
            quantity=1,
            order_amount=1,
            currency="KRW",
            order_status="PURCHASE_CONFIRMED",
            ordered_at=now - timedelta(days=10),
            source_type="naver_onboarding_sync",
            last_synced_at=now,
        )
        db.add_all((second_tracking, stopped_order))
        db.flush()
        stopped_tracking = PxgNaverReadonlyLogisticsRecord(
            order_id=stopped_order.id,
            store_id=second_store.id,
            platform="naver",
            carrier="CJ",
            encrypted_tracking_number=encrypt_value("STOPPED-TRACKING-1234"),
            tracking_number_hash="stopped-tracking-hash",
            tracking_number_masked="****1234",
            shipment_status="DELIVERING",
            shipped_at=now - timedelta(days=40),
            source_updated_at=now,
            source_observed_at=now - timedelta(days=29),
            expires_at=now + timedelta(days=1),
            is_stale=False,
        )
        db.add(stopped_tracking)
        db.commit()
        not_due_cleanup = run_naver_logistics_tracking_retention_cleanup(
            db,
            settings=get_settings(),
            now=now,
        )
        assert not_due_cleanup["store_count"] >= 2
        assert not_due_cleanup["tracking_cleanup_count"] == 0
        db.refresh(second_tracking)
        assert second_tracking.encrypted_tracking_number
        db.refresh(stopped_tracking)
        assert stopped_tracking.encrypted_tracking_number
        second_tracking.source_observed_at = now - timedelta(days=31)
        stopped_tracking.source_observed_at = now - timedelta(days=30)
        db.commit()
        multi_store_cleanup = run_naver_logistics_tracking_retention_cleanup(
            db,
            settings=get_settings(),
            now=now,
        )
        assert multi_store_cleanup == {
            "status": "completed",
            "store_count": 2,
            "tracking_cleanup_count": 2,
            "platform_write": False,
        }
        db.refresh(second_tracking)
        assert second_tracking.encrypted_tracking_number == ""
        assert second_tracking.is_stale is True and second_tracking.tracking_number_hash
        db.refresh(stopped_tracking)
        assert stopped_tracking.encrypted_tracking_number == ""
        assert stopped_tracking.is_stale is True and stopped_tracking.tracking_number_hash
        unavailable_order = Order(
            store_id=second_store.id,
            platform="naver",
            external_order_id="retention-recipient-unavailable",
            external_product_order_id="retention-recipient-unavailable-product",
            product_name="Recipient unavailable product",
            quantity=1,
            order_amount=1,
            currency="KRW",
            order_status="READY",
            ordered_at=now,
            source_type=PXG_NAVER_READONLY_LOCAL_SOURCE,
            last_synced_at=now,
        )
        db.add(unavailable_order)
        db.commit()
        unavailable_batch = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=second_store.id,
            platform="naver",
            order_ids=[unavailable_order.id],
            manual_approval=True,
            actor_context={"role": "admin", "actor_id": "retention-test"},
        )
        assert unavailable_batch == {
            "status": "blocked",
            "skip_reason": "recipient_data_unavailable_or_expired",
            "order_ids": [unavailable_order.id],
        }
        assert db.scalar(select(WarehouseShippingBatchOrder).where(
            WarehouseShippingBatchOrder.local_order_id == unavailable_order.id,
        )) is None
        second_cleanup_status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
            PxgNaverReadonlyCleanupStatus.store_id == second_store.id,
        ))
        assert second_cleanup_status is not None
        assert second_cleanup_status.status == "healthy"
        assert second_cleanup_status.last_success_at is None
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=second_store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_no_successful_run"
        else:
            raise AssertionError("tracking-only cleanup must not certify full retention health")
        second_cleanup_status.status = "manual_review_required"
        second_cleanup_status.manual_review_count = 1
        db.commit()
        preserved_review = run_naver_logistics_tracking_retention_cleanup(
            db,
            settings=get_settings(),
            now=now,
        )
        assert preserved_review["tracking_cleanup_count"] == 0
        db.refresh(second_cleanup_status)
        assert second_cleanup_status.status == "manual_review_required"
        assert second_cleanup_status.manual_review_count == 1
        for state in db.scalars(select(PxgNaverReadonlyRecordState).where(PxgNaverReadonlyRecordState.store_id == store.id)).all():
            if state.resource_type in {"product", "order", "customer_inquiry"}:
                state.source_observed_at = now - timedelta(days=91)
        db.commit()
        metadata = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
        )
        assert metadata["metadata_cleanup_count"] >= 3, metadata
        assert db.scalar(select(Product).where(Product.store_id == store.id, Product.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)) is None
        assert db.scalar(select(Order).where(Order.store_id == store.id, Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE)) is None
        assert db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(PxgNaverReadonlyCustomerInquiry.store_id == store.id)) is None
        audits = db.scalars(select(OperationAuditLog).where(OperationAuditLog.store_id == store.id)).all()
        assert any(item.action == "pxg_naver_readonly_retention_cleanup" for item in audits)
        assert "Fictional Recipient" not in str(audits) and "TEST-CLEANUP-1234" not in str(audits)

        second = persist_pxg_naver_readonly_adapter_batch(
            db, settings=get_settings(), batch=fictional_batch(store.id), actor_id="cleanup-test", manual_approval=True,
        )
        assert second["status"] == "completed", second
        frozen_order = db.scalar(select(Order).where(Order.store_id == store.id, Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE))
        assert frozen_order is not None
        db.add(WarehouseShippingBatch(batch_no="CLEANUP-FROZEN", store_id=store.id, platform="naver", status="warehouse_sent"))
        db.flush()
        batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.batch_no == "CLEANUP-FROZEN"))
        db.add(WarehouseShippingBatchOrder(batch_id=batch.id, local_order_id=frozen_order.id, store_id=store.id, platform="naver", order_reference="cleanup-order", product_name="PXG Fictional Bag", quantity=1))
        secure = db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.order_id == frozen_order.id))
        secure.source_observed_at = now - timedelta(days=31)
        secure_state = db.scalar(select(PxgNaverReadonlyRecordState).where(
            PxgNaverReadonlyRecordState.resource_type == "recipient",
            PxgNaverReadonlyRecordState.local_record_id == secure.id,
        ))
        assert secure_state is not None
        secure_state.source_observed_at = now - timedelta(days=91)
        db.commit()
        frozen = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
        )
        assert frozen["manual_review_frozen_count"] == 1, frozen
        assert db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(PxgNaverOrderRecipientSecureRecord.order_id == frozen_order.id)) is not None
        assert db.get(PxgNaverReadonlyRecordState, secure_state.id) is not None
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_manual_review_required"
        else:
            raise AssertionError("manual-review cleanup state must block operations")
        try:
            readonly_local_summary(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_manual_review_required"
        else:
            raise AssertionError("manual-review cleanup state must block display")
        try:
            warehouse_shipping_service.issue_approval_grant(db, batch_id=batch.id, user_id=admin.id, grant_scope="manifest")
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_manual_review_required"
        else:
            raise AssertionError("manual-review cleanup state must block warehouse approval and export")
        with TestClient(app) as client:
            manual_review_refresh = client.post(
                "/api/v1/pxg-naver-readonly/refresh",
                json={"manual_approval": True},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert manual_review_refresh.status_code == 409, manual_review_refresh.text

        failure = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
            force_failure_for_test=True,
        )
        assert failure["status"] == "failed", failure
        assert failure["recipient_cleanup_count"] == 0
        assert failure["tracking_cleanup_count"] == 0
        assert failure["metadata_cleanup_count"] == 0
        assert failure["manual_review_frozen_count"] == 0
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=store.id)
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_failed"
        else:
            raise AssertionError("cleanup failure must block operations")
        try:
            readonly_local_summary(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_failed"
        else:
            raise AssertionError("cleanup failure must block display")
        activation = readonly_activation_precheck(db, settings=get_settings())
        assert activation["checks"]["retention_cleanup_healthy"] is False
        try:
            warehouse_shipping_service.issue_approval_grant(db, batch_id=batch.id, user_id=admin.id, grant_scope="manifest")
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_failed"
        else:
            raise AssertionError("cleanup failure must block warehouse approval and export")

        batch.status = "completed"
        db.commit()
        recovered = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
        )
        assert recovered["status"] == "completed" and recovered["manual_review_frozen_count"] == 0, recovered
        assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=get_settings())
        cleanup_status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
            PxgNaverReadonlyCleanupStatus.store_id == store.id,
        ))
        assert cleanup_status is not None
        cleanup_status.last_success_at = now - timedelta(hours=25)
        db.commit()
        try:
            assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_overdue"
        else:
            raise AssertionError("a cleanup older than 24 hours must block operations")
        try:
            readonly_local_summary(db, store_id=store.id, settings=get_settings())
        except ApiError as exc:
            assert exc.error_code == "readonly_retention_cleanup_overdue"
        else:
            raise AssertionError("an overdue cleanup must block display")
        daily_recovery = run_pxg_naver_readonly_retention_cleanup(
            db, settings=get_settings(), preview=False, manual_confirmation=True, actor_id="cleanup-test", now=now,
        )
        assert daily_recovery["status"] == "completed", daily_recovery
        assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=get_settings())

        expiry_batch = PxgNaverReadonlySyncBatch(
            batch_no="CLEANUP-EXPIRED-BACKUP", store_id=store.id, platform="naver", status="completed",
            actor_id_hash="a" * 64, baseline_counts={}, mutation_counts={}, created_record_ids={},
        )
        db.add(expiry_batch)
        db.flush()
        expired_backup = PxgNaverReadonlySyncBackup(
            batch_id=expiry_batch.id, store_id=store.id, platform="naver", backup_ref="expired-access-gate",
            encrypted_path=str(TEMP_DB.with_suffix(".expired.enc")), checksum_sha256="b" * 64,
            schema_version="test", actor_id_hash="c" * 64, baseline_manifest={},
            expires_at=now - timedelta(seconds=1),
        )
        db.add(expired_backup)
        db.commit()
        original_runtime_settings = app_main.settings
        app_main.settings = original_runtime_settings.model_copy(update={
            "pxg_naver_local_read_retention_cleanup_enabled": False,
        })
        try:
            with TestClient(app) as client:
                requests = (
                    client.get(
                        f"/api/v1/pxg-naver-readonly/local-summary?store_id={store.id}",
                        headers={"X-ERP-User-Key": admin.user_key_hash},
                    ),
                    client.post(
                        "/api/v1/pxg-naver-readonly/refresh",
                        json={"manual_approval": True},
                        headers={"X-ERP-User-Key": admin.user_key_hash},
                    ),
                )
                for response in requests:
                    assert response.status_code == 409, response.text
                    assert response.json()["error_code"] == "readonly_expired_backup_pending", response.text
            warehouse_order = db.scalar(select(Order).where(
                Order.store_id == store.id,
                Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
            ))
            assert warehouse_order is not None
            try:
                recipient_contract_for_authorized_warehouse(db, order=warehouse_order)
            except ApiError as exc:
                assert exc.error_code == "readonly_expired_backup_pending"
            else:
                raise AssertionError("an expired backup must block warehouse recipient reads")
        finally:
            app_main.settings = original_runtime_settings
        expired_backup.deleted_at = now
        db.commit()

        with TestClient(app) as client:
            denied = client.post("/api/v1/pxg-naver-readonly/retention-cleanup", json={"preview": True, "manual_confirmation": False})
            assert denied.status_code in {401, 403}, denied.text
            permitted = client.post(
                "/api/v1/pxg-naver-readonly/retention-cleanup",
                json={"preview": True, "manual_confirmation": False},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert permitted.status_code == 200, permitted.text
            assert permitted.json()["data"]["status"] == "preview", permitted.text
            status = client.get(
                "/api/v1/pxg-naver-readonly/retention-status",
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert status.status_code == 200, status.text
            assert status.json()["data"]["alert_status"] is None, status.text

    close_all_sessions()
    engine.dispose()
    gc.collect()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_readonly_retention_cleanup: ok")


if __name__ == "__main__":
    try:
        main()
        verify_postgres_atomic_tracking_cleanup()
    finally:
        close_all_sessions()
        engine.dispose()
        gc.collect()
        if TEMP_DB.exists():
            TEMP_DB.unlink(missing_ok=True)
