from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.shipping import ShippingTrackingImportRow
from app.schemas.order import OrderRead
from app.services.store_service import ensure_store_exists

TEST_ORDER_SOURCE_TYPES = {"mock_sync", "local_frontend_mock"}
DELIVERY_COMPANY_LABELS = {
    "CJ": "CJ대한통운",
    "CJGLS": "CJ대한통운",
}


def _clean_text(value: object, max_length: int = 160) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _first_text(*values: object, max_length: int = 160) -> str | None:
    for value in values:
        text = _clean_text(value, max_length=max_length)
        if text:
            return text
    return None


def _display_delivery_company(value: object) -> str | None:
    text = _clean_text(value, max_length=120)
    if not text:
        return None
    return DELIVERY_COMPANY_LABELS.get(text.upper(), text)


def _find_nested_text(payload: object, keys: tuple[str, ...], max_length: int = 160) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value is not None and value != "" and not isinstance(value, (dict, list)):
                return _clean_text(value, max_length=max_length)
        for value in payload.values():
            found = _find_nested_text(value, keys, max_length=max_length)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_nested_text(item, keys, max_length=max_length)
            if found:
                return found
    return None


def _order_reference_keys(order: Order) -> list[str]:
    keys = [
        order.external_order_id,
        order.external_product_order_id,
        f"local-order-{order.id}",
    ]
    return [str(item).strip() for item in keys if str(item or "").strip()]


def _build_tracking_lookup(rows: list[ShippingTrackingImportRow]) -> dict[str, ShippingTrackingImportRow]:
    lookup: dict[str, ShippingTrackingImportRow] = {}
    for row in rows:
        for key in (row.order_reference, row.product_order_reference):
            text = str(key or "").strip()
            if text and text not in lookup:
                lookup[text] = row
    return lookup


def _tracking_row_for_order(
    order: Order,
    lookup: dict[str, ShippingTrackingImportRow] | None,
) -> ShippingTrackingImportRow | None:
    if not lookup:
        return None
    for key in _order_reference_keys(order):
        row = lookup.get(key)
        if row is not None:
            return row
    return None


def _order_delivery_fields(order: Order, tracking_row: ShippingTrackingImportRow | None = None) -> dict[str, str | None]:
    raw_data = order.raw_data if isinstance(order.raw_data, dict) else {}
    delivery_company = _first_text(
        _find_nested_text(raw_data, (
            "delivery_company",
            "deliveryCompany",
            "deliveryCompanyName",
            "delivery_company_name",
            "carrier",
            "carrier_label",
            "shipping_carrier_label",
            "courier",
            "courierCompany",
        )),
        tracking_row.carrier if tracking_row else None,
        _find_nested_text(raw_data, ("delivery_company_code", "deliveryCompanyCode", "shipping_carrier_code")),
        max_length=120,
    )
    delivery_company_code = _first_text(
        _find_nested_text(raw_data, ("delivery_company_code", "deliveryCompanyCode", "shipping_carrier_code")),
        max_length=80,
    )
    tracking_number = _first_text(
        _find_nested_text(raw_data, (
            "tracking_number",
            "trackingNumber",
            "invoice_no",
            "invoiceNo",
            "invoiceNumber",
            "waybill_no",
            "waybillNo",
            "waybillNumber",
            "shipping_tracking_number",
        ), max_length=120),
        tracking_row.tracking_number if tracking_row else None,
        max_length=120,
    )
    trace_status = "local_tracking_trace" if tracking_number else "tracking_number_missing"
    return {
        "delivery_company": _display_delivery_company(delivery_company),
        "delivery_company_code": delivery_company_code,
        "tracking_number": tracking_number,
        "logistics_trace_status": trace_status,
    }


