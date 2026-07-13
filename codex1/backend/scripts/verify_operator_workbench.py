import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-operator-workbench.db"
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
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_CLEANUP_ENABLED"] = "true"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.core.exceptions import ApiError
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.core.timezone import get_utc_now
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.database import Base, SessionLocal, engine
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.main import app
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser, ErpUserSecurity
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.customer_inquiry import CustomerInquiry
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.order import Order
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyCustomerInquiry
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.shipping import WarehouseShippingBatch, WarehouseShippingBatchOrder
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.store import Store
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.encryption import encrypt_value
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.session_service import generate_totp, hash_login_identifier, hash_password


ORIGIN = "https://erp.test"
PASSWORD = "T11-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
IDS: dict[str, int] = {}


def _create_user(db, *, login_identifier: str, role: ErpRole, store_id: int) -> None:
    user = ErpUser(
        user_key_hash=f"workbench-{login_identifier}-hash",
        display_name="Workbench Operator",
        login_identifier_hash=hash_login_identifier(login_identifier),
        login_identifier_masked="w***@example.test",
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


def _order(db, *, store_id: int, external_id: str, status: str, minutes_ago: int) -> Order:
    now = get_utc_now()
    row = Order(
        store_id=store_id,
        platform="naver",
        external_order_id=external_id,
        external_product_order_id=f"PRODUCT-{external_id}",
        buyer_name="Private Buyer Name",
        buyer_phone="010-1234-5678",
        buyer_masked_phone="010-****-5678",
        receiver_name="Private Receiver Name",
        receiver_phone="010-9999-8888",
        receiver_address="Full private recipient address",
        zip_code="12345",
        product_name=f"Product {external_id}",
        quantity=1,
        order_amount=1000,
        currency="KRW",
        order_status=status,
        ordered_at=now - timedelta(minutes=minutes_ago),
        source_type="pxg_naver_readonly_local_v1",
        last_synced_at=now,
    )
    db.add(row)
    db.flush()
    return row


def _batch(db, *, store_id: int, order: Order, code: str, status: str, row_status: str, completed=False) -> WarehouseShippingBatch:
    now = get_utc_now()
    batch = WarehouseShippingBatch(
        batch_no=code,
        store_id=store_id,
        platform="naver",
        status=status,
        warehouse_sent_at=now - timedelta(hours=1) if status != "created" else None,
        warehouse_returned_at=now - timedelta(minutes=30) if status in {"warehouse_returned", "ready_to_writeback", "completed"} else None,
        operator_confirmed_at=now - timedelta(minutes=20) if status in {"ready_to_writeback", "completed"} else None,
        completed_at=now if completed else None,
    )
    db.add(batch)
    db.flush()
    db.add(WarehouseShippingBatchOrder(
        batch_id=batch.id,
        local_order_id=order.id,
        store_id=store_id,
        platform="naver",
        order_reference=order.external_order_id,
        product_order_reference=order.external_product_order_id,
        product_name=order.product_name,
        quantity=1,
        pre_batch_order_status=order.order_status,
        row_status=row_status,
        is_active=not completed,
        active_lock="active" if not completed else None,
        failure_reason="test failure reason" if row_status in {"blocked", "platform_failed"} else None,
    ))
    return batch


def seed() -> None:
    Base.metadata.create_all(engine)
    now = get_utc_now()
    with SessionLocal() as db:
        store = Store(name="PXG Workbench Store", platform="naver", status="active")
        other_store = Store(name="Generic Workbench Store", platform="naver", status="active")
        operator_role = ErpRole(role_key="workbench_operator", role_label_zh="test", role_label_en="test", status="active")
        denied_role = ErpRole(role_key="workbench_denied", role_label_zh="test", role_label_en="test", status="active")
        permissions = [
            ErpPermission(permission_key="dashboard.read", permission_group="dashboard", permission_label_zh="test"),
            ErpPermission(permission_key="orders.read", permission_group="orders", permission_label_zh="test"),
            ErpPermission(permission_key="shipping.batch.manage", permission_group="shipping", permission_label_zh="test"),
        ]
        db.add_all([store, other_store, operator_role, denied_role, *permissions])
        db.flush()
        for permission in permissions:
            db.add(ErpRolePermission(role_id=operator_role.id, permission_id=permission.id))
        _create_user(db, login_identifier="operator@example.test", role=operator_role, store_id=store.id)
        _create_user(db, login_identifier="other@example.test", role=operator_role, store_id=other_store.id)
        _create_user(db, login_identifier="denied@example.test", role=denied_role, store_id=store.id)

        pending = _order(db, store_id=store.id, external_id="PENDING-1", status="paid", minutes_ago=20)
        abnormal = _order(db, store_id=store.id, external_id="ABNORMAL-1", status="cancelled", minutes_ago=50)
        waiting_order = _order(db, store_id=store.id, external_id="WAITING-1", status="paid", minutes_ago=80)
        review_order = _order(db, store_id=store.id, external_id="REVIEW-1", status="paid", minutes_ago=70)
        confirm_order = _order(db, store_id=store.id, external_id="CONFIRM-1", status="dispatched", minutes_ago=60)
        completed_order = _order(db, store_id=store.id, external_id="COMPLETE-1", status="dispatched", minutes_ago=120)

        waiting_batch = _batch(db, store_id=store.id, order=waiting_order, code="WB-WAITING", status="warehouse_sent", row_status="warehouse_sent")
        review_batch = _batch(db, store_id=store.id, order=review_order, code="WB-REVIEW", status="warehouse_returned", row_status="needs_confirmation")
        confirm_batch = _batch(db, store_id=store.id, order=confirm_order, code="WB-CONFIRM", status="ready_to_writeback", row_status="ready_for_writeback")
        completed_batch = _batch(db, store_id=store.id, order=completed_order, code="WB-COMPLETE", status="completed", row_status="platform_written", completed=True)

        generic = CustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id="GENERIC-OPEN",
            inquiry_type="delivery",
            customer_name="Private Customer",
            title="Private inquiry title",
            content="Private phone 010-1111-2222 and address",
            status="open",
            received_at=now - timedelta(minutes=10),
            raw_data={"is_test": True},
        )
        db.add(generic)
        db.flush()
        pxg = PxgNaverReadonlyCustomerInquiry(
            store_id=store.id,
            platform="naver",
            external_inquiry_id_hash="a" * 64,
            related_order_id=pending.id,
            inquiry_type="delivery",
            status="open",
            customer_display_masked="K**",
            subject_category="shipping_status",
            content_available=False,
            received_at=now - timedelta(minutes=5),
            source_updated_at=now,
            source_observed_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        db.add(pxg)
        db.add(PxgNaverReadonlyCleanupStatus(
            store_id=store.id,
            platform="naver",
            status="healthy",
            last_run_at=now,
            last_success_at=now,
        ))
        other_inquiry = CustomerInquiry(
            store_id=other_store.id,
            platform="naver",
            external_inquiry_id="OTHER-GENERIC",
            inquiry_type="product",
            title="Generic-only question",
            content="Safe generic-only fixture",
            status="open",
            received_at=now,
            raw_data={"is_test": True},
        )
        db.add(other_inquiry)
        db.commit()
        IDS.update({
            "store": store.id,
            "other_store": other_store.id,
            "pending": pending.id,
            "abnormal": abnormal.id,
            "waiting_batch": waiting_batch.id,
            "review_batch": review_batch.id,
            "confirm_batch": confirm_batch.id,
            "completed_batch": completed_batch.id,
            "generic_inquiry": generic.id,
        })


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
        missing_session = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["store"]})
        assert missing_session.status_code == 401, missing_session.text

        pending_mfa = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_identifier": "operator@example.test", "password": PASSWORD},
        )
        assert pending_mfa.status_code == 200, pending_mfa.text
        mfa_required = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["store"]})
        assert mfa_required.status_code == 403 and mfa_required.json()["error_code"] == "mfa_required", mfa_required.text

        client.cookies.clear()
        authenticate(client, "operator@example.test")
        response = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["store"], "include_test_orders": True})
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert set(data) >= {"store_count", "order_count", "recent_orders", "operator_workbench"}, data
        workbench = data["operator_workbench"]
        assert set(workbench) == {"summary", "sections", "sources"}, workbench
        assert set(workbench["summary"]) == {"urgent", "action_required", "waiting", "completed_today"}, workbench
        assert set(workbench["sections"]) == {"urgent", "action_required", "waiting", "completed_today"}, workbench
        assert set(workbench["sources"]) == {"orders", "shipping", "customer_inquiries"}, workbench

        tasks = sum(workbench["sections"].values(), [])
        assert len({item["task_id"] for item in tasks}) == len(tasks), tasks
        required_fields = {
            "task_id", "task_type", "priority", "title", "description", "status", "count",
            "action_path", "action_label", "related_order_id", "related_batch_id",
            "related_inquiry_id", "updated_at", "stale",
        }
        assert all(set(item) == required_fields for item in tasks), tasks
        task_types = {item["task_type"] for item in tasks}
        assert {
            "abnormal_order", "unbatched_shipment", "warehouse_waiting", "warehouse_review",
            "writeback_waiting", "customer_inquiry", "completed_batch",
        } <= task_types, task_types
        assert workbench["summary"] == {key: len(workbench["sections"][key]) for key in workbench["summary"]}, workbench
        assert all(item["priority"] >= tasks[index + 1]["priority"] for index, item in enumerate(tasks[:-1]) if item in workbench["sections"]["urgent"] and tasks[index + 1] in workbench["sections"]["urgent"]), tasks
        assert workbench["sources"]["customer_inquiries"]["status"] == "ready", workbench
        assert f"batchId={IDS['review_batch']}" in next(item for item in tasks if item["task_type"] == "warehouse_review")["action_path"]
        assert f"orderId={IDS['abnormal']}" in next(item for item in tasks if item["task_type"] == "abnormal_order")["action_path"]
        response_text = response.text
        for secret in ["Private Buyer Name", "010-1234-5678", "Private Receiver Name", "010-9999-8888", "Full private recipient address", "010-1111-2222"]:
            assert secret not in response_text, secret

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=IDS["store"], platform="naver").one()
            cleanup.status = "failed"
            db.commit()
        blocked = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["store"], "include_test_orders": True})
        assert blocked.status_code == 200, blocked.text
        blocked_workbench = blocked.json()["data"]["operator_workbench"]
        assert blocked_workbench["sources"]["customer_inquiries"]["status"] == "blocked", blocked_workbench
        assert blocked_workbench["sources"]["customer_inquiries"]["reason_code"] == "readonly_retention_cleanup_failed", blocked_workbench
        assert not any(item["task_type"] == "customer_inquiry" for section in blocked_workbench["sections"].values() for item in section), blocked_workbench
        assert any(item["task_type"] == "unbatched_shipment" for section in blocked_workbench["sections"].values() for item in section), blocked_workbench
        assert "GENERIC-OPEN" not in blocked.text and "shipping_status" not in blocked.text, blocked.text

        with SessionLocal() as db:
            cleanup = db.query(PxgNaverReadonlyCleanupStatus).filter_by(store_id=IDS["store"], platform="naver").one()
            cleanup.status = "healthy"
            db.commit()
        with patch(
            "app.services.stats_service.warehouse_shipping_service.list_warehouse_batches",
            side_effect=ApiError("shipping unavailable", "shipping_source_unavailable", 503),
        ):
            shipping_blocked = client.get(
                "/api/v1/dashboard/summary",
                params={"store_id": IDS["store"], "include_test_orders": True},
            )
        assert shipping_blocked.status_code == 200, shipping_blocked.text
        shipping_workbench = shipping_blocked.json()["data"]["operator_workbench"]
        assert shipping_workbench["sources"]["shipping"] == {
            "status": "blocked", "reason_code": "shipping_source_unavailable",
        }, shipping_workbench
        assert any(
            item["task_type"] == "unbatched_shipment"
            for section in shipping_workbench["sections"].values()
            for item in section
        ), shipping_workbench

        with patch(
            "app.services.stats_service.order_service.list_orders",
            side_effect=ApiError("orders unavailable", "orders_source_unavailable", 503),
        ):
            orders_blocked = client.get(
                "/api/v1/dashboard/summary",
                params={"store_id": IDS["store"], "include_test_orders": True},
            )
        assert orders_blocked.status_code == 200, orders_blocked.text
        orders_workbench = orders_blocked.json()["data"]["operator_workbench"]
        assert orders_workbench["sources"]["orders"] == {
            "status": "blocked", "reason_code": "orders_source_unavailable",
        }, orders_workbench
        assert any(
            item["task_type"] == "warehouse_waiting"
            for section in orders_workbench["sections"].values()
            for item in section
        ), orders_workbench

        cross_store = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["other_store"]})
        assert cross_store.status_code == 403, cross_store.text

        client.cookies.clear()
        authenticate(client, "other@example.test")
        unrelated = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["other_store"]})
        assert unrelated.status_code == 200, unrelated.text
        unrelated_workbench = unrelated.json()["data"]["operator_workbench"]
        assert unrelated_workbench["sources"]["customer_inquiries"]["status"] == "ready", unrelated_workbench
        assert any(item["task_type"] == "customer_inquiry" for item in unrelated_workbench["sections"]["action_required"]), unrelated_workbench

        client.cookies.clear()
        authenticate(client, "denied@example.test")
        denied = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["store"]})
        assert denied.status_code == 403, denied.text

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_operator_workbench: ok")


if __name__ == "__main__":
    main()
