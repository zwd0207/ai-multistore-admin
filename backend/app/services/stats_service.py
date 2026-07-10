from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import get_business_date, get_business_day_range, get_business_timezone, to_business_timezone
from app.core.exceptions import ApiError
from app.models.customer_inquiry import CustomerInquiry
from app.models.financial import PlatformSalesDetail, PlatformSettlementDetail
from app.models.api_credential import ApiCredential
from app.models.order import Order
from app.models.product import Product
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services.api_capability_service import get_api_capability_summary
from app.services.order_service import TEST_ORDER_SOURCE_TYPES
from app.services.store_service import ensure_store_exists, normalize_platform


def parse_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(
            message="日期格式错误，请使用 YYYY-MM-DD",
            error_code="INVALID_DATE_FORMAT",
            status_code=400,
            detail={"field": field_name, "value": value},
        ) from exc


def _decimal_to_string(value: Decimal) -> str:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return format(value.quantize(Decimal("0.01")), "f")


def _order_filters(
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_test_orders: bool = False,
) -> list:
    filters = []
    if store_id is not None:
        filters.append(Order.store_id == store_id)
    if platform is not None:
        filters.append(Order.platform == platform)
    if not include_test_orders:
        filters.append(Order.source_type.notin_(TEST_ORDER_SOURCE_TYPES))
    if start_date is not None:
        start, _ = get_business_day_range(start_date)
        filters.append(Order.ordered_at >= start)
    if end_date is not None:
        _, end = get_business_day_range(end_date)
        filters.append(Order.ordered_at < end)
    return filters


def _business_scope_metadata(target_date: date | None = None) -> dict[str, str]:
    business_date = target_date or get_business_date()
    start, end = get_business_day_range(business_date)
    return {
        "business_timezone": get_business_timezone().key,
        "business_date": business_date.isoformat(),
        "business_day_start": start.isoformat(),
        "business_day_end": end.isoformat(),
    }


def _apply_filters(statement, model, store_id: int | None = None, platform: str | None = None):
    if store_id is not None:
        statement = statement.where(model.store_id == store_id)
    if platform is not None and hasattr(model, "platform"):
        statement = statement.where(model.platform == platform)
    return statement


def _safe_order(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "store_id": order.store_id,
        "platform": order.platform,
        "external_order_id": order.external_order_id,
        "buyer_name": order.buyer_name,
        "buyer_masked_phone": order.buyer_masked_phone,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "order_amount": _decimal_to_string(order.order_amount or Decimal("0")),
        "currency": order.currency,
        "order_status": order.order_status,
        "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
    }


def _safe_sync_log(sync_log: SyncLog) -> dict[str, Any]:
    return {
        "id": sync_log.id,
        "store_id": sync_log.store_id,
        "platform": sync_log.platform,
        "sync_type": sync_log.sync_type,
        "status": sync_log.status,
        "started_at": sync_log.started_at.isoformat() if sync_log.started_at else None,
        "finished_at": sync_log.finished_at.isoformat() if sync_log.finished_at else None,
        "message": sync_log.message,
        "error_detail": sync_log.error_detail,
        "raw_summary": sync_log.raw_summary,
    }


def _sum_krw(values: list[int | None]) -> int:
    return sum(value or 0 for value in values)


def _build_order_sales_summary(sales_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": "order_amount_from_orders",
        "total_orders": sales_summary["total_orders"],
        "total_order_sales_amount": sales_summary["total_sales_amount"],
        "currency": sales_summary["currency"],
        "latest_ordered_at": sales_summary["latest_ordered_at"],
    }


