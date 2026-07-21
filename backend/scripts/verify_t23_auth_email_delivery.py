from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from pydantic import ValidationError


DB_PATH = Path(tempfile.gettempdir()) / "codex1-verify-t23-auth-email-delivery.db"
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
DB_PATH.unlink(missing_ok=True)
os.environ.update({
    "APP_ENV": "production",
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "SESSION_TOKEN_PEPPER": "t23-email-session-token-pepper-longer-than-32-characters",
    "PUBLIC_APP_URL": "https://aiglxt.example",
    "EMAIL_DELIVERY_ENABLED": "true",
    "AUTH_EMAIL_FROM_ADDRESS": "noreply@aiglxt.example",
    "AUTH_EMAIL_FROM_NAME": "AIGLXT",
    "AUTH_EMAIL_SMTP_HOST": "smtp.example.invalid",
    "AUTH_EMAIL_SMTP_PORT": "465",
    "AUTH_EMAIL_SMTP_USERNAME": "smtp-user",
    "AUTH_EMAIL_SMTP_PASSWORD": "mock-smtp-password",
    "AUTH_EMAIL_SMTP_SECURITY": "ssl",
    "LIFECYCLE_SCHEDULERS_ENABLED": "false",
})

from app.config import Settings
from app.core.timezone import get_utc_now
from app.database import SessionLocal, engine, init_db
from app.models.auth import ErpUser
from app.services import auth_email_delivery_service, tenant_auth_service
from app.services.auth_email_delivery_service import AuthEmailDeliveryError
from app.services.encryption import encrypt_value
from app.services.session_service import hash_login_identifier


KNOWN_EMAIL = "known-owner@example.com"
UNKNOWN_EMAIL = "unknown-owner@example.com"


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "public_app_url": "https://aiglxt.example",
        "email_delivery_enabled": True,
        "auth_email_from_address": "noreply@aiglxt.example",
        "auth_email_from_name": "AIGLXT",
        "auth_email_smtp_host": "smtp.example.invalid",
        "auth_email_smtp_port": 465,
        "auth_email_smtp_username": "smtp-user",
        "auth_email_smtp_password": "mock-smtp-password",
        "auth_email_smtp_security": "ssl",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def verify_configuration_gate() -> None:
    disabled = Settings(
        _env_file=None,
        email_delivery_enabled=False,
        auth_email_from_address=None,
        auth_email_smtp_host=None,
        auth_email_smtp_username=None,
        auth_email_smtp_password=None,
    )
    assert disabled.email_delivery_enabled is False

    try:
        _settings(auth_email_smtp_password=None)
    except ValidationError as exc:
        assert "complete authentication email SMTP configuration" in str(exc)
    else:
        raise AssertionError("enabled email delivery accepted incomplete SMTP configuration")

    try:
        _settings(public_app_url="http://aiglxt.example")
    except ValidationError as exc:
        assert "HTTPS PUBLIC_APP_URL" in str(exc)
    else:
        raise AssertionError("enabled email delivery accepted a non-HTTPS application URL")

    try:
        _settings(auth_email_from_address="noreply@example.com\r\nBcc: attacker@example.com")
    except ValidationError:
        pass
    else:
        raise AssertionError("enabled email delivery accepted an unsafe sender address")

    configured = _settings()
    assert "mock-smtp-password" not in repr(configured)


def verify_mocked_smtp_transport() -> None:
    action_url = "https://aiglxt.example/#/accept-invite?token=mock-invitation-token"
    expires_at = get_utc_now() + timedelta(hours=24)
    smtp_client = MagicMock()
    smtp_client.send_message.return_value = {}
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_client
    smtp_context.__exit__.return_value = False
    with patch.object(auth_email_delivery_service.smtplib, "SMTP_SSL", return_value=smtp_context) as factory:
        result = auth_email_delivery_service.deliver_invitation_email(
            recipient="operator@example.com",
            invitation_url=action_url,
            expires_at=expires_at,
            settings=_settings(),
        )
    assert result == "sent"
    factory.assert_called_once()
    smtp_client.login.assert_called_once_with("smtp-user", "mock-smtp-password")
    smtp_client.send_message.assert_called_once()
    message = smtp_client.send_message.call_args.args[0]
    assert message["To"] == "operator@example.com"
    assert action_url in message.get_content()
    assert "mock-smtp-password" not in message.as_string()

    starttls_client = MagicMock()
    starttls_client.send_message.return_value = {}
    starttls_context = MagicMock()
    starttls_context.__enter__.return_value = starttls_client
    starttls_context.__exit__.return_value = False
    with patch.object(auth_email_delivery_service.smtplib, "SMTP", return_value=starttls_context):
        result = auth_email_delivery_service.deliver_password_reset_email(
            recipient="operator@example.com",
            reset_url="https://aiglxt.example/#/reset-password?token=mock-reset-token",
            expires_at=expires_at,
            settings=_settings(auth_email_smtp_security="starttls", auth_email_smtp_port=587),
        )
    assert result == "sent"
    method_names = [call[0] for call in starttls_client.method_calls]
    assert method_names.index("starttls") < method_names.index("login") < method_names.index("send_message")

    with patch.object(
        auth_email_delivery_service.smtplib,
        "SMTP_SSL",
        side_effect=RuntimeError("mock-smtp-password mock-invitation-token"),
    ):
        try:
            auth_email_delivery_service.deliver_invitation_email(
                recipient="operator@example.com",
                invitation_url=action_url,
                expires_at=expires_at,
                settings=_settings(),
            )
        except AuthEmailDeliveryError as exc:
            assert str(exc) == "authentication email delivery failed"
        else:
            raise AssertionError("SMTP failure did not fail closed")

    with patch.object(auth_email_delivery_service.smtplib, "SMTP_SSL") as factory:
        result = auth_email_delivery_service.deliver_invitation_email(
            recipient="operator@example.com",
            invitation_url=action_url,
            expires_at=expires_at,
            settings=_settings(email_delivery_enabled=False),
        )
    assert result == "email_delivery_disabled"
    factory.assert_not_called()


