import os
import sys
import tempfile
import gc
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import close_all_sessions


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
from app.database import SessionLocal, engine, init_db
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
            source_observed_at=now - timedelta(days=31),
            expires_at=now + timedelta(days=1),
            is_stale=False,
        )
        db.add(second_tracking)
        db.commit()
        multi_store_cleanup = run_naver_logistics_tracking_retention_cleanup(
            db,
            settings=get_settings(),
            now=now,
            store_ids={second_store.id},
        )
        assert multi_store_cleanup == {
            "status": "completed",
            "store_count": 1,
            "tracking_cleanup_count": 1,
            "platform_write": False,
        }
        db.refresh(second_tracking)
        assert second_tracking.encrypted_tracking_number == ""
        assert second_tracking.is_stale is True and second_tracking.tracking_number_hash
        second_cleanup_status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
            PxgNaverReadonlyCleanupStatus.store_id == second_store.id,
        ))
        assert second_cleanup_status is not None
        assert second_cleanup_status.status == "healthy"
        assert second_cleanup_status.last_success_at is not None
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
    finally:
        close_all_sessions()
        engine.dispose()
        gc.collect()
        if TEMP_DB.exists():
            TEMP_DB.unlink(missing_ok=True)