def serialize_order(order: Order, tracking_row: ShippingTrackingImportRow | None = None) -> dict:
    payload = OrderRead.model_validate(order).model_dump(mode="json")
    raw_data = order.raw_data if isinstance(order.raw_data, dict) else {}
    payload["receiver_phone"] = payload.get("receiver_phone") or _find_nested_text(
        raw_data,
        ("receiver_phone", "receiverPhone", "receiverTelNo", "receiverTelNo1", "receiverTelNo2", "tel1", "tel2"),
        max_length=40,
    )
    payload["receiver_name"] = payload.get("receiver_name") or _find_nested_text(
        raw_data,
        ("receiver_name", "receiverName", "recipientName", "name"),
        max_length=120,
    )
    payload["receiver_address"] = payload.get("receiver_address") or _find_nested_text(
        raw_data,
        ("receiver_address", "receiverAddress", "recipientAddress", "baseAddress", "roadNameAddress"),
        max_length=300,
    )
    payload.update(_order_delivery_fields(order, tracking_row))
    return payload


def serialize_order_summary(order: Order, tracking_row: ShippingTrackingImportRow | None = None) -> dict:
    payload = serialize_order(order, tracking_row)
    for field in ("buyer_name", "buyer_phone", "receiver_name", "receiver_phone", "receiver_address", "zip_code", "raw_data"):
        payload.pop(field, None)
    return payload


def upsert_orders(db: Session, store_id: int, platform: str, items: list[dict]) -> dict:
    ensure_store_exists(db, store_id)
    created = 0
    updated = 0

    for item in items:
        external_order_id = item["external_order_id"]
        order = db.scalar(
            select(Order).where(
                Order.store_id == store_id,
                Order.platform == platform,
                Order.external_order_id == external_order_id,
            )
        )
        payload = {**item, "store_id": store_id, "platform": platform}
        if order is None:
            db.add(Order(**payload))
            created += 1
            continue

        for field, value in payload.items():
            setattr(order, field, value)
        updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(items)}


def list_orders(
    db: Session,
    store_id: int,
    platform: str | None = None,
    include_test_orders: bool = False,
) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(Order).where(Order.store_id == store_id).order_by(Order.id.asc())
    if platform:
        statement = statement.where(Order.platform == platform)
    if not include_test_orders:
        statement = statement.where(Order.source_type.notin_(TEST_ORDER_SOURCE_TYPES))

    orders = db.scalars(statement).all()
    tracking_statement = select(ShippingTrackingImportRow).where(ShippingTrackingImportRow.store_id == store_id)
    if platform:
        tracking_statement = tracking_statement.where(ShippingTrackingImportRow.platform == platform)
    tracking_statement = tracking_statement.order_by(
        ShippingTrackingImportRow.created_at.desc(),
        ShippingTrackingImportRow.id.desc(),
    )
    tracking_lookup = _build_tracking_lookup(db.scalars(tracking_statement).all())

    return [serialize_order_summary(item, _tracking_row_for_order(item, tracking_lookup)) for item in orders]


def list_operations_orders(db: Session, store_id: int, platform: str | None = None, include_test_orders: bool = False) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(Order).where(Order.store_id == store_id).order_by(Order.id.asc())
    if platform:
        statement = statement.where(Order.platform == platform)
    if not include_test_orders:
        statement = statement.where(Order.source_type.notin_(TEST_ORDER_SOURCE_TYPES))
    return [
        {key: value for key, value in serialize_order(order).items() if key != "raw_data"}
        for order in db.scalars(statement).all()
    ]


def count_test_orders(db: Session, store_id: int, platform: str | None = None) -> int:
    ensure_store_exists(db, store_id)
    statement = select(Order).where(
        Order.store_id == store_id,
        Order.source_type.in_(TEST_ORDER_SOURCE_TYPES),
    )
    if platform:
        statement = statement.where(Order.platform == platform)
    return len(db.scalars(statement).all())


