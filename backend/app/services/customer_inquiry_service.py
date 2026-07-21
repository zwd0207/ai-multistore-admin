import re
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.timezone import get_utc_now
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyCustomerInquiry, PxgNaverReadonlyLogisticsRecord
from app.models.shipping import ShippingTrackingImportRow, WarehouseShippingBatchOrder
from app.services.naver_inquiry_identity import naver_inquiry_external_id_hash
from app.services.pxg_naver_readonly_persistence_service import assert_pxg_naver_cleanup_healthy
from app.services.store_service import ensure_store_exists


PXG_NAVER_READONLY_SOURCE = "pxg_naver_readonly_local_v1"
NAVER_LEGACY_SYNC_SOURCE = "naver_customer_inquiry_real_sync"
_PHONE_OR_LONG_NUMBER = re.compile(r"(?<!\w)\+?\d[\d\s()-]{6,}\d(?!\w)")
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")


def _safe_label(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = _EMAIL.sub("[redacted]", _PHONE_OR_LONG_NUMBER.sub("[redacted]", value))
    cleaned = " ".join(cleaned.split())[:160]
    return cleaned or fallback


def _safe_summary(*, inquiry_type: object, category: object = None) -> str:
    label = _safe_label(category if category is not None else inquiry_type, fallback="customer inquiry")
    return f"{label} inquiry"


def _classification(status: object, answered_at=None) -> str:
    normalized = str(status or "").strip().lower()
    return "answered" if answered_at is not None or normalized in {"answered", "resolved", "closed"} else "unanswered"


def _is_superseded_naver_legacy(
    inquiry: CustomerInquiry,
    readonly_hashes: set[tuple[str, str]],
) -> bool:
    if inquiry.platform != "naver":
        return False
    raw_data = inquiry.raw_data if isinstance(inquiry.raw_data, dict) else {}
    if raw_data.get("superseded_by_readonly") is True:
        return True
    if raw_data.get("source_type") != NAVER_LEGACY_SYNC_SOURCE:
        return False
    inquiry_hash = naver_inquiry_external_id_hash(inquiry.external_inquiry_id)
    return bool(inquiry_hash and (inquiry.platform, inquiry_hash) in readonly_hashes)


def _mask_tracking_number(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip()
    if len(normalized) <= 4:
        return "*" * len(normalized)
    if len(normalized) <= 8:
        return f"{normalized[:2]}{'*' * (len(normalized) - 4)}{normalized[-2:]}"
    return f"{normalized[:4]}{'*' * (len(normalized) - 8)}{normalized[-4:]}"


def _order_context(db: Session, order: Order | None) -> tuple[dict, dict]:
    if order is None:
        return {}, {}

    batch_row = db.scalar(select(WarehouseShippingBatchOrder).where(
        WarehouseShippingBatchOrder.local_order_id == order.id,
    ).order_by(WarehouseShippingBatchOrder.id.desc()))
    order_context = {
        "order_no": order.external_order_id,
        "product_order_no": order.external_product_order_id,
        "product_name": order.product_name,
        "order_status": order.order_status,
        "warehouse_batch_no": batch_row.batch.batch_no if batch_row is not None else None,
        "warehouse_batch_status": batch_row.batch.status if batch_row is not None else None,
        "warehouse_row_status": batch_row.row_status if batch_row is not None else None,
    }
    readonly_logistics = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
        PxgNaverReadonlyLogisticsRecord.order_id == order.id,
        PxgNaverReadonlyLogisticsRecord.store_id == order.store_id,
        PxgNaverReadonlyLogisticsRecord.platform == order.platform,
    ).order_by(PxgNaverReadonlyLogisticsRecord.id.desc()))
    if readonly_logistics is not None:
        expires_at = readonly_logistics.expires_at
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        is_stale = bool(readonly_logistics.is_stale or expires_at <= get_utc_now())
        return order_context, {
            "carrier": readonly_logistics.carrier,
            "tracking_number_masked": None if is_stale else readonly_logistics.tracking_number_masked,
            "shipment_status": readonly_logistics.shipment_status,
            "shipped_at": readonly_logistics.shipped_at,
            "updated_at": readonly_logistics.source_updated_at,
            "is_stale": is_stale,
            "logistics_stale": is_stale,
        }
    if batch_row is None or batch_row.batch.tracking_import_batch_id is None:
        return order_context, {}
    tracking_row = db.scalar(select(ShippingTrackingImportRow).where(
        ShippingTrackingImportRow.import_batch_id == batch_row.batch.tracking_import_batch_id,
        ShippingTrackingImportRow.product_order_reference == order.external_product_order_id,
    ).order_by(ShippingTrackingImportRow.id.desc()))
    if tracking_row is None:
        return order_context, {}
    return order_context, {
        "carrier": tracking_row.carrier,
        "tracking_number_masked": _mask_tracking_number(tracking_row.tracking_number),
        "shipment_status": tracking_row.row_status,
        "shipped_at": tracking_row.shipped_at,
        "updated_at": tracking_row.created_at,
        "is_stale": False,
    }


