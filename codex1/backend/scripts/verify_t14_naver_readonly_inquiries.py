import os
import sys
import tempfile
import shutil
import sqlite3
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet


DB_PATH = Path(tempfile.gettempdir()) / "verify-t14-naver-readonly-inquiries.db"
DB_PATH.unlink(missing_ok=True)
os.environ.update({
    "APP_ENV": "test",
    "ALLOW_DEV_AUTH": "false",
    "DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "SESSION_TOKEN_PEPPER": "t14-session-pepper-with-at-least-32-characters",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "CORS_ALLOWED_ORIGINS": '["https://erp.test"]',
    "PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED": "true",
})

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.timezone import get_utc_now
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.api_credential import ApiCredential
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyCustomerInquiry, PxgNaverReadonlySyncControl
from app.models.store import Store
from app.services import api_credential_readiness_service, sync_service
from app.services.naver_readonly_inquiry_service import _related_order, _upsert_item
from app.services.encryption import encrypt_value
from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T14-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
CONTENT = "Customer contact must not appear in a list response."


def _user(db, login, role, store):
    user = ErpUser(user_key_hash=f"t14-{login}", display_name="T14", login_identifier_hash=hash_login_identifier(login), login_identifier_masked="t***", status="active", auth_provider="password")
    db.add(user); db.flush()
    db.add(ErpUserSecurity(user_id=user.id, password_hash=hash_password(PASSWORD), mfa_type="totp", mfa_secret_encrypted=encrypt_value(TOTP_SECRET), mfa_enabled_at=get_utc_now(), password_changed_at=get_utc_now()))
    db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))


def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        one, two = Store(name="T14 One", platform="naver", status="active"), Store(name="T14 Two", platform="naver", status="active")
        full, denied = ErpRole(role_key="t14-full", role_label_zh="t", role_label_en="t", status="active"), ErpRole(role_key="t14-denied", role_label_zh="t", role_label_en="t", status="active")
        read = ErpPermission(permission_key="orders.read", permission_group="t", permission_label_zh="t")
        sync = ErpPermission(permission_key="platform.sync", permission_group="t", permission_label_zh="t")
        content = ErpPermission(permission_key="customer.inquiries.content.read", permission_group="t", permission_label_zh="t")
        db.add_all([one, two, full, denied, read, sync, content]); db.flush()
        for permission in (read, sync, content): db.add(ErpRolePermission(role_id=full.id, permission_id=permission.id))
        db.add(ErpRolePermission(role_id=denied.id, permission_id=read.id))
        _user(db, "full@example.test", full, one); _user(db, "denied@example.test", denied, one); _user(db, "other@example.test", full, two)
        for store in (one, two):
            db.add(ApiCredential(store_id=store.id, platform="naver", credential_name="t14", client_id="id", encrypted_secret_key=encrypt_value("secret"), status="active"))
            db.add(PxgNaverReadonlyCleanupStatus(store_id=store.id, platform="naver", status="healthy", last_run_at=get_utc_now(), last_success_at=get_utc_now()))
        db.commit()


def auth(client, login):
    assert client.post("/api/v1/auth/login", headers={"Origin": ORIGIN}, json={"login_identifier": login, "password": PASSWORD}).status_code == 200
    response = client.post("/api/v1/auth/mfa/verify", headers={"Origin": ORIGIN}, json={"code": generate_totp(TOTP_SECRET)})
    assert response.status_code == 200, response.text
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["data"]["csrf_token"]}


