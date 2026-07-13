"""Create the persistent, local-only PXG Naver rehearsal database.

This script never reads deployment configuration. It writes only beneath
backend/.local-trial, which is ignored by Git.
"""

from __future__ import annotations

import argparse
import base64
import os
import secrets
import shutil
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
TRIAL_DIR = BACKEND_DIR / ".local-trial"
DATABASE_PATH = TRIAL_DIR / "pxg-naver-artificial-trial.sqlite3"
RUNTIME_ENV_PATH = TRIAL_DIR / "runtime.env"
CREDENTIAL_HANDOFF_PATH = TRIAL_DIR / "operator-credentials.txt"
MARKER_PATH = TRIAL_DIR / "README.txt"
STORE_NAME = "pxg\u7403\u5305\u5e97"
OPERATOR_LOGIN = "pxg-trial-operator@local.test"


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _restrict_handoff_acl(path: Path) -> None:
    # Best effort: this is a local handoff file, not an authorization boundary.
    if os.name == "nt":
        import subprocess

        user = os.environ.get("USERNAME")
        if user:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        path.chmod(0o600)


def _write_runtime_env() -> None:
    if RUNTIME_ENV_PATH.exists():
        values = _read_key_values(RUNTIME_ENV_PATH)
        if values.get("AUTOMATIC_READ_SYNC_ENABLED", "").lower() != "true":
            values["AUTOMATIC_READ_SYNC_ENABLED"] = "true"
            _write_text(RUNTIME_ENV_PATH, "\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
        return
    db_url = f"sqlite:///{DATABASE_PATH.as_posix()}"
    _write_text(RUNTIME_ENV_PATH, "\n".join([
        "# Generated local-only operator rehearsal configuration.",
        "APP_ENV=test",
        f"DATABASE_URL={db_url}",
        f"CREDENTIAL_ENCRYPTION_KEY={Fernet.generate_key().decode('ascii')}",
        f"SESSION_TOKEN_PEPPER={secrets.token_urlsafe(48)}",
        "SESSION_COOKIE_NAME=erp_trial_session",
        "SESSION_COOKIE_SECURE=false",
        "ALLOW_DEV_AUTH=false",
        "OPERATOR_TRIAL_ENABLED=true",
        "OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY=true",
        "REAL_API_TEST_ENABLED=false",
        "REAL_API_WRITE_ENABLED=false",
        "AI_AUTOMATIC_OPERATIONS_ENABLED=false",
        "PLATFORM_PRODUCT_WRITE_ENABLED=false",
        "PLATFORM_INVENTORY_WRITE_ENABLED=false",
        "PLATFORM_ORDER_WRITE_ENABLED=false",
        "CUSTOMER_PLATFORM_WRITE_ENABLED=false",
        "SHIPPING_PLATFORM_WRITE_ENABLED=false",
        "AUTOMATIC_READ_SYNC_ENABLED=true",
        "NAVER_API_BASE=http://127.0.0.1:9/platform-network-disabled",
        "NAVER_CLIENT_ID=",
        "NAVER_CLIENT_SECRET=",
        "NAVER_CHANNEL_NO=",
        "NAVER_ACCESS_TOKEN=",
        "NAVER_REFRESH_TOKEN=",
        "COUPANG_VENDOR_ID=",
        "COUPANG_ACCESS_KEY=",
        "COUPANG_SECRET_KEY=",
        "CORS_ALLOWED_ORIGINS=[\"http://127.0.0.1:5180\"]",
        "",
    ]))


def _create_handoff() -> dict[str, str]:
    if CREDENTIAL_HANDOFF_PATH.exists():
        values = _read_key_values(CREDENTIAL_HANDOFF_PATH)
        required = {"login_identifier", "password", "totp_secret"}
        if required <= values.keys():
            return values
        raise RuntimeError("local credential handoff is incomplete; rerun with --reset")
    values = {
        "login_identifier": OPERATOR_LOGIN,
        "password": secrets.token_urlsafe(24),
        "totp_secret": base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("="),
    }
    _write_text(CREDENTIAL_HANDOFF_PATH, "\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    _restrict_handoff_acl(CREDENTIAL_HANDOFF_PATH)
    return values


def _apply_runtime_env() -> None:
    for key, value in _read_key_values(RUNTIME_ENV_PATH).items():
        os.environ[key] = value


def _seed_database(credentials: dict[str, str]) -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from sqlalchemy import select

    from app.database import SessionLocal, init_db
    from app.models.customer_inquiry import CustomerInquiry
    from app.models.order import Order
    from app.models.product import Product
    from app.models.shipping import LogisticsInventoryItem, LogisticsInventoryMapping
    from app.models.store import Store
    from app.services import shipping_service
    from app.services.operator_trial_service import TRIAL_PERMISSION_KEYS, provision_trial_operator
    from app.models.auth import ErpPermission

    init_db()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        store = db.scalar(select(Store).where(Store.name == STORE_NAME))
        if store is None:
            store = Store(
                name=STORE_NAME,
                platform="naver",
                country="KR",
                language="zh-KR",
                status="active",
                owner_name="Artificial trial",
                remark="Artificial-data-only PXG Naver warehouse rehearsal.",
            )
            db.add(store)
            db.flush()
        elif store.platform.casefold() != "naver":
            raise RuntimeError("local trial store name is already bound to a non-Naver platform")

        for key in TRIAL_PERMISSION_KEYS:
            permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == key))
            if permission is None:
                db.add(ErpPermission(
                    permission_key=key,
                    permission_group="local_trial",
                    permission_label_zh=key,
                    status="active",
                ))

        products = [
            ("PXG-TRIAL-PRODUCT-001", "PXG Trial Carry Bag", "PXG-BAG-001", "WH-PXG-001"),
            ("PXG-TRIAL-PRODUCT-002", "PXG Trial Boston Bag", "PXG-BAG-002", "WH-PXG-002"),
        ]
        for external_id, name, sku, inventory_code in products:
            product = db.scalar(select(Product).where(Product.store_id == store.id, Product.external_product_id == external_id))
            if product is None:
                db.add(Product(
                    store_id=store.id, platform="naver", external_product_id=external_id,
                    name=name, sku=sku, brand="PXG", category="trial", status="active",
                    price=Decimal("1000.00"), currency="KRW", stock_quantity=20,
                    source_type="mock_sync", raw_data={"is_test": True, "artificial_data_only": True},
                ))
            normalized_name = shipping_service._normalize_key_part(name)
            mapping = db.scalar(select(LogisticsInventoryMapping).where(
                LogisticsInventoryMapping.store_id == store.id,
                LogisticsInventoryMapping.normalized_product_name == normalized_name,
            ))
            if mapping is None:
                db.add(LogisticsInventoryMapping(
                    store_id=store.id, platform="naver", match_product_name=name, match_option_name="",
                    normalized_product_name=normalized_name, normalized_option_name="", internal_sku=sku,
                    logistics_inventory_code=inventory_code, logistics_provider_name="Artificial Warehouse",
                    match_priority=1, is_active=True,
                ))
            item = db.scalar(select(LogisticsInventoryItem).where(
                LogisticsInventoryItem.store_id == store.id,
                LogisticsInventoryItem.logistics_inventory_code == inventory_code,
            ))
            if item is None:
                db.add(LogisticsInventoryItem(
                    store_id=store.id, platform="naver", logistics_inventory_code=inventory_code,
                    logistics_provider_name="Artificial Warehouse", current_stock_quantity=20,
                    stock_status="available", note="Artificial trial inventory only.", is_active=True,
                ))

        orders = [
            ("PXG-TRIAL-ORDER-001", "PXG-TRIAL-PRODUCT-ORDER-001", "PXG Trial Carry Bag"),
            ("PXG-TRIAL-ORDER-002", "PXG-TRIAL-PRODUCT-ORDER-002", "PXG Trial Boston Bag"),
            ("PXG-TRIAL-ORDER-003", "PXG-TRIAL-PRODUCT-ORDER-003", "PXG Trial Carry Bag"),
        ]
        for external_order_id, product_order_id, product_name in orders:
            order = db.scalar(select(Order).where(Order.store_id == store.id, Order.external_order_id == external_order_id))
            if order is None:
                db.add(Order(
                    store_id=store.id, platform="naver", external_order_id=external_order_id,
                    external_product_order_id=product_order_id, buyer_name="Artificial buyer",
                    buyer_masked_phone="010-0000-0000", receiver_name="Artificial receiver",
                    receiver_phone="010-0000-0000", receiver_address="Artificial rehearsal address",
                    zip_code="00000", product_name=product_name, quantity=1,
                    order_amount=Decimal("1000.00"), currency="KRW", order_status="PAYED",
                    ordered_at=now, paid_at=now, source_type="mock_sync",
                    raw_data={"is_test": True, "artificial_data_only": True, "trial_tag": "pxg_naver"},
                ))

        inquiry = db.scalar(select(CustomerInquiry).where(
            CustomerInquiry.store_id == store.id,
            CustomerInquiry.external_inquiry_id == "PXG-TRIAL-INQUIRY-001",
        ))
        inquiry_data = {
            "is_test": True,
            "artificial_data_only": True,
            "order_id": "PXG-TRIAL-ORDER-001",
            "product_order_id": "PXG-TRIAL-PRODUCT-ORDER-001",
            "product_order_id_list": ["PXG-TRIAL-PRODUCT-ORDER-001"],
            "product_name": "PXG Trial Carry Bag",
        }
        if inquiry is None:
            inquiry = CustomerInquiry(
                store_id=store.id, platform="naver", external_inquiry_id="PXG-TRIAL-INQUIRY-001",
                inquiry_type="shipping", customer_name="Artificial buyer", title="Artificial shipping inquiry",
                content="Artificial rehearsal inquiry. Do not send to a platform.", status="open",
                received_at=now, raw_data=inquiry_data,
            )
            db.add(inquiry)
        else:
            inquiry.raw_data = {**(inquiry.raw_data or {}), **inquiry_data}
        db.commit()
        provision_trial_operator(
            db,
            login_identifier=credentials["login_identifier"],
            password=credentials["password"],
            mfa_secret=credentials["totp_secret"],
            display_name="PXG球包店试运营员",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision the isolated local PXG Naver artificial-data trial")
    parser.add_argument("--reset", action="store_true", help="delete and recreate only backend/.local-trial")
    args = parser.parse_args()
    if args.reset and TRIAL_DIR.exists():
        shutil.rmtree(TRIAL_DIR)
    TRIAL_DIR.mkdir(parents=True, exist_ok=True)
    _write_runtime_env()
    credentials = _create_handoff()
    _apply_runtime_env()
    _seed_database(credentials)
    _write_text(MARKER_PATH, "Local-only artificial PXG Naver rehearsal. Delete with --reset.\n")
    print("local PXG Naver artificial-data trial provisioned")


if __name__ == "__main__":
    main()
