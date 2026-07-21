import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

VERIFY_DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t13-r1-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB_PATH.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.core.exceptions import ApiError
from app.main import create_app
from app.models.api_credential import ApiCredential
from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
from app.models.order import Order
from app.models.product import Product
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate, StoreOnboardingCredentialUpdate
from app.services import api_credential_readiness_service, credential_service, order_service, stats_service, store_onboarding_service


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _run_worker(onboarding_id: int, reads: "InjectedNaverReads") -> dict | None:
    with patch.object(store_onboarding_service, "get_utc_now", return_value=NOW):
        return store_onboarding_service.run_onboarding_worker(
            onboarding_id,
            reader=reads.adapter(),
            session_factory=SessionLocal,
        )


class InjectedNaverReads:
    def __init__(self) -> None:
        self.product_pages: list[int] = []
        self.feed_windows: list[tuple[datetime, datetime]] = []
        self.detail_batches: list[list[str]] = []
        self.fail_feed_call: int | None = 11
        self.platform_write_count = 0

    def validate(self, *, client_id: str, client_secret: str, channel_no: str | None):
        if client_id.startswith("invalid") or client_secret.startswith("invalid"):
            raise store_onboarding_service.NaverReadFailure("auth_failed")
        return store_onboarding_service.NaverValidation(True, True, True, True, True, channel_no or "1001")

    def token(self, context: dict) -> tuple[str, int]:
        assert context["client_id"] in {"client-id-for-test", "client-id-after-provision"}
        assert context["secret_key"] in {"secret-for-test", "secret-after-provision"}
        return "injected-read-token", 200

    def products(self, *, api_base: str, headers: dict, page: int, size: int) -> dict:
        assert headers == {"Authorization": "Bearer injected-read-token"}
        assert size == store_onboarding_service.PRODUCT_PAGE_SIZE
        self.product_pages.append(page)
        return {
            "success": True,
            "http_status": 200,
            "payload": {
                "contents": [{
                    "originProductNo": f"origin-{page}",
                    "channelProducts": [{
                        "channelProductNo": f"product-{page}",
                        "productName": f"Product {page}",
                        "salePrice": page * 1000,
                        "stockQuantity": page,
                        "statusType": "SALE",
                    }],
                }],
                "hasMore": page < 2,
            },
        }

    def orders(self, *, api_base: str, headers: dict, start_kst: datetime, end_kst: datetime, **kwargs) -> dict:
        assert headers == {"Authorization": "Bearer injected-read-token"}
        assert end_kst - start_kst <= timedelta(days=1)
        self.feed_windows.append((start_kst, end_kst))
        if self.fail_feed_call == len(self.feed_windows):
            self.fail_feed_call = None
            return {"success": False, "http_status": 503, "error_code": "readonly_request_failed"}
        day_key = start_kst.date().isoformat()
        return {
            "success": True,
            "http_status": 200,
            "payload": {
                "data": {"lastChangeStatuses": [{
                    "productOrderId": f"po-{day_key}",
                    "lastChangedDate": (start_kst + timedelta(minutes=10)).isoformat(),
                }]},
                "hasMore": False,
            },
        }

    def details(self, *, api_base: str, headers: dict, product_order_ids: list[str]) -> dict:
        assert len(product_order_ids) <= store_onboarding_service.ORDER_DETAIL_BATCH_SIZE
        self.detail_batches.append(list(product_order_ids))
        records = []
        for product_order_id in product_order_ids:
            day = product_order_id.removeprefix("po-")
            records.append({
                "productOrderId": product_order_id,
                "orderId": f"order-{day}",
                "channelProductNo": "product-1",
                "productName": "Product 1",
                "quantity": 1,
                "totalPaymentAmount": "1000",
                "orderStatus": "PAID",
                "orderedAt": f"{day}T03:00:00+09:00",
                "paidAt": f"{day}T03:01:00+09:00",
                "lastChangedDate": f"{day}T03:10:00+09:00",
                "buyerName": "Test Buyer",
                "buyerTelNo": "01012345678",
                "receiverName": "Receiver",
                "receiverTelNo": "01087654321",
            })
        return {"success": True, "http_status": 200, "payload": {"data": records}}

    def adapter(self) -> store_onboarding_service.DefaultNaverReadAdapter:
        return store_onboarding_service.DefaultNaverReadAdapter(
            token_request=self.token,
            product_search=self.products,
            order_feed=self.orders,
            order_detail=self.details,
            validation=self.validate,
        )


