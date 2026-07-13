"""Focused, isolated verification for the local MFA code display endpoint."""

import gc
import os
import re
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-local-mfa-code-display.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{TEMP_DB.as_posix()}",
    "SESSION_TOKEN_PEPPER": "test-only-session-pepper-32-characters-minimum",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "CORS_ALLOWED_ORIGINS": '["https://erp.test"]',
    "LOCAL_MFA_CODE_DISPLAY_ENABLED": "true",
    "SESSION_COOKIE_SECURE": "false",
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
})

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.config import Settings, get_settings
from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.auth import ErpRole, ErpSession, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.store import Store
from app.services.encryption import encrypt_value
from app.services.session_service import _peppered_hash, generate_totp, hash_login_identifier, hash_password, is_loopback_socket_peer


ORIGIN = "https://erp.test"
LOGIN = "pxg-config-admin@local.test"
PASSWORD = "local-mfa-display-test-password"
SECRET = "JBSWY3DPEHPK3PXP"
ROLE_KEY = "pxg_connection_config_admin"
TRIAL_LOGIN = "pxg-trial-operator@local.test"
TRIAL_PASSWORD = "local-trial-operator-test-password"
TRIAL_SECRET = "KRSXG5DSNFXGOIDB"
TRIAL_ROLE_KEY = "pxg_naver_trial_operator"


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store = Store(name="pxg球包店", platform="naver", status="active")
        role = ErpRole(role_key=ROLE_KEY, role_label_zh="test", role_label_en="test", status="active")
        user = ErpUser(
            user_key_hash="local-mfa-display-user",
            display_name="Local MFA display",
            login_identifier_hash=hash_login_identifier(LOGIN),
            login_identifier_masked="pxg-config-admin",
            status="active",
            auth_provider="password",
        )
        trial_role = ErpRole(role_key=TRIAL_ROLE_KEY, role_label_zh="trial", role_label_en="trial", status="active")
        trial_user = ErpUser(
            user_key_hash="local-mfa-display-trial-user",
            display_name="Local trial operator",
            login_identifier_hash=hash_login_identifier(TRIAL_LOGIN),
            login_identifier_masked="pxg-trial-operator",
            status="active",
            auth_provider="password",
        )
        db.add_all([store, role, user, trial_role, trial_user])
        db.flush()
        db.add(ErpUserSecurity(
            user_id=user.id,
            password_hash=hash_password(PASSWORD),
            mfa_type="totp",
            mfa_secret_encrypted=encrypt_value(SECRET),
            mfa_enabled_at=get_utc_now(),
            password_changed_at=get_utc_now(),
        ))
        db.add(ErpUserSecurity(
            user_id=trial_user.id,
            password_hash=hash_password(TRIAL_PASSWORD),
            mfa_type="totp",
            mfa_secret_encrypted=encrypt_value(TRIAL_SECRET),
            mfa_enabled_at=get_utc_now(),
            password_changed_at=get_utc_now(),
        ))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))
        db.add(ErpStoreMembership(user_id=trial_user.id, store_id=store.id, role_id=trial_role.id, membership_status="active"))
        db.commit()


def assert_cache_headers(response) -> None:
    assert response.headers.get("cache-control") == "no-store, private", response.headers
    assert response.headers.get("pragma") == "no-cache", response.headers
    assert response.headers.get("vary") == "Cookie", response.headers


def pending_client(login: str = LOGIN, password: str = PASSWORD) -> TestClient:
    client = TestClient(app, base_url=ORIGIN)
    response = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"login_identifier": login, "password": password})
    assert response.status_code == 200, response.text
    return client


def assert_not_found(client: TestClient, **kwargs) -> None:
    response = client.get("/api/v1/auth/local-mfa-code", **kwargs)
    assert response.status_code == 404, response.text
    assert_cache_headers(response)
    body = response.text
    for forbidden in (SECRET, LOGIN, "erp_session", "session_token", "user_id"):
        assert forbidden not in body, body


def pending_session(db, client: TestClient) -> ErpSession:
    token = client.cookies.get(get_settings().session_cookie_name)
    assert token
    return db.query(ErpSession).filter(ErpSession.session_token_hash == _peppered_hash(token)).one()


