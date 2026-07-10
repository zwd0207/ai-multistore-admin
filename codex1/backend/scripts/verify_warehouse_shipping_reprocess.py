import base64
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-warehouse-shipping-reprocess.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"

from app.database import SessionLocal, engine, init_db
from app.models.order import Order
from app.models.shipping import LogisticsInventoryMapping, WarehouseShippingBatch, WarehouseShippingBatchOrder
from app.models.store import Store
from app.services import order_service, shipping_service, warehouse_shipping_service


ACTOR = {"role": "operator", "actor_id": "warehouse-reprocess-test"}


def tracking_xlsx(rows):
    headers = [
        ("order_reference", "Order reference"),
        ("product_order_reference", "Product order reference"),
        ("logistics_inventory_code", "Warehouse SKU"),
        ("carrier", "Carrier"),
        ("tracking_number", "Tracking number"),
    ]
    return base64.b64encode(shipping_service._build_xlsx_bytes(rows, headers=headers)).decode("ascii")


def add_order(db, store_id: int, suffix: str, raw_data=None) -> Order:
    order = Order(
        store_id=store_id,
        platform="naver",
        external_order_id=f"reprocess-order-{suffix}",
        external_product_order_id=f"reprocess-product-order-{suffix}",
        receiver_name="Test Receiver",
        receiver_phone="010-1000-2000",
        receiver_address="Seoul Base Address",
        zip_code="06123",
        product_name="Warehouse Test Bag",
        quantity=1,
        order_amount=1,
        currency="KRW",
        order_status="PAYED",
        ordered_at=shipping_service.get_utc_now(),
        source_type="verify_warehouse_reprocess",
        raw_data=raw_data,
    )
    db.add(order)
    db.flush()
    return order


def create_batch(db, store_id: int, order_id: int) -> dict:
    result = warehouse_shipping_service.create_warehouse_batch(
        db,
        store_id=store_id,
        platform="naver",
        order_ids=[order_id],
        manual_approval=True,
        actor_context=ACTOR,
    )
    assert result["status"] == "created", result
    return result


def main():
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    init_db()
    with SessionLocal() as db:
        store = Store(name="warehouse-reprocess-test", platform="naver")
        db.add(store)
        db.flush()
        db.add(LogisticsInventoryMapping(
            store_id=store.id,
            platform="naver",
            match_product_name="Warehouse Test Bag",
            match_option_name="",
            normalized_product_name=shipping_service._normalize_key_part("Warehouse Test Bag"),
            normalized_option_name="",
            internal_sku="WH-TEST-001",
            logistics_inventory_code="WH-TEST-001",
            match_priority=1,
            is_active=True,
        ))
        db.commit()

        order = add_order(db, store.id, "main", {
            "receiver_phone_secondary": "010-3000-4000",
            "receiver_address_line1": "Seoul Base Address",
            "receiver_address_line2": "Building 101 Room 202",
            "receiver_address_full": "Seoul Base Address Building 101 Room 202",
            "delivery_memo": "Leave with reception",
        })
        db.commit()

        contract = order_service.list_operations_orders(
            db, store_id=store.id, platform="naver", include_test_orders=True,
        )[0]
        expected_recipient = {
            "receiver_name": "Test Receiver",
            "receiver_phone": "010-1000-2000",
            "receiver_phone_secondary": "010-3000-4000",
            "zip_code": "06123",
            "receiver_address_line1": "Seoul Base Address",
            "receiver_address_line2": "Building 101 Room 202",
            "receiver_address_full": "Seoul Base Address Building 101 Room 202",
            "delivery_memo": "Leave with reception",
        }
        assert {key: contract[key] for key in expected_recipient} == expected_recipient, contract

        first = create_batch(db, store.id, order.id)
        first_batch_id = first["batch"]["id"]
        first_row_id = first["batch"]["rows"][0]["id"]
        assert db.get(WarehouseShippingBatchOrder, first_row_id).pre_batch_order_status == "PAYED"

        manifest = warehouse_shipping_service.download_warehouse_manifest(
            db,
            batch_id=first_batch_id,
            manual_approval=True,
            privacy_access_acknowledged=True,
            actor_context=ACTOR,
        )
        assert manifest["status"] == "warehouse_manifest_ready", manifest
        with ZipFile(BytesIO(base64.b64decode(manifest["file_content_base64"]))) as archive:
            worksheet = archive.read("xl/worksheets/sheet1.xml")
        for value in expected_recipient.values():
            assert value.encode("utf-8") in worksheet, value

        imported = warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db,
            batch_id=first_batch_id,
            source_file_name="reprocess-return.xlsx",
            file_content_base64=tracking_xlsx([{
                "order_reference": order.external_order_id,
                "product_order_reference": order.external_product_order_id,
                "logistics_inventory_code": "WH-TEST-001",
                "carrier": "CJ",
                "tracking_number": "1234567890",
            }]),
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert imported["normal_count"] == 1, imported
        confirmed = warehouse_shipping_service.confirm_warehouse_batch(
            db,
            batch_id=first_batch_id,
            confirmed_row_ids=[],
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert confirmed["status"] == "ready_to_writeback", confirmed
        assert db.get(Order, order.id).order_status == "DISPATCHED"

        blocked_release = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=first_batch_id,
            row_id=first_row_id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=False,
            actor_context=ACTOR,
        )
        assert blocked_release["skip_reason"] == "warehouse_stop_confirmation_required", blocked_release
        released = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=first_batch_id,
            row_id=first_row_id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=True,
            actor_context=ACTOR,
        )
        assert released["status"] == "removed", released
        assert db.get(Order, order.id).order_status == "PAYED"
        reprocessed = create_batch(db, store.id, order.id)
        assert reprocessed["status"] == "created", reprocessed

        stale_order = add_order(db, store.id, "stale")
        db.commit()
        stale_batch = create_batch(db, store.id, stale_order.id)
        stale_batch_id = stale_batch["batch"]["id"]
        stale_row_id = stale_batch["batch"]["rows"][0]["id"]
        stale_grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=stale_batch_id, user_id=77, grant_scope="manifest",
        )
        db.get(WarehouseShippingBatchOrder, stale_row_id).carrier = "CJ"
        db.commit()
        assert warehouse_shipping_service.consume_approval_grant(
            db, batch_id=stale_batch_id, user_id=77, grant_scope="manifest", token=stale_grant["approval_token"],
        ) is False

        completed_order = add_order(db, store.id, "completed")
        db.commit()
        completed_batch = create_batch(db, store.id, completed_order.id)
        completed_batch_id = completed_batch["batch"]["id"]
        completed_row_id = completed_batch["batch"]["rows"][0]["id"]
        completed_row = db.get(WarehouseShippingBatchOrder, completed_row_id)
        completed_row.row_status = "platform_written"
        completed_row.is_active = False
        completed_row.active_lock = None
        db.get(WarehouseShippingBatch, completed_batch_id).status = "completed"
        completed_order.order_status = "DISPATCHED"
        db.commit()
        nonrecoverable = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=completed_batch_id,
            row_id=completed_row_id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=True,
            actor_context=ACTOR,
        )
        assert nonrecoverable["skip_reason"] == "completed_batch_row_cannot_be_removed", nonrecoverable
        rebatch_blocked = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=store.id,
            platform="naver",
            order_ids=[completed_order.id],
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert rebatch_blocked["skip_reason"] == "orders_not_shippable_or_already_platform_written", rebatch_blocked
    print("warehouse shipping reprocess verification ok")


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
