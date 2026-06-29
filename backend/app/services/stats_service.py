from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.product import Product
from app.models.store import Store
from app.models.sync_log import SyncLog
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


def _date_start(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min)


def _date_end(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max)


def _decimal_to_string(value: Decimal) -> str:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return format(value.quantize(Decimal("0.01")), "f")


def _order_filters(
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list:
    filters = []
    if store_id is not None:
        filters.append(Order.store_id == store_id)
    if platform is not None:
        filters.append(Order.platform == platform)
    start = _date_start(start_date)
    end = _date_end(end_date)
    if start is not None:
        filters.append(Order.ordered_at >= start)
    if end is not None:
        filters.append(Order.ordered_at <= end)
    return filters


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


def get_sales_stats(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)

    orders = db.scalars(select(Order).where(*_order_filters(store_id, platform, start_date, end_date))).all()
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
) -> list[dict]:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    orders = db.scalars(select(Order).where(*_order_filters(store_id, None, start_date, end_date))).all()
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
) -> list[dict]:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)
    orders = db.scalars(select(Order).where(*_order_filters(store_id, platform, start_date, end_date))).all()
    grouped: dict[date, dict[str, Any]] = defaultdict(lambda: {"total_orders": 0, "total_sales_amount": Decimal("0")})
    for order in orders:
        order_date = order.ordered_at.date()
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
    limit: int = 5,
) -> list[dict]:
    statement = select(Order).order_by(Order.ordered_at.desc(), Order.id.desc())
    if store_id is not None:
        statement = statement.where(Order.store_id == store_id)
    if platform is not None:
        statement = statement.where(Order.platform == platform)
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

    latest_order_statement = select(Order).order_by(Order.ordered_at.desc())
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
) -> dict:
    if store_id is not None:
        ensure_store_exists(db, store_id)
    if platform is not None:
        platform = normalize_platform(platform)

    sales = get_sales_stats(db, store_id=store_id, platform=platform, start_date=start_date, end_date=end_date)
    return {
        "store_count": len(_get_stores(db, store_id)),
        "product_count": _count_records(db, Product, store_id=store_id, platform=platform),
        "order_count": sales["total_orders"],
        "customer_inquiry_count": _count_records(db, CustomerInquiry, store_id=store_id, platform=platform),
        "total_sales_amount": sales["total_sales_amount"],
        "currency": sales["currency"],
        "latest_sync_logs": get_latest_sync_logs(db, store_id=store_id, platform=platform, limit=5),
        "open_customer_inquiries": _count_open_customer_inquiries(db, store_id=store_id, platform=platform),
        "recent_orders": get_recent_orders(db, store_id=store_id, platform=platform, limit=5),
        "risk_flags": build_risk_flags(db, store_id=store_id, platform=platform),
    }


def get_daily_context(
    db: Session,
    store_id: int | None = None,
    context_date: date | None = None,
) -> dict:
    if context_date is None:
        context_date = date.today()
    store = ensure_store_exists(db, store_id) if store_id is not None else None
    sales_summary = get_sales_stats(db, store_id=store_id)
    risk_flags = build_risk_flags(db, store_id=store_id)
    open_inquiries = _count_records(db, CustomerInquiry, store_id=store_id)
    sync_logs = get_latest_sync_logs(db, store_id=store_id, limit=5)
    recent_orders = get_recent_orders(db, store_id=store_id, limit=5)

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
        "risk_flags": risk_flags,
        "recommended_focus": focus,
    }
