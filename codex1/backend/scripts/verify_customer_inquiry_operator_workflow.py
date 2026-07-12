import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-customer-inquiry-operator-workflow.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["APP_ENV"] = "test"
os.environ["ALLOW_DEV_AUTH"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["SESSION_TOKEN_PEPPER"] = "test-only-session-pepper-32-characters-minimum"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["CORS_ALLOWED_ORIGINS"] = '["https://erp.test"]'
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"
os.environ["OPERATOR_TRIAL_REAL_READ_ENABLED"] = "false"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyCustomerInquiry, PxgNaverReadonlyLogisticsRecord
from app.models.store import Store
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T10-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _create_user(db, *, login_identifier: str, role: ErpRole, store_id: int) -> None:
    user = ErpUser(
        user_key_hash=f"customer-inquiry-{login_identifier}-hash",
        display_name="Test Operator",
        login_identifier_hash=hash_login_identifier(login_identifier),
        login_identifier_masked="t***@example.test",
        status="active",
        auth_provider="password",
    )
    db.add(user)
    db.flush()
    db.add(ErpUserSecurity(
        user_id=user.id,
        password_hash=hash_password(PASSWORD),
        mfa_type="totp",
        mfa_secret_encrypted=encrypt_value(TOTP_SECRET),
        mfa_enabled_at=get_utc_now(),
        password_changed_at=get_utc_now(),
    ))
    db.add(ErpStoreMembership(user_id=user.id, store_id=store_id, role_id=role.id, membership_status="active"))


def seed() -> None:
    Base.metadata.create_all(engine)
    now = get_utc_now()
    with SessionLocal() as db:
        store = Store(name="Customer Inquiry Test Store", platform="naver", status="active")
        other_store = Store(name="Other Store", platform="naver", status="active")
        permitted_role = ErpRole(role_key="customer_inquiry_reader", role_label_zh="test", role_label_en="test", status="active")
        denied_role = ErpRole(role_key="customer_inquiry_denied", role_label_zh="test", role_label_en="test", status="active")
        orders_read = ErpPermission(permission_key="orders.read", permission_group="orders", permission_label_zh="test")
        customer_reply = ErpPermission(
            permission_key="customer.inquiries.reply",
            permission_group="customer",
            permission_label_zh="test",
        )
        db.add_all([store, other_store, permitted_role, denied_role, orders_read, customer_reply])
        db.flush()
        db.add(ErpRolePermission(role_id=permitted_role.id, permission_id=orders_read.id))
        db.add(ErpRolePermission(role_id=permitted_role.id, permission_id=customer_reply.id))
        _create_user(db, login_identifier="reader@example.test", role=permitted_role, store_id=store.id)
        _create_user(db, login_identifier="denied@example.test", role=denied_role, store_id=store.id)

        order = Order(
            store_id=store.id,
            platform="naver",
            external_order_id="ORDER-1",
            external_product_order_id="PRODUCT-1",
            product_name="PXG Golf Bag",
            quantity=1,
            order_amount=0,
            currency="KRW",
            order_status="paid",
            ordered_at=now,
            source_type="pxg_naver_readonly_local_v1",
        )
        db.add(order)
        db.flush()
        db.add(PxgNaverReadonlyLogisticsRecord(
            order_id=order.id,
            store_id=store.id,
            platform="naver",
            carrier="CJ",
            encrypted_tracking_number="test-only-encrypted-tracking",
            tracking_number_hash="a" * 64,
            tracking_number_masked="1234****7890",
            shipment_status="in_transit",
            shipped_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=30),
        ))
        db.add(CustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id="generic-1",
            inquiry_type="delivery",
            customer_name="Full Customer Name",
            title="Delivery status for ORDER-1",
            content="Call 010-1234-5678 and send the package to the full recipient address.",
            status="open",
            received_at=now,
            raw_data={"order_id": "ORDER-1", "recipient_phone": "010-1234-5678"},
        ))
        db.add(PxgNaverReadonlyCustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id_hash="b" * 64,
            related_order_id=order.id,
            inquiry_type="delivery",
            status="open",
            customer_display_masked="K**",
            subject_category="delivery_status",
            content_available=False,
            received_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=15),
        ))
        db.add(PxgNaverReadonlyCustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id_hash="c" * 64,
            related_order_id=None,
            inquiry_type="product",
            status="open",
            customer_display_masked="P**",
            subject_category="product_question",
            content_available=False,
            received_at=now,
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=15),
        ))
        db.commit()


def authenticate(client: TestClient, login_identifier: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"login_identifier": login_identifier, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/mfa/verify",
        headers={"Origin": ORIGIN},
        json={"code": generate_totp(TOTP_SECRET)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["csrf_token"]


def main() -> None:
    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        missing_session = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert missing_session.status_code == 401 and missing_session.json()["error_code"] == "session_required", missing_session.text

        pending_mfa = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_identifier": "reader@example.test", "password": PASSWORD},
        )
        assert pending_mfa.status_code == 200, pending_mfa.text
        mfa_required = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert mfa_required.status_code == 403 and mfa_required.json()["error_code"] == "mfa_required", mfa_required.text

        client.cookies.clear()
        csrf = authenticate(client, "reader@example.test")
        response = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert response.status_code == 200, response.text
        items = response.json()["data"]["items"]
        assert len(items) == 3, items
        assert len({item["inquiry_id"] for item in items}) == 3, items
        assert {item["source"] for item in items} == {"generic", "pxg_naver_readonly_local_v1"}, items
        assert all(item["store_id"] == 1 for item in items), items
        assert all(set(item) >= {"source", "inquiry_id", "category", "inquiry_type", "status", "summary", "created_at", "updated_at", "store_id", "order_context", "logistics_context", "reply_enabled"} for item in items), items
        assert all("customer_name" not in item and "raw_data" not in item and "content" not in item for item in items), items
        assert "Full Customer Name" not in response.text and "010-1234-5678" not in response.text, response.text
        assert "test-only-encrypted-tracking" not in response.text, response.text
        pxg_item = next(item for item in items if item["source"] == "pxg_naver_readonly_local_v1")
        assert pxg_item["reply_enabled"] is False and pxg_item["reply_disabled_reason"] == "readonly_source", pxg_item
        assert pxg_item["order_context"]["order_no"] == "ORDER-1", pxg_item
        assert pxg_item["logistics_context"]["tracking_number_masked"] == "1234****7890", pxg_item
        no_context_item = next(item for item in items if item["category"] == "product_question")
        assert no_context_item["order_context"] == {} and no_context_item["logistics_context"] == {}, no_context_item

        repeated = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["data"]["items"] == items, repeated.text
        no_match = client.get("/api/v1/customer-inquiries", params={"store_id": 1, "platform": "coupang"})
        assert no_match.status_code == 200 and no_match.json()["data"]["items"] == [], no_match.text
        cross_store = client.get("/api/v1/customer-inquiries", params={"store_id": 2})
        assert cross_store.status_code == 403, cross_store.text
        disabled_reply = client.post(
            "/api/v1/sync/customer-inquiries/naver/reply",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"store_id": 1, "inquiry_id": pxg_item["inquiry_id"], "content": "should not send"},
        )
        assert disabled_reply.status_code == 403 and disabled_reply.json()["error_code"] == "legacy_platform_write_disabled", disabled_reply.text

        client.cookies.clear()
        authenticate(client, "denied@example.test")
        no_permission = client.get("/api/v1/customer-inquiries", params={"store_id": 1})
        assert no_permission.status_code == 403, no_permission.text

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_customer_inquiry_operator_workflow: ok")


if __name__ == "__main__":
    main()