def seed_users() -> int:
    init_db()
    with SessionLocal() as db:
        administrator = ErpUser(
            user_key_hash="t23-email-platform-admin-key",
            display_name="Platform administrator",
            login_identifier_hash=hash_login_identifier("admin@example.com"),
            login_identifier_masked="ad***@example.com",
            email_encrypted=encrypt_value("admin@example.com"),
            platform_role="platform_admin",
            status="active",
            auth_provider="password",
        )
        owner = ErpUser(
            user_key_hash="t23-email-known-owner-key",
            display_name="Known owner",
            login_identifier_hash=hash_login_identifier(KNOWN_EMAIL),
            login_identifier_masked="kn***@example.com",
            email_encrypted=encrypt_value(KNOWN_EMAIL),
            platform_role="tenant_owner",
            status="active",
            auth_provider="password",
        )
        db.add_all((administrator, owner))
        db.commit()
        return administrator.id


def verify_production_auth_contract(administrator_id: int) -> None:
    invitation_delivery = MagicMock(return_value="sent")
    with SessionLocal() as db, patch.object(
        tenant_auth_service,
        "deliver_invitation_email",
        invitation_delivery,
    ):
        invitation = tenant_auth_service.create_invitation(
            db,
            email="invited-owner@example.com",
            display_name="Invited owner",
            tenant_name="Invited tenant",
            invited_by_user_id=administrator_id,
        )
    assert invitation["delivery_status"] == "sent"
    assert "invitation_token" not in invitation
    assert "invitation_url" not in invitation
    invitation_delivery.assert_called_once()
    invitation_url = invitation_delivery.call_args.kwargs["invitation_url"]
    invitation_token = invitation_url.rsplit("token=", 1)[1]
    assert invitation_token

    failed_invitation_delivery = MagicMock(
        side_effect=AuthEmailDeliveryError("sensitive mock diagnostic")
    )
    with SessionLocal() as db, patch.object(
        tenant_auth_service,
        "deliver_invitation_email",
        failed_invitation_delivery,
    ):
        failed_invitation = tenant_auth_service.create_invitation(
            db,
            email="second-invited-owner@example.com",
            display_name="Second invited owner",
            tenant_name="Second invited tenant",
            invited_by_user_id=administrator_id,
        )
    assert failed_invitation["delivery_status"] == "delivery_failed"
    assert "invitation_token" not in failed_invitation
    assert "invitation_url" not in failed_invitation

    reset_deliveries: list[dict] = []

    def capture_reset(**kwargs) -> str:
        reset_deliveries.append(kwargs)
        return "sent"

    with SessionLocal() as db, patch.object(
        tenant_auth_service,
        "deliver_password_reset_email",
        side_effect=capture_reset,
    ):
        known = tenant_auth_service.request_password_reset(db, email=KNOWN_EMAIL)
        unknown = tenant_auth_service.request_password_reset(db, email=UNKNOWN_EMAIL)
    assert known == unknown == {"status": "accepted", "delivery_status": "accepted"}
    assert "reset_token" not in known
    assert len(reset_deliveries) == 1
    reset_url = reset_deliveries[0]["reset_url"]
    reset_token = reset_url.rsplit("token=", 1)[1]
    assert reset_token

    with SessionLocal() as db, patch.object(
        tenant_auth_service,
        "deliver_password_reset_email",
        side_effect=AuthEmailDeliveryError("sensitive mock diagnostic"),
    ):
        failed_delivery = tenant_auth_service.request_password_reset(db, email=KNOWN_EMAIL)
    assert failed_delivery == unknown

    database_bytes = DB_PATH.read_bytes()
    assert invitation_token.encode("ascii") not in database_bytes
    assert reset_token.encode("ascii") not in database_bytes
    assert b"mock-smtp-password" not in database_bytes


def main() -> None:
    verify_configuration_gate()
    verify_mocked_smtp_transport()
    administrator_id = seed_users()
    verify_production_auth_contract(administrator_id)
    print("verify_t23_auth_email_delivery: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        DB_PATH.unlink(missing_ok=True)
