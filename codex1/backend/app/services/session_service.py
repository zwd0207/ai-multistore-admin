from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import struct
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpSession, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.store import Store
from app.services.encryption import decrypt_value


PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_MFA_CODE_LOGIN_IDENTIFIER = "pxg-config-admin@local.test"
LOCAL_MFA_CODE_ROLE_KEY = "pxg_connection_config_admin"
LOCAL_MFA_CODE_LEGACY_LOGIN_IDENTIFIER = "pxg-trial-operator@local.test"
LOCAL_MFA_CODE_LEGACY_ROLE_KEY = "pxg_naver_trial_operator"
LOCAL_MFA_CODE_STORE_NAME = "pxg球包店"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    session_id: str
    user_id: int
    user_key_hash: str
    display_name: str
    authn_level: str
    last_reauthenticated_at: datetime | None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _peppered_hash(value: str) -> str:
    pepper = get_settings().session_token_pepper
    if not pepper or len(pepper) < 32:
        raise ApiError("session security is not configured", "session_security_not_configured", 500)
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_login_identifier(value: str) -> str:
    normalized = value.strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_password(value: str) -> str:
    return PASSWORD_HASHER.hash(value)


def verify_password(password_hash: str | None, value: str) -> bool:
    if not password_hash:
        return False
    try:
        return PASSWORD_HASHER.verify(password_hash, value)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_totp(secret: str, *, timestamp: int | None = None) -> str:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding)
    counter = int(timestamp if timestamp is not None else time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify_totp(secret: str, code: str) -> bool:
    now = int(time.time())
    return any(hmac.compare_digest(generate_totp(secret, timestamp=now + offset * 30), code) for offset in (-1, 0, 1))


def _has_active_membership(db: Session, user_id: int) -> bool:
    return db.scalar(
        select(ErpStoreMembership.id)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == user_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
        )
        .limit(1)
    ) is not None


def _create_session(db: Session, *, user: ErpUser, security: ErpUserSecurity, authn_level: str) -> tuple[ErpSession, str, str | None]:
    settings = get_settings()
    now = get_utc_now()
    token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32) if authn_level == "mfa_verified" else None
    if authn_level == "mfa_pending":
        absolute_expires_at = now + timedelta(minutes=settings.session_mfa_pending_minutes)
        idle_expires_at = absolute_expires_at
        last_reauthenticated_at = None
    else:
        absolute_expires_at = now + timedelta(hours=settings.session_absolute_hours)
        idle_expires_at = now + timedelta(minutes=settings.session_idle_minutes)
        last_reauthenticated_at = now
    session = ErpSession(
        id=uuid.uuid4().hex,
        session_token_hash=_peppered_hash(token),
        user_id=user.id,
        environment=settings.app_env,
        authn_level=authn_level,
        session_version=security.session_version,
        authz_version_at_issue=security.authz_version,
        csrf_token_hash=_peppered_hash(csrf_token) if csrf_token else None,
        created_at=now,
        last_seen_at=now,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
        last_reauthenticated_at=last_reauthenticated_at,
    )
    db.add(session)
    return session, token, csrf_token


def begin_login(db: Session, *, login_identifier: str, password: str) -> tuple[dict, str]:
    login_hash = hash_login_identifier(login_identifier)
    user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash == login_hash))
    security = db.get(ErpUserSecurity, user.id) if user else None
    now = get_utc_now()
    blocked = security and security.blocked_until and _as_utc(security.blocked_until) > now
    valid = bool(
        user
        and security
        and user.status == "active"
        and user.auth_provider == "password"
        and not blocked
        and verify_password(security.password_hash, password)
        and security.mfa_enabled_at
        and security.mfa_secret_encrypted
        and _has_active_membership(db, user.id)
    )
    if not valid:
        if security and not blocked:
            security.failed_login_count += 1
            if security.failed_login_count >= 10:
                security.blocked_until = now + timedelta(minutes=15)
            db.commit()
        raise ApiError("invalid credentials", "invalid_credentials", 401)
    security.failed_login_count = 0
    security.blocked_until = None
    pending, token, _csrf = _create_session(db, user=user, security=security, authn_level="mfa_pending")
    db.commit()
    return {
        "status": "mfa_required",
        "mfa_session_expires_at": pending.absolute_expires_at,
    }, token


