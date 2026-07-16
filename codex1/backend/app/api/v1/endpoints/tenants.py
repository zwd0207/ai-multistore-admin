from dataclasses import replace

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.models.auth import ErpSession, ErpUser
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.operator_access_service import (
    OperatorIdentity,
    audit_platform_admin_tenant_access,
    get_operator_identity,
    require_operator_recent_auth,
    require_platform_admin,
)


router = APIRouter(prefix="/admin/tenants", tags=["tenants"])


def _active_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status != "active":
        raise ApiError("tenant is unavailable", "tenant_scope_forbidden", 403)
    return tenant


@router.get("")
def list_tenants(
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_platform_admin(identity)
    tenants = db.scalars(select(Tenant).order_by(Tenant.id.asc())).all()
    items = []
    for tenant in tenants:
        user_count = db.scalar(select(func.count()).select_from(ErpUser).where(ErpUser.tenant_id == tenant.id)) or 0
        store_count = db.scalar(select(func.count()).select_from(Store).where(Store.tenant_id == tenant.id)) or 0
        items.append({
            "id": tenant.id,
            "tenant_key": tenant.tenant_key,
            "name": tenant.name,
            "status": tenant.status,
            "user_count": user_count,
            "store_count": store_count,
            "created_at": tenant.created_at.isoformat(),
        })
    return success_response(data={"items": items, "total": len(items)})


@router.post("/{tenant_id}/select")
def select_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_platform_admin(identity)
    require_operator_recent_auth(identity)
    tenant = _active_tenant(db, tenant_id)
    session = db.get(ErpSession, identity.session_id) if identity.session_id else None
    if session is None or session.revoked_at is not None:
        raise ApiError("login session is required", "session_required", 401)
    session.selected_tenant_id = tenant.id
    db.commit()
    scoped_identity = replace(identity, selected_tenant_id=tenant.id)
    audit_platform_admin_tenant_access(
        db,
        identity=scoped_identity,
        operation="tenant_selected",
    )
    return success_response(data={
        "selected_tenant": {"id": tenant.id, "name": tenant.name, "status": tenant.status},
        "cross_tenant_mode": tenant.id != identity.tenant_id,
    }, message="tenant selected")


@router.delete("/selection")
def clear_tenant_selection(
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_platform_admin(identity)
    require_operator_recent_auth(identity)
    session = db.get(ErpSession, identity.session_id) if identity.session_id else None
    if session is None or session.revoked_at is not None:
        raise ApiError("login session is required", "session_required", 401)
    audit_platform_admin_tenant_access(
        db,
        identity=identity,
        operation="tenant_selection_cleared",
    )
    session.selected_tenant_id = identity.tenant_id
    db.commit()
    return success_response(data={
        "selected_tenant_id": identity.tenant_id,
        "cross_tenant_mode": False,
    }, message="tenant selection cleared")
