from __future__ import annotations

import hashlib

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.auth import (
    ErpPermission,
    ErpRole,
    ErpRolePermission,
    ErpStoreMembership,
    ErpUser,
    ErpUserSecurity,
)
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.store import Store
from app.services.encryption import encrypt_value
from app.services.order_service import TEST_ORDER_SOURCE_TYPES
from app.services.session_service import hash_login_identifier, hash_password


TRIAL_STORE_NAME = "pxg球包店"
TRIAL_PLATFORM = "naver"
TRIAL_ROLE_KEY = "pxg_naver_trial_operator"
TRIAL_PERMISSION_KEYS = {
    "dashboard.read",
    "products.read",
    "orders.read",
    "orders.preview",
    "recipient_pii.view",
    "recipient_pii.export",
    "shipping.batch.manage",
    "platform.sync",
}
FORBIDDEN_TRIAL_PERMISSION_KEYS = {"*", "system.configure", "shipping.writeback.approve", "customer.inquiries.reply"}
DISABLED_TRIAL_WRITE_PATHS = {
    "/api/v1/shipping/shipment-writeback/execute",
    "/api/v1/sync/customer-inquiries/naver/reply",
}


def resolve_trial_store(db: Session) -> Store:
    stores = db.scalars(select(Store).where(
        Store.name == TRIAL_STORE_NAME,
        func.lower(Store.platform) == TRIAL_PLATFORM,
    )).all()
    if len(stores) != 1:
        raise ApiError(
            "trial store must match exactly once by name and platform",
            "trial_store_not_unique",
            409,
            {"name": TRIAL_STORE_NAME, "platform": "Naver", "match_count": len(stores)},
        )
    return stores[0]


def assert_trial_runtime_closed(settings: Settings) -> None:
    if not settings.operator_trial_enabled:
        raise ApiError("operator trial mode is not enabled", "operator_trial_not_enabled", 409)
    flags = {
        "real_api_test_enabled": settings.real_api_test_enabled,
        "real_api_write_enabled": settings.real_api_write_enabled,
        "ai_automatic_operations_enabled": settings.ai_automatic_operations_enabled,
        "platform_product_write_enabled": settings.platform_product_write_enabled,
        "platform_inventory_write_enabled": settings.platform_inventory_write_enabled,
        "platform_order_write_enabled": settings.platform_order_write_enabled,
        "customer_platform_write_enabled": settings.customer_platform_write_enabled,
        "shipping_platform_write_enabled": settings.shipping_platform_write_enabled,
    }
    enabled = sorted(key for key, value in flags.items() if value)
    if enabled:
        raise ApiError("trial real operations must remain disabled", "trial_real_operation_enabled", 409, {"enabled_flags": enabled})
    if not settings.operator_trial_artificial_data_only:
        raise ApiError("first trial must use artificial data only", "trial_artificial_data_required", 409)


def assert_store_has_only_artificial_customer_data(db: Session, store_id: int) -> None:
    real_orders = db.scalar(select(func.count()).select_from(Order).where(
        Order.store_id == store_id,
        Order.source_type.notin_(TEST_ORDER_SOURCE_TYPES),
    )) or 0
    inquiries = db.scalars(select(CustomerInquiry).where(CustomerInquiry.store_id == store_id)).all()
    unsafe_inquiries = [row.id for row in inquiries if not isinstance(row.raw_data, dict) or row.raw_data.get("is_test") is not True]
    if real_orders or unsafe_inquiries:
        raise ApiError(
            "trial store contains non-artificial customer data",
            "trial_real_customer_data_present",
            409,
            {"real_order_count": real_orders, "unsafe_inquiry_count": len(unsafe_inquiries)},
        )


def provision_trial_operator(
    db: Session,
    *,
    login_identifier: str,
    password: str,
    mfa_secret: str,
    display_name: str = "PXG Naver 模拟运营",
) -> dict:
    store = resolve_trial_store(db)
    permissions = db.scalars(select(ErpPermission).where(
        ErpPermission.permission_key.in_(TRIAL_PERMISSION_KEYS),
        ErpPermission.status == "active",
    )).all()
    found = {permission.permission_key for permission in permissions}
    missing = sorted(TRIAL_PERMISSION_KEYS - found)
    if missing:
        raise ApiError("trial permissions are not seeded", "trial_permissions_missing", 409, {"missing": missing})

    role = db.scalar(select(ErpRole).where(ErpRole.role_key == TRIAL_ROLE_KEY))
    if role is None:
        role = ErpRole(
            role_key=TRIAL_ROLE_KEY,
            role_label_zh="PXG Naver 模拟运营",
            role_label_en="PXG Naver trial operator",
            system_role=False,
            status="active",
        )
        db.add(role)
        db.flush()
    else:
        role.status = "active"
    db.execute(delete(ErpRolePermission).where(ErpRolePermission.role_id == role.id))
    for permission in permissions:
        db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id, can_approve_sensitive=False))

    login_hash = hash_login_identifier(login_identifier)
    user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash == login_hash))
    if user is None:
        user = ErpUser(
            user_key_hash=hashlib.sha256(f"trial:{login_hash}".encode()).hexdigest(),
            display_name=display_name,
            login_identifier_hash=login_hash,
            login_identifier_masked="trial-operator",
            status="active",
            auth_provider="password",
        )
        db.add(user)
        db.flush()
    else:
        user.display_name = display_name
        user.status = "active"
        user.auth_provider = "password"

    security = db.get(ErpUserSecurity, user.id)
    if security is None:
        security = ErpUserSecurity(user_id=user.id)
        db.add(security)
    security.password_hash = hash_password(password)
    security.mfa_type = "totp"
    security.mfa_secret_encrypted = encrypt_value(mfa_secret)
    security.mfa_enabled_at = get_utc_now()
    security.password_changed_at = get_utc_now()
    security.session_version = (security.session_version or 0) + 1
    security.authz_version = (security.authz_version or 0) + 1

    db.execute(delete(ErpStoreMembership).where(ErpStoreMembership.user_id == user.id))
    db.add(ErpStoreMembership(
        user_id=user.id,
        store_id=store.id,
        role_id=role.id,
        scope_type="assigned",
        membership_status="active",
    ))
    db.commit()
    return {"user_id": user.id, "store_id": store.id, "store_name": store.name, "platform": store.platform, "membership_count": 1}
