import base64
import os
os.environ.setdefault("ALLOW_DEV_AUTH", "true")
import sys
import tempfile
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEMP_DB = Path(tempfile.gettempdir()) / "verify-warehouse-shipping-batch.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DB.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"

from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models.order import Order
from app.models.shipping import LogisticsInventoryMapping, ShippingTrackingImportRow, WarehouseShippingBatch
from app.models.store import Store
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser
from app.services import shipping_service, warehouse_shipping_service
from app.services.operator_access_service import OperatorIdentity, require_store_permission
from app.services import order_service


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
        other_store = Store(name="warehouse-other-store-test", platform="naver")
        db.add_all([store, other_store])
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
        user = ErpUser(user_key_hash="warehouse-operator-key", display_name="Warehouse Operator", status="active")
        other_user = ErpUser(user_key_hash="warehouse-other-operator-key", display_name="Other Warehouse Operator", status="active")
        restricted_user = ErpUser(user_key_hash="warehouse-restricted-key", display_name="Restricted Warehouse User", status="active")
        role = ErpRole(role_key="shipping_operator_test", role_label_zh="发货运营", role_label_en="Shipping operator")
        restricted_role = ErpRole(role_key="shipping_restricted_test", role_label_zh="受限运营", role_label_en="Restricted operator")
        db.add_all([user, other_user, restricted_user, role, restricted_role])
        db.flush()
        permissions = [
            db.query(ErpPermission).filter(ErpPermission.permission_key == key).one()
            for key in ("recipient_pii.view", "recipient_pii.export", "shipping.batch.manage")
        ]
        db.add_all([ErpRolePermission(role_id=role.id, permission_id=item.id) for item in permissions])
        db.add(ErpStoreMembership(user_id=user.id, store_id=store.id, role_id=role.id, membership_status="active"))
        db.add(ErpStoreMembership(user_id=other_user.id, store_id=other_store.id, role_id=role.id, membership_status="active"))
        db.add(ErpStoreMembership(user_id=restricted_user.id, store_id=store.id, role_id=restricted_role.id, membership_status="active"))
        db.commit()

        identity = OperatorIdentity(user_id=user.id, user_key_hash=user.user_key_hash)
        require_store_permission(db, identity=identity, store_id=store.id, permission_key="recipient_pii.view")
        try:
            require_store_permission(db, identity=identity, store_id=store.id + 999, permission_key="recipient_pii.view")
            raise AssertionError("cross-store recipient PII access should be denied")
        except Exception as exc:
            assert getattr(exc, "error_code", None) == "store_scope_forbidden", exc
        summary = order_service.list_orders(db, store_id=store.id, platform="naver", include_test_orders=True)[0]
        assert "receiver_name" not in summary and "receiver_address" not in summary and "raw_data" not in summary, summary
        operations = order_service.list_operations_orders(db, store_id=store.id, platform="naver", include_test_orders=True)[0]
        assert operations["receiver_name"] == "Kim Operator" and "raw_data" not in operations, operations

        actor = {"role": "operator", "actor_id": "warehouse-test"}
        created = warehouse_shipping_service.create_warehouse_batch(
            db, store_id=store.id, platform="naver", order_ids=[order.id], manual_approval=True, actor_context=actor,
        )
        assert created["status"] == "created", created
        batch_id = created["batch"]["id"]
        approval = warehouse_shipping_service.issue_approval_grant(db, batch_id=batch_id, user_id=user.id, grant_scope="manifest")
        assert warehouse_shipping_service.consume_approval_grant(db, batch_id=batch_id, user_id=user.id, grant_scope="manifest", token=approval["approval_token"]) is True
        assert warehouse_shipping_service.consume_approval_grant(db, batch_id=batch_id, user_id=user.id, grant_scope="manifest", token=approval["approval_token"]) is False
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
        actual_tracking = db.query(ShippingTrackingImportRow).filter(
            ShippingTrackingImportRow.import_batch_id == db.get(WarehouseShippingBatch, batch_id).tracking_import_batch_id,
        ).one()
        actual_tracking.carrier = "LOTTE"
        actual_tracking.tracking_number = "9876543210"
        actual_tracking.shipped_at = "2026-07-11T11:30:00+09:00"
        db.commit()

        review_orders = []
        for suffix in ("normal", "confirm"):
            review_order = Order(
                store_id=store.id,
                platform="naver",
                external_order_id=f"warehouse-review-order-{suffix}",
                external_product_order_id=f"warehouse-review-product-{suffix}",
                product_name="PXG Bag",
                quantity=1,
                order_amount=1,
                currency="KRW",
                order_status="PAYED",
                ordered_at=shipping_service.get_utc_now(),
                source_type="verify_warehouse_review",
            )
            db.add(review_order)
            review_orders.append(review_order)
        db.commit()
        review_batch = warehouse_shipping_service.create_warehouse_batch(
            db,
            store_id=store.id,
            platform="naver",
            order_ids=[item.id for item in review_orders],
            manual_approval=True,
            actor_context=actor,
        )
        assert review_batch["status"] == "created", review_batch
        review_batch_id = review_batch["batch"]["id"]
        review_manifest = warehouse_shipping_service.download_warehouse_manifest(
            db, batch_id=review_batch_id, manual_approval=True,
            privacy_access_acknowledged=True, actor_context=actor,
        )
        assert review_manifest["status"] == "warehouse_manifest_ready", review_manifest
        review_import = warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db,
            batch_id=review_batch_id,
            source_file_name="warehouse-review.xlsx",
            file_content_base64=xlsx([
                {
                    "order_reference": review_orders[0].external_order_id,
                    "product_order_reference": review_orders[0].external_product_order_id,
                    "logistics_inventory_code": "WH-PXG-001",
                    "carrier": "CJ",
                    "tracking_number": "5555555555",
                },
                {
                    "order_reference": review_orders[1].external_order_id,
                    "product_order_reference": review_orders[1].external_product_order_id,
                    "logistics_inventory_code": "WH-WRONG-001",
                    "carrier": "CJ",
                    "tracking_number": "5555555555",
                },
                {
                    "order_reference": "warehouse-review-order-unknown",
                    "product_order_reference": "warehouse-review-product-unknown",
                    "logistics_inventory_code": "WH-PXG-001",
                    "carrier": "CJ",
                    "tracking_number": "7777777777",
                },
            ]),
            manual_approval=True,
            actor_context=actor,
        )
        assert review_import["normal_count"] == 1, review_import
        assert review_import["needs_confirmation_count"] == 1, review_import
        assert review_import["blocked_count"] == 1, review_import
        with TestClient(app) as client:
            details_path = f"/api/v1/shipping/warehouse-batches/{batch_id}/tracking-details"
            unauthorized = client.get(details_path)
            assert unauthorized.status_code == 401, unauthorized.text
            permission_denied = client.get(details_path, headers={"X-ERP-User-Key": restricted_user.user_key_hash})
            assert permission_denied.status_code == 403, permission_denied.text
            cross_store = client.get(details_path, headers={"X-ERP-User-Key": other_user.user_key_hash})
            assert cross_store.status_code == 403, cross_store.text
            response = client.get(details_path, headers={"X-ERP-User-Key": user.user_key_hash})
            assert response.status_code == 200, response.text
            details = response.json()["data"]
            assert details["status"] == "ready" and details["batch_id"] == batch_id, details
            assert details["items"] == [{
                "tracking_record_id": actual_tracking.id,
                "batch_row_id": created["batch"]["rows"][0]["id"],
                "order_reference": "warehouse-order-001",
                "product_order_reference": "warehouse-product-order-001",
                "product_name": "PXG Bag",
                "carrier": "LOTTE",
                "tracking_number": "9876543210",
                "shipped_at": "2026-07-11T11:30:00+09:00",
                "validation_status": "ready_for_writeback",
                "exception_reason": None,
            }], details
            assert not any(field in str(details) for field in (
                "receiver_name", "receiver_phone", "receiver_address", "Seoul Test Street 1", "010-1234-5678",
            )), details

            duplicate_tracking = ShippingTrackingImportRow(
                import_batch_id=actual_tracking.import_batch_id,
                store_id=store.id,
                platform="naver",
                order_reference=actual_tracking.order_reference,
                product_order_reference=actual_tracking.product_order_reference,
                logistics_inventory_code=actual_tracking.logistics_inventory_code,
                carrier="CJ",
                tracking_number="1111222233",
                shipped_at="2026-07-11T11:45:00+09:00",
                row_status="ready_for_confirmation",
                future_write_allowed=False,
            )
            db.add(duplicate_tracking)
            db.commit()
            blocked_details = client.get(details_path, headers={"X-ERP-User-Key": user.user_key_hash})
            assert blocked_details.status_code == 200, blocked_details.text
            blocked_data = blocked_details.json()["data"]
            assert blocked_data["status"] == "blocked", blocked_data
            assert blocked_data["skip_reason"] == "shipping_tracking_product_order_match_not_unique", blocked_data
            db.delete(duplicate_tracking)
            db.commit()

            review_details_path = f"/api/v1/shipping/warehouse-batches/{review_batch_id}/tracking-details"
            review_response = client.get(review_details_path, headers={"X-ERP-User-Key": user.user_key_hash})
            assert review_response.status_code == 200, review_response.text
            review_details = review_response.json()["data"]
            assert review_details["status"] == "ready", review_details
            assert review_details["detail_mode"] == "warehouse_import_review", review_details
            assert len(review_details["items"]) == 3, review_details
            assert {item["validation_status"] for item in review_details["items"]} == {
                "ready_for_confirmation", "needs_confirmation", "blocked",
            }, review_details
            blocked_review_rows = [item for item in review_details["items"] if item["validation_status"] == "blocked"]
            assert len(blocked_review_rows) == 1 and blocked_review_rows[0]["batch_row_id"] is None, review_details
            assert blocked_review_rows[0]["product_name"] is None, review_details
            assert blocked_review_rows[0]["tracking_number"] == "7777777777", review_details
            assert "receiver_" not in str(review_details) and "010-1234-5678" not in str(review_details), review_details

            current_batch = db.get(WarehouseShippingBatch, batch_id)
            current_batch.status = "writeback_partial"
            current_batch.rows[0].row_status = "platform_failed"
            current_batch.rows[0].failure_reason = "platform_writeback_partial_or_failed"
            db.commit()
            partial_response = client.get(details_path, headers={"X-ERP-User-Key": user.user_key_hash})
            assert partial_response.status_code == 200, partial_response.text
            partial_details = partial_response.json()["data"]
            assert partial_details["status"] == "ready" and partial_details["detail_mode"] == "platform_writeback_review", partial_details
            assert partial_details["items"][0]["validation_status"] == "platform_failed", partial_details
            assert partial_details["items"][0]["exception_reason"] == "platform_writeback_partial_or_failed", partial_details
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
