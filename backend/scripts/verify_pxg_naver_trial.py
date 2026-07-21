import os
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-trial.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
os.environ["SESSION_TOKEN_PEPPER"] = "pxg-trial-test-session-pepper-32-characters"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
os.environ["OPERATOR_TRIAL_ENABLED"] = "true"
os.environ["OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY"] = "true"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models.auth import ErpPermission, ErpRolePermission, ErpStoreMembership
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.shipping import ShippingTrackingImportBatch, ShippingTrackingImportRow
from app.models.store import Store
from app.services.operator_trial_service import (
    DISABLED_TRIAL_WRITE_PATHS,
    FORBIDDEN_TRIAL_PERMISSION_KEYS,
    TRIAL_PERMISSION_KEYS,
    assert_store_has_only_artificial_customer_data,
    assert_trial_runtime_closed,
    provision_trial_operator,
    resolve_trial_store,
)


def main() -> None:
    Base.metadata.create_all(engine)
    settings = get_settings()
    assert_trial_runtime_closed(settings)
    with SessionLocal() as db:
        selected = Store(id=37, name="pxg球包店", platform="Naver", status="active")
        other = Store(id=8, name="Other Store", platform="naver", status="active")
        db.add_all([selected, other])
        for key in sorted(TRIAL_PERMISSION_KEYS | FORBIDDEN_TRIAL_PERMISSION_KEYS):
            db.add(ErpPermission(
                permission_key=key,
                permission_group="trial-test",
                permission_label_zh="trial-test",
                status="active",
            ))
        db.flush()
        db.add(Order(
            store_id=selected.id,
            platform="naver",
            external_order_id="MOCK-ORDER-001",
            buyer_name="模拟客户",
            buyer_masked_phone="010-****-0000",
            receiver_name="模拟收件人",
            product_name="PXG 模拟球包",
            quantity=1,
            order_amount=Decimal("100.00"),
            currency="KRW",
            order_status="PAID",
            ordered_at=datetime.now(timezone.utc),
            source_type="mock_sync",
            raw_data={"is_test": True},
        ))
        db.add(CustomerInquiry(
            store_id=selected.id,
            platform="naver",
            external_inquiry_id="MOCK-INQUIRY-001",
            inquiry_type="shipping",
            customer_name="模拟客户",
            title="模拟配送咨询",
            content="仅用于模拟演练",
            status="open",
            received_at=datetime.now(timezone.utc),
            raw_data={"is_test": True},
        ))
        tracking_batch = ShippingTrackingImportBatch(
            store_id=selected.id,
            platform="naver",
            file_type="artificial_trial",
            file_format="xlsx",
            source_file_name="mock-tracking.xlsx",
            row_count=1,
            ready_row_count=1,
            audit_correlation_id="MOCK-TRACKING-AUDIT",
            tracking_number_import_open=False,
            shipment_writeback_called=False,
            orders_updated=False,
        )
        db.add(tracking_batch)
        db.flush()
        db.add(ShippingTrackingImportRow(
            import_batch_id=tracking_batch.id,
            store_id=selected.id,
            platform="naver",
            order_reference="MOCK-ORDER-001",
            product_order_reference="MOCK-PRODUCT-ORDER-001",
            carrier="MOCK-CARRIER",
            tracking_number="MOCK-TRACKING-0001",
            row_status="ready_for_future_review",
            future_write_allowed=False,
        ))
        db.commit()

        assert resolve_trial_store(db).id == 37
        assert_store_has_only_artificial_customer_data(db, selected.id)
        result = provision_trial_operator(
            db,
            login_identifier="pxg-trial@example.test",
            password="artificial-trial-password",
            mfa_secret="JBSWY3DPEHPK3PXP",
        )
        assert result["store_id"] == 37 and result["membership_count"] == 1
        memberships = db.scalars(select(ErpStoreMembership).where(ErpStoreMembership.user_id == result["user_id"])).all()
        assert len(memberships) == 1 and memberships[0].store_id == 37 and memberships[0].scope_type == "assigned"
        granted = set(db.scalars(
            select(ErpPermission.permission_key)
            .join(ErpRolePermission, ErpRolePermission.permission_id == ErpPermission.id)
            .where(ErpRolePermission.role_id == memberships[0].role_id)
        ).all())
        assert granted == TRIAL_PERMISSION_KEYS
        assert not (granted & FORBIDDEN_TRIAL_PERMISSION_KEYS)
        assert "/api/v1/shipping/shipment-writeback/execute" in DISABLED_TRIAL_WRITE_PATHS
        assert "/api/v1/sync/customer-inquiries/naver/reply" in DISABLED_TRIAL_WRITE_PATHS
        assert settings.real_api_test_enabled is False and settings.real_api_write_enabled is False
        assert settings.ai_automatic_operations_enabled is False
        mock_tracking = db.scalar(select(ShippingTrackingImportRow).where(ShippingTrackingImportRow.store_id == 37))
        assert mock_tracking.tracking_number.startswith("MOCK-") and mock_tracking.future_write_allowed is False
        assert tracking_batch.shipment_writeback_called is False and tracking_batch.orders_updated is False
    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_trial: ok (store id resolved as 37, never assumed as 8)")


if __name__ == "__main__":
    main()
