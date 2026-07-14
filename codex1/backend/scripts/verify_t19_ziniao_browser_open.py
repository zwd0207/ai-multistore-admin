import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t19-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
LEGACY_DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t19-legacy-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
CLI_PATH = Path(tempfile.gettempdir()) / f"ziniao-cli-{os.getpid()}-{uuid.uuid4().hex[:8]}" / "ziniao-cli.exe"
CLI_PATH.parent.mkdir(parents=True, exist_ok=True)
CLI_PATH.touch()

os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "SESSION_TOKEN_PEPPER": "t19-session-pepper-32-characters-minimum",
    "SESSION_COOKIE_NAME": "t19_session",
    "SESSION_COOKIE_SECURE": "false",
    "APP_ENV": "test",
    "ALLOW_DEV_AUTH": "false",
    "CORS_ALLOWED_ORIGINS": '["https://t19.test"]',
    "OPERATOR_TRIAL_ENABLED": "false",
    "REAL_API_WRITE_ENABLED": "false",
    "ZINIAO_BROWSER_OPEN_ENABLED": "true",
    "ZINIAO_CLI_EXECUTABLE": str(CLI_PATH),
    "ZINIAO_CLI_PROFILE": "ziniao-sso-pilot",
})

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.operation_audit_log import OperationAuditLog
from app.models.store import Store
from app.services import platform_login_service
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password
from scripts import upgrade_store_browser_schema


ORIGIN = "https://t19.test"
PASSWORD = "T19-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _settings(**overrides) -> Settings:
    values = {
        "database_url": f"sqlite:///{DB_PATH.as_posix()}",
        "credential_encryption_key": Fernet.generate_key().decode("ascii"),
        "session_token_pepper": "t19-settings-pepper-32-characters-minimum",
        "app_env": "test",
        "ziniao_browser_open_enabled": True,
        "ziniao_cli_executable": str(CLI_PATH),
        "ziniao_cli_profile": "ziniao-sso-pilot",
        "ziniao_cli_timeout_seconds": 20,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _seed() -> tuple[int, int, int, int]:
    init_db()
    with SessionLocal() as db:
        store = Store(
            name="T19 Naver",
            platform="naver",
            status="active",
            browser_provider="ziniao",
            browser_profile_name="Pilot Naver",
        )
        other_store = Store(
            name="T19 Other",
            platform="naver",
            status="active",
            browser_provider="ziniao",
            browser_profile_name="Other Naver",
        )
        unbound_store = Store(name="T19 Unbound", platform="naver", status="active")
        user = ErpUser(
            user_key_hash="t19-operator-hash",
            display_name="T19 Operator",
            login_identifier_hash=hash_login_identifier("t19@example.test"),
            login_identifier_masked="t***@example.test",
            status="active",
            auth_provider="password",
        )
        restricted_user = ErpUser(
            user_key_hash="t19-restricted-hash",
            display_name="T19 Restricted",
            login_identifier_hash=hash_login_identifier("restricted-t19@example.test"),
            login_identifier_masked="r***@example.test",
            status="active",
            auth_provider="password",
        )
        role = ErpRole(role_key="t19_operator", role_label_zh="test", role_label_en="test", status="active")
        restricted_role = ErpRole(role_key="t19_restricted", role_label_zh="test", role_label_en="test", status="active")
        db.add_all([store, other_store, unbound_store, user, restricted_user, role, restricted_role])
        db.flush()
        permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == "platform.browser.open"))
        if permission is None:
            permission = ErpPermission(
                permission_key="platform.browser.open",
                permission_group="platform",
                permission_label_zh="test",
                sensitive_action=True,
                status="active",
            )
            db.add(permission)
            db.flush()
        now = get_utc_now()
        for account in (user, restricted_user):
            db.add(ErpUserSecurity(
                user_id=account.id,
                password_hash=hash_password(PASSWORD),
                mfa_type="totp",
                mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
                mfa_enabled_at=now,
                password_changed_at=now,
            ))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))
        db.add(ErpStoreMembership(user_id=restricted_user.id, store_id=store.id, role_id=restricted_role.id, membership_status="active"))
        db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id, can_approve_sensitive=False))
        db.commit()
        return store.id, other_store.id, unbound_store.id, restricted_user.id


