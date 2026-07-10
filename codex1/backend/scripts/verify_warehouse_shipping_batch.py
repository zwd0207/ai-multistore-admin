import base64
import os
import sys
import tempfile
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-warehouse-shipping-batch.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"

from app.database import SessionLocal, engine, init_db
from app.models.order import Order
from app.models.shipping import LogisticsInventoryMapping
from app.models.store import Store
from app.services import shipping_service, warehouse_shipping_service


def xlsx(rows):
    headers = [
        ("order_reference", "订单号"),
        ("product_order_reference", "商品订单号"),
        ("logistics_inventory_code", "仓库货号"),
        ("carrier", "快递公司"),
        ("tracking_number", "物流单号"),
    ]
    return base64.b64encode(shipping_service._build_xlsx_bytes(rows, headers=headers)).decode("ascii")


def main():
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    init_db()
    with SessionLocal() as db:
        store = Store(name="warehouse-workflow-test", platform="naver")
        db.add(store)
        db.flush()
        order = Order(
            store_id=store.id, platform="naver", external_order_id="warehouse-order-001",
            external_product_order_id="warehouse-product-order-001", receiver_name="Kim Operator",
            receiver_phone="010-1234-5678", receiver_address="Seoul Test Street 1", zip_code="06123",
            product_name="PXG Bag", quantity=1, order_amount=1, currency="KRW", order_status="PAYED",
            ordered_at=shipping_service.get_utc_now(), source_type="verify_warehouse_workflow",
        )
        db.add(order)
        db.flush()
        db.add(LogisticsInventoryMapping(
            store_id=store.id, platform="naver", match_product_name="PXG Bag", match_option_name="",
            normalized_product_name=shipping_service._normalize_key_part("PXG Bag"), normalized_option_name="",
            internal_sku="PXG-BAG-001", logistics_inventory_code="WH-PXG-001", match_priority=1, is_active=True,
        ))
        db.commit()

        actor = {"role": "operator", "actor_id": "warehouse-test"}
        created = warehouse_shipping_service.create_warehouse_batch(
            db, store_id=store.id, platform="naver", order_ids=[order.id], manual_approval=True, actor_context=actor,
        )
        assert created["status"] == "created", created
        batch_id = created["batch"]["id"]
        duplicate = warehouse_shipping_service.create_warehouse_batch(
            db, store_id=store.id, platform="naver", order_ids=[order.id], manual_approval=True, actor_context=actor,
        )
        assert duplicate["skip_reason"] == "orders_already_in_active_shipping_batch", duplicate

        manifest = warehouse_shipping_service.download_warehouse_manifest(
            db, batch_id=batch_id, manual_approval=True, privacy_access_acknowledged=True, actor_context=actor,
        )
        assert manifest["status"] == "warehouse_manifest_ready", manifest
        with ZipFile(BytesIO(base64.b64decode(manifest["file_content_base64"]))) as archive:
            assert b"Seoul Test Street 1" in archive.read("xl/worksheets/sheet1.xml"), manifest
        listed = warehouse_shipping_service.list_warehouse_batches(db, store_id=store.id, platform="naver", include_rows=True)
        assert "Seoul Test Street 1" not in str(listed), listed

        imported = warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db, batch_id=batch_id, source_file_name="warehouse-return.xlsx",
            file_content_base64=xlsx([{
                "order_reference": "warehouse-order-001", "product_order_reference": "warehouse-product-order-001",
                "logistics_inventory_code": "WH-PXG-001", "carrier": "CJ", "tracking_number": "1234567890",
            }]), manual_approval=True, actor_context=actor,
        )
        assert imported["normal_count"] == 1 and imported["blocked_count"] == 0, imported
        confirmed = warehouse_shipping_service.confirm_warehouse_batch(
            db, batch_id=batch_id, confirmed_row_ids=[], manual_approval=True, actor_context=actor,
        )
        assert confirmed["status"] == "ready_to_writeback", confirmed
        blocked_writeback = warehouse_shipping_service.execute_warehouse_batch_writeback(
            db, batch_id=batch_id, manual_approval=True, final_operator_confirmation=True,
            real_api_call_requested=False, actor_context=actor,
        )
        assert blocked_writeback["skip_reason"] == "final_operator_confirmation_and_real_api_request_required", blocked_writeback
    print("warehouse shipping batch verification ok")


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
