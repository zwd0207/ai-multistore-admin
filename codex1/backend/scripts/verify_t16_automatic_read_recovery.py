import os
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t16-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "SESSION_TOKEN_PEPPER": "t16-session-pepper-32-characters-minimum",
    "APP_ENV": "test",
    "ALLOW_DEV_AUTH": "false",
    "CORS_ALLOWED_ORIGINS": '["https://t16.test"]',
    "AUTOMATIC_READ_SYNC_ENABLED": "true",
    "REAL_API_TEST_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
})

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models.api_capability import ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpSession, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.operation_audit_log import OperationAuditLog
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import automatic_read_sync_service, stats_service
from app.services.api_credential_readiness_service import run_api_credential_smoke_test
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://t16.test"
PASSWORD = "T16-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _checkpoint(db, store_id, resource):
    return db.scalar(select(SyncCheckpoint).where(
        SyncCheckpoint.store_id == store_id,
        SyncCheckpoint.sync_type == automatic_read_sync_service.RESOURCE_CONFIG[resource]["sync_type"],
    ))


def seed():
    init_db()
    with SessionLocal() as db:
        store = Store(name="T16 Naver", platform="naver", status="active")
        user = ErpUser(
            user_key_hash="t16-operator-hash",
            display_name="T16 Operator",
            login_identifier_hash=hash_login_identifier("t16@example.test"),
            login_identifier_masked="t***@example.test",
            status="active",
            auth_provider="password",
        )
        role = ErpRole(role_key="t16_operator", role_label_zh="test", role_label_en="test", status="active")
        db.add_all([store, user, role])
        db.flush()
        permissions = []
        for key, group, sensitive in [
            ("store.manage", "store", True),
            ("credentials.manage", "credential", True),
            ("platform.sync", "sync", False),
            ("dashboard.read", "dashboard", False),
        ]:
            permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == key))
            if permission is None:
                permission = ErpPermission(permission_key=key, permission_group=group, permission_label_zh="test", sensitive_action=sensitive)
                db.add(permission)
                db.flush()
            permissions.append(permission)
        db.add(ErpUserSecurity(
            user_id=user.id,
            password_hash=hash_password(PASSWORD),
            mfa_type="totp",
            mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
            mfa_enabled_at=get_utc_now(),
            password_changed_at=get_utc_now(),
        ))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))
        for permission in permissions:
            db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id, can_approve_sensitive=True))
        credential = ApiCredential(
            store_id=store.id, platform="naver", credential_name="T16 readonly", client_id="t16-client",
            encrypted_secret_key=encrypt_value("t16-secret-never-returned"), auth_status="test_passed",
            status="active", extra_config={"channel_no": "1"},
        )
        db.add(credential)
        db.flush()
        now = get_utc_now()
        for resource, error_code in {
            "orders": "token_auth_failed",
            "customer_inquiries": "permission_forbidden",
            "products": "invalid_cursor",
        }.items():
            db.add(SyncCheckpoint(
                store_id=store.id,
                platform="naver",
                sync_type=automatic_read_sync_service.RESOURCE_CONFIG[resource]["sync_type"],
                automatic_read_enabled=False,
                status="blocked",
                cursor_value="preserve-cursor" if resource == "products" else None,
                window_start_at=now - timedelta(hours=1),
                window_end_at=now,
                last_synced_at=now - timedelta(hours=2),
                last_attempt_at=now - timedelta(minutes=2),
                fresh_until=now - timedelta(minutes=1),
                retry_count=4,
                last_error_code=error_code,
            ))
        db.commit()
        return store.id, role.id, credential.id


def authenticate(client):
    login = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"login_identifier": "t16@example.test", "password": PASSWORD})
    assert login.status_code == 200, login.text
    mfa = client.post("/api/v1/auth/mfa/verify", headers={"Origin": ORIGIN}, json={"code": generate_totp(TOTP_SECRET)})
    assert mfa.status_code == 200, mfa.text
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200, session.text
    return session.json()["data"]["csrf_token"]


def successful_smoke(**kwargs):
    assert kwargs["capability_scope"] == "seller_channels"
    assert kwargs["persist_channel_no"] is False
    assert kwargs["persist_capability_results"] is False
    return {"results": [{"seller_or_account_test": "success", "error_code": None}]}


