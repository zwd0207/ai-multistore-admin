"""Focused checks for the persistent local PXG Naver rehearsal setup."""

from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
TRIAL_DIR = BACKEND_DIR / ".local-trial"
RUNTIME_ENV_PATH = TRIAL_DIR / "runtime.env"
CREDENTIAL_HANDOFF_PATH = TRIAL_DIR / "operator-credentials.txt"


def read_values(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(f"missing local trial file: {path}")
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))


def main() -> None:
    runtime = read_values(RUNTIME_ENV_PATH)
    credentials = read_values(CREDENTIAL_HANDOFF_PATH)
    os.environ.update(runtime)
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from fastapi.testclient import TestClient
    from sqlalchemy import func, select
    from app.config import get_settings
    from app.database import SessionLocal
    from app.main import app
    from app.models.api_credential import ApiCredential
    from app.models.auth import ErpPermission, ErpRolePermission, ErpStoreMembership, ErpUser
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order
    from app.models.shipping import LogisticsInventoryMapping
    from app.models.store import Store
    from app.services.operator_trial_service import FORBIDDEN_TRIAL_PERMISSION_KEYS, TRIAL_PERMISSION_KEYS
    from app.services.session_service import generate_totp

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.operator_trial_enabled and settings.operator_trial_artificial_data_only
    assert not any((settings.real_api_test_enabled, settings.real_api_write_enabled, settings.ai_automatic_operations_enabled,
                    settings.platform_product_write_enabled, settings.platform_inventory_write_enabled,
                    settings.platform_order_write_enabled, settings.customer_platform_write_enabled,
                    settings.shipping_platform_write_enabled))
    assert settings.naver_api_base.startswith("http://127.0.0.1:9/")
    assert not any((settings.naver_client_id, settings.naver_client_secret, settings.coupang_vendor_id,
                    settings.coupang_access_key, settings.coupang_secret_key))

    with SessionLocal() as db:
        stores = db.scalars(select(Store)).all()
        assert len(stores) == 1 and stores[0].name == "pxg\u7403\u5305\u5e97" and stores[0].platform.casefold() == "naver"
        store = stores[0]
        assert (db.scalar(select(func.count()).select_from(Order).where(Order.store_id == store.id)) or 0) == 3
        assert (db.scalar(select(func.count()).select_from(CustomerInquiry).where(CustomerInquiry.store_id == store.id)) or 0) == 1
        assert (db.scalar(select(func.count()).select_from(LogisticsInventoryMapping).where(LogisticsInventoryMapping.store_id == store.id)) or 0) == 2
        assert all(row.raw_data and row.raw_data.get("is_test") is True for row in db.scalars(select(Order)).all())
        assert all(row.raw_data and row.raw_data.get("is_test") is True for row in db.scalars(select(CustomerInquiry)).all())
        assert db.scalar(select(func.count()).select_from(ApiCredential)) == 0
        user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash.is_not(None)))
        memberships = db.scalars(select(ErpStoreMembership).where(ErpStoreMembership.user_id == user.id)).all()
        assert len(memberships) == 1 and memberships[0].store_id == store.id and memberships[0].scope_type == "assigned"
        granted = set(db.scalars(select(ErpPermission.permission_key).join(ErpRolePermission).where(
            ErpRolePermission.role_id == memberships[0].role_id)).all())
        assert granted == TRIAL_PERMISSION_KEYS and not (granted & FORBIDDEN_TRIAL_PERMISSION_KEYS)

    origin = settings.cors_allowed_origins[0]
    with TestClient(app, base_url=origin) as client:
        login = client.post("/api/v1/auth/login", headers={"Origin": origin}, json={
            "login_identifier": credentials["login_identifier"], "password": credentials["password"],
        })
        assert login.status_code == 200, login.text
        mfa = client.post("/api/v1/auth/mfa/verify", headers={"Origin": origin}, json={
            "code": generate_totp(credentials["totp_secret"]),
        })
        assert mfa.status_code == 200, mfa.text
        session = client.get("/api/v1/auth/session")
        assert session.status_code == 200, session.text
        csrf = session.json()["data"]["csrf_token"]
        stores = client.get("/api/v1/stores")
        assert stores.status_code == 200 and stores.json()["data"]["total"] == 1, stores.text
        orders = client.get("/api/v1/orders", params={"store_id": stores.json()["data"]["items"][0]["id"]})
        assert orders.status_code == 200 and orders.json()["data"]["total"] == 3, orders.text
        assert orders.json()["data"]["include_test_orders"] is True, orders.text
        inquiries = client.get("/api/v1/customer-inquiries", params={"store_id": stores.json()["data"]["items"][0]["id"]})
        assert inquiries.status_code == 200, inquiries.text
        assert inquiries.json()["data"]["items"] == [], inquiries.text
        assert inquiries.json()["data"]["total"] == 0, inquiries.text
        assert inquiries.json()["data"]["classification_counts"] == {"all": 0, "answered": 0, "unanswered": 0}, inquiries.text
        cross_store = client.get("/api/v1/orders", params={"store_id": 999999})
        assert cross_store.status_code == 403, cross_store.text
        headers = {"Origin": origin, "X-CSRF-Token": csrf}
        legacy_shipping = client.post("/api/v1/shipping/shipment-writeback/execute", headers=headers, json={"store_id": 1})
        direct_reply = client.post("/api/v1/sync/customer-inquiries/naver/reply", headers=headers, json={"store_id": 1})
        # The restricted operator has neither real-write permission, so both
        # routes are rejected by middleware before a platform service can run.
        assert legacy_shipping.status_code == 403, legacy_shipping.text
        assert direct_reply.status_code == 403, direct_reply.text
    print("verify_local_pxg_naver_trial: ok")


if __name__ == "__main__":
    main()
