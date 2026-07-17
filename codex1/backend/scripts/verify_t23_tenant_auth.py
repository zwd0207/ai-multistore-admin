from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


DB_PATH = Path(tempfile.gettempdir()) / "codex1-verify-t23-tenant-auth.db"
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
DB_PATH.unlink(missing_ok=True)
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "SESSION_TOKEN_PEPPER": "t23-session-token-pepper-value-longer-than-32-characters",
    "CORS_ALLOWED_ORIGINS": '["https://testserver"]',
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
    "LOCAL_MFA_CODE_DISPLAY_ENABLED": "false",
    "EMAIL_DELIVERY_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models.auth import ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.operation_audit_log import OperationAuditLog
from app.models.store import Store
from app.models.tenant import Tenant, TenantInvitation
from app.core.timezone import get_utc_now
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = {"Origin": "https://testserver"}
ADMIN_EMAIL = "platform-admin@aiglxt.test"
ADMIN_PASSWORD = "AdminPassword2026"
ADMIN_MFA_SECRET = "JBSWY3DPEHPK3PXP"


def seed_platform_admin() -> None:
    init_db()
    with SessionLocal() as db:
        admin = ErpUser(
            user_key_hash="t23-platform-admin-key-hash",
            display_name="Platform administrator",
            login_identifier_hash=hash_login_identifier(ADMIN_EMAIL),
            login_identifier_masked="pl************@aiglxt.test",
            email_encrypted=encrypt_value(ADMIN_EMAIL),
            platform_role="platform_admin",
            status="active",
            auth_provider="password",
        )
        db.add(admin)
        db.flush()
        db.add(ErpUserSecurity(
            user_id=admin.id,
            password_hash=hash_password(ADMIN_PASSWORD),
            mfa_secret_encrypted=encrypt_value(ADMIN_MFA_SECRET),
            mfa_enabled_at=__import__("app.core.timezone", fromlist=["get_utc_now"]).get_utc_now(),
        ))
        db.commit()


def authenticate(client: TestClient, email: str, password: str, mfa_code: str) -> str:
    login = client.post("/api/v1/auth/login", json={"login_identifier": email, "password": password}, headers=ORIGIN)
    assert login.status_code == 200, login.text
    verified = client.post("/api/v1/auth/mfa/verify", json={"code": mfa_code}, headers=ORIGIN)
    assert verified.status_code == 200, verified.text
    return str(verified.json()["data"]["csrf_token"])


def invite_and_activate(client: TestClient, *, csrf: str, email: str, display_name: str, tenant_name: str) -> tuple[dict, list[str]]:
    invited = client.post(
        "/api/v1/auth/invitations",
        json={"email": email, "display_name": display_name, "tenant_name": tenant_name},
        headers={**ORIGIN, "X-CSRF-Token": csrf},
    )
    assert invited.status_code == 200, invited.text
    invitation = invited.json()["data"]
    assert invitation["delivery_status"] == "email_delivery_disabled"
    assert invitation.get("invitation_token")

    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": invitation["invitation_token"], "password": "TenantPassword2026"},
        headers=ORIGIN,
    )
    assert accepted.status_code == 200, accepted.text
    enrollment = accepted.json()["data"]
    assert enrollment["status"] == "mfa_enrollment_required"
    assert enrollment.get("mfa_secret") and enrollment.get("enrollment_token")

    completed = client.post(
        "/api/v1/auth/mfa/enroll/complete",
        json={
            "enrollment_token": enrollment["enrollment_token"],
            "code": generate_totp(enrollment["mfa_secret"]),
        },
        headers=ORIGIN,
    )
    assert completed.status_code == 200, completed.text
    result = completed.json()["data"]
    assert result["status"] == "account_active"
    assert len(result["recovery_codes"]) == 10
    return result, result["recovery_codes"]