def failed_smoke(**kwargs):
    assert kwargs["capability_scope"] == "seller_channels"
    assert kwargs["persist_channel_no"] is False
    assert kwargs["persist_capability_results"] is False
    return {"results": [{"seller_or_account_test": "failed", "error_code": "permission_forbidden"}]}


def main():
    store_id, role_id, credential_id = seed()
    with SessionLocal() as db:
        capability_before = db.query(ApiCapabilityTestResult).count()
        credential_before = db.get(ApiCredential, credential_id).extra_config.copy()
        smoke = run_api_credential_smoke_test(
            db=db, platform="naver", mode="readonly", store_id=store_id, capability_scope="seller_channels",
            persist_channel_no=False, persist_capability_results=False,
        )
        assert smoke["results"][0]["error_code"] == "real_api_test_disabled", smoke
        assert db.query(ApiCapabilityTestResult).count() == capability_before
        assert db.get(ApiCredential, credential_id).extra_config == credential_before
        status = automatic_read_sync_service.automatic_read_status(db, store_id=store_id)
        fields = {"attention_state", "operator_message", "admin_action", "recovery_eligible", "action_path"}
        assert fields.issubset(status["orders"])
        assert status["orders"]["attention_state"] == "admin_action" and status["orders"]["recovery_eligible"] is True
        assert status["orders"]["admin_action"] == "verify_and_recover"
        assert status["orders"]["action_path"] == f"/stores?storeId={store_id}&focus=connection"
        assert status["orders"]["operator_message"] == "自动读取已暂停，请管理员检查店铺连接。"
        assert status["products"]["admin_action"] == "manual_review" and status["products"]["recovery_eligible"] is False
        assert status["products"]["operator_message"] == "自动读取已暂停，需要管理员处理。"
        assert status["products"]["action_path"] == f"/stores?storeId={store_id}&focus=connection"
        assert status["logistics"]["attention_state"] == "none" and status["logistics"]["operator_message"] == "暂未接入自动读取"
        for code in ("product_api_not_allowed", "unknown_forbidden"):
            assert automatic_read_sync_service._recovery_eligible_error(code) is True
        for code in ("invalid_cursor", "unknown_internal"):
            assert automatic_read_sync_service._recovery_eligible_error(code) is False
        overview = stats_service.get_store_overview(db, operator_user_id=1)
        summary = overview["automatic_read_attention_summary"]
        assert set(summary) == {"affected_store_count", "affected_resource_count", "retrying_count", "stale_count", "admin_required_count"}
        assert summary == {"affected_store_count": 1, "affected_resource_count": 3, "retrying_count": 0, "stale_count": 0, "admin_required_count": 3}, summary
        checkpoint_snapshot = [(row.id, row.status, row.automatic_read_enabled, row.last_error_code, row.retry_count) for row in db.query(SyncCheckpoint).order_by(SyncCheckpoint.id)]
        audit_before_failed_verification = db.query(OperationAuditLog).count()
        with patch.object(automatic_read_sync_service.api_credential_readiness_service, "run_api_credential_smoke_test", side_effect=failed_smoke):
            try:
                automatic_read_sync_service.recover_automatic_read(db, store_id=store_id, actor_id="t16-operator")
                raise AssertionError("failed verification must not recover checkpoints")
            except ValueError as exc:
                assert str(exc) == "automatic_read_recovery_verification_failed"
        assert [(row.id, row.status, row.automatic_read_enabled, row.last_error_code, row.retry_count) for row in db.query(SyncCheckpoint).order_by(SyncCheckpoint.id)] == checkpoint_snapshot
        assert db.query(ApiCapabilityTestResult).count() == capability_before
        assert db.get(ApiCredential, credential_id).extra_config == credential_before
        failed_audit = db.query(OperationAuditLog).order_by(OperationAuditLog.id.desc()).first()
        assert db.query(OperationAuditLog).count() == audit_before_failed_verification + 1
        assert failed_audit.status == "failed" and failed_audit.reason_code == "verification_failed"

    with TestClient(app, base_url=ORIGIN) as client:
        csrf = authenticate(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        missing_confirmation = client.post(f"/api/v1/stores/{store_id}/automatic-read/recover", headers=headers, json={"confirmation": False})
        assert missing_confirmation.status_code == 422, missing_confirmation.text
        with SessionLocal() as db:
            sync_log_count = db.query(SyncLog).count()
            audit_count = db.query(OperationAuditLog).count()
            permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == "platform.sync"))
            grant = db.scalar(select(ErpRolePermission).where(ErpRolePermission.role_id == role_id, ErpRolePermission.permission_id == permission.id))
            db.delete(grant)
            db.commit()
        denied = client.post(f"/api/v1/stores/{store_id}/automatic-read/recover", headers=headers, json={"confirmation": True})
        assert denied.status_code == 403 and denied.json()["error_code"] == "platform_sync_forbidden", denied.text
        with SessionLocal() as db:
            permission_id = db.scalar(select(ErpPermission.id).where(ErpPermission.permission_key == "platform.sync"))
            db.add(ErpRolePermission(role_id=role_id, permission_id=permission_id, can_approve_sensitive=True))
            session = db.scalar(select(ErpSession).where(ErpSession.revoked_at.is_(None)))
            session.last_reauthenticated_at = get_utc_now() - timedelta(hours=1)
            db.commit()
        stale_auth = client.post(f"/api/v1/stores/{store_id}/automatic-read/recover", headers=headers, json={"confirmation": True})
        assert stale_auth.status_code == 401 and stale_auth.json()["error_code"] == "reauthentication_required", stale_auth.text
        with SessionLocal() as db:
            session = db.scalar(select(ErpSession).where(ErpSession.revoked_at.is_(None)))
            session.last_reauthenticated_at = get_utc_now()
            db.commit()
        with patch.object(automatic_read_sync_service.api_credential_readiness_service, "run_api_credential_smoke_test", side_effect=successful_smoke) as mocked_smoke:
            recovered = client.post(f"/api/v1/stores/{store_id}/automatic-read/recover", headers=headers, json={"confirmation": True})
        assert recovered.status_code == 200, recovered.text
        recovery_data = recovered.json()["data"]
        assert recovery_data["status"] == "recovered" and recovery_data["verification_status"] == "passed"
        assert recovery_data["restored_resources"] == ["customer_inquiries", "orders"]
        assert recovery_data["automatic_read_status"]["orders"]["status"] == "stale"
        assert recovery_data["automatic_read_status"]["orders"]["attention_state"] == "automatic_retry"
        assert recovery_data["safety_flags"] == {"platform_write": False, "sync_started": False, "smoke_persisted": False}
        assert mocked_smoke.call_count == 1

    with SessionLocal() as db:
        orders = _checkpoint(db, store_id, "orders")
        inquiries = _checkpoint(db, store_id, "customer_inquiries")
        products = _checkpoint(db, store_id, "products")
        for checkpoint in (orders, inquiries):
            assert checkpoint.status == "idle" and checkpoint.automatic_read_enabled is True
            assert checkpoint.next_run_at is not None and checkpoint.retry_count == 0 and checkpoint.last_error_code is None
        assert products.status == "blocked" and products.cursor_value == "preserve-cursor" and products.last_error_code == "invalid_cursor"
        assert db.query(SyncLog).count() == sync_log_count
        audit = db.query(OperationAuditLog).order_by(OperationAuditLog.id.desc()).first()
        assert db.query(OperationAuditLog).count() == audit_count + 1
        audit_text = str({"action": audit.action, "counts": audit.counts_summary, "flags": audit.safety_flags}).lower()
        for marker in ("secret", "cursor", "buyer", "phone"):
            assert marker not in audit_text, audit_text
        products.last_error_code = "credential_unavailable"
        products.lease_token = "live"
        products.lease_expires_at = get_utc_now() + timedelta(minutes=5)
        db.commit()
        try:
            automatic_read_sync_service.recover_automatic_read(db, store_id=store_id, actor_id="t16-operator")
            raise AssertionError("live lease must reject recovery")
        except ValueError as exc:
            assert str(exc) == "automatic_read_live_lease"
        products.lease_token = None
        products.lease_expires_at = None
        db.commit()
        disabled = Settings(automatic_read_sync_enabled=False)
        with patch.object(automatic_read_sync_service, "get_settings", return_value=disabled):
            try:
                automatic_read_sync_service.recover_automatic_read(db, store_id=store_id, actor_id="t16-operator")
                raise AssertionError("disabled runtime must reject recovery")
            except ValueError as exc:
                assert str(exc) == "automatic_read_runtime_disabled"
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    print("verify_t16_automatic_read_recovery: ok")


if __name__ == "__main__":
    main()
