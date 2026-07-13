import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

VERIFY_DB_PATH = Path(tempfile.gettempdir()) / f"codex1-t13-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB_PATH.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")

from app.database import SessionLocal, init_db
from app.models.api_credential import ApiCredential
from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
from app.models.order import Order
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate
from app.services import order_service, store_onboarding_service


class FakeNaverReader:
    def __init__(self) -> None:
        self.product_reads = 0
        self.order_reads = 0

    def validate(self, *, client_id: str, client_secret: str, channel_no: str | None):
        assert client_id == "client-id-for-test"
        assert client_secret == "secret-for-test"
        return store_onboarding_service.NaverValidation(True, True, True, True, True, channel_no or "1001")

    def read_products(self, context, *, start_at, end_at, cursor):
        self.product_reads += 1
        assert context.client_secret == "secret-for-test"
        return store_onboarding_service.NaverReadPage([{
            "external_product_id": "product-1", "name": "Onboarding product", "price": 12000, "stock_quantity": 4,
        }])

    def read_orders(self, context, *, start_at, end_at, cursor):
        self.order_reads += 1
        ordered_at = start_at + timedelta(hours=1)
        return store_onboarding_service.NaverReadPage([{
            "external_order_id": f"order-{self.order_reads}", "external_product_order_id": f"product-order-{self.order_reads}",
            "platform_product_id": "product-1", "product_name": "Onboarding product", "quantity": 1,
            "order_amount": 12000, "order_status": "PAID", "ordered_at": ordered_at,
            "buyer_name": "Buyer", "buyer_phone": "01012345678",
        }])


def main() -> None:
    init_db()
    reader = FakeNaverReader()
    with SessionLocal() as db:
        owner_role = db.query(ErpRole).filter_by(role_key="owner").one()
        creator = ErpUser(user_key_hash="t13-creator", display_name="T13 Creator", status="active", auth_provider="api_operator")
        db.add(creator)
        db.commit()

        now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        payload = StoreOnboardingCreate(
            idempotency_key="t13-idempotency-key",
            store_name="T13 Naver Store",
            client_id="client-id-for-test",
            client_secret="secret-for-test",
            channel_no="1001",
        )
        result = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=creator.id, reader=reader, now=now)
        assert result["status"] == "partially_synced", result
        assert result["store_id"] and result["credential_id"]

        duplicate = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=creator.id, reader=reader, now=now)
        assert duplicate["id"] == result["id"]
        assert reader.product_reads == 1 and reader.order_reads == 1

        onboarding = db.get(StoreOnboarding, result["id"])
        credential = db.get(ApiCredential, result["credential_id"])
        assert onboarding.encrypted_client_secret is None
        assert credential.client_id is None
        assert credential.encrypted_access_key and "client-id-for-test" not in credential.encrypted_access_key
        assert credential.encrypted_secret_key and "secret-for-test" not in credential.encrypted_secret_key
        assert "secret-for-test" not in str(store_onboarding_service.serialize_onboarding(onboarding))
        membership = db.query(ErpStoreMembership).filter_by(user_id=creator.id, store_id=result["store_id"], role_id=owner_role.id).one_or_none()
        assert membership is not None and membership.membership_status == "active"
        assert db.query(SyncLog).filter_by(store_id=result["store_id"], platform="naver").count() == 2
        assert db.query(SyncCheckpoint).filter_by(store_id=result["store_id"], platform="naver").count() == 2
        assert onboarding.snapshot_end_at.replace(tzinfo=timezone.utc) == now
        assert onboarding.initial_window_start_at.replace(tzinfo=timezone.utc) == now - timedelta(days=30)

        current = order_service.query_orders(db, store_id=result["store_id"], view="current", page=1, page_size=20)
        assert current["total"] == 1
        historical_payload = HistoricalBackfillCreate(start_at=now - timedelta(days=61), end_at=now - timedelta(days=31))
        historical = store_onboarding_service.run_historical_order_backfill(db, onboarding_id=result["id"], payload=historical_payload, reader=reader)
        assert historical["platform_write"] is False and historical["unsynced_history_retrieved"] is False
        history = order_service.query_orders(db, store_id=result["store_id"], view="historical", page=1, page_size=20, product_id="product-1", status="PAID")
        assert history["total"] == 1, history
        assert db.query(Order).filter_by(store_id=result["store_id"], source_type="naver_historical_backfill").count() == 1
        assert db.query(SyncCheckpoint).filter_by(store_id=result["store_id"], sync_type=store_onboarding_service.HISTORICAL_ORDER_SYNC).count() == 1
    print("t13 onboarding: ok")


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
