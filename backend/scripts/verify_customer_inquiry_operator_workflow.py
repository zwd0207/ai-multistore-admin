import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-customer-inquiry-operator-workflow.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["APP_ENV"] = "test"
os.environ["ALLOW_DEV_AUTH"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["SESSION_TOKEN_PEPPER"] = "test-only-session-pepper-32-characters-minimum"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["CORS_ALLOWED_ORIGINS"] = '["https://erp.test"]'
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"
os.environ["OPERATOR_TRIAL_REAL_READ_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "true"
os.environ["LIFECYCLE_SCHEDULERS_ENABLED"] = "false"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.pxg_naver_readonly import (
    PxgNaverReadonlyCleanupStatus,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlySyncBackup,
    PxgNaverReadonlySyncBatch,
    PxgNaverReadonlySyncControl,
)
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services.encryption import encrypt_value
from app.services import naver_readonly_inquiry_service, sync_service
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T10-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _create_user(db, *, login_identifier: str, role: ErpRole, store_id: int) -> None:
    user = ErpUser(
        user_key_hash=f"customer-inquiry-{login_identifier}-hash",
        display_name="Test Operator",
        login_identifier_hash=hash_login_identifier(login_identifier),
        login_identifier_masked="t***@example.test",
        status="active",
        auth_provider="password",
    )
    db.add(user)
    db.flush()
    db.add(ErpUserSecurity(
        user_id=user.id,
        password_hash=hash_password(PASSWORD),
        mfa_type="totp",
        mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
        mfa_enabled_at=get_utc_now(),
        password_changed_at=get_utc_now(),
    ))
    db.add(ErpStoreMembership(user_id=user.id, store_id=store_id, role_id=role.id, membership_status="active"))


def seed() -> None:
    Base.metadata.create_all(engine)
    now = get_utc_now()
    with SessionLocal() as db:
        store = Store(name="Customer Inquiry Test Store", platform="naver", status="active")
        other_store = Store(name="Other Store", platform="coupang", status="active")
        permitted_role = ErpRole(role_key="customer_inquiry_reader", role_label_zh="test", role_label_en="test", status="active")
        denied_role = ErpRole(role_key="customer_inquiry_denied", role_label_zh="test", role_label_en="test", status="active")
        orders_read = ErpPermission(permission_key="orders.read", permission_group="orders", permission_label_zh="test")
        customer_reply = ErpPermission(
            permission_key="customer.inquiries.reply",
            permission_group="customer",
            permission_label_zh="test",
        )
        platform_sync = ErpPermission(permission_key="platform.sync", permission_group="sync", permission_label_zh="test")
        db.add_all([store, other_store, permitted_role, denied_role, orders_read, customer_reply, platform_sync])
        db.flush()
        db.add(ErpRolePermission(role_id=permitted_role.id, permission_id=orders_read.id))
        db.add(ErpRolePermission(role_id=permitted_role.id, permission_id=customer_reply.id))
        db.add(ErpRolePermission(role_id=permitted_role.id, permission_id=platform_sync.id))
        _create_user(db, login_identifier="reader@example.test", role=permitted_role, store_id=store.id)
        _create_user(db, login_identifier="denied@example.test", role=denied_role, store_id=store.id)
        _create_user(db, login_identifier="generic@example.test", role=permitted_role, store_id=other_store.id)

        order = Order(
            store_id=store.id,
            platform="naver",
            external_order_id="ORDER-1",
            external_product_order_id="PRODUCT-1",
            product_name="PXG Golf Bag",
            quantity=1,
            order_amount=0,
            currency="KRW",
            order_status="paid",
            ordered_at=now,
            source_type="pxg_naver_readonly_local_v1",
        )
        db.add(order)
        db.flush()
        db.add(PxgNaverReadonlyLogisticsRecord(
            order_id=order.id,
            store_id=store.id,
            platform="naver",
            carrier="CJ",
            encrypted_tracking_number="test-only-encrypted-tracking",
            tracking_number_hash="a" * 64,
            tracking_number_masked="1234****7890",
            shipment_status="in_transit",
            shipped_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=30),
        ))
        db.add(CustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id="generic-1",
            inquiry_type="delivery",
            customer_name="Full Customer Name",
            title="Delivery status for ORDER-1",
            content="Call 010-1234-5678 and send the package to the full recipient address.",
            status="open",
            received_at=now,
            raw_data={"order_id": "ORDER-1", "recipient_phone": "010-1234-5678"},
        ))
        db.add(PxgNaverReadonlyCustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id_hash="b" * 64,
            related_order_id=order.id,
            inquiry_type="delivery",
            status="open",
            customer_display_masked="K**",
            subject_category="delivery_status",
            content_available=False,
            received_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=15),
        ))
        db.add(PxgNaverReadonlyCustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id_hash="c" * 64,
            related_order_id=None,
            inquiry_type="product",
            status="open",
            customer_display_masked="P**",
            subject_category="product_question",
            content_available=False,
            received_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=15),
        ))
        db.add(PxgNaverReadonlyCleanupStatus(
            store_id=store.id,
            platform="naver",
            status="healthy",
            last_run_at=now,
            last_success_at=now,
        ))
        db.add(CustomerInquiry(
            store_id=other_store.id,
            platform="coupang",
            external_inquiry_id="generic-only-1",
            inquiry_type="product",
            customer_name="Unrelated Customer",
            title="Generic-only inquiry",
            content="No PXG local source exists for this store.",
            status="open",
            received_at=now,
            raw_data={"is_test": True},
        ))
        db.commit()


