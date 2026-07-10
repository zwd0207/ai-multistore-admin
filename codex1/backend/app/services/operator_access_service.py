from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.database import get_db
from app.models.auth import ErpPermission, ErpRolePermission, ErpStoreMembership, ErpUser


@dataclass(frozen=True)
class OperatorIdentity:
    user_id: int
    user_key_hash: str


def get_operator_identity(
    x_erp_user_key: str | None = Header(default=None, alias="X-ERP-User-Key"),
    db: Session = Depends(get_db),
) -> OperatorIdentity:
    # The deployment auth middleware must set this opaque key. Role/store claims are never accepted from the client.
    if not x_erp_user_key:
        raise ApiError("operator identity is required", "operator_identity_required", 403)
    user = db.scalar(select(ErpUser).where(
        ErpUser.user_key_hash == x_erp_user_key,
        ErpUser.status == "active",
    ))
    if user is None:
        raise ApiError("operator identity is not active", "operator_identity_forbidden", 403)
    return OperatorIdentity(user_id=user.id, user_key_hash=user.user_key_hash)


def require_store_permission(db: Session, *, identity: OperatorIdentity, store_id: int, permission_key: str) -> None:
    rows = db.execute(
        select(ErpStoreMembership, ErpPermission.permission_key)
        .join(ErpRolePermission, ErpRolePermission.role_id == ErpStoreMembership.role_id)
        .join(ErpPermission, ErpPermission.id == ErpRolePermission.permission_id)
        .where(
            ErpStoreMembership.user_id == identity.user_id,
            ErpStoreMembership.store_id == store_id,
            ErpStoreMembership.membership_status == "active",
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
