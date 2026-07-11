from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.api_credential import ApiCredential
from app.models.customer_inquiry import CustomerInquiry
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.product import Product
from app.models.shipping import ShippingTrackingImportBatch, WarehouseShippingBatch
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services import api_credential_readiness_service, sync_service
from app.services.operator_trial_service import assert_trial_runtime_closed, resolve_trial_store


MAX_REAL_ORDER_PREVIEW = 3
CUSTOMER_INQUIRY_ENDPOINT = "/v1/pay-user/inquiries"
CUSTOMER_INQUIRY_PREVIEW_WINDOW_DAYS = 1


def _resolve_unique_active_credential(db: Session, store_id: int) -> ApiCredential:
    credentials = db.scalars(select(ApiCredential).where(
        ApiCredential.store_id == store_id,
        func.lower(ApiCredential.platform) == "naver",
        ApiCredential.status == "active",
    )).all()
    usable = [item for item in credentials if item.client_id and item.encrypted_secret_key]
    if len(usable) != 1:
        raise ApiError(
            "PXG Naver readonly preview requires one active encrypted credential",
            "readonly_credential_not_unique",
            409,
            {"usable_credential_count": len(usable)},
        )
    return usable[0]


def _business_counts(db: Session, store_id: int) -> dict[str, int]:
    models = {
        "stores": Store,
        "products": Product,
        "orders": Order,
        "customer_inquiries": CustomerInquiry,
        "sync_logs": SyncLog,
        "audit_logs": OperationAuditLog,
        "tracking_batches": ShippingTrackingImportBatch,
        "warehouse_batches": WarehouseShippingBatch,
    }
    existing_tables = set(inspect(db.get_bind()).get_table_names())
    counts = {}
    for key, model in models.items():
        if model.__tablename__ not in existing_tables:
            continue
        statement = select(func.count()).select_from(model)
        if hasattr(model, "store_id"):
            statement = statement.where(model.store_id == store_id)
        counts[key] = int(db.scalar(statement) or 0)
    return counts


def _customer_inquiry_capability_result(request_result: dict, inquiry_count: int) -> dict:
    if request_result.get("success"):
        return {
            "status": "available" if inquiry_count else "available_empty",
            "endpoint": CUSTOMER_INQUIRY_ENDPOINT,
            "http_status": request_result.get("http_status"),
            "platform_error_category": None,
        }
    http_status = request_result.get("http_status")
    safe_error = request_result.get("safe_error") if isinstance(request_result.get("safe_error"), dict) else {}
    if http_status == 400:
        category = "request_error"
        status = "blocked_request_error"
    elif http_status in {401, 403}:
        category = "platform_not_authorized"
        status = "platform_not_authorized_or_unavailable"
    elif http_status == 404:
        category = "capability_unavailable"
        status = "platform_not_authorized_or_unavailable"
    elif isinstance(http_status, int) and http_status >= 500:
        category = "platform_temporarily_unavailable"
        status = "platform_not_authorized_or_unavailable"
    else:
        category = "capability_unavailable"
        status = "platform_not_authorized_or_unavailable"
    return {
        "status": status,
        "endpoint": CUSTOMER_INQUIRY_ENDPOINT,
        "http_status": http_status if isinstance(http_status, int) else None,
        "platform_error_category": category,
        "platform_error_code": safe_error.get("platform_error_code"),
        "platform_error_fields": [
            field for field in safe_error.get("platform_error_fields", [])
            if field in {"fromDate", "toDate", "page", "size", "answered"}
        ][:5],
    }