def _session_from_token(db: Session, token: str | None) -> ErpSession | None:
    if not token:
        return None
    return db.scalar(select(ErpSession).where(
        ErpSession.session_token_hash == _peppered_hash(token),
        ErpSession.environment == get_settings().app_env,
    ))


def is_loopback_socket_peer(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return False


def local_mfa_code_display(db: Session, *, pending_token: str | None) -> dict[str, int | str] | None:
    """Return a local test code only for the isolated configuration-admin MFA step."""
    settings = get_settings()
    if not settings.local_mfa_code_display_enabled or settings.app_env != "test":
        return None
    pending = _session_from_token(db, pending_token)
    now = get_utc_now()
    if (
        pending is None
        or pending.revoked_at is not None
        or pending.authn_level != "mfa_pending"
        or _as_utc(pending.idle_expires_at) <= now
        or _as_utc(pending.absolute_expires_at) <= now
    ):
        return None
    user = db.get(ErpUser, pending.user_id)
    security = db.get(ErpUserSecurity, pending.user_id)
    expected_role_by_login_hash = {
        hash_login_identifier(LOCAL_MFA_CODE_LOGIN_IDENTIFIER): LOCAL_MFA_CODE_ROLE_KEY,
        hash_login_identifier(LOCAL_MFA_CODE_LEGACY_LOGIN_IDENTIFIER): LOCAL_MFA_CODE_LEGACY_ROLE_KEY,
    }
    expected_role_key = expected_role_by_login_hash.get(user.login_identifier_hash) if user else None
    if (
        user is None
        or security is None
        or user.status != "active"
        or user.auth_provider != "password"
        or expected_role_key is None
        or not security.password_hash
        or security.mfa_type != "totp"
        or security.mfa_enabled_at is None
        or not security.mfa_secret_encrypted
        or pending.session_version != security.session_version
        or pending.authz_version_at_issue != security.authz_version
    ):
        return None
    has_required_membership = db.scalar(
        select(ErpStoreMembership.id)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == user.id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.role_key == expected_role_key,
            ErpRole.status == "active",
            Store.name == LOCAL_MFA_CODE_STORE_NAME,
            Store.platform == "naver",
            Store.status == "active",
        )
        .limit(1)
    ) is not None
    if not has_required_membership:
        return None
    try:
        secret = decrypt_value(security.mfa_secret_encrypted)
        if not secret:
            return None
        timestamp = int(time.time())
        return {
            "code": generate_totp(secret, timestamp=timestamp),
            "seconds_remaining": 30 - timestamp % 30,
        }
    except Exception:
        return None


def complete_mfa(db: Session, *, pending_token: str | None, code: str) -> tuple[dict, str, str]:
    pending = _session_from_token(db, pending_token)
    now = get_utc_now()
    if pending is None or pending.revoked_at is not None or pending.authn_level != "mfa_pending":
        raise ApiError("MFA session is required", "session_required", 401)
    if _as_utc(pending.absolute_expires_at) <= now:
        pending.revoked_at = now
        pending.revoke_reason = "mfa_session_expired"
        db.commit()
        raise ApiError("MFA session expired", "session_expired", 401)
    user = db.get(ErpUser, pending.user_id)
    security = db.get(ErpUserSecurity, pending.user_id)
    if user is None or security is None or user.status != "active" or not security.mfa_secret_encrypted:
        raise ApiError("MFA verification failed", "mfa_required", 403)
    secret = decrypt_value(security.mfa_secret_encrypted)
    if not secret or not verify_totp(secret, code.strip()):
        raise ApiError("MFA verification failed", "mfa_invalid", 403)
    pending.revoked_at = now
    pending.revoke_reason = "mfa_completed"
    verified, token, csrf_token = _create_session(db, user=user, security=security, authn_level="mfa_verified")
    active_sessions = db.scalars(
        select(ErpSession).where(
            ErpSession.user_id == user.id,
            ErpSession.authn_level == "mfa_verified",
            ErpSession.revoked_at.is_(None),
            ErpSession.id != verified.id,
        ).order_by(ErpSession.created_at.asc())
    ).all()
    for old_session in active_sessions[:-2]:
        old_session.revoked_at = now
        old_session.revoke_reason = "concurrent_session_limit"
    user.last_login_at = now
    db.commit()
    return {
        "status": "authenticated",
        "user": {"id": user.id, "display_name": user.display_name},
        "csrf_token": csrf_token,
        "absolute_expires_at": verified.absolute_expires_at,
    }, token, csrf_token or ""


