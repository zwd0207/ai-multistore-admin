from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.auth import ErpSession, ErpUser, ErpUserSecurity
from app.models.operation_audit_log import OperationAuditLog
from app.models.tenant import ErpMfaRecoveryCode, PasswordResetToken, Tenant, TenantInvitation
from app.services.auth_email_delivery_service import (
    AuthEmailDeliveryError,
    deliver_invitation_email,
    deliver_password_reset_email,
)
from app.services.encryption import decrypt_value, encrypt_value
from app.services.session_service import (
    _as_utc,
    _peppered_hash,
    generate_totp,
    hash_login_identifier,
    hash_password,
    verify_totp,
)


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, len(local) - len(visible))}@{domain}"


def _validate_password(value: str) -> None:
    if len(value) < 12 or not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(char.isdigit() for char in value):
        raise ApiError(
            "password must contain upper-case, lower-case, and numeric characters",
            "password_policy_failed",
            422,
        )


def _safe_invitation(invitation: TenantInvitation) -> dict:
    return {
        "id": invitation.id,
        "email": invitation.email_masked,
        "display_name": invitation.display_name,
        "tenant_name": invitation.tenant_name,
        "status": invitation.status,
        "expires_at": invitation.expires_at.isoformat(),
        "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
    }


def _invitation_url(raw_token: str) -> str:
    settings = get_settings()
    return f"{settings.public_app_url.rstrip('/')}/#/accept-invite?token={quote(raw_token)}"


def _password_reset_url(raw_token: str) -> str:
    settings = get_settings()
    return f"{settings.public_app_url.rstrip('/')}/#/reset-password?token={quote(raw_token)}"


def _deliver_invitation(*, recipient: str, raw_token: str, expires_at: datetime) -> str:
    try:
        return deliver_invitation_email(
            recipient=recipient,
            invitation_url=_invitation_url(raw_token),
            expires_at=expires_at,
        )
    except AuthEmailDeliveryError:
        return "delivery_failed"


def _deliver_password_reset(*, recipient: str, raw_token: str, expires_at: datetime) -> None:
    try:
        deliver_password_reset_email(
            recipient=recipient,
            reset_url=_password_reset_url(raw_token),
            expires_at=expires_at,
        )
    except AuthEmailDeliveryError:
        pass


def _raise_invitation_integrity_conflict(db: Session, exc: IntegrityError) -> None:
    db.rollback()
    raise ApiError(
        "an active invitation or account already exists",
        "invitation_identity_conflict",
        409,
    ) from exc


