import base64
import copy
import json
import os
import sqlite3
import sys
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly-persistence.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"
os.environ["OPERATOR_TRIAL_REAL_READ_ENABLED"] = "false"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED"] = "true"
os.environ["PXG_NAVER_LOCAL_READ_ORDER_STALE_AFTER_MINUTES"] = "15"
os.environ["PXG_NAVER_LOCAL_READ_INQUIRY_STALE_AFTER_MINUTES"] = "7"
os.environ["PXG_NAVER_LOCAL_READ_LOGISTICS_STALE_AFTER_MINUTES"] = "30"
os.environ["PXG_NAVER_LOCAL_READ_PRODUCT_STALE_AFTER_HOURS"] = "6"
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_DAYS"] = "90"
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "false"

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
)
from app.models.shipping import LogisticsInventoryMapping
from app.models.store import Store
from app.services import order_service, shipping_service, warehouse_shipping_service
from app.services.pxg_naver_readonly_persistence_service import (
    PXG_NAVER_READONLY_LOCAL_SOURCE,
    mark_pxg_naver_readonly_stale,
    persist_pxg_naver_readonly_adapter_batch,
    readonly_local_summary,
    retention_cleanup_status,
)
from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
from scripts.upgrade_pxg_naver_readonly_schema import _rebuild_orders_for_product_order_uniqueness


def fixture(store_id: int) -> dict:
    return {
        "store_id": store_id,
        "platform": "naver",
        "source_mode": "fictional_test",
        "products": [{
            "external_product_id": "fixture-product-001",
            "name": "PXG Fictional Carry Bag",
            "sku": "PXG-FIX-001",
            "brand": "PXG",
            "category": "golf-bag",
            "status": "active",
            "price": "199000",
            "currency": "KRW",
            "stock_quantity": 7,
            "source_updated_at": "2026-07-12T08:00:00+00:00",
        }],
        "orders": [{
            "external_order_id": "fixture-order-001",
            "external_product_order_id": "fixture-product-order-001",
            "product_name": "PXG Fictional Carry Bag",
            "quantity": 1,
            "order_amount": "199000",
            "currency": "KRW",
            "order_status": "PAYED",
            "ordered_at": "2026-07-12T07:30:00+00:00",
            "paid_at": "2026-07-12T07:31:00+00:00",
            "source_updated_at": "2026-07-12T08:00:00+00:00",
            "recipient": {
                "receiver_name": "Fictional Recipient",
                "receiver_phone": "010-5555-1234",
                "receiver_phone_secondary": "010-5555-4321",
                "zip_code": "06123",
                "receiver_address_line1": "Fictional Seoul Road 1",
                "receiver_address_line2": "Suite 101",
                "receiver_address_full": "Fictional Seoul Road 1 Suite 101",
                "delivery_memo": "Leave at fictional front desk",
            },
        }],
        "logistics": [{
            "external_order_id": "fixture-order-001",
            "external_product_order_id": "fixture-product-order-001",
            "carrier": "CJ",
            "tracking_number": "TEST-TRACK-987654321",
            "shipment_status": "observed",
            "shipped_at": "2026-07-12T08:01:00+00:00",
            "source_updated_at": "2026-07-12T08:01:00+00:00",
        }],
        "customer_inquiries": [{
            "external_inquiry_id": "fixture-inquiry-001",
            "related_external_order_id": "fixture-order-001",
            "related_external_product_order_id": "fixture-product-order-001",
            "inquiry_type": "delivery",
            "status": "open",
            "customer_display_masked": "Fi***",
            "subject_category": "delivery_status",
            "content_available": True,
            "received_at": "2026-07-12T08:02:00+00:00",
            "answered_at": None,
            "source_updated_at": "2026-07-12T08:02:00+00:00",
        }],
    }


def assert_not_contains(value: object, *forbidden: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, default=str).lower()
    for item in forbidden:
        assert item.lower() not in serialized, f"unexpected sensitive value: {item}"