def main():
    seed()
    original_context, original_token, original_request = sync_service._build_naver_token_context_from_credential, api_credential_readiness_service._request_naver_token_from_context, sync_service._request_naver_customer_inquiries
    sync_service._build_naver_token_context_from_credential = lambda _credential: {"api_base": "https://test.invalid"}
    api_credential_readiness_service._request_naver_token_from_context = lambda _context: ("test-token", 200)
    calls = {"reply": 0}
    def paged_request(**kwargs):
        page = kwargs["page"]
        if page == 1:
            return {"success": True, "payload": {"content": [
                {"inquiryNo": "i-1", "customerName": "Kim", "title": "Private title", "inquiryContent": CONTENT, "category": "delivery", "answered": False, "createdAt": "2026-07-01T00:00:00+00:00"},
                *[{"inquiryNo": f"page-one-{index}", "inquiryContent": "x", "createdAt": "2026-07-01T00:00:00+00:00"} for index in range(1, 50)],
            ]}}
        if page == 2:
            return {"success": True, "payload": {"content": [{"inquiryNo": "page-two", "inquiryContent": "y", "createdAt": "2026-07-01T00:00:00+00:00"}]}}
        raise AssertionError(f"unexpected page {page}")
    sync_service._request_naver_customer_inquiries = paged_request
    try:
        client = TestClient(app, base_url=ORIGIN)
        headers = auth(client, "full@example.test")
        refreshed = client.post("/api/v1/customer-inquiries/naver/refresh", params={"store_id": 1}, headers=headers)
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["data"]["pages_read"] == 2, refreshed.text
        again = client.post("/api/v1/customer-inquiries/naver/refresh", params={"store_id": 1}, headers=headers)
        assert again.json()["data"]["created_count"] == 0 and again.json()["data"]["skipped_count"] == 51, again.text
        repeated_page = [{"inquiryNo": f"repeat-{index}", "inquiryContent": "z", "createdAt": "2026-07-01T00:00:00+00:00"} for index in range(50)]
        sync_service._request_naver_customer_inquiries = lambda **kwargs: {"success": True, "payload": {"content": repeated_page}}
        repeated = client.post("/api/v1/customer-inquiries/naver/refresh", params={"store_id": 1}, headers=headers)
        assert repeated.status_code == 200 and repeated.json()["data"]["pages_read"] == 1, repeated.text
        sync_service._request_naver_customer_inquiries = paged_request
        with SessionLocal() as db:
            record = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(PxgNaverReadonlyCustomerInquiry.store_id == 1))
            assert record and record.encrypted_content and CONTENT not in record.encrypted_content and record.content_hash and record.content_length == len(CONTENT)
            assert db.scalar(select(CustomerInquiry.id).where(CustomerInquiry.store_id == 1)) is None
            readonly_id, deadline = record.id, record.expires_at
            # The local SQLite source and a raw copy contain ciphertext only.
            backup_copy = DB_PATH.with_suffix(".backup.sqlite")
            shutil.copy2(DB_PATH, backup_copy)
            assert CONTENT.encode("utf-8") not in backup_copy.read_bytes()
            backup_copy.unlink()
        listed = client.get("/api/v1/customer-inquiries", params={"store_id": 1}, headers=headers)
        assert listed.status_code == 200 and CONTENT not in listed.text and "Private title" not in listed.text, listed.text
        detail = client.get(f"/api/v1/customer-inquiries/{readonly_id}", params={"store_id": 1}, headers=headers)
        assert detail.status_code == 200 and detail.json()["data"]["content"] == CONTENT, detail.text
        assert client.get(f"/api/v1/customer-inquiries/{readonly_id}", params={"store_id": 2}, headers=headers).status_code == 403
        denied_headers = auth(client, "denied@example.test")
        assert client.get(f"/api/v1/customer-inquiries/{readonly_id}", params={"store_id": 1}, headers=denied_headers).status_code == 403
        headers = auth(client, "full@example.test")
        with SessionLocal() as db:
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(PxgNaverReadonlyCleanupStatus.store_id == 1)); status.status = "failed"; db.commit()
        assert client.get(f"/api/v1/customer-inquiries/{readonly_id}", params={"store_id": 1}, headers=headers).status_code == 409
        with SessionLocal() as db:
            status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(PxgNaverReadonlyCleanupStatus.store_id == 1)); status.status = "healthy"; status.last_success_at = get_utc_now(); db.commit()
            db.add(PxgNaverReadonlySyncControl(store_id=1, platform="naver", write_and_refresh_blocked=True, reason_code="test_lock")); db.commit()
        assert client.get(f"/api/v1/customer-inquiries/{readonly_id}", params={"store_id": 1}, headers=headers).status_code == 409
        with SessionLocal() as db:
            control = db.scalar(select(PxgNaverReadonlySyncControl).where(PxgNaverReadonlySyncControl.store_id == 1)); control.write_and_refresh_blocked = False; control.reason_code = None; db.commit()
        batch = client.post("/api/v1/sync/manual-batch", headers=headers, json={"store_id": 1, "platforms": ["naver"], "include_products": False, "include_orders": False, "include_customer_inquiries": True})
        assert batch.status_code == 200 and batch.json()["data"]["items"][0]["status"] == "success", batch.text
        legacy = client.post("/api/v1/sync/customer-inquiries/naver", headers=headers, json={"store_id": 1})
        assert legacy.status_code == 403 and legacy.json()["error_code"] in {"legacy_platform_write_disabled", "legacy_naver_customer_inquiry_sync_disabled"}, legacy.text
        with SessionLocal() as db:
            record = db.get(PxgNaverReadonlyCustomerInquiry, readonly_id)
            assert record.expires_at == deadline and calls["reply"] == 0
            now = get_utc_now()
            product_order = Order(store_id=1, platform="naver", external_order_id="order-product", external_product_order_id="product-preferred", product_name="t", quantity=1, order_amount=0, currency="KRW", order_status="paid", ordered_at=now)
            order_fallback = Order(store_id=1, platform="naver", external_order_id="order-fallback", external_product_order_id="product-fallback", product_name="t", quantity=1, order_amount=0, currency="KRW", order_status="paid", ordered_at=now)
            db.add_all([product_order, order_fallback]); db.flush()
            assert _related_order(db, 1, {"productOrderIdList": ["product-preferred"], "orderId": "order-fallback"}).id == product_order.id
            assert _related_order(db, 1, {"productOrderIdList": ["missing"], "orderId": "order-fallback"}).id == order_fallback.id
            initial = {"inquiryNo": "ordering", "inquiryContent": "first", "title": "t", "createdAt": "2026-07-01T00:00:00+00:00"}
            assert _upsert_item(db, store_id=1, item=initial, observed_at=now) == "created"
            db.flush()
            ordering = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(PxgNaverReadonlyCustomerInquiry.external_inquiry_id_hash == __import__("hashlib").sha256(b"customer-inquiry:ordering").hexdigest()))
            ciphertext = ordering.encrypted_content
            ordering.expires_at = now + timedelta(days=90)
            assert _upsert_item(db, store_id=1, item=initial, observed_at=now + timedelta(minutes=1)) == "skipped"
            assert ordering.encrypted_content == ciphertext
            older = {**initial, "inquiryContent": "older", "createdAt": "2026-06-30T00:00:00+00:00"}
            assert _upsert_item(db, store_id=1, item=older, observed_at=now + timedelta(minutes=2)) == "skipped"
            newer = {**initial, "inquiryContent": "newer", "createdAt": "2026-07-02T00:00:00+00:00"}
            assert _upsert_item(db, store_id=1, item=newer, observed_at=now + timedelta(minutes=3)) == "updated"
            assert ordering.expires_at.replace(tzinfo=None) <= ordering.created_at.replace(tzinfo=None) + timedelta(days=30)
            try:
                _upsert_item(db, store_id=1, item={**newer, "inquiryContent": "conflict"}, observed_at=now + timedelta(minutes=4))
            except Exception as exc:
                assert getattr(exc, "error_code", None) == "readonly_inquiry_source_conflict"
            else:
                raise AssertionError("same-source timestamp conflict must fail closed")
            db.rollback()
        legacy_path = Path(tempfile.gettempdir()) / "verify-t14-legacy-inquiry-schema.db"
        legacy_path.unlink(missing_ok=True)
        connection = sqlite3.connect(legacy_path)
        connection.executescript("""
            CREATE TABLE pxg_naver_readonly_sync_backups (id INTEGER PRIMARY KEY, baseline_manifest JSON);
            CREATE TABLE pxg_naver_order_recipient_secure_records (id INTEGER PRIMARY KEY);
            CREATE TABLE pxg_naver_readonly_customer_inquiries (id INTEGER PRIMARY KEY);
        """)
        from scripts.upgrade_pxg_naver_readonly_schema import _upgrade_existing_sync_backup_columns
        _upgrade_existing_sync_backup_columns(connection)
        assert {"encrypted_content", "encrypted_title", "content_hash", "content_length"} <= {row[1] for row in connection.execute("PRAGMA table_info(pxg_naver_readonly_customer_inquiries)")}
        connection.close(); legacy_path.unlink()
        print("verify_t14_naver_readonly_inquiries: ok")
    finally:
        sync_service._build_naver_token_context_from_credential, api_credential_readiness_service._request_naver_token_from_context, sync_service._request_naver_customer_inquiries = original_context, original_token, original_request


if __name__ == "__main__": main()
