import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-production-sessions.db"
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
os.environ["PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED"] = "true"
os.environ["LIFECYCLE_SCHEDULERS_ENABLED"] = "false"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.auth import (
    ErpPermission,
    ErpRole,
    ErpRolePermission,
    ErpSession,
    ErpStoreMembership,
    ErpUser,
    ErpUserSecurity,
)
from app.models.shipping import WarehouseShippingBatch
from app.models.store import Store
from app.models.operation_audit_log import OperationAuditLog
from app.models.sync_log import SyncLog
from app.services import shipping_service, sync_service
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T06-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store1 = Store(name="pxg球包店", platform="naver", status="active")
        store2 = Store(name="Forbidden Store", platform="naver", status="active")
        user = ErpUser(
            user_key_hash="session-test-user-key-hash",
            display_name="Session Test Operator",
            login_identifier_hash=hash_login_identifier("operator@example.test"),
            login_identifier_masked="o***@example.test",
            status="active",
            auth_provider="password",
        )
        role = ErpRole(role_key="session_test_operator", role_label_zh="test", role_label_en="test", status="active")
        permissions = [
            ErpPermission(permission_key="shipping.batch.manage", permission_group="shipping", permission_label_zh="test"),
            ErpPermission(permission_key="shipping.writeback.approve", permission_group="shipping", permission_label_zh="test", sensitive_action=True),
            ErpPermission(permission_key="platform.sync", permission_group="sync", permission_label_zh="test"),
            ErpPermission(permission_key="customer.inquiries.reply", permission_group="customer", permission_label_zh="test"),
            ErpPermission(permission_key="platform.readonly.persist", permission_group="platform", permission_label_zh="test", sensitive_action=True),
            ErpPermission(permission_key="orders.read", permission_group="orders", permission_label_zh="test"),
        ]
        db.add_all([store1, store2, user, role, *permissions])
        db.flush()
        db.add(ErpUserSecurity(
            user_id=user.id,
            password_hash=hash_password(PASSWORD),
            mfa_type="totp",
            mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
            mfa_enabled_at=get_utc_now(),
            password_changed_at=get_utc_now(),
        ))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store1.id, role_id=role.id, membership_status="active"))
        for permission in permissions:
            db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id, can_approve_sensitive=True))
        db.add(WarehouseShippingBatch(batch_no="SESSION-TEST-1", store_id=store1.id, platform="naver", status="created"))
        db.commit()


def authenticate(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_identifier": "operator@example.test", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    pending_business = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
    assert pending_business.status_code == 403 and pending_business.json()["error_code"] == "mfa_required", pending_business.text
    response = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Origin": ORIGIN},
        json={"code": generate_totp(TOTP_SECRET)},
    )
    assert response.status_code == 200, response.text
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200, response.text
    return response.json()["data"]["csrf_token"]


