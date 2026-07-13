import json
import os
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly-activation.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"
os.environ["OPERATOR_TRIAL_REAL_READ_ENABLED"] = "false"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_ACTIVATION_ENABLED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_RETENTION_APPROVED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_BACKUP_ROLLBACK_APPROVED"] = "false"
os.environ["PXG_NAVER_LOCAL_READ_FIRST_SYNC_LIMIT"] = "3"

os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.config import get_settings
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.database import SessionLocal, engine, init_db
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.main import app
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.auth import ErpRole, ErpStoreMembership, ErpUser
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.operation_audit_log import OperationAuditLog
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.order import Order
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.product import Product
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.models.store import Store
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.schemas.pxg_naver_readonly import PxgNaverReadonlyAdapterBatch
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.operator_trial_service import TRIAL_STORE_NAME
os.environ['LIFECYCLE_SCHEDULERS_ENABLED'] = 'false'

from app.services.pxg_naver_readonly_activation_service import (
    readonly_activation_precheck,
    run_fictional_activation_simulation,
)


def fictional_batch(store_id: int, count: int = 1) -> PxgNaverReadonlyAdapterBatch:
    orders = [{
        "external_order_id": f"fictional-platform-order-{index}",
        "external_product_order_id": f"fictional-product-order-{index}",
        "product_name": "PXG Fictional Bag",
        "quantity": 1,
        "order_amount": "1000",
        "currency": "KRW",
        "order_status": "PAYED",
        "ordered_at": "2026-07-12T08:00:00+00:00",
        "source_updated_at": "2026-07-12T08:00:00+00:00",
        "recipient": {
            "receiver_name": "Fictional Recipient",
            "receiver_phone": "010-5555-0001",
            "receiver_address_full": "Fictional Address",
        },
    } for index in range(count)]
    return PxgNaverReadonlyAdapterBatch.model_validate({
        "store_id": store_id,
        "platform": "naver",
        "source_mode": "fictional_test",
        "products": [{
            "external_product_id": "fictional-product",
            "name": "PXG Fictional Bag",
            "price": "1000",
            "currency": "KRW",
            "stock_quantity": 1,
            "source_updated_at": "2026-07-12T08:00:00+00:00",
        }],
        "orders": orders,
        "logistics": [],
        "customer_inquiries": [],
    })


def assert_not_contains(value: object, *forbidden: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, default=str).lower()
    for item in forbidden:
        assert item.lower() not in serialized, f"unexpected private value: {item}"


def main() -> None:
    init_db()
    with SessionLocal() as db:
        store = Store(name=TRIAL_STORE_NAME, platform="naver", status="active")
        db.add(store)
        db.commit()
        db.refresh(store)
        admin_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "admin"))
        assert admin_role is not None
        admin = ErpUser(user_key_hash="pxg-t09-admin", display_name="PXG T09 Admin", status="active")
        db.add(admin)
        db.flush()
        db.add(ErpStoreMembership(user_id=admin.id, store_id=store.id, role_id=admin_role.id, membership_status="active"))
        db.commit()

        precheck = readonly_activation_precheck(db, settings=get_settings())
        assert precheck["status"] == "activation_blocked", precheck
        assert precheck["first_sync_limit"] == 3, precheck
        assert precheck["checks"]["real_persistence_enabled"] is False, precheck
        assert precheck["checks"]["all_platform_writes_disabled"] is True, precheck
        assert {"retention_explicitly_approved", "backup_rollback_explicitly_approved", "activation_explicitly_enabled"}.issubset(set(precheck["missing_checks"]))

        before = {"products": db.query(Product).count(), "orders": db.query(Order).count()}
        simulation = run_fictional_activation_simulation(
            db,
            settings=get_settings(),
            batch=fictional_batch(store.id),
            actor_id=admin.user_key_hash,
        )
        assert simulation["status"] == "simulation_completed", simulation
        assert simulation["candidate_count"] == 1 and simulation["first_sync_limit"] == 3, simulation
        assert simulation["rollback_verified"] is True
        assert simulation["business_records_written"] is False
        assert simulation["platform_write"] is False
        assert simulation["customer_send"] is False
        assert simulation["ai_automatic_operation"] is False
        assert_not_contains(simulation, "Fictional Recipient", "010-5555-0001", "Fictional Address")

        with SessionLocal() as fresh_db:
            assert {"products": fresh_db.query(Product).count(), "orders": fresh_db.query(Order).count()} == before
            audits = fresh_db.scalars(select(OperationAuditLog).where(OperationAuditLog.store_id == store.id)).all()
            assert len(audits) == 1 and audits[0].action == "pxg_naver_readonly_activation_simulated"
            assert_not_contains(audits, "Fictional Recipient", "010-5555-0001", "Fictional Address")

        before_audit_count = db.query(OperationAuditLog).count()
        oversized = run_fictional_activation_simulation(
            db,
            settings=get_settings(),
            batch=fictional_batch(store.id, count=4),
            actor_id=admin.user_key_hash,
        )
        assert oversized["status"] == "blocked" and oversized["skip_reason"] == "readonly_first_sync_limit_exceeded", oversized
        assert db.query(OperationAuditLog).count() == before_audit_count
        assert db.query(Product).count() == before["products"] and db.query(Order).count() == before["orders"]

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/pxg-naver-readonly/activation-check",
                headers={"X-ERP-User-Key": admin.user_key_hash},
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["status"] == "activation_blocked", response.text
            assert_not_contains(response.json(), "Fictional Recipient", "010-5555-0001", "Fictional Address")

    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_readonly_activation: ok")


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