def _find_generic_related_order(db: Session, inquiry: CustomerInquiry) -> Order | None:
    raw_data = inquiry.raw_data if isinstance(inquiry.raw_data, dict) else {}
    order_reference = raw_data.get("order_id") or raw_data.get("external_order_id")
    product_order_ids = raw_data.get("product_order_id_list") or []
    product_order_reference = raw_data.get("product_order_id") or (product_order_ids[0] if product_order_ids else None)
    if not order_reference and not product_order_reference:
        return None
    statement = select(Order).where(
        Order.store_id == inquiry.store_id,
        Order.platform == inquiry.platform,
    )
    if order_reference:
        statement = statement.where(Order.external_order_id == str(order_reference))
    else:
        statement = statement.where(Order.external_product_order_id == str(product_order_reference))
    return db.scalar(statement)


def _serialize_generic_inquiry(db: Session, inquiry: CustomerInquiry) -> dict:
    order_context, logistics_context = _order_context(db, _find_generic_related_order(db, inquiry))
    inquiry_type = _safe_label(inquiry.inquiry_type, fallback="customer_inquiry")
    classification = _classification(inquiry.status, inquiry.answered_at)
    return {
        "source": "generic",
        "inquiry_id": f"generic:{inquiry.id}",
        "platform": inquiry.platform,
        "category": inquiry_type,
        "inquiry_type": inquiry_type,
        "status": inquiry.status,
        "classification": classification,
        "has_answer_content": classification == "answered",
        "conversation_message_count": 2 if classification == "answered" else 1,
        "summary": _safe_summary(inquiry_type=inquiry_type),
        "created_at": inquiry.received_at,
        "updated_at": inquiry.updated_at,
        "store_id": inquiry.store_id,
        "order_context": order_context,
        "logistics_context": logistics_context,
        "reply_enabled": False,
        "reply_disabled_reason": "legacy_readonly",
    }


def _serialize_pxg_readonly_inquiry(db: Session, inquiry: PxgNaverReadonlyCustomerInquiry) -> dict:
    order = db.get(Order, inquiry.related_order_id) if inquiry.related_order_id is not None else None
    order_context, logistics_context = _order_context(db, order)
    inquiry_type = _safe_label(inquiry.inquiry_type, fallback="customer_inquiry")
    category = _safe_label(inquiry.subject_category or inquiry_type, fallback=inquiry_type)
    classification = _classification(inquiry.status, inquiry.answered_at)
    has_answer_content = bool(inquiry.encrypted_answer_content and inquiry.answer_content_hash)
    return {
        "source": PXG_NAVER_READONLY_SOURCE,
        "inquiry_id": f"pxg_naver_readonly:{inquiry.id}",
        "platform": inquiry.platform,
        "category": category,
        "inquiry_type": inquiry_type,
        "status": inquiry.status,
        "classification": classification,
        "has_answer_content": has_answer_content,
        "conversation_message_count": 1 + int(has_answer_content),
        "customer_name_masked": inquiry.customer_display_masked,
        "summary": _safe_summary(inquiry_type=inquiry_type, category=category),
        "created_at": inquiry.received_at or inquiry.created_at,
        "updated_at": inquiry.updated_at,
        "store_id": inquiry.store_id,
        "order_context": order_context,
        "logistics_context": logistics_context,
        "reply_enabled": False,
        "reply_disabled_reason": "readonly_source",
    }


def assert_customer_inquiry_read_cleanup_healthy(
    db: Session,
    *,
    store_id: int,
    platform: str | None = None,
) -> None:
    if platform is not None and platform != "naver":
        return
    has_pxg_inquiry = db.scalar(select(PxgNaverReadonlyCustomerInquiry.id).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
    ).limit(1))
    if has_pxg_inquiry is not None:
        assert_pxg_naver_cleanup_healthy(db, store_id=store_id, settings=get_settings())


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


