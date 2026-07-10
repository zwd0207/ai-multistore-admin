from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.database import get_db
from app.config import get_settings
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser
from app.models.store import Store
from app.services.session_service import AuthenticatedPrincipal, require_csrf, require_recent_auth, require_session


@dataclass(frozen=True)
class OperatorIdentity:
    user_id: int
    user_key_hash: str
    session_id: str | None = None
    last_reauthenticated_at: object | None = None
    is_development_identity: bool = False


def get_operator_identity(
    request: Request,
    x_erp_user_key: str | None = Header(default=None, alias="X-ERP-User-Key"),
    db: Session = Depends(get_db),
) -> OperatorIdentity:
    settings = get_settings()
    if x_erp_user_key:
        if settings.app_env != "development" or not settings.allow_dev_auth:
            raise ApiError("development identity is disabled", "session_required", 401)
        user = db.scalar(select(ErpUser).where(ErpUser.user_key_hash == x_erp_user_key, ErpUser.status == "active"))
        if user is None:
            raise ApiError("operator identity is not active", "operator_identity_forbidden", 403)
        return OperatorIdentity(user_id=user.id, user_key_hash=user.user_key_hash, is_development_identity=True)
    principal: AuthenticatedPrincipal = require_session(request, db)
    require_csrf(request, db, principal)
    return OperatorIdentity(
        user_id=principal.user_id,
        user_key_hash=principal.user_key_hash,
        session_id=principal.session_id,
        last_reauthenticated_at=principal.last_reauthenticated_at,
    )


def require_operator_recent_auth(identity: OperatorIdentity) -> None:
    if identity.is_development_identity:
        return
    require_recent_auth(AuthenticatedPrincipal(
        session_id=identity.session_id or "",
        user_id=identity.user_id,
        user_key_hash=identity.user_key_hash,
        display_name="",
        authn_level="mfa_verified",
        last_reauthenticated_at=identity.last_reauthenticated_at,
    ))


def require_store_permission(db: Session, *, identity: OperatorIdentity, store_id: int, permission_key: str) -> None:
    rows = db.execute(
        select(ErpStoreMembership, ErpPermission.permission_key)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(ErpRolePermission, ErpRolePermission.role_id == ErpStoreMembership.role_id)
        .join(ErpPermission, ErpPermission.id == ErpRolePermission.permission_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == identity.user_id,
            ErpStoreMembership.store_id == store_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
            ErpPermission.status == "active",
        )
    ).all()
    if not rows:
        raise ApiError("store is outside assigned scope", "recipient_pii_store_scope_forbidden", 403)
    granted = {key for _membership, key in rows}
    if permission_key not in granted and "*" not in granted:
        code = "shipping_writeback_approval_forbidden" if permission_key == "shipping.writeback.approve" else f"{permission_key.replace('.', '_')}_forbidden"
        raise ApiError("operator does not have this permission", code, 403)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