def _authenticate(client: TestClient, login_identifier: str = "t19@example.test") -> str:
    login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_identifier": login_identifier, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    mfa = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Origin": ORIGIN},
        json={"code": generate_totp(TOTP_SECRET)},
    )
    assert mfa.status_code == 200, mfa.text
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200, session.text
    return session.json()["data"]["csrf_token"]


class FakeRunner:
    def __init__(self, *, duplicate: bool = False, open_code: int = 0, active_profile: str = "ziniao-sso-pilot"):
        self.duplicate = duplicate
        self.open_code = open_code
        self.active_profile = active_profile
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command, **kwargs):
        self.calls.append((list(command), kwargs))
        args = list(command)[1:]
        if args == ["config", "list"]:
            return subprocess.CompletedProcess(command, 0, f"  default\n* {self.active_profile}\n", "")
        if args[:2] == ["store", "resolve"]:
            row = {
                "storeId": "never-return-this-id",
                "name": "Pilot Naver",
                "platformName": "Naver-韩国-本土",
                "matched": True,
                "ip": "never-return-this-ip",
            }
            if self.duplicate:
                data = [row, {
                    "storeId": "another-hidden-id",
                    "name": "Pilot Naver",
                    "platformName": "Naver-韩国-本土",
                    "matched": True,
                }]
            else:
                data = row
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "data": data}), "")
        if args[:2] == ["store", "open"]:
            return subprocess.CompletedProcess(command, self.open_code, '{"ok":true}', "safe failure")
        raise AssertionError(f"unexpected command: {args}")


def _assert_error_code(callback, code: str) -> None:
    try:
        callback()
        raise AssertionError(f"expected {code}")
    except ApiError as exc:
        assert exc.error_code == code, exc.error_code


def _verify_migration() -> None:
    connection = sqlite3.connect(LEGACY_DB_PATH)
    try:
        connection.execute("CREATE TABLE stores (id INTEGER PRIMARY KEY, name VARCHAR(200), platform VARCHAR(50))")
        connection.commit()
    finally:
        connection.close()
    with patch.object(upgrade_store_browser_schema, "_database_path", return_value=LEGACY_DB_PATH):
        assert set(upgrade_store_browser_schema.upgrade()) == {"browser_provider", "browser_profile_name"}
        assert upgrade_store_browser_schema.upgrade() == []
    connection = sqlite3.connect(LEGACY_DB_PATH)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(stores)").fetchall()}
        assert {"browser_provider", "browser_profile_name"} <= columns
    finally:
        connection.close()