def _normalized_platform(platform: str | None) -> str | None:
    normalized = str(platform or "").strip().casefold()
    return normalized or None


def _formal_customer_inquiry_rows(
    db: Session,
    *,
    store_id: int | None = None,
    platform: str | None = None,
) -> tuple[list[CustomerInquiry], list[PxgNaverReadonlyCustomerInquiry]]:
    """Return the single formal read source without exposing legacy Naver rows.

    `CustomerInquiry` remains for non-Naver compatibility and historical storage,
    but Naver business views must only use the protected readonly records.
    """
    normalized_platform = _normalized_platform(platform)

    readonly_statement = select(PxgNaverReadonlyCustomerInquiry).where(
        func.lower(PxgNaverReadonlyCustomerInquiry.platform) == "naver",
    ).order_by(PxgNaverReadonlyCustomerInquiry.id.asc())
    generic_statement = select(CustomerInquiry).where(
        func.lower(CustomerInquiry.platform) != "naver",
    ).order_by(CustomerInquiry.id.asc())
    if store_id is not None:
        readonly_statement = readonly_statement.where(PxgNaverReadonlyCustomerInquiry.store_id == store_id)
        generic_statement = generic_statement.where(CustomerInquiry.store_id == store_id)
    if normalized_platform is not None:
        readonly_statement = readonly_statement.where(func.lower(PxgNaverReadonlyCustomerInquiry.platform) == normalized_platform)
        generic_statement = generic_statement.where(func.lower(CustomerInquiry.platform) == normalized_platform)

    return (
        db.scalars(generic_statement).all(),
        db.scalars(readonly_statement).all(),
    )


def _formal_customer_inquiry_summary(
    generic_rows: list[CustomerInquiry],
    readonly_rows: list[PxgNaverReadonlyCustomerInquiry],
) -> dict[str, int | dict[str, int]]:
    classifications = {"all": 0, "answered": 0, "unanswered": 0}
    open_count = 0
    authenticity_open_count = 0
    for inquiry in [*generic_rows, *readonly_rows]:
        status = str(inquiry.status or "").strip().casefold()
        classification = _classification(status, inquiry.answered_at)
        classifications["all"] += 1
        classifications[classification] += 1
        if status == "open":
            open_count += 1
            if str(inquiry.inquiry_type or "").strip().casefold() == "authenticity":
                authenticity_open_count += 1
    return {
        "total": classifications["all"],
        "classification_counts": classifications,
        "open_count": open_count,
        "authenticity_open_count": authenticity_open_count,
    }


def get_customer_inquiry_read_model(
    db: Session,
    *,
    store_id: int,
    platform: str | None = None,
) -> dict:
    """Build the formal customer-inquiry list and its matching aggregate counts."""
    ensure_store_exists(db, store_id)
    generic_rows, readonly_rows = _formal_customer_inquiry_rows(
        db,
        store_id=store_id,
        platform=platform,
    )
    results = [_serialize_generic_inquiry(db, item) for item in generic_rows]
    results.extend(_serialize_pxg_readonly_inquiry(db, item) for item in readonly_rows)
    deduplicated = {(item["source"], item["inquiry_id"]): item for item in results}
    return {
        "items": list(deduplicated.values()),
        **_formal_customer_inquiry_summary(generic_rows, readonly_rows),
    }


def summarize_formal_customer_inquiries(
    db: Session,
    *,
    store_id: int | None = None,
    platform: str | None = None,
) -> dict[str, int | dict[str, int]]:
    """Return dashboard-safe counts from the same formal customer-inquiry source."""
    generic_rows, readonly_rows = _formal_customer_inquiry_rows(
        db,
        store_id=store_id,
        platform=platform,
    )
    return _formal_customer_inquiry_summary(generic_rows, readonly_rows)


def list_customer_inquiries(db: Session, store_id: int, platform: str | None = None) -> list[dict]:
    return get_customer_inquiry_read_model(
        db,
        store_id=store_id,
        platform=platform,
    )["items"]


def summarize_classifications(items: list[dict]) -> dict[str, int]:
    answered = sum(1 for item in items if item.get("classification") == "answered")
    unanswered = len(items) - answered
    return {"all": len(items), "answered": answered, "unanswered": unanswered}
