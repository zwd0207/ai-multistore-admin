import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-multi-store-workbench.db"
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
from sqlalchemy import event

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

from app.models.order import Order
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.store import Store
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.encryption import encrypt_value
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.session_service import generate_totp, hash_login_identifier, hash_password
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services import stats_service


ORIGIN = "https://erp.test"
PASSWORD = "T12-test-password-not-production"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
IDS: dict[str, int] = {}


def _role(db, key: str, *permission_keys: str, status: str = "active") -> ErpRole:
    role = ErpRole(role_key=key, role_label_zh="test", role_label_en="test", status=status)
    db.add(role)
    db.flush()
    for permission_key in permission_keys:
        permission = db.query(ErpPermission).filter_by(permission_key=permission_key).one()
        db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id))
    return role


def _user(db, login_identifier: str) -> ErpUser:
    user = ErpUser(
        user_key_hash=f"t12-{login_identifier}-hash",
        display_name="T12 Operator",
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
    return user


def _membership(db, user: ErpUser, store: Store, role: ErpRole, status: str = "active") -> None:
    db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status=status))


def _order(db, store_id: int, external_id: str) -> None:
    now = get_utc_now()
    db.add(Order(
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
        product_name="Private Product",
        quantity=1,
        order_amount=1000,
        currency="KRW",
        order_status="cancelled",
        ordered_at=now - timedelta(minutes=10),
        source_type="local_readonly_fixture",
        last_synced_at=now,
    ))


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        stores = {
            key: Store(name=name, platform="naver", status=status)
            for key, name, status in [
                ("alpha", "Alpha Store", "active"),
                ("beta", "Beta Store", "active"),
                ("private", "Private Store", "active"),
                ("inactive_membership", "Inactive Membership Store", "active"),
                ("inactive_role", "Inactive Role Store", "active"),
                ("inactive_store", "Inactive Store", "inactive"),
            ]
        }
        db.add_all(stores.values())
        db.add_all([
            ErpPermission(permission_key="dashboard.read", permission_group="dashboard", permission_label_zh="test"),
            ErpPermission(permission_key="*", permission_group="system", permission_label_zh="test"),
        ])
        db.flush()
        dashboard_role = _role(db, "t12-dashboard", "dashboard.read")
        duplicate_dashboard_role = _role(db, "t12-dashboard-duplicate", "dashboard.read")
        wildcard_role = _role(db, "t12-wildcard", "*")
        denied_role = _role(db, "t12-denied")
        inactive_role = _role(db, "t12-inactive-role", "dashboard.read", status="inactive")

        operator = _user(db, "operator@example.test")
        denied = _user(db, "denied@example.test")
        _membership(db, operator, stores["alpha"], dashboard_role)
        _membership(db, operator, stores["alpha"], duplicate_dashboard_role)
        _membership(db, operator, stores["beta"], wildcard_role)
        _membership(db, operator, stores["inactive_membership"], dashboard_role, status="inactive")
        _membership(db, operator, stores["inactive_role"], inactive_role)
        _membership(db, operator, stores["inactive_store"], dashboard_role)
        _membership(db, denied, stores["private"], denied_role)
        _order(db, stores["alpha"].id, "ALPHA-PRIVATE-ORDER")
        _order(db, stores["private"].id, "PRIVATE-STORE-ORDER")
        db.commit()
        IDS.update({key: store.id for key, store in stores.items()})


def authenticate(client: TestClient, login_identifier: str) -> None:
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


def _task(task_id: str, priority: int, updated_at: str | None) -> dict:
    return {
        "task_id": task_id,
        "task_type": "fixture",
        "priority": priority,
        "title": "Safe task",
        "description": "Safe description",
        "status": "action_required",
        "count": 1,
        "action_path": "/orders",
        "action_label": "View",
        "related_order_id": None,
        "related_batch_id": None,
        "related_inquiry_id": None,
        "updated_at": updated_at,
        "stale": False,
    }