def create_invitation(
    db: Session,
    *,
    email: str,
    display_name: str,
    tenant_name: str,
    invited_by_user_id: int,
) -> dict:
    settings = get_settings()
    normalized_email = email.strip().casefold()
    email_hash = hash_login_identifier(normalized_email)
    if db.scalar(select(ErpUser.id).where(ErpUser.login_identifier_hash == email_hash)) is not None:
        raise ApiError("email is already registered", "account_already_exists", 409)
    now = get_utc_now()
    pending_invitations = db.scalars(select(TenantInvitation).where(
        TenantInvitation.email_hash == email_hash,
        TenantInvitation.status.in_(("pending", "pending_mfa")),
    )).all()
    for pending in pending_invitations:
        pending.status = "revoked"
        pending.revoked_at = now
    if pending_invitations:
        db.flush()
    raw_token = secrets.token_urlsafe(48)
    invitation = TenantInvitation(
        email_hash=email_hash,
        email_encrypted=encrypt_value(normalized_email),
        email_masked=_mask_email(normalized_email),
        display_name=display_name.strip(),
        tenant_name=tenant_name.strip(),
        token_hash=_token_hash(raw_token),
        invited_by_user_id=invited_by_user_id,
        expires_at=now + timedelta(hours=settings.auth_invitation_hours),
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError as exc:
        _raise_invitation_integrity_conflict(db, exc)
    db.refresh(invitation)
    delivery_status = _deliver_invitation(
        recipient=normalized_email,
        raw_token=raw_token,
        expires_at=invitation.expires_at,
    )
    result = {
        **_safe_invitation(invitation),
        "delivery_status": delivery_status,
    }
    if settings.app_env != "production":
        result.update({
            "invitation_token": raw_token,
            "invitation_url": _invitation_url(raw_token),
        })
    return result


def create_platform_admin_bootstrap_invitation(
    db: Session,
    *,
    email: str,
    display_name: str,
    tenant_id: int,
    commit: bool = True,
) -> dict:
    settings = get_settings()
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if tenant is None or tenant.status != "active":
        raise ApiError("bootstrap tenant is unavailable", "tenant_scope_forbidden", 403)
    if db.scalar(select(ErpUser.id).where(ErpUser.platform_role == "platform_admin")) is not None:
        raise ApiError("platform administrator already exists", "platform_admin_already_exists", 409)
    if db.scalar(select(TenantInvitation.id).where(
        TenantInvitation.invited_platform_role == "platform_admin",
        TenantInvitation.status.in_(("pending", "pending_mfa")),
    )) is not None:
        raise ApiError("platform administrator invitation already exists", "platform_admin_invitation_exists", 409)
    normalized_email = email.strip().casefold()
    email_hash = hash_login_identifier(normalized_email)
    if db.scalar(select(ErpUser.id).where(ErpUser.login_identifier_hash == email_hash)) is not None:
        raise ApiError("email is already registered", "account_already_exists", 409)
    now = get_utc_now()
    raw_token = secrets.token_urlsafe(48)
    invitation = TenantInvitation(
        email_hash=email_hash,
        email_encrypted=encrypt_value(normalized_email),
        email_masked=_mask_email(normalized_email),
        display_name=display_name.strip(),
        tenant_name=tenant.name,
        target_tenant_id=tenant.id,
        invited_platform_role="platform_admin",
        token_hash=_token_hash(raw_token),
        invited_by_user_id=None,
        expires_at=now + timedelta(hours=settings.auth_invitation_hours),
    )
    db.add(invitation)
    try:
        db.flush()
    except IntegrityError as exc:
        _raise_invitation_integrity_conflict(db, exc)
    correlation_id = f"platform-admin-bootstrap-{uuid.uuid4().hex}"
    db.add(OperationAuditLog(
        created_at=now,
        updated_at=now,
        environment=settings.app_env,
        actor_type="system",
        actor_id="platform-admin-bootstrap-cli",
        actor_role="bootstrap",
        action="platform_admin_invitation_created",
        operation_phase="tenant_bootstrap",
        correlation_id=correlation_id,
        request_id=correlation_id,
        status="success",
        reason_code="initial_platform_admin_required",
        target_type="tenant",
        target_id=tenant.id,
        changed_field_names=["tenant_invitations"],
        counts_summary={"invitations_created": 1},
        safety_flags={"platform_write": False, "secrets_recorded": False},
        sensitive_scan_passed=True,
        raw_response_saved=False,
        secrets_saved=False,
        privacy_fields_redacted=True,
        notes="Initial platform administrator invitation created without storing its token in audit data.",
    ))
    if commit:
        db.commit()
        db.refresh(invitation)
    else:
        db.flush()
    return {
        **_safe_invitation(invitation),
        "invitation_token": raw_token,
        "invitation_url": _invitation_url(raw_token),
        "target_tenant_id": tenant.id,
        "platform_role": "platform_admin",
    }


def accept_invitation(db: Session, *, token: str, password: str) -> dict:
    _validate_password(password)
    now = get_utc_now()
    invitation = db.scalar(
        select(TenantInvitation).where(TenantInvitation.token_hash == _token_hash(token)).with_for_update()
    )
    if invitation is None or invitation.status != "pending":
        raise ApiError("invitation is unavailable", "invitation_invalid", 404)
    if _as_utc(invitation.expires_at) <= now:
        invitation.status = "expired"
        db.commit()
        raise ApiError("invitation has expired", "invitation_expired", 410)
    if db.scalar(select(ErpUser.id).where(ErpUser.login_identifier_hash == invitation.email_hash)) is not None:
        raise ApiError("email is already registered", "account_already_exists", 409)

    if invitation.invited_platform_role == "platform_admin":
        tenant = db.scalar(
            select(Tenant).where(Tenant.id == invitation.target_tenant_id).with_for_update()
        ) if invitation.target_tenant_id else None
        if tenant is None or tenant.status != "active":
            raise ApiError("invitation is unavailable", "invitation_invalid", 404)
        if db.scalar(select(ErpUser.id).where(ErpUser.platform_role == "platform_admin")) is not None:
            raise ApiError("platform administrator already exists", "platform_admin_already_exists", 409)
    else:
        tenant = Tenant(tenant_key=uuid.uuid4().hex, name=invitation.tenant_name, status="active")
    email = decrypt_value(invitation.email_encrypted)
    mfa_secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    user = ErpUser(
        tenant=tenant,
        user_key_hash=hashlib.sha256(secrets.token_bytes(48)).hexdigest(),
        display_name=invitation.display_name,
        login_identifier_hash=invitation.email_hash,
        login_identifier_masked=invitation.email_masked,
        email_encrypted=invitation.email_encrypted,
        email_verified_at=now,
        platform_role=invitation.invited_platform_role,
        status="invited",
        auth_provider="local_pending",
    )
    security = ErpUserSecurity(
        user=user,
        password_hash=hash_password(password),
        mfa_type="totp",
        mfa_secret_encrypted=encrypt_value(mfa_secret),
        password_changed_at=now,
    )
    enrollment_token = secrets.token_urlsafe(48)
    db.add_all((tenant, user, security))
    try:
        db.flush()
        invitation.accepted_user_id = user.id
        invitation.status = "pending_mfa"
        invitation.mfa_enrollment_token_hash = _token_hash(enrollment_token)
        invitation.mfa_enrollment_expires_at = now + timedelta(minutes=15)
        db.commit()
    except IntegrityError as exc:
        _raise_invitation_integrity_conflict(db, exc)
    return {
        "status": "mfa_enrollment_required",
        "email": invitation.email_masked,
        "tenant": {"id": tenant.id, "name": tenant.name},
        "enrollment_token": enrollment_token,
        "mfa_secret": mfa_secret,
        "otpauth_uri": (
            f"otpauth://totp/AIGLXT:{quote(email or invitation.email_masked)}"
            f"?secret={mfa_secret}&issuer=AIGLXT&digits=6&period=30"
        ),
        "enrollment_expires_at": invitation.mfa_enrollment_expires_at.isoformat(),
    }


def complete_mfa_enrollment(db: Session, *, enrollment_token: str, code: str) -> dict:
    now = get_utc_now()
    invitation = db.scalar(select(TenantInvitation).where(
        TenantInvitation.mfa_enrollment_token_hash == _token_hash(enrollment_token),
    ).with_for_update())
    if invitation is None or invitation.status != "pending_mfa" or invitation.accepted_user_id is None:
        raise ApiError("MFA enrollment is unavailable", "mfa_enrollment_invalid", 404)
    if invitation.mfa_enrollment_expires_at is None or _as_utc(invitation.mfa_enrollment_expires_at) <= now:
        raise ApiError("MFA enrollment has expired", "mfa_enrollment_expired", 410)
    user = db.get(ErpUser, invitation.accepted_user_id)
    security = db.get(ErpUserSecurity, invitation.accepted_user_id)
    if user is None or security is None or not security.mfa_secret_encrypted:
        raise ApiError("MFA enrollment is unavailable", "mfa_enrollment_invalid", 404)
    secret = decrypt_value(security.mfa_secret_encrypted)
    if not secret or not verify_totp(secret, code):
        raise ApiError("MFA verification failed", "mfa_invalid", 403)

    recovery_codes = [
        "-".join((secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2))).upper()
        for _ in range(10)
    ]
    db.add_all(ErpMfaRecoveryCode(
        user_id=user.id,
        code_hash=_peppered_hash(recovery_code.replace("-", "")),
    ) for recovery_code in recovery_codes)
    user.status = "active"
    user.auth_provider = "password"
    security.mfa_enabled_at = now
    security.authz_version += 1
    invitation.status = "accepted"
    invitation.accepted_at = now
    invitation.mfa_enrollment_token_hash = None
    invitation.mfa_enrollment_expires_at = None
    db.commit()
    return {
        "status": "account_active",
        "user": {"id": user.id, "display_name": user.display_name},
        "tenant_id": user.tenant_id,
        "recovery_codes": recovery_codes,
    }