def main() -> None:
    init_db()
    reads = InjectedNaverReads()
    with SessionLocal() as db:
        owner_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "owner"))
        creator = ErpUser(user_key_hash="t13-r1-creator", display_name="T13 Creator", status="active", auth_provider="api_operator")
        outsider = ErpUser(user_key_hash="t13-r1-outsider", display_name="T13 Outsider", status="active", auth_provider="api_operator")
        db.add_all((creator, outsider))
        db.commit()

        payload = StoreOnboardingCreate(
            idempotency_key="t13-r1-idempotency-key",
            store_name="T13 R1 Naver Store",
            client_id="invalid-client-id",
            client_secret="invalid-secret",
            channel_no="1001",
        )
        submitted = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=creator.id, now=NOW)
        assert submitted["status"] == "validating"
        assert submitted["store_id"] is None and reads.product_pages == [] and reads.feed_windows == []
        duplicate = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=creator.id, now=NOW)
        assert duplicate["id"] == submitted["id"]

        client = TestClient(create_app())
        creator_poll = client.get(f"/api/v1/store-onboardings/{submitted['id']}", headers={"X-ERP-User-Key": creator.user_key_hash})
        outsider_poll = client.get(f"/api/v1/store-onboardings/{submitted['id']}", headers={"X-ERP-User-Key": outsider.user_key_hash})
        assert creator_poll.status_code == 200
        assert outsider_poll.status_code == 403

        blocked = _run_worker(submitted["id"], reads)
        db.expire_all()
        assert blocked["status"] == "blocked" and blocked["last_error_code"] == "auth_failed"
        corrected = store_onboarding_service.update_onboarding_credentials(
            db,
            onboarding_id=submitted["id"],
            payload=StoreOnboardingCredentialUpdate(client_id="client-id-for-test", client_secret="secret-for-test"),
        )
        assert corrected["id"] == submitted["id"] and corrected["configuration_version"] == 2
        assert "invalid-secret" not in str(corrected) and "secret-for-test" not in str(corrected)

        interrupted = _run_worker(submitted["id"], reads)
        db.expire_all()
        assert interrupted["status"] == "retry_wait", interrupted
        assert interrupted["progress_summary"]["products"]["status"] == "success"
        assert interrupted["progress_summary"]["orders"]["pages"] == 10
        store_id = interrupted["store_id"]
        credential_id = interrupted["credential_id"]
        assert store_id and credential_id
        checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store_id, SyncCheckpoint.sync_type == store_onboarding_service.ONBOARDING_ORDER_SYNC))
        assert checkpoint and '"slice":10' in checkpoint.cursor_value

        store_onboarding_service.request_onboarding_resume(db, onboarding_id=submitted["id"])
        completed = _run_worker(submitted["id"], reads)
        db.expire_all()
        assert completed["status"] == "partially_synced", completed
        assert completed["store_id"] == store_id and completed["credential_id"] == credential_id
        assert completed["progress_summary"]["orders"]["pages"] == 30, completed["progress_summary"]["orders"]
        assert reads.product_pages == [1, 2]
        assert len(reads.feed_windows) == 31
        assert all(end - start <= timedelta(days=1) for start, end in reads.feed_windows)
        assert db.query(Store).filter_by(name="T13 R1 Naver Store").count() == 1
        assert db.query(ApiCredential).filter_by(store_id=store_id, platform="naver").count() == 1
        assert db.query(ErpStoreMembership).filter_by(user_id=creator.id, store_id=store_id, role_id=owner_role.id).count() == 1
        viewer_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "viewer"))
        db.add(ErpStoreMembership(user_id=outsider.id, store_id=store_id, role_id=viewer_role.id, membership_status="active", scope_type="assigned", assigned_by_user_id=creator.id))
        db.commit()
        member_poll = client.get(f"/api/v1/store-onboardings/{submitted['id']}", headers={"X-ERP-User-Key": outsider.user_key_hash})
        assert member_poll.status_code == 200
        store_runs = store_onboarding_service.list_store_onboardings(db, store_id=store_id, user_id=outsider.id)
        assert [item["id"] for item in store_runs] == [submitted["id"]]
        list_response = client.get(
            "/api/v1/store-onboardings",
            params={"store_id": store_id},
            headers={"X-ERP-User-Key": outsider.user_key_hash},
        )
        assert list_response.status_code == 200
        assert list_response.json()["data"]["items"][0]["store_id"] == store_id

        invalid_secret = "t13-client-secret-must-never-appear-in-a-422-response"
        invalid_secret_response = client.patch(
            f"/api/v1/store-onboardings/{submitted['id']}",
            json={"client_secret": invalid_secret * 30},
            headers={"X-ERP-User-Key": creator.user_key_hash},
        )
        assert invalid_secret_response.status_code == 422
        assert invalid_secret not in invalid_secret_response.text
        assert all("input" not in detail for detail in invalid_secret_response.json()["detail"])

        member_patch = client.patch(
            f"/api/v1/store-onboardings/{submitted['id']}",
            json={"client_secret": "member-must-not-change-secret"},
            headers={"X-ERP-User-Key": outsider.user_key_hash},
        )
        member_resume = client.post(
            f"/api/v1/store-onboardings/{submitted['id']}/resume",
            headers={"X-ERP-User-Key": outsider.user_key_hash},
        )
        member_backfill = client.post(
            f"/api/v1/store-onboardings/{submitted['id']}/historical-backfill",
            json={
                "start_at": (NOW - timedelta(days=61)).isoformat(),
                "end_at": (NOW - timedelta(days=31)).isoformat(),
            },
            headers={"X-ERP-User-Key": outsider.user_key_hash},
        )
        assert member_patch.status_code == 403
        assert member_resume.status_code == 403
        assert member_backfill.status_code == 403

        credential = db.get(ApiCredential, credential_id)
        assert credential.client_id == "client-id-for-test"
        assert credential.encrypted_access_key is None
        assert credential.encrypted_secret_key and "secret-for-test" not in credential.encrypted_secret_key
        listed = credential_service.list_credentials(db, store_id=store_id)
        assert listed[0]["client_id"] == "client-id-for-test"
        readiness = api_credential_readiness_service.get_api_credential_readiness(db, store_id)["store_bound_readiness"]
        assert readiness["configured"] is True and readiness["client_id_configured"] is True
        assert api_credential_readiness_service._get_active_store_credential(db, store_id, "naver").id == credential_id

        corrected_after_store = store_onboarding_service.update_onboarding_credentials(
            db,
            onboarding_id=submitted["id"],
            payload=StoreOnboardingCredentialUpdate(client_id="client-id-after-provision", client_secret="secret-after-provision"),
        )
        assert corrected_after_store["configuration_version"] == 3
        assert "secret-for-test" not in str(corrected_after_store) and "secret-after-provision" not in str(corrected_after_store)
        revalidated = _run_worker(submitted["id"], reads)
        db.expire_all()
        assert revalidated["status"] == "partially_synced"
        assert revalidated["store_id"] == store_id and revalidated["credential_id"] == credential_id
        assert db.query(Store).count() == 1 and db.query(ApiCredential).count() == 1

        current_window_start = order_service.current_order_window_start(as_of=NOW)
        for end_at in (current_window_start, current_window_start + timedelta(seconds=1)):
            try:
                store_onboarding_service.run_historical_order_backfill(
                    db,
                    onboarding_id=submitted["id"],
                    payload=HistoricalBackfillCreate(
                        start_at=current_window_start - timedelta(days=1),
                        end_at=end_at,
                    ),
                    reader=reads.adapter(),
                    now=NOW,
                )
                raise AssertionError("historical/current boundary overlap must be rejected")
            except ApiError as exc:
                assert exc.error_code == "historical_backfill_current_window_overlap"

        history_payload = HistoricalBackfillCreate(start_at=NOW - timedelta(days=61), end_at=NOW - timedelta(days=31))
        history_result = store_onboarding_service.run_historical_order_backfill(
            db, onboarding_id=submitted["id"], payload=history_payload, reader=reads.adapter(), now=NOW,
        )
        assert history_result["platform_write"] is False
        assert history_result["unsynced_history_retrieved"] is True
        history = order_service.query_orders(db, store_id=store_id, view="historical", page=1, page_size=100, as_of=NOW)
        current = order_service.query_orders(db, store_id=store_id, view="current", page=1, page_size=100, as_of=NOW)
        assert history["total"] == 31 and current["total"] == 29, (history["total"], current["total"])

        overlap = db.scalar(select(Order).where(Order.store_id == store_id, Order.ordered_at < NOW - timedelta(days=30)).limit(1))
        before_count = db.query(Order).filter_by(store_id=store_id).count()
        order_service.upsert_orders(db, store_id, "naver", [{
            "external_order_id": overlap.external_order_id,
            "external_product_order_id": overlap.external_product_order_id,
            "product_name": overlap.product_name,
            "quantity": 1,
            "order_amount": 1000,
            "currency": "KRW",
            "order_status": "PAID",
            "ordered_at": NOW - timedelta(days=1),
            "source_type": "naver_onboarding_sync",
            "raw_data": {"sync_scope": "initial_30_day", "raw_response_saved": False, "platform_write": False},
        }])
        assert db.query(Order).filter_by(store_id=store_id).count() == before_count
        assert order_service.query_orders(db, store_id=store_id, view="current", page=1, page_size=100, as_of=NOW)["total"] == 30
        assert order_service.query_orders(db, store_id=store_id, view="historical", page=1, page_size=100, as_of=NOW)["total"] == 30

        workbench_before = stats_service._build_operator_workbench(
            db, store_id=store_id, platform="naver", include_test_orders=False,
        )
        today_metrics_before = stats_service._store_order_metrics(
            db, store_id, "naver", {"data_status": "confirmed"},
        )
        order_service.upsert_orders(db, store_id, "naver", [{
            "external_order_id": "history-source-must-not-be-a-today-task",
            "external_product_order_id": "history-source-must-not-be-a-today-task",
            "product_name": "Historical source regression",
            "quantity": 1,
            "order_amount": 1000,
            "currency": "KRW",
            "order_status": "PAID",
            "ordered_at": NOW - timedelta(hours=1),
            "source_type": "legacy",
            "raw_data": {"source_type": order_service.HISTORICAL_BACKFILL_SOURCE_TYPE},
        }])
        historical_source_order = db.scalar(select(Order).where(
            Order.store_id == store_id,
            Order.external_order_id == "history-source-must-not-be-a-today-task",
        ))
        assert historical_source_order is not None
        workbench_after = stats_service._build_operator_workbench(
            db, store_id=store_id, platform="naver", include_test_orders=False,
        )
        today_metrics_after = stats_service._store_order_metrics(
            db, store_id, "naver", {"data_status": "confirmed"},
        )
        task_order_ids = {
            task.get("related_order_id")
            for section in workbench_after["sections"].values()
            for task in section
        }
        assert historical_source_order.id not in task_order_ids
        assert workbench_after["summary"] == workbench_before["summary"]
        assert today_metrics_after == today_metrics_before

        serialized_rows = str([
            product.raw_data for product in db.scalars(select(Product).where(Product.store_id == store_id)).all()
        ] + [
            order.raw_data for order in db.scalars(select(Order).where(Order.store_id == store_id)).all()
        ] + [
            log.raw_summary for log in db.scalars(select(SyncLog).where(SyncLog.store_id == store_id)).all()
        ])
        assert "injected-read-token" not in serialized_rows
        assert "secret-for-test" not in serialized_rows and "secret-after-provision" not in serialized_rows
        assert "raw_response_saved': True" not in serialized_rows
        assert reads.platform_write_count == 0
        assert completed["progress_summary"]["customer_inquiries"]["adapter_called"] is False
        assert completed["progress_summary"]["logistics"]["adapter_called"] is False

        due = StoreOnboarding(
            idempotency_key="t13-restart-recovery",
            requested_store_name="Restart recovery store",
            creator_user_id=creator.id,
            encrypted_client_id="encrypted-test-client",
            encrypted_client_secret="encrypted-test-secret",
            status="retry_wait",
            next_retry_at=NOW - timedelta(seconds=1),
            progress_summary={"products": {"status": "pending"}, "orders": {"status": "pending"}},
        )
        db.add(due)
        db.commit()
        scheduled_ids = []

        def fake_worker(onboarding_id, *, session_factory):
            assert session_factory is SessionLocal
            scheduled_ids.append(onboarding_id)
            return {"status": "scheduled"}

        recovery = store_onboarding_service.run_due_onboarding_workers(
            session_factory=SessionLocal,
            worker=fake_worker,
            now=NOW,
        )
        assert recovery == {"scheduled": 1, "completed": 1}
        assert scheduled_ids == [due.id]
    print("t13-r1 onboarding: ok")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            from app.database import engine
            engine.dispose()
        except Exception:
            pass
        for path in (VERIFY_DB_PATH, VERIFY_DB_PATH.with_suffix(".db-wal"), VERIFY_DB_PATH.with_suffix(".db-shm")):
            path.unlink(missing_ok=True)