def _workbench_for_store(store_id: int) -> dict:
    if store_id == IDS["alpha"]:
        return {
            "summary": {"urgent": 0, "action_required": 2, "waiting": 0, "completed_today": 0},
            "sections": {"urgent": [], "action_required": [_task("same", 5, None), _task("same", 5, None), _task("alpha-later", 5, "2026-01-02T00:00:00+00:00")], "waiting": [], "completed_today": []},
            "sources": {"orders": {"status": "ready", "reason_code": None}, "shipping": {"status": "blocked", "reason_code": "shipping_down"}, "customer_inquiries": {"status": "ready", "reason_code": None}},
        }
    return {
        "summary": {"urgent": 0, "action_required": 2, "waiting": 0, "completed_today": 0},
        "sections": {"urgent": [], "action_required": [_task("same", 5, None), _task("beta-earlier", 5, "2026-01-01T00:00:00+00:00")], "waiting": [], "completed_today": []},
        "sources": {"orders": {"status": "blocked", "reason_code": "orders_down"}, "shipping": {"status": "ready", "reason_code": None}, "customer_inquiries": {"status": "ready", "reason_code": None}},
    }


def main() -> None:
    seed()
    with TestClient(app, base_url=ORIGIN) as client:
        missing_session = client.get("/api/v1/dashboard/store-overview")
        assert missing_session.status_code == 401 and missing_session.json()["error_code"] == "session_required", missing_session.text

        pending_mfa = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"login_identifier": "operator@example.test", "password": PASSWORD},
        )
        assert pending_mfa.status_code == 200, pending_mfa.text
        mfa_required = client.get("/api/v1/dashboard/store-overview")
        assert mfa_required.status_code == 403 and mfa_required.json()["error_code"] == "mfa_required", mfa_required.text

        client.cookies.clear()
        authenticate(client, "denied@example.test")
        denied = client.get("/api/v1/dashboard/store-overview")
        assert denied.status_code == 403 and denied.json()["error_code"] == "dashboard_read_forbidden", denied.text

        client.cookies.clear()
        authenticate(client, "operator@example.test")
        writes: list[str] = []

        def record_write(_, __, statement, ___, ____, _____):
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(statement)

        event.listen(engine, "before_cursor_execute", record_write)
        try:
            with patch("app.services.stats_service._build_operator_workbench", side_effect=lambda db, *, store_id, platform, include_test_orders: _workbench_for_store(store_id)) as build:
                response = client.get("/api/v1/dashboard/store-overview", params={"include_inactive": "true"})
        finally:
            event.remove(engine, "before_cursor_execute", record_write)
        assert response.status_code == 200, response.text
        assert not writes, writes
        assert build.call_count == 2, build.call_args_list
        assert all(call.kwargs["include_test_orders"] is False for call in build.call_args_list), build.call_args_list
        data = response.json()["data"]
        assert {"business_timezone", "business_date", "business_day_start", "business_day_end", "status", "data_policy", "store_count", "stores", "summary", "operator_workbench"} <= set(data), data
        assert [store["store_id"] for store in data["stores"]] == [IDS["alpha"], IDS["beta"]], data["stores"]
        assert all(set(store) >= {"id", "store_id", "store_name", "platform", "metrics", "workbench_summary"} for store in data["stores"]), data["stores"]
        assert all(store["workbench_summary"] == {"urgent": 0, "action_required": 2, "waiting": 0, "completed_today": 0} for store in data["stores"]), data["stores"]
        assert data["summary"]["store_count"] == 2 and data["store_count"] == 2, data["summary"]
        workbench = data["operator_workbench"]
        assert set(workbench) == {"summary", "sections", "sources"}, workbench
        tasks = workbench["sections"]["action_required"]
        assert [(task["store_id"], task["task_id"]) for task in tasks] == [
            (IDS["alpha"], "same"),
            (IDS["beta"], "same"),
            (IDS["beta"], "beta-earlier"),
            (IDS["alpha"], "alpha-later"),
        ], tasks
        assert all(task["store_name"] in {"Alpha Store", "Beta Store"} and task["platform"] == "naver" for task in tasks), tasks
        assert workbench["summary"] == {"urgent": 0, "action_required": 4, "waiting": 0, "completed_today": 0}, workbench
        assert workbench["sources"]["orders"] == {
            "status": "partial", "reason_code": "partial_failure", "failed_store_count": 1,
            "failures": [{"store_id": IDS["beta"], "reason_code": "orders_down"}],
        }, workbench
        assert workbench["sources"]["shipping"] == {
            "status": "partial", "reason_code": "partial_failure", "failed_store_count": 1,
            "failures": [{"store_id": IDS["alpha"], "reason_code": "shipping_down"}],
        }, workbench
        assert workbench["sources"]["customer_inquiries"] == {
            "status": "ready", "reason_code": None, "failed_store_count": 0, "failures": [],
        }, workbench
        response_text = response.text
        for forbidden in ["Private Buyer Name", "010-1234-5678", "Private Receiver Name", "010-9999-8888", "Full private recipient address", "Private Store", "PRIVATE-STORE-ORDER"]:
            assert forbidden not in response_text, forbidden

        live_workbench = client.get("/api/v1/dashboard/store-overview")
        assert live_workbench.status_code == 200, live_workbench.text
        live_tasks = live_workbench.json()["data"]["operator_workbench"]["sections"]["urgent"]
        assert any(task["store_id"] == IDS["alpha"] and task["task_type"] == "abnormal_order" for task in live_tasks), live_tasks

        original_list_orders = stats_service.order_service.list_orders

        def fail_beta_orders(db, *, store_id, platform, include_test_orders):
            if store_id == IDS["beta"]:
                raise ApiError("orders unavailable", "orders_down", 503)
            return original_list_orders(
                db,
                store_id=store_id,
                platform=platform,
                include_test_orders=include_test_orders,
            )

        with patch("app.services.stats_service.order_service.list_orders", side_effect=fail_beta_orders):
            source_failure = client.get("/api/v1/dashboard/store-overview")
        assert source_failure.status_code == 200, source_failure.text
        assert source_failure.json()["data"]["operator_workbench"]["sources"]["orders"] == {
            "status": "partial", "reason_code": "partial_failure", "failed_store_count": 1,
            "failures": [{"store_id": IDS["beta"], "reason_code": "orders_down"}],
        }, source_failure.text

        summary_regression = client.get("/api/v1/dashboard/summary", params={"store_id": IDS["alpha"]})
        assert summary_regression.status_code == 200 and "operator_workbench" in summary_regression.json()["data"], summary_regression.text

        with patch("app.services.stats_service._build_operator_workbench", side_effect=ApiError("source unavailable", "source_unavailable", 503)):
            api_error = client.get("/api/v1/dashboard/store-overview")
        assert api_error.status_code == 503, api_error.text

        def all_blocked(db, *, store_id, platform, include_test_orders):
            return {
                "summary": {"urgent": 0, "action_required": 0, "waiting": 0, "completed_today": 0},
                "sections": {"urgent": [], "action_required": [], "waiting": [], "completed_today": []},
                "sources": {
                    "orders": {"status": "blocked", "reason_code": "orders_down"},
                    "shipping": {"status": "ready", "reason_code": None},
                    "customer_inquiries": {"status": "ready", "reason_code": None},
                },
            }

        with patch("app.services.stats_service._build_operator_workbench", side_effect=all_blocked):
            all_failed = client.get("/api/v1/dashboard/store-overview")
        assert all_failed.status_code == 200, all_failed.text
        assert all_failed.json()["data"]["operator_workbench"]["sources"]["orders"] == {
            "status": "blocked", "reason_code": "all_stores_blocked", "failed_store_count": 2,
            "failures": [
                {"store_id": IDS["alpha"], "reason_code": "orders_down"},
                {"store_id": IDS["beta"], "reason_code": "orders_down"},
            ],
        }, all_failed.text

        with patch("app.services.stats_service._build_operator_workbench", side_effect=RuntimeError("must propagate")):
            try:
                client.get("/api/v1/dashboard/store-overview")
            except RuntimeError as exc:
                assert str(exc) == "must propagate", exc
            else:
                raise AssertionError("non-ApiError was swallowed")

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_multi_store_workbench: ok")


if __name__ == "__main__":
    main()