def request_password_reset(db: Session, *, email: str) -> dict:
    settings = get_settings()
    normalized_email = email.strip().casefold()
    user = db.scalar(select(ErpUser).where(
        ErpUser.login_identifier_hash == hash_login_identifier(normalized_email),
        ErpUser.status == "active",
    ))
    raw_token = None
    if user is not None:
        now = get_utc_now()
        for old in db.scalars(select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )).all():
            old.used_at = now
        raw_token = secrets.token_urlsafe(48)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
        )
        db.add(reset)
        db.commit()
        _deliver_password_reset(
            recipient=normalized_email,
            raw_token=raw_token,
            expires_at=reset.expires_at,
        )
    result = {
        "status": "accepted",
        "delivery_status": "accepted" if settings.email_delivery_enabled else "email_delivery_disabled",
    }
    if settings.app_env != "production" and raw_token:
        result["reset_token"] = raw_token
    return result


def complete_password_reset(db: Session, *, token: str, password: str) -> dict:
    _validate_password(password)
    now = get_utc_now()
    reset = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == _token_hash(token),
    ).with_for_update())
    if reset is None or reset.used_at is not None or _as_utc(reset.expires_at) <= now:
        raise ApiError("password reset is unavailable", "password_reset_invalid", 404)
    user = db.get(ErpUser, reset.user_id)
    security = db.get(ErpUserSecurity, reset.user_id)
    if user is None or security is None or user.status != "active":
        raise ApiError("password reset is unavailable", "password_reset_invalid", 404)
    security.password_hash = hash_password(password)
    security.password_changed_at = now
    security.session_version += 1
    reset.used_at = now
    for session in db.scalars(select(ErpSession).where(
        ErpSession.user_id == user.id,
        ErpSession.revoked_at.is_(None),
    )).all():
        session.revoked_at = now
        session.revoke_reason = "password_reset"
    db.commit()
    return {"status": "password_reset"}