def require_session(request: Request, db: Session, *, require_mfa: bool = True) -> AuthenticatedPrincipal:
    settings = get_settings()
    session = _session_from_token(db, request.cookies.get(settings.session_cookie_name))
    if session is None:
        raise ApiError("login session is required", "session_required", 401)
    now = get_utc_now()
    if session.revoked_at is not None:
        raise ApiError("login session was revoked", "session_revoked", 401)
    if _as_utc(session.idle_expires_at) <= now or _as_utc(session.absolute_expires_at) <= now:
        session.revoked_at = now
        session.revoke_reason = "session_expired"
        db.commit()
        raise ApiError("login session expired", "session_expired", 401)
    user = db.get(ErpUser, session.user_id)
    security = db.get(ErpUserSecurity, session.user_id)
    if (
        user is None
        or security is None
        or user.status != "active"
        or session.session_version != security.session_version
        or session.authz_version_at_issue != security.authz_version
    ):
        session.revoked_at = now
        session.revoke_reason = "identity_or_authorization_changed"
        db.commit()
        raise ApiError("login session was revoked", "session_revoked", 401)
    if require_mfa and session.authn_level != "mfa_verified":
        raise ApiError("MFA verification is required", "mfa_required", 403)
    if (now - _as_utc(session.last_seen_at)).total_seconds() >= 60:
        session.last_seen_at = now
        session.idle_expires_at = min(
            now + timedelta(minutes=settings.session_idle_minutes),
            _as_utc(session.absolute_expires_at),
        )
        db.commit()
    return AuthenticatedPrincipal(
        session_id=session.id,
        user_id=user.id,
        user_key_hash=user.user_key_hash,
        display_name=user.display_name,
        authn_level=session.authn_level,
        last_reauthenticated_at=session.last_reauthenticated_at,
    )


def require_csrf(request: Request, db: Session, principal: AuthenticatedPrincipal) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return
    settings = get_settings()
    origin = request.headers.get("Origin")
    if not origin or origin not in settings.cors_allowed_origins:
        raise ApiError("CSRF origin validation failed", "csrf_validation_failed", 403)
    token = request.headers.get("X-CSRF-Token")
    session = db.get(ErpSession, principal.session_id)
    if not token or session is None or not session.csrf_token_hash or not hmac.compare_digest(session.csrf_token_hash, _peppered_hash(token)):
        raise ApiError("CSRF token validation failed", "csrf_validation_failed", 403)


def require_recent_auth(principal: AuthenticatedPrincipal) -> None:
    if principal.last_reauthenticated_at is None:
        raise ApiError("recent authentication is required", "reauthentication_required", 401)
    cutoff = get_utc_now() - timedelta(minutes=get_settings().session_recent_auth_minutes)
    if _as_utc(principal.last_reauthenticated_at) < cutoff:
        raise ApiError("recent authentication is required", "reauthentication_required", 401)


def revoke_session(db: Session, *, token: str | None) -> None:
    session = _session_from_token(db, token)
    if session and session.revoked_at is None:
        session.revoked_at = get_utc_now()
        session.revoke_reason = "logout"
        db.commit()


def rotate_csrf_token(db: Session, principal: AuthenticatedPrincipal) -> str:
    session = db.get(ErpSession, principal.session_id)
    if session is None or session.revoked_at is not None:
        raise ApiError("login session is required", "session_required", 401)
    token = secrets.token_urlsafe(32)
    session.csrf_token_hash = _peppered_hash(token)
    db.commit()
    return token


def session_summary(db: Session, principal: AuthenticatedPrincipal) -> dict:
    rows = db.execute(
        select(ErpStoreMembership, ErpRole)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == principal.user_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
        )
    ).all()
    stores = []
    for membership, role in rows:
        permissions = db.scalars(
            select(ErpPermission.permission_key)
            .join(ErpRolePermission, ErpRolePermission.permission_id == ErpPermission.id)
            .where(
                ErpRolePermission.role_id == role.id,
                ErpPermission.status == "active",
            )
        ).all()
        stores.append({
            "store_id": membership.store_id,
            "role": role.role_key,
            "permissions": sorted(set(permissions)),
        })
    return {
        "user": {"id": principal.user_id, "display_name": principal.display_name},
        "authn_level": principal.authn_level,
        "stores": stores,
    }