def create_tenant_store(client: TestClient, *, csrf: str, name: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={"name": name, "platform": "naver"},
        headers={**ORIGIN, "X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def main() -> None:
    seed_platform_admin()
    admin_client = TestClient(app, base_url="https://testserver")
    admin_csrf = authenticate(admin_client, ADMIN_EMAIL, ADMIN_PASSWORD, generate_totp(ADMIN_MFA_SECRET))

    invitation_payload = {
        "email": "csrf-check@example.com",
        "display_name": "CSRF Check",
        "tenant_name": "CSRF Check Tenant",
    }
    no_invitation_csrf = admin_client.post(
        "/api/v1/auth/invitations",
        json=invitation_payload,
        headers=ORIGIN,
    )
    assert no_invitation_csrf.status_code == 403, no_invitation_csrf.text
    assert no_invitation_csrf.json()["error_code"] == "csrf_validation_failed"
    wrong_invitation_origin = admin_client.post(
        "/api/v1/auth/invitations",
        json=invitation_payload,
        headers={"Origin": "https://wrong.example", "X-CSRF-Token": admin_csrf},
    )
    assert wrong_invitation_origin.status_code == 403, wrong_invitation_origin.text
    assert wrong_invitation_origin.json()["error_code"] == "csrf_validation_failed"

    owner1, recovery1 = invite_and_activate(
        admin_client,
        csrf=admin_csrf,
        email="owner-one@example.com",
        display_name="Owner One",
        tenant_name="Tenant One",
    )
    owner2, _recovery2 = invite_and_activate(
        admin_client,
        csrf=admin_csrf,
        email="owner-two@example.com",
        display_name="Owner Two",
        tenant_name="Tenant Two",
    )
    assert owner1["tenant_id"] != owner2["tenant_id"]

    owner1_client = TestClient(app, base_url="https://testserver")
    owner1_csrf = authenticate(owner1_client, "owner-one@example.com", "TenantPassword2026", recovery1[0])
    empty_session = owner1_client.get("/api/v1/auth/session")
    assert empty_session.status_code == 200, empty_session.text
    assert empty_session.json()["data"]["stores"] == []
    owner1_csrf = empty_session.json()["data"]["csrf_token"]
    store1 = create_tenant_store(owner1_client, csrf=owner1_csrf, name="Shared Naver Store")

    owner2_client = TestClient(app, base_url="https://testserver")
    owner2_secret = None
    with SessionLocal() as db:
        owner2_user = db.get(ErpUser, owner2["user"]["id"])
        owner2_secret = __import__("app.services.encryption", fromlist=["decrypt_value"]).decrypt_value(
            db.get(ErpUserSecurity, owner2_user.id).mfa_secret_encrypted
        )
    owner2_csrf = authenticate(owner2_client, "owner-two@example.com", "TenantPassword2026", generate_totp(owner2_secret))
    store2 = create_tenant_store(owner2_client, csrf=owner2_csrf, name="Shared Naver Store")
    assert store1["tenant_id"] != store2["tenant_id"]

    cross_tenant = owner1_client.get(f"/api/v1/stores/{store2['id']}")
    assert cross_tenant.status_code == 403, cross_tenant.text
    assert cross_tenant.json()["error_code"] in {"tenant_scope_forbidden", "store_scope_forbidden"}

    tenants = admin_client.get("/api/v1/admin/tenants")
    assert tenants.status_code == 200, tenants.text
    assert tenants.json()["data"]["total"] == 2

    select_without_csrf = admin_client.post(
        f"/api/v1/admin/tenants/{owner2['tenant_id']}/select",
        headers=ORIGIN,
    )
    assert select_without_csrf.status_code == 403, select_without_csrf.text
    assert select_without_csrf.json()["error_code"] == "csrf_validation_failed"

    selected = admin_client.post(
        f"/api/v1/admin/tenants/{owner2['tenant_id']}/select",
        headers={**ORIGIN, "X-CSRF-Token": admin_csrf},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["data"]["cross_tenant_mode"] is True
    admin_session = admin_client.get("/api/v1/auth/session")
    assert admin_session.status_code == 200, admin_session.text
    admin_session_data = admin_session.json()["data"]
    assert admin_session_data["administration"] == {
        "is_platform_admin": True,
        "selected_tenant_id": owner2["tenant_id"],
        "cross_tenant_mode": True,
    }
    assert {row["store_id"] for row in admin_session_data["stores"]} == {store2["id"]}
    selected_stores = admin_client.get("/api/v1/stores")
    assert selected_stores.status_code == 200, selected_stores.text
    assert {row["id"] for row in selected_stores.json()["data"]["items"]} == {store2["id"]}
    admin_cross_scope = admin_client.get(f"/api/v1/stores/{store1['id']}")
    assert admin_cross_scope.status_code == 403, admin_cross_scope.text
    assert admin_cross_scope.json()["error_code"] == "tenant_scope_forbidden"

    reset_request = owner1_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "owner-one@example.com"},
        headers=ORIGIN,
    )
    assert reset_request.status_code == 200, reset_request.text
    reset_token = reset_request.json()["data"].get("reset_token")
    assert reset_token
    reset = owner1_client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": reset_token, "password": "NewTenantPassword2026"},
        headers=ORIGIN,
    )
    assert reset.status_code == 200, reset.text
    assert owner1_client.get("/api/v1/auth/session").status_code == 401

    with SessionLocal() as db:
        stores = db.scalars(select(Store).order_by(Store.id)).all()
        assert len(stores) == 2 and stores[0].name == stores[1].name
        assert len({store.tenant_id for store in stores}) == 2
        assert db.query(Tenant).count() == 2
        assert db.query(ErpStoreMembership).count() == 2
        assert db.scalar(select(OperationAuditLog).where(
            OperationAuditLog.action == "platform_admin_cross_tenant_access",
            OperationAuditLog.target_id == owner2["tenant_id"],
        )) is not None
        raw = DB_PATH.read_bytes()
        assert b"owner-one@example.com" not in raw
        assert b"owner-two@example.com" not in raw

        indexes = {
            row[1]
            for table_name in ("erp_users", "tenant_invitations")
            for row in db.execute(text(f"PRAGMA index_list('{table_name}')")).all()
        }
        assert "uq_erp_users_login_identifier_hash" in indexes
        assert "uq_tenant_invitations_active_email_hash" in indexes

        duplicate_user = ErpUser(
            user_key_hash="t23-duplicate-login-user",
            display_name="Duplicate Login",
            login_identifier_hash=hash_login_identifier("owner-one@example.com"),
            login_identifier_masked="du********@example.com",
            status="active",
            auth_provider="password",
        )
        db.add(duplicate_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("login identifier hash must be database-unique")

        now = get_utc_now()
        active_email_hash = hash_login_identifier("pending-duplicate@example.com")
        first_pending = TenantInvitation(
            email_hash=active_email_hash,
            email_encrypted=encrypt_value("pending-duplicate@example.com"),
            email_masked="pe***************@example.com",
            display_name="Pending One",
            tenant_name="Pending Tenant One",
            token_hash="a" * 64,
            expires_at=now + timedelta(hours=24),
        )
        db.add(first_pending)
        db.commit()
        db.add(TenantInvitation(
            email_hash=active_email_hash,
            email_encrypted=encrypt_value("pending-duplicate@example.com"),
            email_masked="pe***************@example.com",
            display_name="Pending Two",
            tenant_name="Pending Tenant Two",
            token_hash="b" * 64,
            expires_at=now + timedelta(hours=24),
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("active invitation email hash must be database-unique")

    print("verify_t23_tenant_auth: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)