def add_memberships(db, store: Store, other_store: Store) -> tuple[ErpUser, ErpUser, ErpUser]:
    admin_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "admin"))
    operator_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "operator"))
    assert admin_role is not None and operator_role is not None
    admin = ErpUser(user_key_hash="pxg-readonly-admin", display_name="Readonly Admin", status="active")
    operator = ErpUser(user_key_hash="pxg-readonly-operator", display_name="Readonly Operator", status="active")
    other_admin = ErpUser(user_key_hash="pxg-readonly-other", display_name="Other Store Admin", status="active")
    db.add_all([admin, operator, other_admin])
    db.flush()
    db.add_all([
        ErpStoreMembership(user_id=admin.id, store_id=store.id, role_id=admin_role.id, membership_status="active"),
        ErpStoreMembership(user_id=operator.id, store_id=store.id, role_id=operator_role.id, membership_status="active"),
        ErpStoreMembership(user_id=other_admin.id, store_id=other_store.id, role_id=admin_role.id, membership_status="active"),
    ])
    db.commit()
    return admin, operator, other_admin


def verify_legacy_order_uniqueness_migration() -> None:
    legacy_path = Path(tempfile.gettempdir()) / "verify-pxg-naver-legacy-order-upgrade.db"
    if legacy_path.exists():
        legacy_path.unlink()
    connection = sqlite3.connect(legacy_path)
    try:
        connection.executescript("""
            CREATE TABLE stores (id INTEGER PRIMARY KEY);
            INSERT INTO stores (id) VALUES (1);
            CREATE TABLE orders (
                id INTEGER NOT NULL PRIMARY KEY,
                store_id INTEGER NOT NULL,
                platform VARCHAR(50) NOT NULL,
                external_order_id VARCHAR(120) NOT NULL,
                external_product_order_id VARCHAR(120),
                buyer_name VARCHAR(120), buyer_phone VARCHAR(40), buyer_masked_phone VARCHAR(30),
                receiver_name VARCHAR(120), receiver_phone VARCHAR(40), receiver_address VARCHAR(300), zip_code VARCHAR(30),
                product_name VARCHAR(300) NOT NULL, quantity INTEGER NOT NULL, order_amount NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(10) NOT NULL, order_status VARCHAR(30) NOT NULL, paid_at DATETIME, ordered_at DATETIME NOT NULL,
                source_type VARCHAR(30) NOT NULL, last_synced_at DATETIME, raw_data JSON,
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
                FOREIGN KEY(store_id) REFERENCES stores(id),
                CONSTRAINT uq_order_external_id UNIQUE (store_id, platform, external_order_id)
            );
            INSERT INTO orders VALUES (
                1, 1, 'naver', 'legacy-platform-order', 'legacy-product-order-1',
                NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                'Legacy Item', 1, 1000, 'KRW', 'PAYED', NULL, '2026-07-12T00:00:00+00:00',
                'legacy', NULL, NULL, '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
            );
        """)
        _rebuild_orders_for_product_order_uniqueness(connection)
        connection.execute("""
            INSERT INTO orders (
                id, store_id, platform, external_order_id, external_product_order_id,
                product_name, quantity, order_amount, currency, order_status, ordered_at,
                source_type, created_at, updated_at
            ) VALUES (
                2, 1, 'naver', 'legacy-second-platform-order', 'legacy-product-order-2',
                'Second Legacy Item', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                'legacy', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
            )
        """)
        connection.execute("""
            INSERT INTO orders (
                id, store_id, platform, external_order_id, external_product_order_id,
                product_name, quantity, order_amount, currency, order_status, ordered_at,
                source_type, created_at, updated_at
            ) VALUES (
                3, 1, 'naver', 'legacy-other-platform-order', 'legacy-product-order-1',
                'Legacy Shared Product Order', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                'legacy', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
            )
        """)
        connection.execute("""
            INSERT INTO orders (
                id, store_id, platform, external_order_id, external_product_order_id,
                product_name, quantity, order_amount, currency, order_status, ordered_at,
                source_type, created_at, updated_at
            ) VALUES (
                4, 1, 'naver', 'pxg-platform-order', 'pxg-product-order-1',
                'PXG First Item', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                'pxg_naver_readonly_local_v1', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
            )
        """)
        try:
            connection.execute("""
                INSERT INTO orders (
                    id, store_id, platform, external_order_id, external_product_order_id,
                    product_name, quantity, order_amount, currency, order_status, ordered_at,
                    source_type, created_at, updated_at
                ) VALUES (
                    6, 1, 'naver', 'legacy-platform-order', 'legacy-product-order-3',
                    'Legacy Duplicate Platform Order', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                    'legacy', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
                )
            """)
            raise AssertionError("legacy duplicate platform-order identifier should be rejected")
        except sqlite3.IntegrityError:
            pass
        connection.execute("""
            INSERT INTO orders (
                id, store_id, platform, external_order_id, external_product_order_id,
                product_name, quantity, order_amount, currency, order_status, ordered_at,
                source_type, created_at, updated_at
            ) VALUES (
                5, 1, 'naver', 'pxg-platform-order', 'pxg-product-order-2',
                'PXG Second Item', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                'pxg_naver_readonly_local_v1', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
            )
        """)
        try:
            connection.execute("""
                INSERT INTO orders (
                    id, store_id, platform, external_order_id, external_product_order_id,
                    product_name, quantity, order_amount, currency, order_status, ordered_at,
                    source_type, created_at, updated_at
                ) VALUES (
                    7, 1, 'naver', 'pxg-other-platform-order', 'pxg-product-order-1',
                    'PXG Duplicate Item', 1, 1000, 'KRW', 'PAYED', '2026-07-12T00:00:00+00:00',
                    'pxg_naver_readonly_local_v1', '2026-07-12T00:00:00+00:00', '2026-07-12T00:00:00+00:00'
                )
            """)
            raise AssertionError("PXG duplicate product-order identifier should be rejected")
        except sqlite3.IntegrityError:
            pass
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 5
    finally:
        connection.close()
        if legacy_path.exists():
            legacy_path.unlink()