def main() -> None:
    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        missing = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
        assert missing.status_code == 401 and missing.json()["error_code"] == "session_required", missing.text
        missing_readonly_write = client.post(
            "/api/v1/pxg-naver-readonly/refresh",
            json={"manual_approval": True},
        )
        assert missing_readonly_write.status_code == 401, missing_readonly_write.text
        for protected_read in (
            "/api/v1/stores",
            "/api/v1/products?store_id=1",
            "/api/v1/orders?store_id=1",
            "/api/v1/customer-inquiries?store_id=1",
            "/api/v1/dashboard/summary?store_id=1",
            "/api/v1/sync-logs?store_id=1",
        ):
            response = client.get(protected_read)
            assert response.status_code == 401 and response.json()["error_code"] == "session_required", response.text
        with SessionLocal() as db:
            store_count_before = db.query(Store).count()
        rejected_store_create = client.post("/api/v1/stores", json={"name": "Rejected Store", "platform": "naver"})
        assert rejected_store_create.status_code == 401, rejected_store_create.text
        rejected_capability_result = client.post("/api/v1/api-capability-results", json={})
        assert rejected_capability_result.status_code == 401, rejected_capability_result.text
        rejected_unknown_write = client.post("/api/v1/future-unknown-write", json={"store_id": 1})
        assert rejected_unknown_write.status_code == 401, rejected_unknown_write.text
        with SessionLocal() as db:
            assert db.query(Store).count() == store_count_before
        forged = client.get(
            "/api/v1/shipping/warehouse-batches",
            params={"store_id": 1},
            headers={"X-ERP-User-Key": "session-test-user-key-hash"},
        )
        assert forged.status_code == 401, forged.text
        invalid = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_identifier": "operator@example.test", "password": "wrong"},
        )
        assert invalid.status_code == 401 and invalid.json()["error_code"] == "invalid_credentials", invalid.text

        csrf = authenticate(client)
        readonly_payload = {"manual_approval": True}
        visible_stores = client.get("/api/v1/stores")
        assert visible_stores.status_code == 200, visible_stores.text
        assert [item["id"] for item in visible_stores.json()["data"]["items"]] == [1], visible_stores.text
        allowed = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
        assert allowed.status_code == 200, allowed.text
        forbidden = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 2})
        assert forbidden.status_code == 403, forbidden.text
        cross_store_read = client.get("/api/v1/products", params={"store_id": 2})
        assert cross_store_read.status_code == 403 and cross_store_read.json()["error_code"] == "store_scope_forbidden", cross_store_read.text
        no_csrf = client.post("/api/v1/shipping/warehouse-batches/1/approval/writeback", json={"confirmation": True})
        assert no_csrf.status_code == 403 and no_csrf.json()["error_code"] == "csrf_validation_failed", no_csrf.text
        readonly_without_csrf = client.post(
            "/api/v1/pxg-naver-readonly/refresh",
            json=readonly_payload,
        )
        assert readonly_without_csrf.status_code == 403 and readonly_without_csrf.json()["error_code"] == "csrf_validation_failed", readonly_without_csrf.text
        unknown_without_csrf = client.post("/api/v1/future-unknown-write", json={"store_id": 1})
        assert unknown_without_csrf.status_code == 403 and unknown_without_csrf.json()["error_code"] == "csrf_validation_failed", unknown_without_csrf.text
        unknown_without_permission = client.post(
            "/api/v1/future-unknown-write",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"store_id": 1},
        )
        assert unknown_without_permission.status_code == 403 and unknown_without_permission.json()["error_code"] == "system_configure_forbidden", unknown_without_permission.text
        capability_without_permission = client.post(
            "/api/v1/api-capability-results",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"store_id": 1},
        )
        assert capability_without_permission.status_code == 403 and capability_without_permission.json()["error_code"] == "system_configure_forbidden", capability_without_permission.text
        denied_store_create = client.post(
            "/api/v1/stores",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"name": "Denied Store", "platform": "naver"},
        )
        assert denied_store_create.status_code == 403, denied_store_create.text
        cross_store_write = client.post(
            "/api/v1/shipping/warehouse-batches",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"store_id": 2, "platform": "naver", "order_ids": [], "manual_approval": True},
        )
        assert cross_store_write.status_code == 403, cross_store_write.text
        with SessionLocal() as db:
            audit_count_before_rejections = db.query(OperationAuditLog).count()
            sync_log_count_before_rejections = db.query(SyncLog).count()
        all_store_sync = client.post(
            "/api/v1/sync/manual-batch/all",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={},
        )
        assert all_store_sync.status_code == 403 and all_store_sync.json()["error_code"] == "system_configure_forbidden", all_store_sync.text
        original_shipping_write = shipping_service.execute_naver_shipment_writeback
        original_customer_reply = sync_service.reply_naver_customer_inquiry
        def unexpected_platform_call(*_args, **_kwargs):
            raise AssertionError("a disabled legacy route reached its platform service")
        shipping_service.execute_naver_shipment_writeback = unexpected_platform_call
        sync_service.reply_naver_customer_inquiry = unexpected_platform_call
        try:
            legacy_shipping = client.post(
                "/api/v1/shipping/shipment-writeback/execute",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={"store_id": 1},
            )
            assert legacy_shipping.status_code == 403 and legacy_shipping.json()["error_code"] == "legacy_platform_write_disabled", legacy_shipping.text
            direct_customer_reply = client.post(
                "/api/v1/sync/customer-inquiries/naver/reply",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={"store_id": 1},
            )
            assert direct_customer_reply.status_code == 403 and direct_customer_reply.json()["error_code"] == "legacy_platform_write_disabled", direct_customer_reply.text
        finally:
            shipping_service.execute_naver_shipment_writeback = original_shipping_write
            sync_service.reply_naver_customer_inquiry = original_customer_reply
        with SessionLocal() as db:
            try:
                sync_service.reply_naver_customer_inquiry(
                    db,
                    store_id=1,
                    external_inquiry_id="1",
                    answer_comment="must remain closed",
                    manual_approval=True,
                    final_operator_confirmation=True,
                )
                raise AssertionError("disabled customer platform writes reached the reply workflow")
            except ApiError as exc:
                assert exc.error_code == "customer_platform_write_disabled"
        with SessionLocal() as db:
            assert db.query(Store).count() == store_count_before
            assert db.query(WarehouseShippingBatch).count() == 1
            assert db.query(OperationAuditLog).count() == audit_count_before_rejections
            assert db.query(SyncLog).count() == sync_log_count_before_rejections
        writeback_permission = client.post(
            "/api/v1/shipping/warehouse-batches/1/approval/writeback",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"confirmation": True},
        )
        assert writeback_permission.status_code == 403 and writeback_permission.json()["error_code"] == "trial_t18_write_gates_required", writeback_permission.text

        readonly_success = client.post(
            "/api/v1/pxg-naver-readonly/refresh",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=readonly_payload,
        )
        assert readonly_success.status_code == 409 and readonly_success.json()["error_code"] in {"readonly_retention_cleanup_disabled", "readonly_sync_safety_blocked"}, readonly_success.text
        with SessionLocal() as db:
            assert db.query(OperationAuditLog).count() == audit_count_before_rejections

        session_cookie = client.cookies.get("__Host-erp_session")
        assert session_cookie
        with SessionLocal() as db:
            session = db.query(ErpSession).filter(ErpSession.revoked_at.is_(None), ErpSession.authn_level == "mfa_verified").one()
            assert session.session_token_hash != session_cookie
            session.idle_expires_at = get_utc_now() - timedelta(seconds=1)
            db.commit()
        expired = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
        assert expired.status_code == 401 and expired.json()["error_code"] == "session_expired", expired.text

        client.cookies.clear()
        csrf = authenticate(client)
        logout = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert logout.status_code == 200, logout.text
        after_logout = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
        assert after_logout.status_code == 401, after_logout.text
    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_production_sessions: ok")


if __name__ == "__main__":
    main()
