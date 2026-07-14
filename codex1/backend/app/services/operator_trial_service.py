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
    "shipping.writeback.approve",
    "platform.sync",
    "platform.browser.open",
    "customer.inquiries.content.read",
}
FORBIDDEN_TRIAL_PERMISSION_KEYS = {"*", "system.configure", "customer.inquiries.reply"}
DISABLED_TRIAL_WRITE_PATHS = {
    "/api/v1/shipping/shipment-writeback/execute",
    "/api/v1/sync/customer-inquiries/naver",
    "/api/v1/sync/customer-inquiries/naver/reply",
}

T18_TRIAL_WRITEBACK_PREFIX = "/api/v1/shipping/warehouse-batches/"
T18_TRIAL_WRITEBACK_SUFFIX = "/writeback"
T18_TRIAL_APPROVAL_SUFFIX = "/approval/writeback"


def t18_trial_write_gates_enabled(settings: Settings) -> bool:
    return all((
        bool(getattr(settings, "real_api_write_enabled", False)),
        bool(getattr(settings, "shipping_platform_write_enabled", False)),
        bool(getattr(settings, "pxg_naver_shipping_pilot_enabled", False)),
    ))


def is_t18_trial_writeback_path(path: str) -> bool:
    if not path.startswith(T18_TRIAL_WRITEBACK_PREFIX) or not path.endswith(T18_TRIAL_WRITEBACK_SUFFIX):
        return False
    batch_text = path[len(T18_TRIAL_WRITEBACK_PREFIX):-len(T18_TRIAL_WRITEBACK_SUFFIX)]
    return batch_text.isdigit()


def is_t18_trial_approval_path(path: str) -> bool:
    if not path.startswith(T18_TRIAL_WRITEBACK_PREFIX) or not path.endswith(T18_TRIAL_APPROVAL_SUFFIX):
        return False
    batch_text = path[len(T18_TRIAL_WRITEBACK_PREFIX):-len(T18_TRIAL_APPROVAL_SUFFIX)]
    return batch_text.isdigit()


def assert_t18_trial_writeback_request_allowed(
    db: Session,
    *,
    settings: Settings,
    path: str,
    body: dict,
    store_id: int | None,
) -> None:
    """Allow exactly the constrained T18 warehouse route during an operator trial."""

    if path in DISABLED_TRIAL_WRITE_PATHS:
        raise ApiError("legacy real platform write is disabled", "legacy_platform_write_disabled", 403)
    is_t18_execution = is_t18_trial_writeback_path(path)
    is_t18_approval = is_t18_trial_approval_path(path)
    if not is_t18_execution and not is_t18_approval:
        if path.endswith("/writeback"):
            raise ApiError("platform writeback is disabled for the trial", "trial_platform_write_disabled", 403)
        return

    if store_id is None:
        raise ApiError("trial shipping store scope is required", "trial_t18_store_required", 403)
    store = resolve_trial_store(db)
    if store.id != store_id or store.platform != TRIAL_PLATFORM:
        raise ApiError("T18 requires the unique PXG/Naver trial store", "trial_t18_store_required", 403)

    if is_t18_approval:
        if not t18_trial_write_gates_enabled(settings):
            raise ApiError("T18 writeback requires all three pilot write gates", "trial_t18_write_gates_required", 403)
        return

    action = str(body.get("action") or "execute").strip().lower()
    if action not in {"execute", "reconcile"}:
        raise ApiError("T18 writeback action is invalid", "trial_t18_action_invalid", 403)
    if action == "execute" and not t18_trial_write_gates_enabled(settings):
        raise ApiError("T18 writeback requires all three pilot write gates", "trial_t18_write_gates_required", 403)


def assert_legacy_naver_customer_inquiry_sync_closed(settings: Settings) -> None:
    raise ApiError(
        "legacy Naver customer inquiry sync is permanently disabled",
        "legacy_naver_customer_inquiry_sync_disabled",
        403,
    )


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
    if settings.operator_trial_real_read_enabled:
        if not settings.real_api_test_enabled or settings.operator_trial_artificial_data_only:
            raise ApiError("real readonly trial flags are inconsistent", "trial_readonly_flags_invalid", 409)
    elif settings.real_api_test_enabled or not settings.operator_trial_artificial_data_only:
        raise ApiError("artificial trial flags are inconsistent", "trial_artificial_flags_invalid", 409)
    t18_flags = {
        "real_api_write_enabled": bool(getattr(settings, "real_api_write_enabled", False)),
        "shipping_platform_write_enabled": bool(getattr(settings, "shipping_platform_write_enabled", False)),
        "pxg_naver_shipping_pilot_enabled": bool(getattr(settings, "pxg_naver_shipping_pilot_enabled", False)),
    }
    other_write_flags = {
        "ai_automatic_operations_enabled": bool(getattr(settings, "ai_automatic_operations_enabled", False)),
        "platform_product_write_enabled": bool(getattr(settings, "platform_product_write_enabled", False)),
        "platform_inventory_write_enabled": bool(getattr(settings, "platform_inventory_write_enabled", False)),
        # T18 dispatch must not widen generic platform-order mutation authority.
        "platform_order_write_enabled": bool(getattr(settings, "platform_order_write_enabled", False)),
        "customer_platform_write_enabled": bool(getattr(settings, "customer_platform_write_enabled", False)),
    }
    if any(other_write_flags.values()):
        enabled = sorted(key for key, value in other_write_flags.items() if value)
        raise ApiError("trial real operations must remain disabled", "trial_real_operation_enabled", 409, {"enabled_flags": enabled})
    enabled_t18 = sorted(key for key, value in t18_flags.items() if value)
    if enabled_t18 and not all(t18_flags.values()):
        raise ApiError(
            "T18 pilot write flags must be enabled as one constrained set",
            "trial_t18_write_flags_incomplete",
            409,
            {"enabled_flags": enabled_t18},
        )


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