def main() -> None:
    assert Settings(app_env="test", local_mfa_code_display_enabled=True).local_mfa_code_display_enabled
    assert not Settings(app_env="development", local_mfa_code_display_enabled=False).local_mfa_code_display_enabled
    try:
        Settings(app_env="development", local_mfa_code_display_enabled=True)
        raise AssertionError("local MFA code display must reject non-test settings")
    except ValidationError:
        pass

    loopback_request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", b"203.0.113.7")], "client": ("127.0.0.1", 50100)})
    remote_request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", b"127.0.0.1")], "client": ("203.0.113.7", 50100)})
    assert is_loopback_socket_peer(loopback_request)
    assert not is_loopback_socket_peer(remote_request)

    seed()
    import app.api.v1.endpoints.auth as auth_endpoint
    import app.services.session_service as session_service

    original_loopback_check = auth_endpoint.is_loopback_socket_peer
    auth_endpoint.is_loopback_socket_peer = lambda _request: True
    try:
        client = pending_client()
        original_time = session_service.time.time
        session_service.time.time = lambda: 120
        try:
            response = client.get("/api/v1/auth/local-mfa-code")
        finally:
            session_service.time.time = original_time
        assert response.status_code == 200, response.text
        assert response.json()["data"] == {"code": generate_totp(SECRET, timestamp=120), "seconds_remaining": 30}, response.text
        assert_cache_headers(response)
        assert set(response.json()) == {"success", "message", "data"}
        assert set(response.json()["data"]) == {"code", "seconds_remaining"}
        assert re.fullmatch(r"\d{6}", response.json()["data"]["code"])
        for forbidden in (SECRET, LOGIN, "user", "session"):
            assert forbidden not in response.text, response.text

        with pending_client(TRIAL_LOGIN, TRIAL_PASSWORD) as trial_client:
            trial_response = trial_client.get("/api/v1/auth/local-mfa-code")
            assert trial_response.status_code == 200, trial_response.text
            assert re.fullmatch(r"\d{6}", trial_response.json()["data"]["code"])
            assert TRIAL_SECRET not in trial_response.text

        settings = get_settings()
        settings.app_env = "development"
        assert_not_found(client)
        settings.app_env = "test"

        settings.local_mfa_code_display_enabled = False
        with pending_client() as client:
            assert_not_found(client)
        settings.local_mfa_code_display_enabled = True

        with pending_client() as client:
            assert_not_found(client, headers={"Origin": "https://forbidden.test"})
        with TestClient(app, base_url=ORIGIN) as client:
            response = client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"login_identifier": LOGIN, "password": PASSWORD})
            assert response.status_code == 200, response.text
            auth_endpoint.is_loopback_socket_peer = original_loopback_check
            assert_not_found(client, headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"})
            auth_endpoint.is_loopback_socket_peer = lambda _request: True

        with TestClient(app, base_url=ORIGIN) as client:
            assert_not_found(client)
        with pending_client() as client:
            response = client.post("/api/v1/auth/mfa/verify", headers={"Origin": ORIGIN}, json={"code": generate_totp(SECRET)})
            assert response.status_code == 200, response.text
            assert_not_found(client)
        with pending_client() as client:
            with SessionLocal() as db:
                session = pending_session(db, client)
                session.absolute_expires_at = get_utc_now() - timedelta(seconds=1)
                db.commit()
            assert_not_found(client)
        with pending_client() as client:
            with SessionLocal() as db:
                pending_session(db, client).revoked_at = get_utc_now()
                db.commit()
            assert_not_found(client)
        with pending_client() as client:
            with SessionLocal() as db:
                db.get(ErpUserSecurity, pending_session(db, client).user_id).session_version += 1
                db.commit()
            assert_not_found(client)
        with pending_client() as client:
            with SessionLocal() as db:
                db.get(ErpUserSecurity, pending_session(db, client).user_id).authz_version += 1
                db.commit()
            assert_not_found(client)
        with pending_client() as client:
            with SessionLocal() as db:
                user = db.get(ErpUser, pending_session(db, client).user_id)
                user.login_identifier_hash = hash_login_identifier("wrong@example.test")
                db.commit()
            assert_not_found(client)
            with SessionLocal() as db:
                db.get(ErpUser, 1).login_identifier_hash = hash_login_identifier(LOGIN)
                db.commit()
        with pending_client() as client:
            with SessionLocal() as db:
                db.query(ErpRole).filter(ErpRole.role_key == ROLE_KEY).one().role_key = "wrong_role"
                db.commit()
            assert_not_found(client)
            with SessionLocal() as db:
                db.query(ErpRole).filter(ErpRole.role_key == "wrong_role").one().role_key = ROLE_KEY
                db.commit()
        with pending_client() as client:
            with SessionLocal() as db:
                db.get(ErpUserSecurity, pending_session(db, client).user_id).mfa_secret_encrypted = "not-a-fernet-token"
                db.commit()
            assert_not_found(client)
    finally:
        auth_endpoint.is_loopback_socket_peer = original_loopback_check

    engine.dispose()
    if TEMP_DB.exists():
        for _ in range(20):
            try:
                TEMP_DB.unlink()
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.05)
        else:
            raise PermissionError(f"temporary verification database is still locked: {TEMP_DB}")
    print("verify_local_mfa_code_display: ok")


if __name__ == "__main__":
    main()