def _verify_service(store_id: int, unbound_store_id: int) -> None:
    runner = FakeRunner()
    with SessionLocal() as db:
        result = platform_login_service.open_store_backend(
            db,
            store_id=store_id,
            actor_id="t19-operator-hash",
            settings=_settings(),
            command_runner=runner,
        )
        assert result == {
            "status": "opened",
            "store_id": store_id,
            "provider": "ziniao",
            "manual_browser_session_opened": True,
            "automated_platform_write_enabled": False,
            "arbitrary_url_allowed": False,
            "audit_recorded": True,
        }
        assert len(runner.calls) == 3
        assert runner.calls[0][0][1:] == ["config", "list"]
        assert runner.calls[1][0][1:4] == ["store", "resolve", "--name"]
        assert runner.calls[2][0][1:4] == ["store", "open", "--name"]
        for command, kwargs in runner.calls:
            assert "--url" not in command
            assert kwargs["shell"] is False
            assert "never-return-this-id" not in command
        audits = db.scalars(select(OperationAuditLog).where(
            OperationAuditLog.store_id == store_id,
            OperationAuditLog.action == "ziniao_browser_open",
        ).order_by(OperationAuditLog.id)).all()
        assert [row.status for row in audits] == ["planned", "success"]
        serialized = json.dumps(result, ensure_ascii=False)
        assert "never-return-this-id" not in serialized and "never-return-this-ip" not in serialized

        no_call_runner = FakeRunner()
        _assert_error_code(
            lambda: platform_login_service.open_store_backend(
                db,
                store_id=unbound_store_id,
                actor_id="t19-operator-hash",
                settings=_settings(),
                command_runner=no_call_runner,
            ),
            "ZINIAO_STORE_NOT_BOUND",
        )
        assert no_call_runner.calls == []
        _assert_error_code(
            lambda: platform_login_service.open_store_backend(
                db,
                store_id=store_id,
                actor_id="t19-operator-hash",
                settings=_settings(ziniao_browser_open_enabled=False),
                command_runner=no_call_runner,
            ),
            "ZINIAO_BROWSER_OPEN_DISABLED",
        )

        duplicate_runner = FakeRunner(duplicate=True)
        _assert_error_code(
            lambda: platform_login_service.open_store_backend(
                db,
                store_id=store_id,
                actor_id="t19-operator-hash",
                settings=_settings(),
                command_runner=duplicate_runner,
            ),
            "ZINIAO_STORE_MATCH_NOT_UNIQUE",
        )
        assert all(call[0][1:3] != ["store", "open"] for call in duplicate_runner.calls)

        profile_runner = FakeRunner(active_profile="default")
        _assert_error_code(
            lambda: platform_login_service.open_store_backend(
                db,
                store_id=store_id,
                actor_id="t19-operator-hash",
                settings=_settings(),
                command_runner=profile_runner,
            ),
            "ZINIAO_PROFILE_NOT_ACTIVE",
        )
        assert len(profile_runner.calls) == 1

        failure_runner = FakeRunner(open_code=1)
        audit_count = db.query(OperationAuditLog).count()
        _assert_error_code(
            lambda: platform_login_service.open_store_backend(
                db,
                store_id=store_id,
                actor_id="t19-operator-hash",
                settings=_settings(),
                command_runner=failure_runner,
            ),
            "ZINIAO_STORE_OPEN_FAILED",
        )
        failed_audits = db.scalars(select(OperationAuditLog).order_by(OperationAuditLog.id).offset(audit_count)).all()
        assert [row.status for row in failed_audits] == ["planned", "failed"]


def _verify_http(store_id: int, other_store_id: int) -> None:
    safe_result = {
        "status": "opened",
        "store_id": store_id,
        "provider": "ziniao",
        "manual_browser_session_opened": True,
        "automated_platform_write_enabled": False,
        "arbitrary_url_allowed": False,
        "audit_recorded": True,
    }
    with TestClient(app, base_url=ORIGIN) as anonymous:
        denied = anonymous.post(f"/api/v1/stores/{store_id}/open-backend", headers={"Origin": ORIGIN}, json={})
        assert denied.status_code == 401, denied.text

    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _authenticate(client)
        missing_csrf = client.post(f"/api/v1/stores/{store_id}/open-backend", headers={"Origin": ORIGIN}, json={})
        assert missing_csrf.status_code == 403, missing_csrf.text
        with patch.object(platform_login_service, "open_store_backend", return_value=safe_result) as mocked:
            opened = client.post(
                f"/api/v1/stores/{store_id}/open-backend",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={},
            )
            assert opened.status_code == 200, opened.text
            mocked.assert_called_once()
            cross_store = client.post(
                f"/api/v1/stores/{other_store_id}/open-backend",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={},
            )
            assert cross_store.status_code == 403, cross_store.text
            assert mocked.call_count == 1

    with TestClient(app, base_url=ORIGIN) as restricted:
        csrf = _authenticate(restricted, "restricted-t19@example.test")
        with patch.object(platform_login_service, "open_store_backend") as mocked:
            denied = restricted.post(
                f"/api/v1/stores/{store_id}/open-backend",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={},
            )
            assert denied.status_code == 403, denied.text
            mocked.assert_not_called()


def main() -> None:
    _verify_migration()
    store_id, other_store_id, unbound_store_id, _restricted_user_id = _seed()
    _verify_service(store_id, unbound_store_id)
    _verify_http(store_id, other_store_id)
    print("T19 Ziniao browser open verification passed")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        for path in (DB_PATH, LEGACY_DB_PATH, CLI_PATH):
            path.unlink(missing_ok=True)
        try:
            CLI_PATH.parent.rmdir()
        except OSError:
            pass
