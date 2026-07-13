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
from app.schemas.pxg_naver_readonly import (
    PxgNaverReadonlyAdapterBatch,
    PxgNaverReadonlyInquiryCandidate,
    PxgNaverReadonlyLogisticsCandidate,
    PxgNaverReadonlyOrderCandidate,
    PxgNaverReadonlyProductCandidate,
    PxgNaverReadonlyRecipientCandidate,
)
from app.services import api_credential_readiness_service, sync_service
from app.services.operator_trial_service import assert_trial_runtime_closed, resolve_trial_store
from app.services.product_thumbnail_service import approved_pstatic_product_image_url


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
            if field in {"startSearchDate", "endSearchDate", "page", "size", "answered"}
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
        size=10,
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


def _approved_product_thumbnail_sources(payload: object) -> dict[str, str]:
    """Extract transient, explicitly-approved image URLs from a product read.

    The returned URLs stay in the server-only adapter batch. They are never
    persisted in product metadata, audit records, or API responses.
    """
    sources: dict[str, str] = {}
    for content in sync_service._iter_naver_product_contents(payload):
        channel_products = content.get("channelProducts")
        if not isinstance(channel_products, list) or len(channel_products) != 1:
            continue
        channel_product = channel_products[0]
        if not isinstance(channel_product, dict):
            continue
        external_product_id = sync_service._bounded_text(
            sync_service._extract_scalar_by_keys(channel_product, ("channelProductNo", "channelProductId")),
            120,
        )
        if not external_product_id:
            continue
        source_url = None
        for container in (channel_product, content):
            for key in ("representativeImageUrl", "imageUrl", "image"):
                source_url = approved_pstatic_product_image_url(container.get(key))
                if source_url:
                    break
            if source_url:
                break
        if source_url:
            sources[external_product_id] = source_url
    return sources