def _build_platform_sales_detail_summary(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    statement = _apply_filters(select(PlatformSalesDetail), PlatformSalesDetail, store_id=store_id, platform=platform)
    rows = db.scalars(statement).all()
    latest_recognition_date = db.scalar(
        _apply_filters(
            select(func.max(PlatformSalesDetail.recognition_date)),
            PlatformSalesDetail,
            store_id=store_id,
            platform=platform,
        )
    )

    total_sale_amount = sum((row.total_sale if row.total_sale is not None else row.sale_amount or 0) for row in rows)
    total_settlement_target_amount = _sum_krw([row.settlement_target_amount for row in rows])
    total_settlement_amount = _sum_krw([row.settlement_amount for row in rows])

    return {
        "scope": "platform_sales_details",
        "sales_detail_rows": len(rows),
        "total_sale_amount": total_sale_amount,
        "total_settlement_target_amount": total_settlement_target_amount,
        "total_settlement_amount": total_settlement_amount,
        "latest_recognition_date": latest_recognition_date.isoformat() if latest_recognition_date else None,
        "currency": "KRW",
        "data_status": "local_persisted_rows",
    }


def _build_settlement_summary(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    statement = _apply_filters(
        select(PlatformSettlementDetail),
        PlatformSettlementDetail,
        store_id=store_id,
        platform=platform,
    )
    rows = db.scalars(statement).all()
    latest_revenue_recognition_year_month = db.scalar(
        _apply_filters(
            select(func.max(PlatformSettlementDetail.revenue_recognition_year_month)),
            PlatformSettlementDetail,
            store_id=store_id,
            platform=platform,
        )
    )
    latest_settlement_date = db.scalar(
        _apply_filters(
            select(func.max(PlatformSettlementDetail.settlement_date)),
            PlatformSettlementDetail,
            store_id=store_id,
            platform=platform,
        )
    )

    return {
        "scope": "platform_settlement_details",
        "settlement_rows": len(rows),
        "total_settlement_amount": _sum_krw([row.settlement_amount for row in rows]),
        "total_final_amount": _sum_krw([row.final_amount for row in rows]),
        "total_service_fee": _sum_krw([row.service_fee for row in rows]),
        "latest_revenue_recognition_year_month": latest_revenue_recognition_year_month,
        "latest_settlement_date": latest_settlement_date.isoformat() if latest_settlement_date else None,
        "currency": "KRW",
        "data_status": "local_persisted_rows",
    }


def _build_financial_source_boundaries() -> dict[str, str]:
    return {
        "order_sales_scope": "orders.order_amount is the order amount scope and remains separate from Coupang financial summaries.",
        "platform_sales_detail_scope": (
            "platform_sales_details contains Coupang sales confirmation and revenue detail scope, not the same as order totals."
        ),
        "settlement_scope": "platform_settlement_details contains Coupang settlement scope and must not be mixed with orders or sales details.",
        "settlement_month_granularity_notice": (
            "Settlement data is queried by revenueRecognitionYearMonth and is not a day-precise cutoff."
        ),
        "final_amount_notice": "finalAmount is not profit and is not withdrawable balance unless a later business definition says so.",
        "zero_data_notice": "A zero row count only means current local persisted data is zero and does not prove the platform has no data.",
    }


def _build_financial_summary(
    db: Session,
    order_sales_summary: dict[str, Any],
    store_id: int | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    return {
        "order_sales_summary": order_sales_summary,
        "platform_sales_detail_summary": _build_platform_sales_detail_summary(
            db,
            store_id=store_id,
            platform=platform,
        ),
        "settlement_summary": _build_settlement_summary(
            db,
            store_id=store_id,
            platform=platform,
        ),
        "source_boundaries": _build_financial_source_boundaries(),
    }


def _build_financial_context(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    order_sales_summary = _build_order_sales_summary(
        get_sales_stats(db, store_id=store_id, platform=platform)
    )
    return _build_financial_summary(
        db,
        order_sales_summary=order_sales_summary,
        store_id=store_id,
        platform=platform,
    )


def get_sales_stats(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_test_orders: bool = False,
) -> dict:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)

    orders = db.scalars(select(Order).where(*_order_filters(
        store_id,
        platform,
        start_date,
        end_date,
        include_test_orders=include_test_orders,
    ))).all()
    paid_statuses = {"paid", "completed", "shipped", "delivered"}
    canceled_statuses = {"canceled", "cancelled", "failed", "refunded"}

    total_sales = sum(((order.order_amount or Decimal("0")) for order in orders), Decimal("0"))
    paid_orders = sum(1 for order in orders if order.order_status in paid_statuses)
    canceled_orders = sum(1 for order in orders if order.order_status in canceled_statuses)
    latest_ordered_at = max((order.ordered_at for order in orders if order.ordered_at), default=None)
    currency = orders[0].currency if orders else "KRW"

    return {
        "store_id": store_id,
        "platform": platform,
        "total_orders": len(orders),
        "total_sales_amount": _decimal_to_string(total_sales),
        "currency": currency,
        "paid_orders": paid_orders,
        "canceled_orders": canceled_orders,
        "failed_orders": canceled_orders,
        "latest_ordered_at": latest_ordered_at.isoformat() if latest_ordered_at else None,
    }


def get_sales_by_platform(
    db: Session,
    store_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_test_orders: bool = False,
) -> list[dict]:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    orders = db.scalars(select(Order).where(*_order_filters(
        store_id,
        None,
        start_date,
        end_date,
        include_test_orders=include_test_orders,
    ))).all()
    grouped: dict[str, dict[str, Any]] = {}
    for order in orders:
        item = grouped.setdefault(
            order.platform,
            {"platform": order.platform, "total_orders": 0, "total_sales_amount": Decimal("0")},
        )
        item["total_orders"] += 1
        item["total_sales_amount"] += order.order_amount or Decimal("0")

    return [
        {
            "platform": item["platform"],
            "total_orders": item["total_orders"],
            "total_sales_amount": _decimal_to_string(item["total_sales_amount"]),
        }
        for item in grouped.values()
    ]


def get_sales_by_date(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_test_orders: bool = False,
) -> list[dict]:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)
    orders = db.scalars(select(Order).where(*_order_filters(
        store_id,
        platform,
        start_date,
        end_date,
        include_test_orders=include_test_orders,
    ))).all()
    grouped: dict[date, dict[str, Any]] = defaultdict(lambda: {"total_orders": 0, "total_sales_amount": Decimal("0")})
    for order in orders:
        order_date = to_business_timezone(order.ordered_at).date()
        grouped[order_date]["total_orders"] += 1
        grouped[order_date]["total_sales_amount"] += order.order_amount or Decimal("0")

    return [
        {
            "date": key.isoformat(),
            "total_orders": value["total_orders"],
            "total_sales_amount": _decimal_to_string(value["total_sales_amount"]),
        }
        for key, value in sorted(grouped.items())
    ]


def _count_records(db: Session, model, store_id: int | None = None, platform: str | None = None) -> int:
    statement = _apply_filters(select(model), model, store_id=store_id, platform=platform)
    return len(db.scalars(statement).all())


def _count_open_customer_inquiries(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> int:
    statement = select(CustomerInquiry).where(CustomerInquiry.status == "open")
    if store_id is not None:
        statement = statement.where(CustomerInquiry.store_id == store_id)
    if platform is not None:
        statement = statement.where(CustomerInquiry.platform == platform)
    return len(db.scalars(statement).all())


def _latest_manual_batch_log(db: Session, store_id: int, platform: str) -> SyncLog | None:
    return db.scalar(
        select(SyncLog)
        .where(
            SyncLog.store_id == store_id,
            SyncLog.platform == platform,
            SyncLog.sync_type == "manual_batch_sync",
        )
        .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    )


def _latest_credential(db: Session, store_id: int, platform: str) -> ApiCredential | None:
    return db.scalar(
        select(ApiCredential)
        .where(ApiCredential.store_id == store_id, ApiCredential.platform == platform)
        .order_by(ApiCredential.id.desc())
    )


def _metric(value: int | None, data_status: str, reason: str = "") -> dict[str, Any]:
    return {
        "value": value,
        "display_value": "?" if value is None else str(value),
        "data_status": data_status,
        "reason": reason,
    }


OVERVIEW_CONNECTION_BLOCKER_CODES = {
    "ip_not_allowed",
    "auth_failed",
    "permission_forbidden",
    "product_api_not_allowed",
    "order_api_not_allowed",
    "credential_not_ready",
    "credential_invalid",
    "credential_not_found",
    "channel_no_missing",
}


def _manual_log_connection_blocker(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            entry
            for entry in items or []
            if str(entry.get("error_code") or "").lower() in OVERVIEW_CONNECTION_BLOCKER_CODES
        ),
        None,
    )


def _overview_blocker_reason(error_code: str, message: str = "") -> str:
    code = str(error_code or "").lower()
    if code == "ip_not_allowed":
        return "IP 白名单未通过"
    if code in {"auth_failed", "permission_forbidden", "product_api_not_allowed", "order_api_not_allowed"} or "permission" in code:
        return "API 权限未开通"
    if code in {"credential_not_ready", "credential_invalid", "credential_not_found", "channel_no_missing"}:
        return "API 资料未配置完整"
    if code == "blocked_by_connection":
        return "平台连接未通过"
    if "暂未接入" in message:
        return "暂未接入"
    if "暂未开放" in message:
        return "暂未开放"
    return message or "同步状态未确认"


def _overview_unconfirmed_reason(data_status: dict[str, Any]) -> str:
    reason = _overview_blocker_reason(
        str(data_status.get("error_code") or ""),
        str(data_status.get("message") or ""),
    )
    return f"最近一次同步无法确认：{reason}"


def _manual_item_status_from_log(log: SyncLog | None, resource: str, platform: str, credential: ApiCredential | None) -> dict[str, Any]:
    if credential is None:
        label = "Coupang" if platform == "coupang" else "Naver"
        return {
            "status": "unknown",
            "error_code": "credential_not_ready",
            "message": f"{label}：API 资料未配置完整",
            "data_status": "unknown",
        }

    if log is None:
        return {
            "status": "pending",
            "error_code": "not_synced",
            "message": "待同步",
            "data_status": "unknown",
        }

    raw_summary = log.raw_summary or {}
    items = raw_summary.get("items") if isinstance(raw_summary, dict) else []
    connection_blocker = _manual_log_connection_blocker(items or [])
    item = next((entry for entry in items or [] if entry.get("resource") == resource), None)
    if item is None:
        return {
            "status": raw_summary.get("status") or log.status,
            "error_code": "resource_not_synced",
            "message": "待同步",
            "data_status": "unknown",
        }

    status = str(item.get("status") or "").lower()
    error_code = str(item.get("error_code") or "").lower()
    message = item.get("message") or ""

    if status == "success":
        return {
            "status": "success",
            "error_code": error_code,
            "message": message or "本地同步完成",
            "data_status": "confirmed",
        }
    if error_code == "blocked_by_connection" or (
        error_code == "not_open" and resource in {"products", "orders"} and connection_blocker is not None
    ):
        blocker_code = str((connection_blocker or {}).get("error_code") or "blocked_by_connection").lower()
        return {
            "status": "failed",
            "error_code": "blocked_by_connection",
            "message": f"最近一次同步无法确认：{_overview_blocker_reason(blocker_code, message)}",
            "data_status": "unknown",
        }
    if error_code == "not_open":
        return {
            "status": "not_open",
            "error_code": error_code,
            "message": message or "暂未开放",
            "data_status": "not_open",
        }
    if error_code == "ip_not_allowed":
        return {
            "status": "failed",
            "error_code": "ip_not_allowed",
            "message": "最近一次同步无法确认：IP 白名单未通过",
            "data_status": "unknown",
        }
    if error_code == "auth_failed" or "permission" in error_code or error_code in {"product_api_not_allowed", "order_api_not_allowed"}:
        return {
            "status": "failed",
            "error_code": error_code,
            "message": "最近一次同步无法确认：API 权限未开通",
            "data_status": "unknown",
        }
    if error_code in {"credential_not_ready", "credential_invalid", "credential_not_found", "channel_no_missing"}:
        return {
            "status": "failed",
            "error_code": error_code,
            "message": "最近一次同步无法确认：API 资料未配置完整",
            "data_status": "unknown",
        }

    return {
        "status": status or "skipped",
        "error_code": error_code or "sync_not_confirmed",
        "message": message or "同步状态未确认",
        "data_status": "unknown",
    }


def _order_is_pending_shipment(order: Order) -> bool:
    raw_data = order.raw_data or {}
    text = " ".join(str(value or "") for value in (
        order.order_status,
        raw_data.get("order_status_label_zh"),
        raw_data.get("delivery_status"),
        raw_data.get("delivery_status_label_zh"),
    )).lower()
    return any(flag in text for flag in (
        "待发货",
        "新订单",
        "已付款",
        "ready",
        "payed",
        "paid",
        "place_product_order",
        "delivery_ready",
    ))


def _order_is_abnormal(order: Order) -> bool:
    raw_data = order.raw_data or {}
    text = " ".join(str(value or "") for value in (
        order.order_status,
        raw_data.get("order_status_label_zh"),
        raw_data.get("claim_status"),
        raw_data.get("claim_status_label_zh"),
    )).lower()
    return any(flag in text for flag in (
        "取消",
        "退款",
        "退货",
        "换货",
        "异常",
        "cancel",
        "refund",
        "return",
        "exchange",
    ))


def _store_order_metrics(db: Session, store_id: int, platform: str, data_status: dict[str, Any]) -> dict[str, Any]:
    if data_status["data_status"] != "confirmed":
        reason = _overview_unconfirmed_reason(data_status)
        return {
            "today_orders": _metric(None, data_status["data_status"], reason),
            "pending_shipments": _metric(None, data_status["data_status"], reason),
            "abnormal_orders": _metric(None, data_status["data_status"], reason),
        }

    today = get_business_date()
    orders = db.scalars(select(Order).where(*_order_filters(
        store_id=store_id,
        platform=platform,
        start_date=today,
        end_date=today,
        include_test_orders=False,
    ))).all()
    return {
        "today_orders": _metric(len(orders), "confirmed"),
        "pending_shipments": _metric(sum(1 for order in orders if _order_is_pending_shipment(order)), "confirmed"),
        "abnormal_orders": _metric(sum(1 for order in orders if _order_is_abnormal(order)), "confirmed"),
    }


def _store_inventory_metrics(db: Session, store_id: int, platform: str, data_status: dict[str, Any]) -> dict[str, Any]:
    if data_status["data_status"] != "confirmed":
        return {
            "inventory_alerts": _metric(None, data_status["data_status"], _overview_unconfirmed_reason(data_status)),
        }
    products = db.scalars(
        select(Product).where(Product.store_id == store_id, Product.platform == platform)
    ).all()
    return {
        "inventory_alerts": _metric(sum(1 for product in products if int(product.stock_quantity or 0) <= 5), "confirmed"),
    }


def _connection_status(resources: dict[str, dict[str, Any]], credential: ApiCredential | None) -> dict[str, str]:
    ordered_resources = [resources["products"], resources["orders"], resources["customer_inquiries"]]
    if credential is None:
        return {"label": "API资料未配置完整", "tone": "danger", "reason": "请先在店铺管理中填写平台 API 资料。"}
    for code, label in (
        ("ip_not_allowed", "最近一次同步：IP 白名单未通过"),
        ("blocked_by_connection", "最近一次同步：平台连接未通过"),
        ("auth_failed", "最近一次同步：API 权限未开通"),
        ("product_api_not_allowed", "最近一次同步：API 权限未开通"),
        ("order_api_not_allowed", "最近一次同步：API 权限未开通"),
        ("credential_not_ready", "最近一次同步：API 资料未配置完整"),
        ("credential_invalid", "最近一次同步：API 资料未配置完整"),
        ("credential_not_found", "最近一次同步：API 资料未配置完整"),
        ("channel_no_missing", "最近一次同步：API 资料未配置完整"),
    ):
        if any(resource.get("error_code") == code for resource in ordered_resources):
            reason = next((resource["message"] for resource in ordered_resources if resource.get("error_code") == code), label)
            return {"label": label, "tone": "danger", "reason": reason}

    products_confirmed = resources["products"]["data_status"] == "confirmed"
    orders_confirmed = resources["orders"]["data_status"] == "confirmed"
    orders_not_open = resources["orders"]["data_status"] == "not_open"
    customer_not_open = resources["customer_inquiries"]["data_status"] == "not_open"
    if products_confirmed and orders_confirmed:
        return {"label": "商品和订单可读", "tone": "success", "reason": "商品和订单已可读取并写入本地 ERP。"}
    if products_confirmed and orders_not_open:
        return {"label": "商品可读，订单暂未开放", "tone": "warning", "reason": resources["orders"]["message"]}
    if products_confirmed and customer_not_open:
        return {"label": "商品可读，客服暂未接入", "tone": "warning", "reason": resources["customer_inquiries"]["message"]}
    if all(resource["status"] == "pending" for resource in ordered_resources):
        return {"label": "待同步", "tone": "warning", "reason": "还没有执行过当前店铺手动同步。"}
    if any(resource["data_status"] == "confirmed" for resource in ordered_resources):
        return {"label": "部分同步完成", "tone": "warning", "reason": "部分基础数据已写入本地，其余项目仍需处理。"}
    return {"label": "同步状态未确认", "tone": "warning", "reason": ordered_resources[0]["message"]}


def _store_overview_row(db: Session, store: Store) -> dict[str, Any]:
    try:
        platform = normalize_platform(store.platform)
    except ApiError:
        not_open_reason = "该平台暂未接入官方 API 读取。"
        return {
            "id": store.id,
            "store_id": store.id,
            "store_name": store.name,
            "platform": store.platform,
            "owner_name": store.owner_name,
            "store_status": store.status,
            "connection_status": "暂未接入",
            "connection_tone": "warning",
            "connection_reason": "该平台暂未接入官方 API 读取。",
            "last_sync_at": None,
            "latest_manual_sync_status": None,
            "resources": {
                "products": {"status": "not_open", "error_code": "not_open", "message": "暂未接入", "data_status": "not_open"},
                "orders": {"status": "not_open", "error_code": "not_open", "message": "暂未接入", "data_status": "not_open"},
                "customer_inquiries": {"status": "not_open", "error_code": "not_open", "message": "暂未接入", "data_status": "not_open"},
            },
            "metrics": {
                "today_orders": _metric(None, "not_open", not_open_reason),
                "pending_shipments": _metric(None, "not_open", not_open_reason),
                "abnormal_orders": _metric(None, "not_open", not_open_reason),
                "inventory_alerts": _metric(None, "not_open", not_open_reason),
            },
        }
    credential = _latest_credential(db, store.id, platform)
    latest_log = _latest_manual_batch_log(db, store.id, platform)
    resources = {
        "products": _manual_item_status_from_log(latest_log, "products", platform, credential),
        "orders": _manual_item_status_from_log(latest_log, "orders", platform, credential),
        "customer_inquiries": _manual_item_status_from_log(latest_log, "customer_inquiries", platform, credential),
    }
    connection = _connection_status(resources, credential)
    metrics = {
        **_store_order_metrics(db, store.id, platform, resources["orders"]),
        **_store_inventory_metrics(db, store.id, platform, resources["products"]),
    }
    last_sync_at = None
    if latest_log is not None:
        last_sync_at = (latest_log.finished_at or latest_log.started_at).isoformat()

    return {
        "id": store.id,
        "store_id": store.id,
        "store_name": store.name,
        "platform": platform,
        "owner_name": store.owner_name,
        "store_status": store.status,
        "connection_status": connection["label"],
        "connection_tone": connection["tone"],
        "connection_reason": connection["reason"],
        "last_sync_at": last_sync_at,
        "latest_manual_sync_status": (latest_log.raw_summary or {}).get("status") if latest_log and isinstance(latest_log.raw_summary, dict) else None,
        "resources": resources,
        "metrics": metrics,
    }


def _metric_known_value(row: dict[str, Any], metric_key: str) -> int:
    metric = row["metrics"][metric_key]
    return int(metric["value"] or 0) if metric["value"] is not None else 0


def get_store_overview(
    db: Session,
    include_inactive: bool = False,
) -> dict[str, Any]:
    stores = db.scalars(select(Store).order_by(Store.id.asc())).all()
    if not include_inactive:
        stores = [store for store in stores if store.status != "inactive"]
    rows = [_store_overview_row(db, store) for store in stores]
    orders_unknown_store_count = sum(
        1 for row in rows
        if row["metrics"]["today_orders"]["display_value"] == "?"
        or row["metrics"]["pending_shipments"]["display_value"] == "?"
        or row["metrics"]["abnormal_orders"]["display_value"] == "?"
    )
    inventory_unknown_store_count = sum(1 for row in rows if row["metrics"]["inventory_alerts"]["display_value"] == "?")
    return {
        **_business_scope_metadata(),
        "status": "store_overview_ready",
        "data_policy": "无法确认真实平台数据时显示 ?，避免把未知误判为 0。",
        "store_count": len(rows),
        "stores": rows,
        "summary": {
            "store_count": len(rows),
            "connected_store_count": sum(1 for row in rows if row["connection_tone"] == "success"),
            "attention_store_count": sum(1 for row in rows if row["connection_tone"] in {"warning", "danger"}),
            "ip_blocked_store_count": sum(1 for row in rows if any(resource.get("error_code") == "ip_not_allowed" for resource in row["resources"].values())),
            "orders_unknown_store_count": orders_unknown_store_count,
            "inventory_unknown_store_count": inventory_unknown_store_count,
            "today_order_count": sum(_metric_known_value(row, "today_orders") for row in rows),
            "pending_shipment_count": sum(_metric_known_value(row, "pending_shipments") for row in rows),
            "abnormal_order_count": sum(_metric_known_value(row, "abnormal_orders") for row in rows),
            "inventory_alert_count": sum(_metric_known_value(row, "inventory_alerts") for row in rows),
        },
    }


def _get_stores(db: Session, store_id: int | None = None) -> list[Store]:
    if store_id is not None:
        return [ensure_store_exists(db, store_id)]
    return db.scalars(select(Store).order_by(Store.id.asc())).all()


def get_latest_sync_logs(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    limit: int = 5,
) -> list[dict]:
    statement = select(SyncLog).order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    if store_id is not None:
        statement = statement.where(SyncLog.store_id == store_id)
    if platform is not None:
        statement = statement.where(SyncLog.platform == platform)
    return [_safe_sync_log(item) for item in db.scalars(statement.limit(limit)).all()]


def get_recent_orders(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 5,
    include_test_orders: bool = False,
) -> list[dict]:
    statement = select(Order).where(*_order_filters(
        store_id,
        platform,
        start_date,
        end_date,
        include_test_orders=include_test_orders,
    )).order_by(
        Order.ordered_at.desc(),
        Order.id.desc(),
    )
    return [_safe_order(item) for item in db.scalars(statement.limit(limit)).all()]


def build_risk_flags(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> list[dict]:
    stores = _get_stores(db, store_id)
    flags = []

    failed_logs_statement = select(SyncLog).where(SyncLog.status == "failed")
    if store_id is not None:
        failed_logs_statement = failed_logs_statement.where(SyncLog.store_id == store_id)
    if platform is not None:
        failed_logs_statement = failed_logs_statement.where(SyncLog.platform == platform)
    failed_logs = db.scalars(failed_logs_statement).all()
    if failed_logs:
        flags.append(
            {
                "code": "FAILED_SYNC_LOG",
                "level": "warning",
                "message": "存在同步失败记录 / 동기화 실패 기록이 있습니다",
                "count": len(failed_logs),
            }
        )

    open_inquiries_statement = select(CustomerInquiry).where(CustomerInquiry.status == "open")
    if store_id is not None:
        open_inquiries_statement = open_inquiries_statement.where(CustomerInquiry.store_id == store_id)
    if platform is not None:
        open_inquiries_statement = open_inquiries_statement.where(CustomerInquiry.platform == platform)
    open_inquiries = db.scalars(open_inquiries_statement).all()
    if open_inquiries:
        flags.append(
            {
                "code": "OPEN_CUSTOMER_INQUIRIES",
                "level": "info",
                "message": "存在未处理客服咨询 / 미처리 고객문의가 있습니다",
                "count": len(open_inquiries),
            }
        )

    latest_order_statement = select(Order).where(Order.source_type.notin_(TEST_ORDER_SOURCE_TYPES)).order_by(Order.ordered_at.desc())
    if store_id is not None:
        latest_order_statement = latest_order_statement.where(Order.store_id == store_id)
    if platform is not None:
        latest_order_statement = latest_order_statement.where(Order.platform == platform)
    latest_order = db.scalars(latest_order_statement.limit(1)).first()
    if latest_order is None:
        flags.append(
            {
                "code": "NO_RECENT_ORDERS",
                "level": "info",
                "message": "暂无订单数据 / 최근 주문 데이터가 없습니다",
                "count": 0,
            }
        )

    suspended_stores = [store for store in stores if store.status == "suspended"]
    if suspended_stores:
        flags.append(
            {
                "code": "SUSPENDED_STORE",
                "level": "critical",
                "message": "存在暂停状态店铺 / 일시중지 상태의 스토어가 있습니다",
                "store_ids": [store.id for store in suspended_stores],
            }
        )

    return flags


def get_dashboard_summary(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_test_orders: bool = False,
) -> dict:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)

    sales = get_sales_stats(
        db,
        store_id=store_id,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        include_test_orders=include_test_orders,
    )
    financial_summary = _build_financial_summary(
        db,
        order_sales_summary=_build_order_sales_summary(sales),
        store_id=store_id,
        platform=platform,
    )
    business_metadata = _business_scope_metadata(start_date if start_date == end_date else None)
    return {
        **business_metadata,
        "store_count": len(_get_stores(db, store_id)),
        "product_count": _count_records(db, Product, store_id=store_id, platform=platform),
        "order_count": sales["total_orders"],
        "customer_inquiry_count": _count_records(db, CustomerInquiry, store_id=store_id, platform=platform),
        "total_sales_amount": sales["total_sales_amount"],
        "currency": sales["currency"],
        "latest_sync_logs": get_latest_sync_logs(db, store_id=store_id, platform=platform, limit=5),
        "open_customer_inquiries": _count_open_customer_inquiries(db, store_id=store_id, platform=platform),
        "recent_orders": get_recent_orders(
            db,
            store_id=store_id,
            platform=platform,
            limit=5,
            include_test_orders=include_test_orders,
        ),
        "risk_flags": build_risk_flags(db, store_id=store_id, platform=platform),
        "financial_summary": financial_summary,
        "api_capability_summary": get_api_capability_summary(db, store_id=store_id, platform=platform),
    }


def get_daily_context(
    db: Session,
    store_id: int | None = None,
    context_date: date | None = None,
) -> dict:
    if context_date is None:
        context_date = get_business_date()
    store = ensure_store_exists(db, store_id) if store_id is not None else None
    sales_summary = get_sales_stats(db, store_id=store_id, start_date=context_date, end_date=context_date)
    risk_flags = build_risk_flags(db, store_id=store_id)
    open_inquiries = _count_records(db, CustomerInquiry, store_id=store_id)
    sync_logs = get_latest_sync_logs(db, store_id=store_id, limit=5)
    recent_orders = get_recent_orders(db, store_id=store_id, start_date=context_date, end_date=context_date, limit=5)
    financial_context = _build_financial_context(
        db,
        store_id=store_id,
        platform=store.platform if store else None,
    )

    focus = []
    if open_inquiries:
        focus.append({"code": "CHECK_OPEN_INQUIRIES", "message": "检查未处理客服咨询 / 미처리 고객문의 확인"})
    if any(log["status"] == "failed" for log in sync_logs):
        focus.append({"code": "CHECK_SYNC_FAILURES", "message": "关注同步失败平台 / 동기화 실패 플랫폼 확인"})
    if not recent_orders:
        focus.append({"code": "CHECK_ORDER_DROP", "message": "检查近期订单下降 / 최근 주문 감소 확인"})
    authenticity_statement = select(CustomerInquiry).where(
        CustomerInquiry.inquiry_type == "authenticity",
        CustomerInquiry.status == "open",
    )
    if store_id is not None:
        authenticity_statement = authenticity_statement.where(CustomerInquiry.store_id == store_id)
    if db.scalars(authenticity_statement).first():
        focus.append({"code": "AUTHENTICITY_INQUIRIES", "message": "处理正品申诉类咨询 / 정품 소명 문의 처리"})

    return {
        "date": context_date.isoformat(),
        "business_timezone": get_business_timezone().key,
        "business_day_start": get_business_day_range(context_date)[0].isoformat(),
        "business_day_end": get_business_day_range(context_date)[1].isoformat(),
        "scope": {
            "store_id": store_id,
            "platform": store.platform if store else None,
        },
        "sales_summary": sales_summary,
        "order_summary": {
            "total_orders": sales_summary["total_orders"],
            "recent_orders": recent_orders,
        },
        "customer_inquiry_summary": {
            "total": _count_records(db, CustomerInquiry, store_id=store_id),
            "open": open_inquiries,
        },
        "sync_summary": {
            "latest_sync_logs": sync_logs,
            "failed_count": sum(1 for log in sync_logs if log["status"] == "failed"),
        },
        "financial_context": financial_context,
        "api_capability_context": get_api_capability_summary(
            db,
            store_id=store_id,
            platform=store.platform if store else None,
        ),
        "risk_flags": risk_flags,
        "recommended_focus": focus,
    }