def preview_pxg_naver_real_reads(db: Session, settings: Settings) -> dict:
    assert_trial_runtime_closed(settings)
    if not settings.operator_trial_real_read_enabled:
        raise ApiError("PXG Naver real reads are disabled", "trial_real_read_disabled", 403)
    store = resolve_trial_store(db)
    credential = _resolve_unique_active_credential(db, store.id)
    counts_before = _business_counts(db, store.id)
    now = get_utc_now()

    products = sync_service.preview_naver_products(
        db,
        store_id=store.id,
        credential_id=credential.id,
        page=1,
        size=3,
        status="ALL",
        real_preview=True,
        real_sync=False,
    )
    orders = sync_service.preview_naver_orders(
        db,
        store_id=store.id,
        credential_id=credential.id,
        start_datetime=now - timedelta(days=7),
        end_datetime=now,
        order_status="ALL",
        page=1,
        size=MAX_REAL_ORDER_PREVIEW,
        real_preview=True,
        include_detail=True,
        complete_field_preview=False,
        real_sync=False,
    )
    order_window_days = 7
    if orders.get("preview_status") in {"success", "success_empty"} and not (orders.get("sample_ids") or []):
        orders = sync_service.preview_naver_orders(
            db,
            store_id=store.id,
            credential_id=credential.id,
            start_datetime=now - timedelta(days=30),
            end_datetime=now,
            order_status="ALL",
            page=1,
            size=MAX_REAL_ORDER_PREVIEW,
            real_preview=True,
            include_detail=True,
            complete_field_preview=False,
            real_sync=False,
            readonly_window_max_days=30,
        )
        order_window_days = 30

    context = sync_service._build_naver_token_context_from_credential(credential)
    access_token, _token_status = api_credential_readiness_service._request_naver_token_from_context(context)
    inquiry_result = sync_service._request_naver_customer_inquiries(
        api_base=context["api_base"],
        headers={"Authorization": f"Bearer {access_token}"},
        start_date=(now - timedelta(days=CUSTOMER_INQUIRY_PREVIEW_WINDOW_DAYS)).date(),
        end_date=now.date(),
        answered=None,
        page=1,
        size=3,
    )
    inquiry_count = 0
    if inquiry_result.get("success"):
        inquiry_count = len(sync_service._extract_naver_customer_inquiry_items(inquiry_result.get("payload")))
    inquiry_capability = _customer_inquiry_capability_result(inquiry_result, inquiry_count)

    db.rollback()
    counts_after = _business_counts(db, store.id)
    if counts_before != counts_after:
        raise ApiError("readonly preview changed local business state", "readonly_local_state_changed", 500)

    order_fields = orders.get("field_observation") if isinstance(orders, dict) else {}
    order_fields = order_fields if isinstance(order_fields, dict) else {}
    order_count = min(MAX_REAL_ORDER_PREVIEW, len(orders.get("sample_ids") or []))
    order_status = orders.get("preview_status")
    if order_status in {"success", "success_empty"} and order_count == 0:
        order_status = "current_no_orders"
    logistics_status = "not_required" if order_count == 0 else (
        "observed_in_masked_order_details" if order_fields.get("detail_called") else "not_observed"
    )
    result = {
        "status": "blocked" if inquiry_capability["platform_error_category"] == "request_error" else "completed",
        "store": {"name": store.name, "platform": "Naver"},
        "limits": {
            "max_real_orders": MAX_REAL_ORDER_PREVIEW,
            "order_window_days": order_window_days,
            "customer_inquiry_window_days": CUSTOMER_INQUIRY_PREVIEW_WINDOW_DAYS,
        },
        "counts": {
            "products": min(3, len(products.get("sample_ids") or [])),
            "orders": order_count,
            "customer_inquiries": inquiry_count,
            "logistics_order_details": int(order_fields.get("detail_limit") or 0),
        },
        "reads": {
            "products": products.get("preview_status"),
            "orders": order_status,
            "customer_inquiries": inquiry_capability["status"],
            "logistics": logistics_status,
        },
        "customer_inquiry_result": inquiry_capability,
        "privacy": {
            "ordinary_order_list_redacted": True,
            "complete_recipient_returned": False,
            "raw_response_saved": False,
            "credential_values_returned": False,
        },
        "writes": {
            "platform_write": False,
            "local_business_write": False,
            "shipping_writeback": False,
            "customer_send": False,
            "ai_automatic_operation": False,
        },
        "state_unchanged": True,
    }
    serialized = json.dumps(result, ensure_ascii=False).lower()
    for forbidden in ("receiver_name", "receiver_phone", "receiver_address", "zip_code", "access_token", "secret_key", "authorization"):
        if forbidden in serialized:
            raise ApiError("readonly summary contains a forbidden field", "readonly_summary_privacy_failed", 500)
    return result
