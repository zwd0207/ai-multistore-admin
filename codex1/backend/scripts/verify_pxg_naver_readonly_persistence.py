import base64
import copy
import json
import os
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
os.environ["PXG_NAVER_LOCAL_READ_STALE_AFTER_HOURS"] = "24"
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
    persist_pxg_naver_readonly_candidates,
    readonly_local_summary,
    retention_cleanup_status,
)
from app.schemas.pxg_naver_readonly import parse_pxg_naver_readonly_persistence_request


def fixture(store_id: int) -> dict:
    return {
        "store_id": store_id,
        "platform": "naver",
        "source_mode": "fictional_test",
        "manual_approval": True,
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


def main() -> None:
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
        parsed = parse_pxg_naver_readonly_persistence_request(payload)

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
            persist_pxg_naver_readonly_candidates(
                db,
                settings=disabled_settings,
                request=parsed,
                actor_id=admin.user_key_hash,
            )
            raise AssertionError("default-disabled persistence should be rejected")
        except ApiError as exc:
            assert exc.error_code == "readonly_local_persistence_disabled", exc

        result = persist_pxg_naver_readonly_candidates(
            db,
            settings=get_settings(),
            request=parsed,
            actor_id=admin.user_key_hash,
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

        duplicate = persist_pxg_naver_readonly_candidates(
            db,
            settings=get_settings(),
            request=parsed,
            actor_id=admin.user_key_hash,
        )
        for resource in ("products", "orders", "logistics", "customer_inquiries"):
            assert duplicate["counts"][resource].get("unchanged") == 1, duplicate
        assert db.query(Product).filter(Product.store_id == store.id).count() == 1
        assert db.query(Order).filter(Order.store_id == store.id).count() == 1
        assert db.query(PxgNaverReadonlyLogisticsRecord).filter(PxgNaverReadonlyLogisticsRecord.store_id == store.id).count() == 1
        assert db.query(PxgNaverReadonlyCustomerInquiry).filter(PxgNaverReadonlyCustomerInquiry.store_id == store.id).count() == 1

        old_payload = copy.deepcopy(payload)
        old_payload["orders"][0]["product_name"] = "Attempted old overwrite"
        old_payload["orders"][0]["source_updated_at"] = "2026-07-11T08:00:00+00:00"
        old_result = persist_pxg_naver_readonly_candidates(
            db,
            settings=get_settings(),
            request=parse_pxg_naver_readonly_persistence_request(old_payload),
            actor_id=admin.user_key_hash,
        )
        assert old_result["counts"]["orders"].get("older_source") == 1, old_result
        db.refresh(order)
        assert order.product_name == "PXG Fictional Carry Bag"

        cross_store_payload = copy.deepcopy(payload)
        cross_store_payload["store_id"] = other_store.id
        try:
            persist_pxg_naver_readonly_candidates(
                db,
                settings=get_settings(),
                request=parse_pxg_naver_readonly_persistence_request(cross_store_payload),
                actor_id=admin.user_key_hash,
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
        assert db.query(Order).filter(Order.store_id == store.id).count() == 1
        assert retention_cleanup_status(get_settings())["automatic_cleanup_enabled"] is False

        refreshed = persist_pxg_naver_readonly_candidates(
            db,
            settings=get_settings(),
            request=parsed,
            actor_id=admin.user_key_hash,
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

        audits = db.scalars(select(OperationAuditLog).where(OperationAuditLog.store_id == store.id)).all()
        assert audits
        assert_not_contains(audits, "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road", "TEST-TRACK-987654321")
        assert db.query(PxgNaverReadonlyRecordState).filter(PxgNaverReadonlyRecordState.store_id == store.id).count() >= 4

        unsafe_payload = copy.deepcopy(payload)
        unsafe_payload["raw_response"] = {"unsafe": "Fictional Recipient"}
        before_orders = db.query(Order).filter(Order.store_id == store.id).count()
        try:
            persist_pxg_naver_readonly_candidates(
                db,
                settings=get_settings(),
                request=unsafe_payload,
                actor_id=admin.user_key_hash,
            )
            raise AssertionError("raw response input should be rejected")
        except ApiError as exc:
            assert exc.error_code == "readonly_persistence_payload_invalid", exc
        assert db.query(Order).filter(Order.store_id == store.id).count() == before_orders

        unsafe_inquiry_payload = copy.deepcopy(payload)
        unsafe_inquiry_payload["customer_inquiries"][0]["subject_category"] = "call 010-5555-1234"
        try:
            parse_pxg_naver_readonly_persistence_request(unsafe_inquiry_payload)
            raise AssertionError("customer inquiry free text should be rejected")
        except ApiError as exc:
            assert exc.error_code == "readonly_persistence_payload_invalid", exc

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
                "/api/v1/pxg-naver-readonly/persist",
                json=payload,
                headers={"X-ERP-User-Key": operator.user_key_hash},
            )
            assert forbidden_write.status_code == 403, forbidden_write.text

            cross_store_read = client.get(
                f"/api/v1/pxg-naver-readonly/local-summary?store_id={store.id}",
                headers={"X-ERP-User-Key": other_admin.user_key_hash},
            )
            assert cross_store_read.status_code == 403, cross_store_read.text

            invalid_response = client.post(
                "/api/v1/pxg-naver-readonly/persist",
                json=unsafe_payload,
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert invalid_response.status_code == 400, invalid_response.text
            assert_not_contains(invalid_response.json(), "Fictional Recipient")

            accepted_response = client.post(
                "/api/v1/pxg-naver-readonly/persist",
                json=payload,
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert accepted_response.status_code == 200, accepted_response.text
            assert_not_contains(accepted_response.json(), "Fictional Recipient", "010-5555-1234", "Fictional Seoul Road", "TEST-TRACK-987654321")

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