def _event_time(value: datetime | str | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return _clean_text(value, max_length=80)


def _add_timeline_event(
    events: list[dict[str, Any]],
    *,
    time: datetime | str | None,
    label: str,
    description: str,
    source: str,
) -> None:
    events.append({
        "time": _event_time(time),
        "label": label,
        "description": description,
        "source": source,
    })


def get_order_logistics_timeline(db: Session, *, store_id: int, order_id: int) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    order = db.scalar(select(Order).where(Order.id == order_id, Order.store_id == store_id))
    if order is None:
        return {
            "status": "order_not_found",
            "order_id": order_id,
            "store_id": store_id,
            "message": "订单不存在或不属于当前店铺。",
            "events": [],
        }

    tracking_rows = db.scalars(
        select(ShippingTrackingImportRow)
        .where(
            ShippingTrackingImportRow.store_id == store_id,
            ShippingTrackingImportRow.platform == order.platform,
        )
        .order_by(ShippingTrackingImportRow.created_at.desc(), ShippingTrackingImportRow.id.desc())
    ).all()
    tracking_lookup = _build_tracking_lookup(tracking_rows)
    tracking_row = _tracking_row_for_order(order, tracking_lookup)
    delivery_fields = _order_delivery_fields(order, tracking_row)
    raw_data = order.raw_data if isinstance(order.raw_data, dict) else {}

    events: list[dict[str, Any]] = []
    _add_timeline_event(
        events,
        time=order.ordered_at,
        label="订单已创建",
        description=f"平台订单状态：{order.order_status or '未记录'}。",
        source="orders",
    )

    delivery_status = _find_nested_text(raw_data, ("delivery_status_label_zh", "deliveryStatusLabelZh"), max_length=120)
    if order.last_synced_at:
        _add_timeline_event(
            events,
            time=order.last_synced_at,
            label="平台订单状态已同步到本地",
            description=delivery_status or "已读取平台订单状态并保存到本地 ERP。",
            source="orders.raw_data",
        )

    if tracking_row is not None:
        _add_timeline_event(
            events,
            time=tracking_row.created_at,
            label="物流单号已导入本地",
            description=f"{tracking_row.carrier} / {tracking_row.tracking_number}",
            source="shipping_tracking_import_rows",
        )

    status_events = db.scalars(
        select(OrderStatusEvent)
        .where(OrderStatusEvent.order_id == order.id)
        .order_by(OrderStatusEvent.observed_at.asc(), OrderStatusEvent.id.asc())
    ).all()
    for event in status_events:
        _add_timeline_event(
            events,
            time=event.observed_at or event.created_at,
            label=event.status_label_zh or event.delivery_status_label_zh or event.event_type,
            description=event.delivery_status_label_zh or event.status_raw or "订单状态事件已记录。",
            source=event.source_type or "order_status_events",
        )

    if raw_data.get("naver_shipment_writeback"):
        _add_timeline_event(
            events,
            time=order.last_synced_at,
            label="Naver 发货回填已提交",
            description="系统已记录人工确认后的 Naver 发货回填结果。",
            source="orders.raw_data",
        )

    events = sorted(events, key=lambda item: item.get("time") or "")
    if not events:
        _add_timeline_event(
            events,
            time=None,
            label="暂无本地物流轨迹",
            description="该订单当前没有本地物流轨迹记录。",
            source="local_tracking_trace",
        )

    has_tracking_number = bool(delivery_fields.get("tracking_number"))
    return {
        "status": "local_tracking_trace" if has_tracking_number else "tracking_number_missing",
        "order_id": order.id,
        "store_id": store_id,
        "platform": order.platform,
        "order_no": order.external_order_id,
        "product_order_no": order.external_product_order_id,
        "delivery_company": delivery_fields.get("delivery_company"),
        "delivery_company_code": delivery_fields.get("delivery_company_code"),
        "tracking_number": delivery_fields.get("tracking_number"),
        "tracking_source": "shipping_tracking_import_rows" if tracking_row else "orders.raw_data",
        "realtime_tracking_open": False,
        "message": (
            "实时快递轨迹暂未接入；当前显示本地订单同步、物流单号导入和发货状态记录。"
            if has_tracking_number
            else "该订单本地还没有快递单号，无法查询物流轨迹。"
        ),
        "events": events,
    }
