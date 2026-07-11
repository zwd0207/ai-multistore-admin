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

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

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
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T06-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store1 = Store(name="Session Test Store", platform="naver", status="active")
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
        allowed = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 1})
        assert allowed.status_code == 200, allowed.text
        forbidden = client.get("/api/v1/shipping/warehouse-batches", params={"store_id": 2})
        assert forbidden.status_code == 403, forbidden.text
        no_csrf = client.post("/api/v1/shipping/warehouse-batches/1/approval/writeback", json={"confirmation": True})
        assert no_csrf.status_code == 403 and no_csrf.json()["error_code"] == "csrf_validation_failed", no_csrf.text
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
            assert db.query(Store).count() == store_count_before
        writeback_permission = client.post(
            "/api/v1/shipping/warehouse-batches/1/approval/writeback",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"confirmation": True},
        )
        assert writeback_permission.status_code == 200, writeback_permission.text

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
