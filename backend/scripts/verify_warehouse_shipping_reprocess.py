import base64
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-warehouse-shipping-reprocess.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"

from app.database import SessionLocal, engine, init_db
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.shipping import LogisticsInventoryMapping, ShippingTrackingImportBatch, ShippingTrackingImportRow, WarehouseShippingBatch, WarehouseShippingBatchOrder
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
        ("shipped_at", "Shipped at"),
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
        order_metadata = db.get(Order, order.id).raw_data or {}
        assert order_metadata["shipping_carrier_code"] == "CJGLS", order_metadata
        assert order_metadata["shipping_carrier_label"] == "CJ", order_metadata
        status_event = db.scalars(select(OrderStatusEvent).where(
            OrderStatusEvent.order_id == order.id,
            OrderStatusEvent.source_type == shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_SOURCE_TYPE,
        )).one()
        assert status_event.safe_metadata["shipping_carrier_code"] == "CJGLS", status_event.safe_metadata
        assert status_event.safe_metadata["shipping_carrier_label"] == "CJ", status_event.safe_metadata
        displayed_before_release = order_service.list_orders(
            db, store_id=store.id, platform="naver", include_test_orders=True,
        )[0]
        assert displayed_before_release["tracking_number"] == "1234**7890", displayed_before_release

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
        displayed_after_release = order_service.list_orders(
            db, store_id=store.id, platform="naver", include_test_orders=True,
        )[0]
        assert displayed_after_release["tracking_number"] is None, displayed_after_release
        assert displayed_after_release["delivery_company"] is None, displayed_after_release
        assert db.scalars(select(ShippingTrackingImportRow).where(
            ShippingTrackingImportRow.order_reference == order.external_order_id,
        )).first() is None
        assert db.get(WarehouseShippingBatch, first_batch_id).tracking_import_batch_id is None
        assert db.scalars(select(OrderStatusEvent).where(
            OrderStatusEvent.order_id == order.id,
            OrderStatusEvent.source_type == shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_SOURCE_TYPE,
        )).first() is None
        release_raw_data = db.get(Order, order.id).raw_data or {}
        assert not {
            "shipping_status_update_source",
            "shipping_status_update_phase",
            "shipping_status_update_correlation_id",
            "shipping_status_previous_status",
            "shipping_status_current_status",
            "shipping_tracking_hash",
            "shipping_carrier_code",
            "shipping_carrier_label",
            "shipping_tracking_import_batch_id",
        } & set(release_raw_data), release_raw_data
        reprocessed = create_batch(db, store.id, order.id)
        assert reprocessed["status"] == "created", reprocessed

        sibling_one = add_order(db, store.id, "sibling-one")
        sibling_two = add_order(db, store.id, "sibling-two")
        db.commit()
        sibling_batch = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=store.id,
            platform="naver",
            order_ids=[sibling_one.id, sibling_two.id],
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert sibling_batch["status"] == "created", sibling_batch
        sibling_batch_id = sibling_batch["batch"]["id"]
        sibling_rows = {
            item.local_order_id: item
            for item in db.scalars(select(WarehouseShippingBatchOrder).where(
                WarehouseShippingBatchOrder.batch_id == sibling_batch_id,
            )).all()
        }
        sibling_one_row = sibling_rows[sibling_one.id]
        sibling_two_row = sibling_rows[sibling_two.id]
        shared_order_reference = "shared-platform-order"
        sibling_one_row.order_reference = shared_order_reference
        sibling_two_row.order_reference = shared_order_reference
        db.commit()
        sibling_manifest = warehouse_shipping_service.download_warehouse_manifest(
            db,
            batch_id=sibling_batch_id,
            manual_approval=True,
            privacy_access_acknowledged=True,
            actor_context=ACTOR,
        )
        assert sibling_manifest["status"] == "warehouse_manifest_ready", sibling_manifest
        sibling_import = warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db,
            batch_id=sibling_batch_id,
            source_file_name="siblings-return.xlsx",
            file_content_base64=tracking_xlsx([
                {
                    "order_reference": shared_order_reference,
                    "product_order_reference": sibling_one.external_product_order_id,
                    "logistics_inventory_code": "WH-TEST-001",
                    "carrier": "CJ",
                    "tracking_number": "1111111111",
                    "shipped_at": "2026-07-11T09:00:00+09:00",
                },
                {
                    "order_reference": shared_order_reference,
                    "product_order_reference": sibling_two.external_product_order_id,
                    "logistics_inventory_code": "WH-TEST-001",
                    "carrier": "CJ",
                    "tracking_number": "2222222222",
                    "shipped_at": "2026-07-11T09:05:00+09:00",
                },
            ]),
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert sibling_import["normal_count"] == 2, sibling_import
        sibling_import_batch_id = db.get(WarehouseShippingBatch, sibling_batch_id).tracking_import_batch_id
        sibling_one_row.product_order_reference = None
        db.commit()
        ambiguous_release = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=sibling_batch_id,
            row_id=sibling_one_row.id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=True,
            actor_context=ACTOR,
        )
        assert ambiguous_release["skip_reason"] == "shipping_tracking_cleanup_ambiguous_manual_resolution_required", ambiguous_release
        assert sibling_one_row.tracking_number_hash is not None
        sibling_one_row.product_order_reference = sibling_one.external_product_order_id
        db.commit()
        missing_target_import = db.scalar(select(ShippingTrackingImportRow).where(
            ShippingTrackingImportRow.import_batch_id == sibling_import_batch_id,
            ShippingTrackingImportRow.product_order_reference == sibling_one.external_product_order_id,
        ))
        db.delete(missing_target_import)
        db.commit()
        missing_target_release = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=sibling_batch_id,
            row_id=sibling_one_row.id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=True,
            actor_context=ACTOR,
        )
        assert missing_target_release["skip_reason"] == "shipping_tracking_cleanup_ambiguous_manual_resolution_required", missing_target_release
        protected_sibling_import = db.scalars(select(ShippingTrackingImportRow).where(
            ShippingTrackingImportRow.import_batch_id == sibling_import_batch_id,
        )).all()
        assert len(protected_sibling_import) == 1
        assert protected_sibling_import[0].product_order_reference == sibling_two.external_product_order_id
        db.add(ShippingTrackingImportRow(
            import_batch_id=sibling_import_batch_id,
            store_id=store.id,
            platform="naver",
            order_reference=shared_order_reference,
            product_order_reference=sibling_one.external_product_order_id,
            logistics_inventory_code="WH-TEST-001",
            carrier="CJ",
            tracking_number="1111111111",
            shipped_at="2026-07-11T09:00:00+09:00",
            row_status="ready_for_confirmation",
            operator_note=None,
            future_write_allowed=False,
        ))
        db.commit()
        sibling_release = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=sibling_batch_id,
            row_id=sibling_one_row.id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=True,
            actor_context=ACTOR,
        )
        assert sibling_release["status"] == "removed", sibling_release
        db.refresh(sibling_one_row)
        db.refresh(sibling_two_row)
        assert sibling_one_row.carrier is None and sibling_one_row.tracking_number_hash is None and sibling_one_row.shipped_at is None
        assert sibling_two_row.carrier == "CJ" and sibling_two_row.tracking_number_hash is not None
        sibling_import_rows = db.scalars(select(ShippingTrackingImportRow).where(
            ShippingTrackingImportRow.import_batch_id == sibling_import_batch_id,
        )).all()
        assert len(sibling_import_rows) == 1 and sibling_import_rows[0].product_order_reference == sibling_two.external_product_order_id
        sibling_import_batch = db.get(ShippingTrackingImportBatch, sibling_import_batch_id)
        assert sibling_import_batch.row_count == 1 and sibling_import_batch.ready_row_count == 1
        assert sibling_import_batch.duplicate_row_count == 0 and sibling_import_batch.blocked_row_count == 0

        legacy_order = add_order(db, store.id, "legacy")
        db.commit()
        legacy_batch = create_batch(db, store.id, legacy_order.id)
        legacy_row_id = legacy_batch["batch"]["rows"][0]["id"]
        db.get(WarehouseShippingBatchOrder, legacy_row_id).pre_batch_order_status = None
        db.commit()
        legacy_release = warehouse_shipping_service.remove_warehouse_batch_row(
            db,
            batch_id=legacy_batch["batch"]["id"],
            row_id=legacy_row_id,
            reason_code="warehouse_exception",
            warehouse_stopped_shipping=False,
            actor_context=ACTOR,
        )
        assert legacy_release["skip_reason"] == "pre_batch_order_status_missing_manual_resolution_required", legacy_release

        stale_order = add_order(db, store.id, "stale")
        db.commit()
        stale_batch = create_batch(db, store.id, stale_order.id)
        stale_batch_id = stale_batch["batch"]["id"]
        stale_row_id = stale_batch["batch"]["rows"][0]["id"]
        stale_grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=stale_batch_id, user_id=77, grant_scope="manifest",
        )
        db.get(WarehouseShippingBatchOrder, stale_row_id).product_name = "Changed manifest product"
        db.commit()
        assert warehouse_shipping_service.consume_approval_grant(
            db, batch_id=stale_batch_id, user_id=77, grant_scope="manifest", token=stale_grant["approval_token"],
        ) is False

        writeback_order = add_order(db, store.id, "writeback-approval")
        db.commit()
        writeback_batch = create_batch(db, store.id, writeback_order.id)
        writeback_batch_id = writeback_batch["batch"]["id"]
        writeback_manifest = warehouse_shipping_service.download_warehouse_manifest(
            db, batch_id=writeback_batch_id, manual_approval=True,
            privacy_access_acknowledged=True, actor_context=ACTOR,
        )
        assert writeback_manifest["status"] == "warehouse_manifest_ready", writeback_manifest
        writeback_import = warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db,
            batch_id=writeback_batch_id,
            source_file_name="writeback-approval.xlsx",
            file_content_base64=tracking_xlsx([{
                "order_reference": writeback_order.external_order_id,
                "product_order_reference": writeback_order.external_product_order_id,
                "logistics_inventory_code": "WH-TEST-001",
                "carrier": "CJ",
                "tracking_number": "3333333333",
                "shipped_at": "2026-07-11T10:00:00+09:00",
            }]),
            manual_approval=True,
            actor_context=ACTOR,
        )
        assert writeback_import["normal_count"] == 1, writeback_import
        writeback_confirmed = warehouse_shipping_service.confirm_warehouse_batch(
            db, batch_id=writeback_batch_id, confirmed_row_ids=[], manual_approval=True, actor_context=ACTOR,
        )
        assert writeback_confirmed["status"] == "ready_to_writeback", writeback_confirmed
        writeback_import_batch_id = db.get(WarehouseShippingBatch, writeback_batch_id).tracking_import_batch_id
        actual_tracking = db.scalar(select(ShippingTrackingImportRow).where(
            ShippingTrackingImportRow.import_batch_id == writeback_import_batch_id,
        ))
        original_tracking = {
            "carrier": actual_tracking.carrier,
            "tracking_number": actual_tracking.tracking_number,
            "shipped_at": actual_tracking.shipped_at,
        }
        changed_values = {
            "carrier": "LOTTE",
            "tracking_number": "4444444444",
            "shipped_at": "2026-07-11T10:30:00+09:00",
        }
        for index, (field, changed_value) in enumerate(changed_values.items(), start=81):
            grant = warehouse_shipping_service.issue_approval_grant(
                db, batch_id=writeback_batch_id, user_id=index, grant_scope="writeback",
            )
            assert grant["status"] == "approval_granted", grant
            setattr(actual_tracking, field, changed_value)
            db.commit()
            assert warehouse_shipping_service.consume_approval_grant(
                db, batch_id=writeback_batch_id, user_id=index, grant_scope="writeback", token=grant["approval_token"],
            ) is False
            setattr(actual_tracking, field, original_tracking[field])
            db.commit()

        final_candidates, final_candidate_error = warehouse_shipping_service._writeback_execution_candidates(
            db, db.get(WarehouseShippingBatch, writeback_batch_id),
        )
        assert final_candidate_error is None and final_candidates, final_candidate_error
        final_grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=writeback_batch_id, user_id=90, grant_scope="writeback",
        )
        approved_candidate_hash = warehouse_shipping_service.consume_approval_grant_with_candidate_hash(
            db, batch_id=writeback_batch_id, user_id=90, grant_scope="writeback", token=final_grant["approval_token"],
        )
        captured_tracking_rows = []
        original_writeback = shipping_service.execute_naver_shipment_writeback

        def fake_writeback(*_args, **kwargs):
            captured_tracking_rows.extend(kwargs["tracking_rows"])
            return {"status": "success", "real_api_called": False}

        shipping_service.execute_naver_shipment_writeback = fake_writeback
        try:
            writeback_result = warehouse_shipping_service.execute_warehouse_batch_writeback(
                db,
                batch_id=writeback_batch_id,
                manual_approval=True,
                final_operator_confirmation=True,
                real_api_call_requested=True,
                actor_context=ACTOR,
                approved_candidate_hash=approved_candidate_hash,
            )
        finally:
            shipping_service.execute_naver_shipment_writeback = original_writeback
        assert writeback_result["status"] == "success", writeback_result
        assert captured_tracking_rows == [{
            "order_reference": final_candidates[0]["order_reference"],
            "product_order_reference": final_candidates[0]["product_order_reference"],
            "carrier": final_candidates[0]["carrier"],
            "tracking_number": final_candidates[0]["tracking_number"],
            "shipped_at": final_candidates[0]["shipped_at"],
        }], captured_tracking_rows

        recipient_order = add_order(db, store.id, "recipient", {"delivery_memo": "Original memo"})
        db.commit()
        recipient_batch = create_batch(db, store.id, recipient_order.id)
        recipient_grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=recipient_batch["batch"]["id"], user_id=78, grant_scope="manifest",
        )
        recipient_order.raw_data = {"delivery_memo": "Changed memo"}
        db.commit()
        assert warehouse_shipping_service.consume_approval_grant(
            db, batch_id=recipient_batch["batch"]["id"], user_id=78, grant_scope="manifest", token=recipient_grant["approval_token"],
        ) is False

        product_order = add_order(db, store.id, "product")
        db.commit()
        product_batch = create_batch(db, store.id, product_order.id)
        product_batch_id = product_batch["batch"]["id"]
        product_grant = warehouse_shipping_service.issue_approval_grant(
            db, batch_id=product_batch_id, user_id=79, grant_scope="manifest",
        )
        db.get(WarehouseShippingBatchOrder, product_batch["batch"]["rows"][0]["id"]).product_name = "Changed warehouse product"
        db.commit()
        assert warehouse_shipping_service.consume_approval_grant(
            db, batch_id=product_batch_id, user_id=79, grant_scope="manifest", token=product_grant["approval_token"],
        ) is False

        generic_name_order = add_order(db, store.id, "generic-name", {"name": "Warehouse Test Bag"})
        generic_name_order.receiver_name = None
        db.commit()
        generic_contract = order_service.recipient_contract(generic_name_order)
        assert generic_contract["receiver_name"] == "", generic_contract

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
