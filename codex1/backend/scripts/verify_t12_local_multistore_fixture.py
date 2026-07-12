"""TDD verification for the local-only T12 dual-store fixture."""

from __future__ import annotations

import subprocess
import sys

from provision_t12_local_multistore_fixture import (
    BACKEND_DIR,
    CONFIG_ADMIN_LOGIN,
    FIXTURE_RAW_DATA,
    INQUIRY_ID,
    MARKER,
    ORDER_ID,
    PLATFORM,
    ROLE_KEY,
    STORE_NAME,
    TRIAL_DB_PATH,
    _load_runtime,
    cleanup,
    configure_safe_local_environment,
    provision,
)


def _assert_fixture(*, expected: bool) -> None:
    SessionLocal = _load_runtime()
    from sqlalchemy import func, select, text
    from app.models.auth import ErpPermission, ErpRolePermission, ErpStoreMembership, ErpUser
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order
    from app.models.store import Store
    from app.services import order_service, stats_service
    from app.services.operator_trial_service import resolve_trial_store
    from app.services.session_service import hash_login_identifier

    with SessionLocal() as db:
        stores = db.scalars(select(Store).where(Store.name == STORE_NAME,
                                                 func.lower(Store.platform) == PLATFORM,
                                                 Store.remark == MARKER)).all()
        if not expected:
            assert not stores, stores
            return
        assert len(stores) == 1, stores
        store = stores[0]
        orders = db.scalars(select(Order).where(Order.store_id == store.id, Order.platform == PLATFORM,
                                                Order.external_order_id == ORDER_ID)).all()
        inquiries = db.scalars(select(CustomerInquiry).where(CustomerInquiry.store_id == store.id,
                                                              CustomerInquiry.platform == PLATFORM,
                                                              CustomerInquiry.external_inquiry_id == INQUIRY_ID)).all()
        assert len(orders) == 1 and len(inquiries) == 1
        order = orders[0]
        assert order.order_status == "异常" and order.source_type == "local_readonly_fixture"
        assert order.raw_data == FIXTURE_RAW_DATA
        default_orders = order_service.list_orders(db, store_id=store.id, platform=PLATFORM,
                                                   include_test_orders=False)
        assert any(row["external_order_id"] == ORDER_ID for row in default_orders)
        workbench = stats_service._build_operator_workbench(
            db,
            store_id=store.id,
            platform=PLATFORM,
            include_test_orders=False,
        )
        urgent = workbench["sections"]["urgent"]
        assert len(urgent) == 1
        assert urgent[0]["task_type"] == "abnormal_order"
        assert urgent[0]["related_order_id"] == order.id
        assert all(getattr(order, field) is None for field in ("buyer_name", "buyer_phone", "receiver_name",
                                                               "receiver_phone", "receiver_address", "zip_code"))
        assert inquiries[0].status == "open" and inquiries[0].answered_at is None and inquiries[0].customer_name is None
        assert inquiries[0].raw_data == FIXTURE_RAW_DATA
        user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash == hash_login_identifier(CONFIG_ADMIN_LOGIN)))
        assert user is not None
        memberships = db.scalars(select(ErpStoreMembership).where(ErpStoreMembership.user_id == user.id)).all()
        pxg_store = resolve_trial_store(db)
        t12 = [row for row in memberships if row.store_id == store.id]
        pxg = [row for row in memberships if row.store_id == pxg_store.id]
        assert len(memberships) == 2 and len(pxg) == 1
        assert len(t12) == 1 and t12[0].scope_type == "assigned" and t12[0].membership_status == "active"
        granted = set(db.scalars(select(ErpPermission.permission_key).join(ErpRolePermission).where(
            ErpRolePermission.role_id == t12[0].role_id)).all())
        assert t12[0].role.role_key == ROLE_KEY and "platform.sync" in granted
        assert db.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"


def _account_snapshot() -> tuple:
    SessionLocal = _load_runtime()
    from sqlalchemy import select
    from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpUser
    from app.services.session_service import hash_login_identifier

    with SessionLocal() as db:
        user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash == hash_login_identifier(CONFIG_ADMIN_LOGIN)))
        role = db.scalar(select(ErpRole).where(ErpRole.role_key == ROLE_KEY))
        assert user is not None and role is not None
        permissions = tuple(sorted(db.scalars(select(ErpPermission.permission_key).join(ErpRolePermission).where(
            ErpRolePermission.role_id == role.id)).all()))
        return user.id, user.user_key_hash, user.login_identifier_hash, role.id, role.role_key, permissions


def _write_legacy_contract() -> None:
    SessionLocal = _load_runtime()
    from sqlalchemy import select
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order
    from app.models.store import Store

    with SessionLocal() as db:
        store = db.scalar(select(Store).where(Store.name == STORE_NAME, Store.platform == PLATFORM,
                                               Store.remark == MARKER))
        assert store is not None
        order = db.scalar(select(Order).where(Order.store_id == store.id, Order.external_order_id == ORDER_ID))
        inquiry = db.scalar(select(CustomerInquiry).where(
            CustomerInquiry.store_id == store.id,
            CustomerInquiry.external_inquiry_id == INQUIRY_ID,
        ))
        assert order is not None and inquiry is not None
        order.order_status = "exception"
        order.source_type = "mock_sync"
        order.raw_data = {"is_test": True, "marker": MARKER}
        inquiry.raw_data = {"is_test": True, "marker": MARKER}
        db.commit()


def main() -> None:
    configure_safe_local_environment()
    assert TRIAL_DB_PATH.resolve().parent == (BACKEND_DIR / ".local-trial").resolve()
    cleanup()
    _assert_fixture(expected=False)
    provision()
    _write_legacy_contract()
    provision()
    provision()
    _assert_fixture(expected=True)
    subprocess.run([sys.executable, str(BACKEND_DIR / "scripts" / "provision_local_config_admin.py")],
                   cwd=BACKEND_DIR, env=__import__("os").environ.copy(), check=True)
    _assert_fixture(expected=True)
    before_cleanup = _account_snapshot()
    cleanup()
    _assert_fixture(expected=False)
    assert _account_snapshot() == before_cleanup
    provision()
    provision()
    _assert_fixture(expected=True)
    print("verify_t12_local_multistore_fixture: ok")


if __name__ == "__main__":
    main()