def authenticate(client: TestClient, login_identifier: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_identifier": login_identifier, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Origin": ORIGIN},
        json={"code": generate_totp(TOTP_SECRET)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["csrf_token"]


def assert_pxg_metadata_blocked(client: TestClient, *, expected_error_code: str) -> None:
    response = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["error_code"] == expected_error_code, payload
    assert "data" not in payload and "ORDER-1" not in response.text and "product_question" not in response.text, response.text


def restore_cleanup_health() -> None:
    with SessionLocal() as db:
        cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=1, platform="naver").one()
        cleanup.status = "healthy"
        cleanup.last_run_at = get_utc_now()
        cleanup.last_success_at = get_utc_now()
        control = db.query(PxgNaverReadonlySyncControl).filter_by(store_id=1, platform="naver").one_or_none()
        if control is not None:
            control.write_and_refresh_blocked = False
            control.backup_retention_failed = False
            control.reason_code = None
        db.commit()


def main() -> None:
    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        missing_session = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert missing_session.status_code == 401 and missing_session.json()["error_code"] == "session_required", missing_session.text

        pending_mfa = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_identifier": "reader@example.test", "password": PASSWORD},
        )
        assert pending_mfa.status_code == 200, pending_mfa.text
        mfa_required = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert mfa_required.status_code == 403 and mfa_required.json()["error_code"] == "mfa_required", mfa_required.text

        client.cookies.clear()
        csrf = authenticate(client, "reader@example.test")
        response = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert response.status_code == 200, response.text
        items = response.json()["data"]["items"]
        assert len(items) == 2, items
        assert len({item["inquiry_id"] for item in items}) == 2, items
        assert {item["source"] for item in items} == {"pxg_naver_readonly_local_v1"}, items
        assert response.json()["data"]["total"] == 2, response.text
        assert response.json()["data"]["classification_counts"] == {"all": 2, "answered": 0, "unanswered": 2}, response.text
        assert all(item["store_id"] == 1 for item in items), items
        assert all(set(item) >= {"source", "inquiry_id", "category", "inquiry_type", "status", "summary", "created_at", "updated_at", "store_id", "order_context", "logistics_context", "reply_enabled"} for item in items), items
        assert all("customer_name" not in item and "raw_data" not in item and "content" not in item for item in items), items
        assert "Full Customer Name" not in response.text and "010-1234-5678" not in response.text, response.text
        assert "test-only-encrypted-tracking" not in response.text, response.text
        pxg_item = next(item for item in items if item["source"] == "pxg_naver_readonly_local_v1")
        assert pxg_item["reply_enabled"] is False and pxg_item["reply_disabled_reason"] == "readonly_source", pxg_item
        assert pxg_item["order_context"]["order_no"] == "ORDER-1", pxg_item
        assert pxg_item["logistics_context"]["tracking_number_masked"] == "1234****7890", pxg_item
        no_context_item = next(item for item in items if item["category"] == "product_question")
        assert no_context_item["order_context"] == {} and no_context_item["logistics_context"] == {}, no_context_item

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=1, platform="naver").one()
            cleanup.last_success_at = None
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_retention_cleanup_no_successful_run")
        restore_cleanup_health()

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=1, platform="naver").one()
            cleanup.status = "failed"
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_retention_cleanup_failed")
        restore_cleanup_health()

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=1, platform="naver").one()
            cleanup.status = "manual_review_required"
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_retention_cleanup_manual_review_required")
        restore_cleanup_health()

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=1, platform="naver").one()
            cleanup.last_success_at = get_utc_now() - timedelta(hours=25)
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_retention_cleanup_overdue")
        restore_cleanup_health()

        os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "false"
        get_settings.cache_clear()
        try:
            assert_pxg_metadata_blocked(client, expected_error_code="readonly_retention_cleanup_disabled")
            client.cookies.clear()
            authenticate(client, "generic@example.test")
            unrelated = client.get("/api/v1/customer-inquiries", params={"store_id": 2})
            assert unrelated.status_code == 200 and unrelated.json()["data"]["total"] == 1, unrelated.text
            generic_item = unrelated.json()["data"]["items"][0]
            assert generic_item["source"] == "generic", generic_item
            assert generic_item["platform"] == "coupang", generic_item
            assert generic_item["reply_enabled"] is False, generic_item
            assert generic_item["reply_disabled_reason"] == "legacy_readonly", generic_item
        finally:
            os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "true"
            get_settings.cache_clear()
        client.cookies.clear()
        csrf = authenticate(client, "reader@example.test")

        with SessionLocal() as db:
            control = PxgNaverReadonlySyncControl(
                store_id=1,
                platform="naver",
                write_and_refresh_blocked=True,
                reason_code="test_lock",
            )
            db.add(control)
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_sync_safety_blocked")
        restore_cleanup_health()

        with SessionLocal() as db:
            batch = PxgNaverReadonlySyncBatch(
                batch_no="T10-EXPIRED-BACKUP",
                store_id=1,
                platform="naver",
                status="completed",
                actor_id_hash="a" * 64,
                baseline_counts={},
            )
            db.add(batch)
            db.flush()
            backup = PxgNaverReadonlySyncBackup(
                batch_id=batch.id,
                store_id=1,
                platform="naver",
                backup_ref="t10-expired-backup",
                encrypted_path="t10-test-only.enc",
                checksum_sha256="b" * 64,
                schema_version="test",
                actor_id_hash="c" * 64,
                baseline_manifest={},
                expires_at=get_utc_now() - timedelta(seconds=1),
            )
            db.add(backup)
            db.commit()
        assert_pxg_metadata_blocked(client, expected_error_code="readonly_expired_backup_pending")
        with SessionLocal() as db:
            db.query(PxgNaverReadonlySyncBackup).filter_by(backup_ref="t10-expired-backup").one().deleted_at = get_utc_now()
            db.commit()

        original_legacy_sync = sync_service.sync_naver_customer_inquiries
        original_readonly_refresh = naver_readonly_inquiry_service.refresh_naver_readonly_inquiries

        def unexpected_legacy_inquiry_work(*_args, **_kwargs):
            raise AssertionError("manual batch reached the permanently disabled legacy inquiry sync")

        def controlled_readonly_refresh(*_args, **_kwargs):
            return {
                "status": "success",
                "message": "controlled readonly inquiry refresh completed",
                "created_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "source_type": "pxg_naver_readonly_customer_inquiries",
            }

        sync_service.sync_naver_customer_inquiries = unexpected_legacy_inquiry_work
        naver_readonly_inquiry_service.refresh_naver_readonly_inquiries = controlled_readonly_refresh
        try:
            with SessionLocal() as db:
                inquiry_count_before = db.query(CustomerInquiry).filter_by(store_id=1).count()
                legacy_sync_log_count_before = db.query(SyncLog).filter_by(
                    store_id=1,
                    sync_type="naver_customer_inquiry_real_sync",
                ).count()
            direct_legacy_sync = client.post(
                "/api/v1/sync/customer-inquiries/naver",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={"store_id": 1, "page": 1, "size": 1},
            )
            assert direct_legacy_sync.status_code == 403 and direct_legacy_sync.json()["error_code"] == "legacy_platform_write_disabled", direct_legacy_sync.text
            with SessionLocal() as db:
                assert db.query(CustomerInquiry).filter_by(store_id=1).count() == inquiry_count_before
                assert db.query(SyncLog).filter_by(
                    store_id=1,
                    sync_type="naver_customer_inquiry_real_sync",
                ).count() == legacy_sync_log_count_before
            with SessionLocal() as db:
                manual = sync_service.manual_batch_sync(
                    db,
                    store_id=1,
                    platforms=["naver"],
                    include_products=False,
                    include_orders=False,
                    include_customer_inquiries=True,
                )
            inquiry_item = next(item for item in manual["items"] if item["resource"] == "customer_inquiries")
            assert inquiry_item["status"] == "success", manual
            assert inquiry_item["source_type"] == "pxg_naver_readonly_customer_inquiries", manual
            with SessionLocal() as db:
                assert db.query(CustomerInquiry).filter_by(store_id=1).count() == inquiry_count_before
                assert db.query(SyncLog).filter_by(
                    store_id=1,
                    sync_type="naver_customer_inquiry_real_sync",
                ).count() == legacy_sync_log_count_before
        finally:
            sync_service.sync_naver_customer_inquiries = original_legacy_sync
            naver_readonly_inquiry_service.refresh_naver_readonly_inquiries = original_readonly_refresh

        repeated = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["data"]["items"] == items, repeated.text
        no_match = client.get("/api/v1/customer-inquiries", params={"store_id": 1, "platform": "coupang"})
        assert no_match.status_code == 200 and no_match.json()["data"]["items"] == [], no_match.text
        cross_store = client.get("/api/v1/customer-inquiries", params={"store_id": 2})
        assert cross_store.status_code == 403, cross_store.text
        disabled_reply = client.post(
            "/api/v1/sync/customer-inquiries/naver/reply",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"store_id": 1, "inquiry_id": pxg_item["inquiry_id"], "content": "should not send"},
        )
        assert disabled_reply.status_code == 403 and disabled_reply.json()["error_code"] == "legacy_platform_write_disabled", disabled_reply.text

        client.cookies.clear()
        authenticate(client, "denied@example.test")
        no_permission = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert no_permission.status_code == 403, no_permission.text

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_customer_inquiry_operator_workflow: ok")


if __name__ == "__main__":
    main()
