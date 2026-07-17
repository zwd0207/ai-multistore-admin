from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email

from app.config import Settings, get_settings


class AuthEmailDeliveryError(RuntimeError):
    pass


def _validated_address(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise AuthEmailDeliveryError("authentication email delivery failed")
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        raise AuthEmailDeliveryError("authentication email delivery failed") from None


def _validate_action_url(action_url: str, settings: Settings) -> None:
    expected = urlsplit(settings.public_app_url)
    actual = urlsplit(action_url)
    if (
        expected.scheme != "https"
        or actual.scheme != "https"
        or not expected.netloc
        or actual.netloc != expected.netloc
        or actual.username is not None
        or actual.password is not None
    ):
        raise AuthEmailDeliveryError("authentication email delivery failed")


def _build_message(*, recipient: str, subject: str, body: str, settings: Settings) -> EmailMessage:
    if "\r" in subject or "\n" in subject:
        raise AuthEmailDeliveryError("authentication email delivery failed")
    sender = _validated_address(settings.auth_email_from_address or "")
    target = _validated_address(recipient)
    message = EmailMessage()
    message["From"] = formataddr((settings.auth_email_from_name, sender))
    message["To"] = target
    message["Subject"] = subject
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    message.set_content(body)
    return message


def _send(message: EmailMessage, *, recipient: str, settings: Settings) -> None:
    password = settings.auth_email_smtp_password
    if password is None:
        raise AuthEmailDeliveryError("authentication email delivery failed")
    context = ssl.create_default_context()
    try:
        if settings.auth_email_smtp_security == "ssl":
            client_context = smtplib.SMTP_SSL(
                settings.auth_email_smtp_host,
                settings.auth_email_smtp_port,
                timeout=settings.auth_email_smtp_timeout_seconds,
                context=context,
            )
        else:
            client_context = smtplib.SMTP(
                settings.auth_email_smtp_host,
                settings.auth_email_smtp_port,
                timeout=settings.auth_email_smtp_timeout_seconds,
            )
        with client_context as client:
            if settings.auth_email_smtp_security == "starttls":
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            client.login(
                settings.auth_email_smtp_username or "",
                password.get_secret_value(),
            )
            refused = client.send_message(
                message,
                from_addr=settings.auth_email_from_address,
                to_addrs=[str(recipient)],
            )
            if refused:
                raise AuthEmailDeliveryError("authentication email delivery failed")
    except AuthEmailDeliveryError:
        raise
    except Exception:
        raise AuthEmailDeliveryError("authentication email delivery failed") from None


def _deliver(
    *,
    recipient: str,
    action_url: str,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> str:
    runtime_settings = settings or get_settings()
    if not runtime_settings.email_delivery_enabled:
        return "email_delivery_disabled"
    _validate_action_url(action_url, runtime_settings)
    message = _build_message(
        recipient=recipient,
        subject=subject,
        body=body,
        settings=runtime_settings,
    )
    _send(message, recipient=str(message["To"]), settings=runtime_settings)
    return "sent"


def deliver_invitation_email(
    *,
    recipient: str,
    invitation_url: str,
    expires_at: datetime,
    settings: Settings | None = None,
) -> str:
    return _deliver(
        recipient=recipient,
        action_url=invitation_url,
        subject="Your AIGLXT invitation",
        body=(
            "An administrator invited you to AIGLXT.\n\n"
            f"Accept the invitation: {invitation_url}\n\n"
            f"This invitation expires at {expires_at.isoformat()}.\n"
            "If you did not expect this invitation, ignore this email.\n"
        ),
        settings=settings,
    )


def deliver_password_reset_email(
    *,
    recipient: str,
    reset_url: str,
    expires_at: datetime,
    settings: Settings | None = None,
) -> str:
    return _deliver(
        recipient=recipient,
        action_url=reset_url,
        subject="Reset your AIGLXT password",
        body=(
            "A password reset was requested for your AIGLXT account.\n\n"
            f"Reset your password: {reset_url}\n\n"
            f"This link expires at {expires_at.isoformat()}.\n"
            "If you did not request a reset, ignore this email.\n"
        ),
        settings=settings,
    )