def main() -> None:
    verify_legacy_order_uniqueness_migration()
    init_db()
    schema = inspect(engine)
    expected_tables = {
        "pxg_naver_readonly_record_states",
        "pxg_naver_order_recipient_secure_records",
        "pxg_naver_readonly_logistics_records",
        "pxg_naver_readonly_customer_inquiries",
    }
    assert expected_tables.issubset(set(schema.get_table_names()))

    with SessionLocal() as db:
        store = Store(name="pxg球包店", platform="naver")
        other_store = Store(name="pxg-readonly-other-store", platform="naver")
        db.add_all([store, other_store])
        db.commit()
        db.refresh(store)
        db.refresh(other_store)
        admin, operator, other_admin = add_memberships(db, store, other_store)
        payload = fixture(store.id)
        batch = PxgNaverReadonlyAdapterBatch.model_validate(payload)

        disabled_settings = Settings(
            app_env="development",
            database_url=f"sqlite:///{TEMP_DB.as_posix()}",
            operator_trial_enabled=True,
            operator_trial_artificial_data_only=True,
            real_api_test_enabled=False,
            real_api_write_enabled=False,
            pxg_naver_local_read_persistence_enabled=False,
        )
        try:
            persist_pxg_naver_readonly_adapter_batch(
                db,
                settings=disabled_settings,
                batch=batch,
                actor_id=admin.user_key_hash,
                manual_approval=True,
            )
            raise AssertionError("default-disabled persistence should be rejected")
        except ApiError as exc:
            assert exc.error_code == "readonly_local_persistence_disabled", exc

        result = persist_pxg_naver_readonly_adapter_batch(
            db,
            settings=get_settings(),
            batch=batch,
            actor_id=admin.user_key_hash,
            manual_approval=True,
        )
        assert result["status"] == "completed", result
        for resource in ("products", "orders", "logistics", "customer_inquiries"):
            assert result["counts"][resource].get("created") == 1, result
        assert result["writes"] == {
            "platform_write": False,
            "customer_send": False,
            "ai_automatic_operation": False,
        }

        product = db.scalar(select(Product).where(Product.store_id == store.id))
        order = db.scalar(select(Order).where(Order.store_id == store.id))
        secure_recipient = db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(
            PxgNaverOrderRecipientSecureRecord.order_id == order.id,
        ))
        logistics = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == order.id,
        ))
        inquiry = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(
            PxgNaverReadonlyCustomerInquiry.store_id == store.id,
        ))
        assert product is not None and order is not None and secure_recipient is not None and logistics is not None and inquiry is not None
        assert product.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE
        assert order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE
        assert order.receiver_name is None and order.receiver_phone is None and order.receiver_address is None and order.zip_code is None
        assert "Fictional Recipient" not in secure_recipient.encrypted_recipient_payload
        assert "010-5555-1234" not in secure_recipient.encrypted_recipient_payload
        assert "Fictional Seoul Road" not in secure_recipient.encrypted_recipient_payload
        assert "TEST-TRACK-987654321" not in logistics.encrypted_tracking_number
        assert logistics.tracking_number_masked.endswith("4321")
        assert inquiry.customer_display_masked == "Fi***" and inquiry.content_available is True
        state_durations = {
            item.resource_type: int((item.expires_at - item.source_observed_at).total_seconds())
            for item in db.scalars(select(PxgNaverReadonlyRecordState).where(
                PxgNaverReadonlyRecordState.store_id == store.id,
            )).all()
        }
        assert state_durations["product"] == 6 * 60 * 60
        assert state_durations["order"] == 15 * 60
        assert state_durations["recipient"] == 15 * 60
        assert state_durations["logistics"] == 30 * 60
        assert state_durations["customer_inquiry"] == 7 * 60
        assert int((secure_recipient.expires_at - secure_recipient.source_observed_at).total_seconds()) == 15 * 60
        assert int((logistics.expires_at - logistics.source_observed_at).total_seconds()) == 30 * 60

        # Verify the success transaction from an independent session, rather than
        # relying on the writer's SQLAlchemy identity map.
        with SessionLocal() as fresh_db:
            assert fresh_db.query(Product).filter(Product.store_id == store.id).count() == 1
            assert fresh_db.query(Order).filter(Order.store_id == store.id).count() == 1
            assert fresh_db.query(PxgNaverReadonlyLogisticsRecord).filter(
                PxgNaverReadonlyLogisticsRecord.store_id == store.id,
            ).count() == 1
            assert fresh_db.query(OperationAuditLog).filter(OperationAuditLog.store_id == store.id).count() == 1

        ordinary_orders = order_service.list_orders(db, store_id=store.id, platform="naver", include_test_orders=True)
        operations_orders = order_service.list_operations_orders(db, store_id=store.id, platform="naver", include_test_orders=True)
        summary = readonly_local_summary(db, store_id=store.id, settings=get_settings())
        assert_not_contains(ordinary_orders, "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road")
        assert_not_contains(operations_orders, "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road")
        assert operations_orders[0]["receiver_name"] == ""
        assert_not_contains(summary, "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road", "TEST-TRACK-987654321")
        assert summary["logistics"][0]["tracking_number_masked"].endswith("4321")
        assert summary["customer_inquiries"][0]["customer_display_masked"] == "Fi***"
        assert summary["orders"][0]["source_updated_at"] is not None
        assert summary["orders"][0]["expires_at"] is not None

        duplicate = persist_pxg_naver_readonly_adapter_batch(
            db,
            settings=get_settings(),
            batch=batch,
            actor_id=admin.user_key_hash,
            manual_approval=True,
        )
        for resource in ("products", "orders", "logistics", "customer_inquiries"):
            assert duplicate["counts"][resource].get("unchanged") == 1, duplicate
        assert db.query(Product).filter(Product.store_id == store.id).count() == 1
        assert db.query(Order).filter(Order.store_id == store.id).count() == 1
        assert db.query(PxgNaverReadonlyLogisticsRecord).filter(PxgNaverReadonlyLogisticsRecord.store_id == store.id).count() == 1
        assert db.query(PxgNaverReadonlyCustomerInquiry).filter(PxgNaverReadonlyCustomerInquiry.store_id == store.id).count() == 1

        multi_item_payload = copy.deepcopy(payload)
        second_order = copy.deepcopy(multi_item_payload["orders"][0])
        second_order["external_product_order_id"] = "fixture-product-order-002"
        second_order["source_updated_at"] = "2026-07-12T08:05:00+00:00"
        second_order["recipient"]["receiver_name"] = "Second Fictional Recipient"
        multi_item_payload["orders"].append(second_order)
        second_logistics = copy.deepcopy(multi_item_payload["logistics"][0])
        second_logistics["external_product_order_id"] = "fixture-product-order-002"
        second_logistics["tracking_number"] = "TEST-TRACK-SECOND-1234"
        second_logistics["source_updated_at"] = "2026-07-12T08:05:00+00:00"
        multi_item_payload["logistics"].append(second_logistics)
        multi_result = persist_pxg_naver_readonly_adapter_batch(
            db,
            settings=get_settings(),
            batch=PxgNaverReadonlyAdapterBatch.model_validate(multi_item_payload),
            actor_id=admin.user_key_hash,
            manual_approval=True,
        )
        assert multi_result["counts"]["orders"].get("created") == 1, multi_result
        assert multi_result["counts"]["logistics"].get("created") == 1, multi_result
        same_platform_order = db.scalars(select(Order).where(
            Order.store_id == store.id,
            Order.external_order_id == "fixture-order-001",
        ).order_by(Order.external_product_order_id.asc())).all()
        assert [item.external_product_order_id for item in same_platform_order] == [
            "fixture-product-order-001", "fixture-product-order-002",
        ]

        old_payload = copy.deepcopy(payload)
        old_payload["orders"][0]["product_name"] = "Attempted old overwrite"
        old_payload["orders"][0]["source_updated_at"] = "2026-07-11T08:00:00+00:00"
        old_result = persist_pxg_naver_readonly_adapter_batch(
            db,
            settings=get_settings(),
            batch=PxgNaverReadonlyAdapterBatch.model_validate(old_payload),
            actor_id=admin.user_key_hash,
            manual_approval=True,
        )
        assert old_result["counts"]["orders"].get("older_source") == 1, old_result
        db.refresh(order)
        assert order.product_name == "PXG Fictional Carry Bag"

        cross_store_payload = copy.deepcopy(payload)
        cross_store_payload["store_id"] = other_store.id
        try:
            persist_pxg_naver_readonly_adapter_batch(
                db,
                settings=get_settings(),
                batch=PxgNaverReadonlyAdapterBatch.model_validate(cross_store_payload),
                actor_id=admin.user_key_hash,
                manual_approval=True,
            )
            raise AssertionError("cross-store persistence should be rejected")
        except ApiError as exc:
            assert exc.error_code == "readonly_persistence_store_mismatch", exc

        marked = mark_pxg_naver_readonly_stale(
            db,
            store_id=store.id,
            settings=get_settings(),
            now=order.last_synced_at + timedelta(hours=48),
        )
        assert marked >= 4
        db.commit()
        stale_summary = readonly_local_summary(db, store_id=store.id, settings=get_settings())
        assert stale_summary["orders"][0]["is_stale"] is True
        assert stale_summary["freshness"]["stale_warning_count"] >= 4
        assert db.query(Order).filter(Order.store_id == store.id).count() == 2
        assert retention_cleanup_status(get_settings())["automatic_cleanup_enabled"] is False

        refreshed = persist_pxg_naver_readonly_adapter_batch(
            db,
            settings=get_settings(),
            batch=batch,
            actor_id=admin.user_key_hash,
            manual_approval=True,
        )
        assert refreshed["counts"]["orders"].get("unchanged") == 1
        db.refresh(secure_recipient)
        assert secure_recipient.is_stale is False

        db.add(LogisticsInventoryMapping(
            store_id=store.id,
            platform="naver",
            match_product_name="PXG Fictional Carry Bag",
            match_option_name="",
            normalized_product_name=shipping_service._normalize_key_part("PXG Fictional Carry Bag"),
            normalized_option_name="",
            internal_sku="PXG-FIX-001",
            logistics_inventory_code="WH-PXG-FIX-001",
            match_priority=1,
            is_active=True,
        ))
        db.commit()
        actor = {"role": "operator", "actor_id": admin.user_key_hash}
        batch_result = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=store.id,
            platform="naver",
            order_ids=[order.id],
            manual_approval=True,
            actor_context=actor,
        )
        assert batch_result["status"] == "created", batch_result
        batch_id = batch_result["batch"]["id"]
        approval = warehouse_shipping_service.issue_approval_grant(
            db,
            batch_id=batch_id,
            user_id=admin.id,
            grant_scope="manifest",
        )
        manifest = warehouse_shipping_service.download_warehouse_manifest(
            db,
            batch_id=batch_id,
            manual_approval=True,
            privacy_access_acknowledged=True,
            actor_context=actor,
        )
        assert approval["status"] == "approval_granted" and manifest["status"] == "warehouse_manifest_ready"
        with ZipFile(BytesIO(base64.b64decode(manifest["file_content_base64"]))) as archive:
            warehouse_sheet = archive.read("xl/worksheets/sheet1.xml")
        assert b"Fictional Recipient" in warehouse_sheet
        assert b"Fictional Seoul Road 1" in warehouse_sheet

        second_local_order = db.scalar(select(Order).where(
            Order.store_id == store.id,
            Order.external_product_order_id == "fixture-product-order-002",
        ))
        assert second_local_order is not None
        stale_batch = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=store.id,
            platform="naver",
            order_ids=[second_local_order.id],
            manual_approval=True,
            actor_context=actor,
        )
        assert stale_batch["status"] == "created", stale_batch
        stale_batch_id = stale_batch["batch"]["id"]
        stale_approval = warehouse_shipping_service.issue_approval_grant(
            db,
            batch_id=stale_batch_id,
            user_id=admin.id,
            grant_scope="manifest",
        )
        assert stale_approval == {"status": "blocked", "skip_reason": "recipient_data_stale"}, stale_approval
        stale_manifest = warehouse_shipping_service.download_warehouse_manifest(
            db,
            batch_id=stale_batch_id,
            manual_approval=True,
            privacy_access_acknowledged=True,
            actor_context=actor,
        )
        assert stale_manifest == {"status": "blocked", "skip_reason": "recipient_data_stale"}, stale_manifest

        audits = db.scalars(select(OperationAuditLog).where(OperationAuditLog.store_id == store.id)).all()
        assert audits
        assert_not_contains(audits, "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road", "TEST-TRACK-987654321")
        assert db.query(PxgNaverReadonlyRecordState).filter(PxgNaverReadonlyRecordState.store_id == store.id).count() >= 4

        with TestClient(app) as client:
            ordinary_response = client.get(
                f"/api/v1/pxg-naver-readonly/local-summary?store_id={store.id}",
                headers={"X-ERP-User-Key": operator.user_key_hash},
            )
            assert ordinary_response.status_code == 200, ordinary_response.text
            assert_not_contains(ordinary_response.json(), "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road", "TEST-TRACK-987654321")

            operations_response = client.get(
                f"/api/v1/orders/operations?store_id={store.id}&platform=naver",
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert operations_response.status_code == 200, operations_response.text
            assert_not_contains(operations_response.json(), "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road")

            forbidden_write = client.post(
                "/api/v1/pxg-naver-readonly/refresh",
                json={"manual_approval": True},
                headers={"X-ERP-User-Key": operator.user_key_hash},
            )
            assert forbidden_write.status_code == 403, forbidden_write.text

            removed_persist_endpoint = client.post(
                "/api/v1/pxg-naver-readonly/persist",
                json={"manual_approval": True},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert removed_persist_endpoint.status_code == 404, removed_persist_endpoint.text

            cross_store_read = client.get(
                f"/api/v1/pxg-naver-readonly/local-summary?store_id={store.id}",
                headers={"X-ERP-User-Key": other_admin.user_key_hash},
            )
            assert cross_store_read.status_code == 403, cross_store_read.text

            invalid_response = client.post(
                "/api/v1/pxg-naver-readonly/refresh",
                json={"manual_approval": True, "orders": payload["orders"]},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert invalid_response.status_code == 400, invalid_response.text
            assert_not_contains(invalid_response.json(), "Fictional Recipient")

            disabled_refresh = client.post(
                "/api/v1/pxg-naver-readonly/refresh",
                json={"manual_approval": True},
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert disabled_refresh.status_code == 403, disabled_refresh.text

        assert db.query(OperationAuditLog).filter(OperationAuditLog.store_id == store.id).count() >= 4

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_readonly_persistence: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        engine.dispose()
        if TEMP_DB.exists():
            try:
                TEMP_DB.unlink()
            except PermissionError:
                pass
