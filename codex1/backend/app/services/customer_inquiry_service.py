from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.shipping import ShippingTrackingImportRow, WarehouseShippingBatchOrder
from app.schemas.customer_inquiry import CustomerInquiryRead
from app.services.store_service import ensure_store_exists


def serialize_customer_inquiry(inquiry: CustomerInquiry) -> dict:
    return CustomerInquiryRead.model_validate(inquiry).model_dump(mode="json")


def upsert_customer_inquiries(db: Session, store_id: int, platform: str, items: list[dict]) -> dict:
    ensure_store_exists(db, store_id)
    created = 0
    updated = 0

    for item in items:
        external_inquiry_id = item["external_inquiry_id"]
        inquiry = db.scalar(
            select(CustomerInquiry).where(
                CustomerInquiry.store_id == store_id,
                CustomerInquiry.platform == platform,
                CustomerInquiry.external_inquiry_id == external_inquiry_id,
            )
        )
        payload = {**item, "store_id": store_id, "platform": platform}
        if inquiry is None:
            db.add(CustomerInquiry(**payload))
            created += 1
            continue

        for field, value in payload.items():
            setattr(inquiry, field, value)
        updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(items)}


def list_customer_inquiries(db: Session, store_id: int, platform: str | None = None) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(CustomerInquiry).where(CustomerInquiry.store_id == store_id).order_by(CustomerInquiry.id.asc())
    if platform:
        statement = statement.where(CustomerInquiry.platform == platform)

    results = []
    for item in db.scalars(statement).all():
        serialized = serialize_customer_inquiry(item)
        raw_data = item.raw_data if isinstance(item.raw_data, dict) else {}
        order_reference = raw_data.get("order_id") or raw_data.get("external_order_id")
        product_order_ids = raw_data.get("product_order_id_list") or []
        product_order_reference = raw_data.get("product_order_id") or (product_order_ids[0] if product_order_ids else None)
        order = db.scalar(select(Order).where(
            Order.store_id == item.store_id,
            (Order.external_order_id == order_reference) if order_reference else (
                Order.external_product_order_id == product_order_reference
            ),
        )) if order_reference or product_order_reference else None
        if order is not None:
            batch_row = db.scalar(select(WarehouseShippingBatchOrder).where(
                WarehouseShippingBatchOrder.local_order_id == order.id,
            ).order_by(WarehouseShippingBatchOrder.id.desc()))
            tracking_row = None
            if batch_row is not None and batch_row.batch.tracking_import_batch_id is not None:
                tracking_row = db.scalar(select(ShippingTrackingImportRow).where(
                    ShippingTrackingImportRow.import_batch_id == batch_row.batch.tracking_import_batch_id,
                    ShippingTrackingImportRow.product_order_reference == order.external_product_order_id,
                ).order_by(ShippingTrackingImportRow.id.desc()))
            serialized["related_order"] = {
                "order_no": order.external_order_id,
                "product_order_no": order.external_product_order_id,
                "product_name": order.product_name,
                "order_status": order.order_status,
                "batch_no": batch_row.batch.batch_no if batch_row is not None else None,
                "batch_status": batch_row.batch.status if batch_row is not None else None,
                "warehouse_row_status": batch_row.row_status if batch_row is not None else None,
                "carrier": tracking_row.carrier if tracking_row is not None else (batch_row.carrier if batch_row is not None else None),
                "tracking_number": tracking_row.tracking_number if tracking_row is not None else None,
                "tracking_status": tracking_row.row_status if tracking_row is not None else None,
            }
        results.append(serialized)
    return results
