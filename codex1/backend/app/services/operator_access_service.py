from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.database import get_db
from app.config import get_settings
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser
from app.models.store import Store
from app.models.tenant import Tenant
from app.core.timezone import get_utc_now
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.session_service import AuthenticatedPrincipal, require_csrf, require_recent_auth, require_session


@dataclass(frozen=True)
class OperatorIdentity:
    user_id: int
    user_key_hash: str
    session_id: str | None = None
    last_reauthenticated_at: object | None = None
    is_development_identity: bool = False
    tenant_id: int | None = None
    platform_role: str = "tenant_owner"
    selected_tenant_id: int | None = None


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
        return OperatorIdentity(
            user_id=user.id,
            user_key_hash=user.user_key_hash,
            is_development_identity=True,
            tenant_id=user.tenant_id,
            platform_role=user.platform_role,
            selected_tenant_id=user.tenant_id,
        )
    principal: AuthenticatedPrincipal = require_session(request, db)
    require_csrf(request, db, principal)
    return OperatorIdentity(
        user_id=principal.user_id,
        user_key_hash=principal.user_key_hash,
        session_id=principal.session_id,
        last_reauthenticated_at=principal.last_reauthenticated_at,
        tenant_id=principal.tenant_id,
        platform_role=principal.platform_role,
        selected_tenant_id=principal.selected_tenant_id,
    )


def require_session_backed_identity(identity: OperatorIdentity) -> None:
    if identity.is_development_identity:
        raise ApiError(
            "verified login session is required for this operation",
            "session_backed_identity_required",
            403,
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
        tenant_id=identity.tenant_id,
        platform_role=identity.platform_role,
        selected_tenant_id=identity.selected_tenant_id,
    ))


def require_selected_tenant(db: Session, identity: OperatorIdentity) -> Tenant:
    tenant_id = identity.selected_tenant_id if identity.platform_role == "platform_admin" else identity.tenant_id
    if tenant_id is None:
        raise ApiError("select a tenant before accessing business data", "tenant_selection_required", 409)
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status != "active":
        raise ApiError("selected tenant is unavailable", "tenant_scope_forbidden", 403)
    return tenant


def _require_platform_admin_store_scope(identity: OperatorIdentity, store: Store) -> None:
    if identity.selected_tenant_id is None:
        raise ApiError("select a tenant before accessing business data", "tenant_selection_required", 409)
    if store.tenant_id != identity.selected_tenant_id:
        raise ApiError("store is outside selected tenant scope", "tenant_scope_forbidden", 403)


def audit_platform_admin_tenant_access(
    db: Session,
    *,
    identity: OperatorIdentity,
    operation: str,
    store_id: int | None = None,
) -> None:
    if (
        identity.platform_role != "platform_admin"
        or identity.selected_tenant_id is None
        or identity.selected_tenant_id == identity.tenant_id
    ):
        return
    now = get_utc_now()
    correlation_id = f"tenant-admin-{uuid.uuid4().hex}"
    result = write_operation_audit_log_local(
        db,
        {
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "environment": get_settings().app_env,
            "actor_type": "human",
            "actor_id": str(identity.user_id),
            "actor_role": "platform_admin",
            "action": "platform_admin_cross_tenant_access",
            "operation_phase": operation,
            "correlation_id": correlation_id,
            "request_id": correlation_id,
            "status": "success",
            "reason_code": "explicit_tenant_scope_authorized",
            "target_type": "tenant",
            "target_id": identity.selected_tenant_id,
            "changed_field_names": [],
            "counts_summary": {"stores_targeted": 1 if store_id is not None else 0},
            "safety_flags": {
                "cross_tenant_admin": True,
                "explicit_tenant_selection": True,
                "platform_write": False,
            },
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Authorized platform administrator access; no credentials or business payload recorded.",
        },
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )
    if result.get("status") != "audit_row_written":
        raise ApiError("cross-tenant audit is unavailable", "cross_tenant_audit_required", 503)


def require_store_permission(db: Session, *, identity: OperatorIdentity, store_id: int, permission_key: str) -> None:
    store = db.get(Store, store_id)
    if store is None or store.status != "active":
        raise ApiError("store is outside assigned scope", "store_scope_forbidden", 403)
    if identity.platform_role == "platform_admin":
        _require_platform_admin_store_scope(identity, store)
        return
    if identity.tenant_id is not None and store.tenant_id != identity.tenant_id:
        raise ApiError("store is outside tenant scope", "tenant_scope_forbidden", 403)
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


def require_store_membership(db: Session, *, identity: OperatorIdentity, store_id: int) -> None:
    store = db.get(Store, store_id)
    if store is None or store.status != "active":
        raise ApiError("store is outside assigned scope", "store_scope_forbidden", 403)
    if identity.platform_role == "platform_admin":
        _require_platform_admin_store_scope(identity, store)
        return
    if identity.tenant_id is not None and store.tenant_id != identity.tenant_id:
        raise ApiError("store is outside tenant scope", "tenant_scope_forbidden", 403)
    membership = db.scalar(
        select(ErpStoreMembership.id)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == identity.user_id,
            ErpStoreMembership.store_id == store_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
        )
        .limit(1)
    )
    if membership is None:
        raise ApiError("store is outside assigned scope", "store_scope_forbidden", 403)


def require_any_store_permission(db: Session, *, identity: OperatorIdentity, permission_key: str) -> None:
    if identity.platform_role == "platform_admin":
        require_selected_tenant(db, identity)
        return
    if identity.tenant_id is not None and permission_key in {"store.manage", "credentials.manage"}:
        tenant = db.get(Tenant, identity.tenant_id)
        if tenant is not None and tenant.status == "active":
            return
    statement = (
        select(ErpPermission.permission_key)
        .select_from(ErpStoreMembership)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(ErpRolePermission, ErpRolePermission.role_id == ErpStoreMembership.role_id)
        .join(ErpPermission, ErpPermission.id == ErpRolePermission.permission_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.user_id == identity.user_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
            ErpPermission.status == "active",
        )
    )
    if identity.tenant_id is not None:
        statement = statement.where(Store.tenant_id == identity.tenant_id)
    granted = db.scalars(statement).all()
    if permission_key not in granted and "*" not in granted:
        raise ApiError("operator does not have this permission", f"{permission_key.replace('.', '_')}_forbidden", 403)


def require_platform_admin(identity: OperatorIdentity) -> None:
    if identity.platform_role != "platform_admin":
        raise ApiError("platform administrator permission is required", "platform_admin_forbidden", 403)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
