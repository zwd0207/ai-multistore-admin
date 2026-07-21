"""Provision or remove the T12 artificial second-store fixture locally."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
TRIAL_DB_PATH = BACKEND_DIR / ".local-trial" / "pxg-naver-artificial-trial.sqlite3"
RUNTIME_ENV_PATH = BACKEND_DIR / ".local-trial" / "runtime.env"
STORE_NAME = "[FICTIONAL][LOCAL][T12] Naver Multi-store Demo"
PLATFORM = "naver"
MARKER = "t12_multistore_fixture_v1"
ORDER_ID = "T12-FICT-NAVER-ORDER-001"
INQUIRY_ID = "T12-FICT-NAVER-INQUIRY-001"
CONFIG_ADMIN_LOGIN = "pxg-config-admin@local.test"
ROLE_KEY = "pxg_connection_config_admin"
FIXED_TIME = datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)
FIXTURE_RAW_DATA = {
    "is_test": True,
    "artificial_data_only": True,
    "fixture_tag": MARKER,
    "marker": MARKER,
}


def _is_owned_fixture(raw_data: object) -> bool:
    return isinstance(raw_data, dict) and (
        raw_data.get("fixture_tag") == MARKER or raw_data.get("marker") == MARKER
    )


def configure_safe_local_environment() -> None:
    """Pin this process to the designated local database with platform access closed."""
    runtime = {}
    if RUNTIME_ENV_PATH.exists():
        runtime = dict(
            line.split("=", 1)
            for line in RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.startswith("#")
        )
    encryption_key = runtime.get("CREDENTIAL_ENCRYPTION_KEY")
    session_pepper = runtime.get("SESSION_TOKEN_PEPPER")
    if not encryption_key or not session_pepper:
        raise RuntimeError("local trial encryption and session settings are required")
    os.environ.update({
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{TRIAL_DB_PATH.as_posix()}",
        "CREDENTIAL_ENCRYPTION_KEY": encryption_key,
        "SESSION_TOKEN_PEPPER": session_pepper,
        "ALLOW_DEV_AUTH": "false",
        "OPERATOR_TRIAL_ENABLED": "true",
        "OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY": "true",
        "OPERATOR_TRIAL_REAL_READ_ENABLED": "false",
        "REAL_API_TEST_ENABLED": "false",
        "REAL_API_WRITE_ENABLED": "false",
        "AI_AUTOMATIC_OPERATIONS_ENABLED": "false",
        "PLATFORM_PRODUCT_WRITE_ENABLED": "false",
        "PLATFORM_INVENTORY_WRITE_ENABLED": "false",
        "PLATFORM_ORDER_WRITE_ENABLED": "false",
        "CUSTOMER_PLATFORM_WRITE_ENABLED": "false",
        "SHIPPING_PLATFORM_WRITE_ENABLED": "false",
        "NAVER_API_BASE": "http://127.0.0.1:9/",
        "NAVER_CLIENT_ID": "",
        "NAVER_CLIENT_SECRET": "",
        "NAVER_ACCESS_TOKEN": "",
        "NAVER_REFRESH_TOKEN": "",
        "COUPANG_VENDOR_ID": "",
        "COUPANG_ACCESS_KEY": "",
        "COUPANG_SECRET_KEY": "",
    })


def _load_runtime():
    configure_safe_local_environment()
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from app.config import get_settings
    from app.database import SessionLocal, init_db

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.database_url == f"sqlite:///{TRIAL_DB_PATH.as_posix()}"
    assert not any((settings.real_api_test_enabled, settings.real_api_write_enabled,
                    settings.operator_trial_real_read_enabled, settings.ai_automatic_operations_enabled,
                    settings.platform_product_write_enabled, settings.platform_inventory_write_enabled,
                    settings.platform_order_write_enabled, settings.customer_platform_write_enabled,
                    settings.shipping_platform_write_enabled))
    init_db()
    return SessionLocal


def _fixture_store(db):
    from sqlalchemy import func, select
    from app.models.store import Store

    same_name = db.scalars(select(Store).where(
        Store.name == STORE_NAME,
        func.lower(Store.platform) == PLATFORM,
    )).all()
    if any(store.remark != MARKER for store in same_name):
        raise RuntimeError("T12 fixture store identity conflict")
    if len(same_name) > 1:
        raise RuntimeError("T12 fixture store must match at most once")
    if same_name:
        return same_name[0]
    store = Store(name=STORE_NAME, platform=PLATFORM, remark=MARKER, status="active")
    db.add(store)
    db.flush()
    return store


def _config_admin(db):
    from sqlalchemy import select
    from app.models.auth import ErpRole, ErpUser
    from app.services.session_service import hash_login_identifier

    user = db.scalar(select(ErpUser).where(
        ErpUser.login_identifier_hash == hash_login_identifier(CONFIG_ADMIN_LOGIN),
    ))
    role = db.scalar(select(ErpRole).where(ErpRole.role_key == ROLE_KEY))
    if user is None or role is None:
        raise RuntimeError("run provision_local_config_admin.py before provisioning the T12 fixture")
    return user, role


def provision() -> None:
    SessionLocal = _load_runtime()
    from sqlalchemy import delete, select
    from app.models.auth import ErpStoreMembership
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order

    with SessionLocal() as db:
        store = _fixture_store(db)
        user, role = _config_admin(db)
        db.execute(delete(ErpStoreMembership).where(
            ErpStoreMembership.user_id == user.id,
            ErpStoreMembership.store_id == store.id,
        ))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id,
                                  scope_type="assigned", membership_status="active"))
        orders = db.scalars(select(Order).where(Order.store_id == store.id, Order.platform == PLATFORM,
                                                Order.external_order_id == ORDER_ID)).all()
        if any(not _is_owned_fixture(row.raw_data) for row in orders):
            raise RuntimeError("T12 fixture order identity conflict")
        if not orders:
            orders = [Order(store_id=store.id, platform=PLATFORM, external_order_id=ORDER_ID)]
            db.add_all(orders)
        for order in orders:
            order.external_product_order_id = None
            order.buyer_name = None
            order.buyer_phone = None
            order.buyer_masked_phone = None
            order.receiver_name = None
            order.receiver_phone = None
            order.receiver_address = None
            order.zip_code = None
            order.product_name = "T12 Fixture Item"
            order.quantity = 1
            order.order_amount = 0
            order.currency = "KRW"
            order.order_status = "异常"
            order.ordered_at = FIXED_TIME
            order.paid_at = None
            order.last_synced_at = FIXED_TIME
            order.source_type = "local_readonly_fixture"
            order.raw_data = dict(FIXTURE_RAW_DATA)
        inquiries = db.scalars(select(CustomerInquiry).where(CustomerInquiry.store_id == store.id,
                                                              CustomerInquiry.platform == PLATFORM,
                                                              CustomerInquiry.external_inquiry_id == INQUIRY_ID)).all()
        if any(not _is_owned_fixture(row.raw_data) for row in inquiries):
            raise RuntimeError("T12 fixture inquiry identity conflict")
        if not inquiries:
            inquiries = [CustomerInquiry(store_id=store.id, platform=PLATFORM,
                                         external_inquiry_id=INQUIRY_ID)]
            db.add_all(inquiries)
        for inquiry in inquiries:
            inquiry.inquiry_type = "product"
            inquiry.customer_name = None
            inquiry.title = "T12 Fixture Inquiry"
            inquiry.content = "Artificial local fixture only."
            inquiry.status = "open"
            inquiry.received_at = FIXED_TIME
            inquiry.answered_at = None
            inquiry.raw_data = dict(FIXTURE_RAW_DATA)
        db.commit()
    print("t12_local_multistore_fixture: provisioned")


def cleanup() -> None:
    SessionLocal = _load_runtime()
    from sqlalchemy import delete, func, select
    from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order
    from app.models.store import Store

    with SessionLocal() as db:
        stores = db.scalars(select(Store).where(Store.name == STORE_NAME,
                                                 func.lower(Store.platform) == PLATFORM,
                                                 Store.remark == MARKER)).all()
        if len(stores) > 1:
            raise RuntimeError("T12 cleanup requires exactly one triple-matched store")
        if stores:
            store = stores[0]
            user, role = _config_admin(db)
            unexpected_orders = db.scalars(select(Order).where(
                Order.store_id == store.id,
                (Order.platform != PLATFORM) | (Order.external_order_id != ORDER_ID)
                | Order.raw_data["marker"].as_string().is_not(MARKER),
            )).all()
            unexpected_inquiries = db.scalars(select(CustomerInquiry).where(
                CustomerInquiry.store_id == store.id,
                (CustomerInquiry.platform != PLATFORM) | (CustomerInquiry.external_inquiry_id != INQUIRY_ID)
                | CustomerInquiry.raw_data["marker"].as_string().is_not(MARKER),
            )).all()
            unexpected_memberships = db.scalars(select(ErpStoreMembership).where(
                ErpStoreMembership.store_id == store.id,
                (ErpStoreMembership.user_id != user.id) | (ErpStoreMembership.role_id != role.id),
            )).all()
            if unexpected_orders or unexpected_inquiries or unexpected_memberships:
                raise RuntimeError("T12 cleanup will not remove data outside the exact fixture markers")
            db.execute(delete(CustomerInquiry).where(CustomerInquiry.store_id == store.id,
                                                     CustomerInquiry.platform == PLATFORM,
                                                     CustomerInquiry.external_inquiry_id == INQUIRY_ID,
                                                     CustomerInquiry.raw_data["marker"].as_string() == MARKER))
            db.execute(delete(Order).where(Order.store_id == store.id, Order.platform == PLATFORM,
                                           Order.external_order_id == ORDER_ID,
                                           Order.raw_data["marker"].as_string() == MARKER))
            db.execute(delete(ErpStoreMembership).where(ErpStoreMembership.user_id == user.id,
                                                        ErpStoreMembership.store_id == store.id,
                                                        ErpStoreMembership.role_id == role.id))
            db.execute(delete(Store).where(Store.id == store.id, Store.name == STORE_NAME,
                                           func.lower(Store.platform) == PLATFORM, Store.remark == MARKER))
        db.commit()
    print("t12_local_multistore_fixture: cleaned")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the local-only T12 multistore fixture")
    parser.add_argument("--cleanup", "--reset", action="store_true", dest="cleanup")
    args = parser.parse_args()
    if args.cleanup:
        cleanup()
    else:
        provision()


if __name__ == "__main__":
    main()