def collect_pxg_naver_readonly_adapter_batch(db: Session, settings: Settings) -> PxgNaverReadonlyAdapterBatch:
    """Read and normalize a bounded Naver batch entirely on the server.

    Raw responses, credential material, and request headers stay in local memory
    only. This adapter is the sole production source for persistence candidates.
    """

    assert_trial_runtime_closed(settings)
    if not settings.pxg_naver_local_read_persistence_enabled:
        raise ApiError("PXG/Naver readonly local persistence is disabled", "readonly_local_persistence_disabled", 403)
    if not settings.operator_trial_real_read_enabled:
        raise ApiError("PXG Naver real reads are disabled", "trial_real_read_disabled", 403)

    store = resolve_trial_store(db)
    credential = _resolve_unique_active_credential(db, store.id)
    now = get_utc_now()
    context = sync_service._build_naver_token_context_from_credential(credential)
    access_token, _token_status = api_credential_readiness_service._request_naver_token_from_context(context)
    headers = {"Authorization": f"Bearer {access_token}"}

    product_result = sync_service._request_naver_product_search(
        api_base=context["api_base"], headers=headers, page=1, size=3,
    )
    if not product_result.get("success"):
        raise ApiError("Naver product readonly adapter failed", "readonly_adapter_product_read_failed", 502)
    raw_products, _skip_reasons = sync_service._extract_naver_product_sync_candidates(product_result.get("payload"))
    thumbnail_sources = _approved_product_thumbnail_sources(product_result.get("payload"))
    products = [
        PxgNaverReadonlyProductCandidate(
            external_product_id=item["external_product_id"],
            name=item["name"],
            sku=item.get("sku"),
            brand=item.get("brand"),
            category=item.get("category"),
            status=item.get("status") or "unknown",
            price=item.get("price") or 0,
            currency=item.get("currency") or "KRW",
            stock_quantity=item.get("stock_quantity") or 0,
            thumbnail_source_url=thumbnail_sources.get(item["external_product_id"]),
            source_updated_at=now,
        )
        for item in raw_products[:3]
    ]

    feed_result = sync_service._request_naver_order_last_changed_feed(
        api_base=context["api_base"],
        headers=headers,
        start_kst=now - timedelta(days=7),
        end_kst=now,
        size=MAX_REAL_ORDER_PREVIEW,
        attempt="pxg_readonly_persistence",
        include_last_changed_to=False,
        datetime_format_shape="offset_milliseconds",
    )
    if not feed_result.get("success"):
        raise ApiError("Naver order readonly adapter failed", "readonly_adapter_order_read_failed", 502)
    product_order_ids = sync_service._extract_naver_product_order_ids(feed_result.get("payload"))[:MAX_REAL_ORDER_PREVIEW]
    detail_records: list[dict] = []
    if product_order_ids:
        detail_result = sync_service._request_naver_order_detail_query(
            api_base=context["api_base"], headers=headers, product_order_ids=product_order_ids,
        )
        if not detail_result.get("success"):
            raise ApiError("Naver order detail readonly adapter failed", "readonly_adapter_order_detail_failed", 502)
        detail_records = sync_service._extract_naver_order_detail_records(
            detail_result.get("payload"), product_order_ids,
        )

    orders: list[PxgNaverReadonlyOrderCandidate] = []
    logistics: list[PxgNaverReadonlyLogisticsCandidate] = []
    for raw_detail in detail_records:
        detail = sync_service._build_naver_order_internal_detail(raw_detail, store_id=store.id)
        external_order_id = str(detail.get("external_order_id_full") or "").strip()
        external_product_order_id = str(detail.get("external_product_order_id") or "").strip()
        if not external_order_id or not external_product_order_id:
            raise ApiError("Naver order adapter key is missing", "readonly_adapter_order_key_missing", 502)
        status = detail.get("order_status") if isinstance(detail.get("order_status"), dict) else {}
        recipient = PxgNaverReadonlyRecipientCandidate(
            receiver_name=detail.get("receiver_name"),
            receiver_phone=detail.get("receiver_phone"),
            zip_code=detail.get("zip_code"),
            receiver_address_full=detail.get("receiver_address"),
        )
        orders.append(PxgNaverReadonlyOrderCandidate(
            external_order_id=external_order_id,
            external_product_order_id=external_product_order_id,
            product_name=str(detail.get("product_name") or "Naver product order"),
            platform_product_id=detail.get("platform_product_id"),
            option_name=detail.get("option_name"),
            quantity=max(1, int(detail.get("quantity") or 1)),
            order_amount=detail.get("order_amount") or 0,
            currency=str(detail.get("currency") or "KRW"),
            order_status=str(status.get("raw") or "unknown"),
            ordered_at=detail.get("ordered_at") or now,
            paid_at=detail.get("paid_at"),
            source_updated_at=detail.get("last_changed_at") or now,
            recipient=recipient,
        ))
        tracking_number = str(detail.get("tracking_number") or "").strip()
        if tracking_number:
            delivery_status = detail.get("delivery_status") if isinstance(detail.get("delivery_status"), dict) else {}
            logistics.append(PxgNaverReadonlyLogisticsCandidate(
                external_order_id=external_order_id,
                external_product_order_id=external_product_order_id,
                carrier=detail.get("delivery_company") or detail.get("delivery_company_code"),
                tracking_number=tracking_number,
                shipment_status=str(delivery_status.get("raw") or "observed"),
                shipped_at=detail.get("shipped_at"),
                source_updated_at=detail.get("last_changed_at") or now,
            ))

    inquiry_result = sync_service._request_naver_customer_inquiries(
        api_base=context["api_base"],
        headers=headers,
        start_date=(now - timedelta(days=CUSTOMER_INQUIRY_PREVIEW_WINDOW_DAYS)).date(),
        end_date=now.date(),
        answered=None,
        page=1,
        size=10,
    )
    inquiries: list[PxgNaverReadonlyInquiryCandidate] = []
    if inquiry_result.get("success"):
        for item in sync_service._extract_naver_customer_inquiry_items(inquiry_result.get("payload"))[:10]:
            inquiry_id = str(item.get("inquiryNo") or item.get("inquiry_no") or "").strip()
            if not inquiry_id:
                continue
            product_order_ids = sync_service._split_naver_product_order_ids(
                item.get("productOrderIdList") or item.get("product_order_id_list"),
            )
            customer_name = item.get("customerName") or item.get("customer_name")
            inquiries.append(PxgNaverReadonlyInquiryCandidate(
                external_inquiry_id=inquiry_id,
                related_external_order_id=(str(item.get("orderId") or item.get("order_id") or "").strip() or None),
                related_external_product_order_id=product_order_ids[0] if product_order_ids else None,
                inquiry_type="platform_message",
                status="answered" if bool(item.get("answered")) else "open",
                customer_display_masked=sync_service._mask_person_name(customer_name) if customer_name else None,
                subject_category="platform_message",
                content_available=bool(item.get("inquiryContent") or item.get("content")),
                received_at=sync_service._parse_preview_iso_datetime(
                    sync_service._extract_scalar_by_keys(item, ("inquiryRegistrationDateTime", "registeredAt", "createdAt")),
                ),
                answered_at=sync_service._parse_preview_iso_datetime(
                    sync_service._extract_scalar_by_keys(item, ("answerRegistrationDateTime", "answeredAt")),
                ),
                source_updated_at=now,
            ))

    return PxgNaverReadonlyAdapterBatch(
        store_id=store.id,
        platform="naver",
        source_mode="real_readonly",
        products=products,
        orders=orders,
        logistics=logistics,
        customer_inquiries=inquiries,
    )
