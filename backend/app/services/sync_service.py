import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.coupang_client import CoupangClient
from app.clients.naver_client import NaverClient
from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_business_date, get_business_day_range, get_business_timezone, get_utc_now
from app.models.order import Order
from app.models.product import Product
from app.models.sync_checkpoint import SyncCheckpoint
from app.schemas.credential import DecryptedCredential
from app.services import credential_service, customer_inquiry_service, order_service, product_service, sync_log_service
from app.services.store_service import ensure_store_exists, normalize_platform


CLIENTS = {
    "naver": NaverClient,
    "coupang": CoupangClient,
}
COUPANG_ORDER_PREVIEW_SYNC_TYPE = "orders_coupang_real_preview"
COUPANG_ORDER_SYNC_TYPE = "orders_coupang_real"
COUPANG_ORDER_CHECKPOINT_SYNC_TYPE = "orders"
COUPANG_PRODUCT_PREVIEW_SYNC_TYPE = "products_coupang_real_preview"
COUPANG_PRODUCT_SYNC_TYPE = "products_coupang_real"
COUPANG_PRODUCT_CHECKPOINT_SYNC_TYPE = "products"
COUPANG_SALES_PREVIEW_SYNC_TYPE = "sales_coupang_real_preview"
COUPANG_SETTLEMENT_PREVIEW_SYNC_TYPE = "settlements_coupang_real_preview"
COUPANG_ORDER_SOURCE_TYPE = "real_coupang"
COUPANG_PRODUCT_SOURCE_TYPE = "real_coupang"
COUPANG_FINANCIAL_SOURCE_TYPE = "real_coupang"
COUPANG_ORDER_PREVIEW_MAX_DAYS = 3
COUPANG_FINANCIAL_PREVIEW_MAX_DAYS = 7
COUPANG_ORDER_PREVIEW_MAX_PAGES = 3
COUPANG_ORDER_PREVIEW_PAGE_SIZE = 50
COUPANG_PRODUCT_MAX_PAGES = 3
COUPANG_PRODUCT_PAGE_SIZE = 50
COUPANG_FINANCIAL_MAX_PAGES = 3
COUPANG_FINANCIAL_PAGE_SIZE = 50
COUPANG_SETTLEMENT_FORBIDDEN_FIELDS = {
    "bankaccountholder",
    "bankname",
    "bankaccount",
}
COUPANG_PRODUCT_STATUSES = (
    "IN_REVIEW",
    "SAVED",
    "APPROVING",
    "APPROVED",
    "PARTIAL_APPROVED",
    "DENIED",
    "DELETED",
)


def _build_client(db: Session, store_id: int, platform: str):
    platform = normalize_platform(platform)
    ensure_store_exists(db, store_id)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, platform)
    client_class = CLIENTS.get(platform)
    if client_class is None:
        raise ApiError(
            message="Platform is not supported",
            error_code="PLATFORM_NOT_SUPPORTED",
            status_code=400,
            detail={"platform": platform},
        )
    return client_class(credential)


def _mask_sensitive_text(message: str | None) -> str:
    text = str(message or "")
    if not text:
        return ""
    text = re.sub(
        r"(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|access[_-]?key|secret[_-]?key|authorization|signature)",
        "credential_field",
        text,
    )
    text = re.sub(r"[A-Za-z0-9_\-+/=]{32,}", "[masked]", text)
    return text[:300]


def _enrich_sync_items(items: list[dict], source_type: str) -> list[dict]:
    synced_at = get_utc_now()
    return [
        {
            **item,
            "source_type": source_type,
            "last_synced_at": synced_at,
        }
        for item in items
    ]


def _run_mock_sync(
    db: Session,
    store_id: int,
    platform: str,
    sync_type: str,
    fetcher_name: str,
    writer: Callable[[Session, int, str, list[dict]], dict],
    item_enricher: Callable[[list[dict]], list[dict]] | None = None,
) -> dict:
    platform = normalize_platform(platform)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform=platform,
        sync_type=sync_type,
        message=f"{sync_type} mock sync started",
        raw_summary={
            "stage": "started",
            "scope": "mock_sync",
            "说明": "mock sync started",
            "한국어": "mock 동기화 시작",
            "璇存槑": "mock 鍚屾寮€濮?",
            "頃滉淡鞏?": "mock 霃欔赴頇?鞁滌瀾",
        },
    )

    try:
        client = _build_client(db, store_id, platform)
        fetcher = getattr(client, fetcher_name)
        client_result = fetcher()
        items = client_result.get("data", {}).get("items", [])
        if item_enricher is not None:
            items = item_enricher(items)
        write_result = writer(db, store_id, platform, items)
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message=f"{sync_type} mock sync success",
            raw_summary={
                "platform": platform,
                "store_id": store_id,
                "sync_type": sync_type,
                "scope": "mock_sync",
                "items": write_result,
                "中文": "同步成功",
                "한국어": "동기화 성공",
                "legacy_cn": "鍚屾鎴愬姛",
                "legacy_ko": "霃欔赴頇?靹标车",
            },
        )
        return {
            "platform": platform,
            "store_id": store_id,
            "sync_type": sync_type,
            "write_result": write_result,
            "sync_log": finished_log,
        }
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message=f"{sync_type} mock sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "platform": platform,
                "store_id": store_id,
                "sync_type": sync_type,
                "scope": "mock_sync",
                "中文": "同步失败",
                "한국어": "동기화 실패",
                "legacy_cn": "鍚屾澶辫触",
                "legacy_ko": "霃欔赴頇?鞁ろ尐",
            },
        )
        raise


def sync_products_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="products",
        fetcher_name="fetch_products_mock",
        writer=product_service.upsert_products,
        item_enricher=lambda items: _enrich_sync_items(items, "mock_sync"),
    )


def preview_coupang_products(
    db: Session,
    store_id: int,
    status: str = "APPROVED",
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API product preview is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    _ensure_coupang_store(db, store_id)
    statuses = _resolve_coupang_product_statuses(status)
    _ensure_coupang_page_limit(max_pages)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)

    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_PRODUCT_PREVIEW_SYNC_TYPE,
        message="coupang product preview started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
            "status_filter": status,
            "statuses": statuses,
            "max_pages": max_pages,
        },
    )

    try:
        fetch_result = _fetch_coupang_product_statuses(
            credential=credential,
            statuses=statuses,
            max_pages=max_pages,
        )
        unique_product_ids = [_resolve_product_id(item) for item in fetch_result["items"]]
        existing_ids = _find_existing_product_ids(db, store_id=store_id, platform="coupang", external_product_ids=unique_product_ids)
        per_status = _build_product_preview_per_status(fetch_result["per_status"], existing_ids)
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_PRODUCT_PREVIEW_SYNC_TYPE,
            "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
            "status_filter": status,
            "status_semantic_notice": "APPROVED is a Coupang API product review/listing status and may not exactly match the seller center sales status.",
            "max_pages": max_pages,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": fetch_result["next_cursor_exists"],
            "would_create": sum(1 for product_id in unique_product_ids if product_id not in existing_ids),
            "would_update": sum(1 for product_id in unique_product_ids if product_id in existing_ids),
            "sample_ids": unique_product_ids[:10],
            "per_status": per_status,
        }
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang product preview success",
            raw_summary=_product_preview_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang product preview failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang product preview failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
                "error_code": "COUPANG_PRODUCT_PREVIEW_FAILED",
            },
        )
        raise ApiError(
            message="Coupang product preview failed",
            error_code="COUPANG_PRODUCT_PREVIEW_FAILED",
            status_code=502,
        ) from exc


def sync_coupang_products(
    db: Session,
    store_id: int,
    status: str = "APPROVED",
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API product sync is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    _ensure_coupang_store(db, store_id)
    statuses = _resolve_coupang_product_statuses(status)
    _ensure_coupang_page_limit(max_pages)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)

    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_PRODUCT_SYNC_TYPE,
        message="coupang readonly product sync started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
            "write_scope": "local_products_only",
            "platform_write": False,
            "status_filter": status,
            "statuses": statuses,
            "max_pages": max_pages,
        },
    )

    try:
        fetch_result = _fetch_coupang_product_statuses(
            credential=credential,
            statuses=statuses,
            max_pages=max_pages,
        )
        synced_at = get_utc_now()
        product_items: list[dict] = []
        skipped_count = sum(item["skipped_count"] for item in fetch_result["per_status"])
        for item in fetch_result["items"]:
            payload = _to_coupang_product_payload(item, synced_at=synced_at)
            if payload is None:
                skipped_count += 1
                continue
            product_items.append(payload)

        write_result = product_service.upsert_products(db, store_id, "coupang", product_items)
        sample_ids = [item["external_product_id"] for item in product_items[:10]]
        per_status = _build_product_sync_per_status(fetch_result["per_status"])
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_PRODUCT_SYNC_TYPE,
            "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
            "write_scope": "local_products_only",
            "platform_write": False,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "status_filter": status,
            "status_semantic_notice": "APPROVED is a Coupang API product review/listing status and may not exactly match the seller center sales status.",
            "max_pages": max_pages,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": fetch_result["next_cursor_exists"],
            "created_count": write_result["created"],
            "updated_count": write_result["updated"],
            "skipped_count": skipped_count,
            "sample_ids": sample_ids,
            "per_status": per_status,
            "last_synced_at": synced_at.isoformat(),
        }
        checkpoint = _upsert_coupang_sync_checkpoint(
            db,
            store_id=store_id,
            sync_type=COUPANG_PRODUCT_CHECKPOINT_SYNC_TYPE,
            cursor_payload={
                "status_filter": status,
                "statuses": statuses,
                "max_pages": max_pages,
                "next_cursor_exists": fetch_result["next_cursor_exists"],
            },
            synced_at=synced_at,
            notes_payload={
                "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
                "last_success_at": synced_at.isoformat(),
                "write_scope": "local_products_only",
            },
        )
        result["checkpoint"] = checkpoint
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly product sync success",
            raw_summary=_product_sync_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly product sync failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly product sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
                "error_code": "COUPANG_PRODUCT_SYNC_FAILED",
            },
        )
        raise ApiError(
            message="Coupang readonly product sync failed",
            error_code="COUPANG_PRODUCT_SYNC_FAILED",
            status_code=502,
        ) from exc


def preview_coupang_sales(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API sales preview is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    _ensure_coupang_store(db, store_id)
    start_date, end_date = _resolve_sales_preview_date_range(start_date, end_date)
    _ensure_financial_page_limit(max_pages)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)

    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_SALES_PREVIEW_SYNC_TYPE,
        message="coupang sales preview started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "date_window": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "business_timezone": str(get_business_timezone()),
            },
            "max_pages": max_pages,
            "system_phase_limit_days": COUPANG_FINANCIAL_PREVIEW_MAX_DAYS,
        },
    )

    try:
        fetch_result = _fetch_coupang_sales_pages(
            credential=credential,
            start_date=start_date,
            end_date=end_date,
            max_pages=max_pages,
        )
        sample_rows = [_sanitize_financial_sample_row(item) for item in fetch_result["items"][:10]]
        sample_ids = [_resolve_financial_row_id(item) for item in fetch_result["items"][:10]]
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_SALES_PREVIEW_SYNC_TYPE,
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "business_timezone": str(get_business_timezone()),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "window_start_at": _utc_isoformat(get_business_day_range(start_date)[0]),
            "window_end_at": _utc_isoformat(get_business_day_range(end_date)[1]),
            "max_pages": max_pages,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": fetch_result["next_cursor_exists"],
            "total_rows": len(fetch_result["items"]),
            "sample_ids": sample_ids,
            "sample_rows": sample_rows,
            "summary_totals": _build_financial_summary_totals(fetch_result["items"]),
            "semantic_notice": "Sales preview is readonly and writes only a sanitized SyncLog. It does not write a sales table or call Coupang write APIs.",
            "date_availability_notice": "Sales preview only allows completed historical KST dates before the current business date. The 7-day window is this system phase limit, not Coupang's official maximum.",
        }
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang sales preview success",
            raw_summary=_financial_preview_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang sales preview failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang sales preview failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": "COUPANG_SALES_PREVIEW_FAILED",
            },
        )
        raise ApiError(
            message="Coupang sales preview failed",
            error_code="COUPANG_SALES_PREVIEW_FAILED",
            status_code=502,
        ) from exc


def preview_coupang_settlements(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API settlement preview is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    _ensure_coupang_store(db, store_id)
    start_date, end_date = _resolve_financial_preview_date_range(start_date, end_date)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)
    months = _settlement_months_between(start_date, end_date)

    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_SETTLEMENT_PREVIEW_SYNC_TYPE,
        message="coupang settlement preview started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "months": months,
            "date_window": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "business_timezone": str(get_business_timezone()),
            },
            "month_semantic_notice": "Settlement preview queries revenueRecognitionYearMonth=YYYY-MM. The date window is used only to derive months and does not mean day-precise truncation.",
        },
    )

    try:
        fetch_result = _fetch_coupang_settlement_months(credential=credential, months=months)
        sample_rows = [_sanitize_financial_sample_row(item, settlement=True) for item in fetch_result["items"][:10]]
        sample_ids = [_resolve_financial_row_id(item) for item in fetch_result["items"][:10]]
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_SETTLEMENT_PREVIEW_SYNC_TYPE,
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "business_timezone": str(get_business_timezone()),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "months": months,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": False,
            "total_rows": len(fetch_result["items"]),
            "sample_ids": sample_ids,
            "sample_rows": sample_rows,
            "per_month": fetch_result["per_month"],
            "summary_totals": _build_financial_summary_totals(fetch_result["items"]),
            "semantic_notice": "Settlement preview is readonly and writes only a sanitized SyncLog. It does not write a settlement table or call Coupang write APIs.",
            "month_semantic_notice": "Settlement preview queries revenueRecognitionYearMonth=YYYY-MM. start_date/end_date only derive queried months and the response is not day-precisely truncated.",
            "field_mapping_suggestion": _settlement_field_mapping_suggestion(),
        }
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang settlement preview success",
            raw_summary=_financial_preview_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang settlement preview failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang settlement preview failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": "COUPANG_SETTLEMENT_PREVIEW_FAILED",
            },
        )
        raise ApiError(
            message="Coupang settlement preview failed",
            error_code="COUPANG_SETTLEMENT_PREVIEW_FAILED",
            status_code=502,
        ) from exc


def sync_orders_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="orders",
        fetcher_name="fetch_orders_mock",
        writer=order_service.upsert_orders,
        item_enricher=lambda items: _enrich_sync_items(items, "mock_sync"),
    )


def sync_customer_inquiries_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="customer_inquiries",
        fetcher_name="fetch_customer_inquiries_mock",
        writer=customer_inquiry_service.upsert_customer_inquiries,
    )


def preview_coupang_orders(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API preview is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    ensure_store_exists(db, store_id)
    start_date, end_date = _resolve_preview_date_range(start_date, end_date)
    if max_pages < 1 or max_pages > COUPANG_ORDER_PREVIEW_MAX_PAGES:
        raise ApiError(
            message="max_pages must be between 1 and 3",
            error_code="INVALID_SYNC_PREVIEW_WINDOW",
            status_code=400,
            detail={"max_pages": max_pages, "allowed_max_pages": COUPANG_ORDER_PREVIEW_MAX_PAGES},
        )

    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_ORDER_PREVIEW_SYNC_TYPE,
        message="coupang order preview started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_ORDER_SOURCE_TYPE,
            "window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "max_pages": max_pages,
        },
    )

    try:
        page_result = _fetch_coupang_order_pages(
            credential=credential,
            start_date=start_date,
            end_date=end_date,
            max_pages=max_pages,
        )
        unique_order_ids = [_resolve_preview_order_id(item) for item in page_result["items"]]
        page_count = page_result["page_count"]
        next_token = page_result["next_token"]

        existing_ids = _find_existing_order_ids(db, store_id=store_id, platform="coupang", external_order_ids=unique_order_ids)
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_ORDER_PREVIEW_SYNC_TYPE,
            "source_type": COUPANG_ORDER_SOURCE_TYPE,
            "business_timezone": get_business_timezone().key,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "window_start_at": get_business_day_range(start_date)[0].isoformat(),
            "window_end_at": get_business_day_range(end_date)[1].isoformat(),
            "max_pages": max_pages,
            "page_count": page_count,
            "next_cursor_exists": bool(next_token),
            "would_create": sum(1 for order_id in unique_order_ids if order_id not in existing_ids),
            "would_update": sum(1 for order_id in unique_order_ids if order_id in existing_ids),
            "sample_ids": unique_order_ids[:10],
        }
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang order preview success",
            raw_summary=_preview_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang order preview failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_ORDER_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang order preview failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_ORDER_SOURCE_TYPE,
                "error_code": "COUPANG_ORDER_PREVIEW_FAILED",
            },
        )
        raise ApiError(
            message="Coupang order preview failed",
            error_code="COUPANG_ORDER_PREVIEW_FAILED",
            status_code=502,
        ) from exc


def sync_coupang_orders(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API sync is disabled",
            error_code="REAL_API_TEST_DISABLED",
            status_code=403,
        )

    _ensure_coupang_store(db, store_id)
    start_date, end_date = _resolve_preview_date_range(start_date, end_date)
    if max_pages < 1 or max_pages > COUPANG_ORDER_PREVIEW_MAX_PAGES:
        raise ApiError(
            message="max_pages must be between 1 and 3",
            error_code="INVALID_SYNC_WINDOW",
            status_code=400,
            detail={"max_pages": max_pages, "allowed_max_pages": COUPANG_ORDER_PREVIEW_MAX_PAGES},
        )

    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, "coupang")
    _ensure_coupang_preview_credential(credential)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="coupang",
        sync_type=COUPANG_ORDER_SYNC_TYPE,
        message="coupang readonly order sync started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_ORDER_SOURCE_TYPE,
            "write_scope": "local_orders_only",
            "platform_write": False,
            "window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "max_pages": max_pages,
        },
    )

    try:
        page_result = _fetch_coupang_order_pages(
            credential=credential,
            start_date=start_date,
            end_date=end_date,
            max_pages=max_pages,
        )
        synced_at = get_utc_now()
        order_items = [
            _to_coupang_order_payload(item, synced_at=synced_at)
            for item in page_result["items"]
        ]
        write_result = order_service.upsert_orders(db, store_id, "coupang", order_items)
        sample_ids = [item["external_order_id"] for item in order_items[:10]]
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_ORDER_SYNC_TYPE,
            "source_type": COUPANG_ORDER_SOURCE_TYPE,
            "write_scope": "local_orders_only",
            "platform_write": False,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "business_timezone": get_business_timezone().key,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "window_start_at": get_business_day_range(start_date)[0].isoformat(),
            "window_end_at": get_business_day_range(end_date)[1].isoformat(),
            "max_pages": max_pages,
            "page_count": page_result["page_count"],
            "next_cursor_exists": bool(page_result["next_token"]),
            "created_count": write_result["created"],
            "updated_count": write_result["updated"],
            "skipped_count": 0,
            "sample_ids": sample_ids,
            "last_synced_at": synced_at.isoformat(),
        }
        checkpoint = _upsert_coupang_order_checkpoint(
            db,
            store_id=store_id,
            start_date=start_date,
            end_date=end_date,
            next_cursor_exists=bool(page_result["next_token"]),
            synced_at=synced_at,
        )
        result["checkpoint"] = checkpoint
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly order sync success",
            raw_summary=_order_sync_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly order sync failed",
            error_detail=_mask_sensitive_text(exc.message),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_ORDER_SOURCE_TYPE,
                "error_code": exc.error_code,
            },
        )
        raise
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly order sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_ORDER_SOURCE_TYPE,
                "error_code": "COUPANG_ORDER_SYNC_FAILED",
            },
        )
        raise ApiError(
            message="Coupang readonly order sync failed",
            error_code="COUPANG_ORDER_SYNC_FAILED",
            status_code=502,
        ) from exc


def _ensure_coupang_store(db: Session, store_id: int) -> None:
    store = ensure_store_exists(db, store_id)
    if normalize_platform(store.platform) != "coupang":
        raise ApiError(
            message="Coupang order sync requires a Coupang store",
            error_code="STORE_PLATFORM_MISMATCH",
            status_code=400,
            detail={"store_id": store_id, "store_platform": store.platform},
        )


def _fetch_coupang_order_pages(
    credential: DecryptedCredential,
    start_date: date,
    end_date: date,
    max_pages: int,
) -> dict:
    unique_items: list[dict] = []
    seen_ids: set[str] = set()
    next_token: str | None = None
    page_count = 0

    while page_count < max_pages:
        payload = _fetch_coupang_order_preview_page(
            credential=credential,
            start_date=start_date,
            end_date=end_date,
            next_token=next_token,
        )
        for item in _extract_preview_items(payload):
            order_id = _resolve_preview_order_id(item)
            if order_id in seen_ids:
                continue
            seen_ids.add(order_id)
            unique_items.append(item)
        page_count += 1
        next_token = _extract_next_token(payload)
        if not next_token:
            break

    return {
        "items": unique_items,
        "page_count": page_count,
        "next_token": next_token,
    }


def _resolve_coupang_product_statuses(status: str | None) -> list[str]:
    normalized = str(status or "APPROVED").strip().upper()
    if normalized == "ALL":
        return list(COUPANG_PRODUCT_STATUSES)
    if normalized not in COUPANG_PRODUCT_STATUSES:
        raise ApiError(
            message="Unsupported Coupang product status",
            error_code="INVALID_COUPANG_PRODUCT_STATUS",
            status_code=400,
            detail={"status": status, "supported_statuses": ["all", *COUPANG_PRODUCT_STATUSES]},
        )
    return [normalized]


def _ensure_coupang_page_limit(max_pages: int) -> None:
    if max_pages < 1 or max_pages > COUPANG_PRODUCT_MAX_PAGES:
        raise ApiError(
            message="max_pages must be between 1 and 3",
            error_code="INVALID_SYNC_WINDOW",
            status_code=400,
            detail={"max_pages": max_pages, "allowed_max_pages": COUPANG_PRODUCT_MAX_PAGES},
        )


def _fetch_coupang_product_statuses(
    credential: DecryptedCredential,
    statuses: list[str],
    max_pages: int,
) -> dict:
    unique_items: list[dict] = []
    seen_ids: set[str] = set()
    per_status: list[dict] = []
    total_page_count = 0
    any_next_cursor_exists = False

    for status in statuses:
        status_items: list[dict] = []
        skipped_count = 0
        next_token: str | None = None
        page_count = 0

        while page_count < max_pages:
            payload = _fetch_coupang_product_page(
                credential=credential,
                status=status,
                next_token=next_token,
            )
            for item in _extract_preview_items(payload):
                product_id = _resolve_product_id(item)
                if not product_id:
                    skipped_count += 1
                    continue
                if product_id not in seen_ids:
                    seen_ids.add(product_id)
                    unique_items.append(item)
                status_items.append(item)
            page_count += 1
            total_page_count += 1
            next_token = _extract_next_token(payload)
            if not next_token:
                break

        any_next_cursor_exists = any_next_cursor_exists or bool(next_token)
        per_status.append({
            "status": status,
            "page_count": page_count,
            "next_cursor_exists": bool(next_token),
            "item_count": len(status_items),
            "skipped_count": skipped_count,
            "product_ids": [_resolve_product_id(item) for item in status_items if _resolve_product_id(item)],
            "sample_ids": [_resolve_product_id(item) for item in status_items[:10] if _resolve_product_id(item)],
        })

    return {
        "items": unique_items,
        "per_status": per_status,
        "page_count": total_page_count,
        "next_cursor_exists": any_next_cursor_exists,
    }


def _fetch_coupang_product_page(
    credential: DecryptedCredential,
    status: str,
    next_token: str | None = None,
) -> dict:
    assert credential.vendor_id is not None
    path = "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products"
    params = {
        "vendorId": credential.vendor_id,
        "maxPerPage": str(COUPANG_PRODUCT_PAGE_SIZE),
        "status": status,
    }
    if next_token:
        params["nextToken"] = next_token
    response = _coupang_get_with_credential(credential, path, urlencode(params))
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                message="Coupang product query returned a non-JSON payload",
                error_code="COUPANG_PRODUCT_INVALID_RESPONSE",
                status_code=502,
            ) from exc

    if response.status_code in {401, 403}:
        error_code = "auth_failed"
    elif response.status_code == 429:
        error_code = "rate_limited"
    else:
        error_code = "readonly_request_failed"
    raise ApiError(
        message=f"Coupang product query failed with HTTP {response.status_code}",
        error_code=error_code,
        status_code=502 if response.status_code >= 500 else response.status_code,
        detail={"http_status": response.status_code, "status": status},
    )


def _fetch_coupang_sales_pages(
    credential: DecryptedCredential,
    start_date: date,
    end_date: date,
    max_pages: int,
) -> dict:
    unique_items: list[dict] = []
    seen_ids: set[str] = set()
    next_token: str | None = ""
    page_count = 0

    while page_count < max_pages:
        payload = _fetch_coupang_sales_page(
            credential=credential,
            start_date=start_date,
            end_date=end_date,
            token=next_token or "",
        )
        for item in _extract_preview_items(payload):
            item_id = _resolve_financial_row_id(item)
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            unique_items.append(item)
        page_count += 1
        next_token = _extract_next_token(payload)
        if not next_token:
            break

    return {
        "items": unique_items,
        "page_count": page_count,
        "next_cursor_exists": bool(next_token),
    }


def _fetch_coupang_sales_page(
    credential: DecryptedCredential,
    start_date: date,
    end_date: date,
    token: str = "",
) -> dict:
    assert credential.vendor_id is not None
    path = "/v2/providers/openapi/apis/api/v1/revenue-history"
    params = {
        "vendorId": credential.vendor_id,
        "recognitionDateFrom": start_date.isoformat(),
        "recognitionDateTo": end_date.isoformat(),
        "token": token,
        "maxPerPage": str(COUPANG_FINANCIAL_PAGE_SIZE),
    }
    response = _coupang_get_with_credential(credential, path, urlencode(params))
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                message="Coupang sales preview returned a non-JSON payload",
                error_code="COUPANG_SALES_INVALID_RESPONSE",
                status_code=502,
            ) from exc

    if response.status_code in {401, 403}:
        error_code = "auth_failed"
        message = f"Coupang sales preview request failed with HTTP {response.status_code}"
    elif response.status_code == 400:
        error_code = "SALES_DATE_NOT_AVAILABLE"
        message = "Coupang sales date may not be available yet. Sales preview can require completed historical recognition dates."
    elif response.status_code == 429:
        error_code = "rate_limited"
        message = "Coupang sales preview request was rate limited"
    else:
        error_code = "readonly_request_failed"
        message = f"Coupang sales preview request failed with HTTP {response.status_code}"
    raise ApiError(
        message=message,
        error_code=error_code,
        status_code=502 if response.status_code >= 500 else response.status_code,
        detail={
            "http_status": response.status_code,
            "date_availability_notice": "Sales confirmation dates may only be queryable after Coupang completes historical recognition.",
        },
    )


def _fetch_coupang_settlement_months(
    credential: DecryptedCredential,
    months: list[str],
) -> dict:
    items: list[dict] = []
    per_month: list[dict] = []
    for month in months:
        payload = _fetch_coupang_settlement_month(credential=credential, month=month)
        month_items = _extract_preview_items(payload)
        items.extend(month_items)
        per_month.append({
            "revenue_recognition_year_month": month,
            "item_count": len(month_items),
            "sample_ids": [_resolve_financial_row_id(item) for item in month_items[:10]],
        })
    return {
        "items": items,
        "per_month": per_month,
        "page_count": len(months),
    }


def _fetch_coupang_settlement_month(
    credential: DecryptedCredential,
    month: str,
) -> dict:
    path = "/v2/providers/marketplace_openapi/apis/api/v1/settlement-histories"
    response = _coupang_get_with_credential(credential, path, urlencode({
        "revenueRecognitionYearMonth": month,
    }))
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                message="Coupang settlement preview returned a non-JSON payload",
                error_code="COUPANG_SETTLEMENT_INVALID_RESPONSE",
                status_code=502,
            ) from exc

    if response.status_code in {401, 403}:
        error_code = "auth_failed"
    elif response.status_code == 429:
        error_code = "rate_limited"
    else:
        error_code = "readonly_request_failed"
    raise ApiError(
        message=f"Coupang settlement preview request failed with HTTP {response.status_code}",
        error_code=error_code,
        status_code=502 if response.status_code >= 500 else response.status_code,
        detail={"http_status": response.status_code, "revenueRecognitionYearMonth": month},
    )


def _to_coupang_product_payload(item: dict, synced_at: datetime) -> dict | None:
    external_product_id = _resolve_product_id(item)
    if not external_product_id:
        return None
    status_name = _extract_scalar_by_keys(item, ("statusName", "status", "saleStatus"))
    return {
        "external_product_id": external_product_id,
        "name": _bounded_text(
            _extract_scalar_by_keys(item, ("sellerProductName", "productName", "vendorItemName", "itemName"))
            or f"Coupang product {external_product_id}",
            300,
        ),
        "sku": _bounded_text(_extract_scalar_by_keys(item, ("sellerProductId", "vendorItemId", "externalVendorSku", "sku")), 120),
        "brand": _bounded_text(_extract_scalar_by_keys(item, ("brand", "brandName")), 120),
        "category": _bounded_text(_extract_scalar_by_keys(item, ("categoryName", "displayCategoryCode", "categoryId")), 120),
        "status": _bounded_text(status_name or "unknown", 30),
        "price": _extract_decimal_by_keys(item, ("salePrice", "originalPrice", "price")) or Decimal("0"),
        "currency": _extract_scalar_by_keys(item, ("currency", "currencyCode")) or "KRW",
        "stock_quantity": _extract_int_by_keys(item, ("stockQuantity", "quantity", "inventory")) or 0,
        "source_type": COUPANG_PRODUCT_SOURCE_TYPE,
        "last_synced_at": synced_at,
    }


def _resolve_product_id(item: dict) -> str | None:
    return _bounded_text(_extract_scalar_by_keys(
        item,
        ("sellerProductId", "productId", "vendorItemId", "itemId", "externalProductId"),
    ), 120)


def _bounded_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:max_length]


def _find_existing_product_ids(
    db: Session,
    store_id: int,
    platform: str,
    external_product_ids: list[str],
) -> set[str]:
    if not external_product_ids:
        return set()
    rows = db.scalars(
        select(Product.external_product_id).where(
            Product.store_id == store_id,
            Product.platform == platform,
            Product.external_product_id.in_(external_product_ids),
        )
    ).all()
    return set(rows)


def _build_product_preview_per_status(per_status: list[dict], existing_ids: set[str]) -> list[dict]:
    result: list[dict] = []
    for item in per_status:
        product_ids = item["product_ids"]
        result.append({
            "status": item["status"],
            "status_semantic": "Coupang API product review/listing status",
            "page_count": item["page_count"],
            "next_cursor_exists": item["next_cursor_exists"],
            "item_count": item["item_count"],
            "would_create": sum(1 for product_id in product_ids if product_id not in existing_ids),
            "would_update": sum(1 for product_id in product_ids if product_id in existing_ids),
            "skipped_count": item["skipped_count"],
            "sample_ids": item["sample_ids"],
        })
    return result


def _build_product_sync_per_status(per_status: list[dict]) -> list[dict]:
    return [
        {
            "status": item["status"],
            "status_semantic": "Coupang API product review/listing status",
            "page_count": item["page_count"],
            "next_cursor_exists": item["next_cursor_exists"],
            "item_count": item["item_count"],
            "skipped_count": item["skipped_count"],
            "sample_ids": item["sample_ids"],
        }
        for item in per_status
    ]


def _to_coupang_order_payload(item: dict, synced_at: datetime) -> dict:
    external_order_id = _resolve_preview_order_id(item)
    ordered_at = _extract_datetime_by_keys(
        item,
        ("orderedAt", "orderDate", "createdAt", "paidAt", "paymentDate", "orderedDate"),
    ) or synced_at
    paid_at = _extract_datetime_by_keys(item, ("paidAt", "paymentDate", "paidDate"))

    return {
        "external_order_id": external_order_id,
        "buyer_name": _extract_scalar_by_keys(item, ("buyerName", "ordererName", "receiverName")),
        "buyer_masked_phone": _mask_phone(_extract_scalar_by_keys(item, ("buyerPhone", "ordererPhone", "receiverPhone", "ordererSafeNumber", "receiverSafeNumber"))),
        "product_name": _extract_scalar_by_keys(
            item,
            ("sellerProductName", "productName", "vendorItemName", "itemName", "orderItemName"),
        )
        or f"Coupang order {external_order_id}",
        "quantity": _extract_int_by_keys(item, ("quantity", "shippingCount", "orderCount", "count")) or 1,
        "order_amount": _extract_decimal_by_keys(
            item,
            ("orderAmount", "paidAmount", "paymentAmount", "totalPrice", "orderPrice", "salesPrice"),
        )
        or Decimal("0"),
        "currency": _extract_scalar_by_keys(item, ("currency", "currencyCode")) or "KRW",
        "order_status": _extract_scalar_by_keys(item, ("orderStatus", "status", "shipmentStatus")) or "unknown",
        "paid_at": paid_at,
        "ordered_at": ordered_at,
        "source_type": COUPANG_ORDER_SOURCE_TYPE,
        "last_synced_at": synced_at,
        "raw_data": None,
    }


def _extract_int_by_keys(payload: object, keys: tuple[str, ...]) -> int | None:
    value = _extract_scalar_by_keys(payload, keys)
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _extract_decimal_by_keys(payload: object, keys: tuple[str, ...]) -> Decimal | None:
    value = _extract_scalar_by_keys(payload, keys)
    return _to_decimal(value)


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _extract_datetime_by_keys(payload: object, keys: tuple[str, ...]) -> datetime | None:
    value = _extract_scalar_by_keys(payload, keys)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            parsed = datetime.combine(date.fromisoformat(text), time.min)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=get_business_timezone())
    return parsed.astimezone(timezone.utc)


def _mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "****"
    return f"****{digits[-4:]}"


def _upsert_coupang_order_checkpoint(
    db: Session,
    store_id: int,
    start_date: date,
    end_date: date,
    next_cursor_exists: bool,
    synced_at: datetime,
) -> dict:
    return _upsert_coupang_sync_checkpoint(
        db,
        store_id=store_id,
        sync_type=COUPANG_ORDER_CHECKPOINT_SYNC_TYPE,
        cursor_payload={
            "last_window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "next_cursor_exists": next_cursor_exists,
        },
        synced_at=synced_at,
        notes_payload={
            "source_type": COUPANG_ORDER_SOURCE_TYPE,
            "last_success_at": synced_at.isoformat(),
            "write_scope": "local_orders_only",
        },
        window_start_at=get_business_day_range(start_date)[0],
        window_end_at=get_business_day_range(end_date)[1],
    )


def _upsert_coupang_sync_checkpoint(
    db: Session,
    store_id: int,
    sync_type: str,
    cursor_payload: dict,
    synced_at: datetime,
    notes_payload: dict,
    window_start_at: datetime | None = None,
    window_end_at: datetime | None = None,
) -> dict:
    checkpoint = db.scalar(
        select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == store_id,
            SyncCheckpoint.platform == "coupang",
            SyncCheckpoint.sync_type == sync_type,
        )
    )
    cursor_value = json.dumps(cursor_payload, ensure_ascii=True)
    notes = json.dumps(notes_payload, ensure_ascii=True)

    if checkpoint is None:
        checkpoint = SyncCheckpoint(
            store_id=store_id,
            platform="coupang",
            sync_type=sync_type,
            cursor_value=cursor_value,
            window_start_at=window_start_at,
            window_end_at=window_end_at,
            last_synced_at=synced_at,
            notes=notes,
        )
        db.add(checkpoint)
    else:
        checkpoint.cursor_value = cursor_value
        checkpoint.window_start_at = window_start_at
        checkpoint.window_end_at = window_end_at
        checkpoint.last_synced_at = synced_at
        checkpoint.notes = notes

    db.commit()
    db.refresh(checkpoint)
    return {
        "id": checkpoint.id,
        "store_id": checkpoint.store_id,
        "platform": checkpoint.platform,
        "sync_type": checkpoint.sync_type,
        "cursor_value": checkpoint.cursor_value,
        "window_start_at": _utc_isoformat(checkpoint.window_start_at),
        "window_end_at": _utc_isoformat(checkpoint.window_end_at),
        "last_synced_at": _utc_isoformat(checkpoint.last_synced_at),
        "notes": checkpoint.notes,
    }


def _utc_isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _resolve_financial_preview_date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    if start_date is None and end_date is None:
        target = get_business_date()
        start_date = target
        end_date = target
    elif start_date is None:
        start_date = end_date
    elif end_date is None:
        end_date = start_date

    assert start_date is not None
    assert end_date is not None
    _ensure_financial_date_window(start_date, end_date)
    return start_date, end_date


def _resolve_sales_preview_date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    current_business_date = get_business_date()
    if start_date is None and end_date is None:
        target = current_business_date - timedelta(days=1)
        start_date = target
        end_date = target
    elif start_date is None:
        start_date = end_date
    elif end_date is None:
        end_date = start_date

    assert start_date is not None
    assert end_date is not None
    _ensure_financial_date_window(start_date, end_date)
    if end_date >= current_business_date:
        raise ApiError(
            message="Sales preview only allows completed historical KST dates before the current business date",
            error_code="SALES_DATE_NOT_AVAILABLE",
            status_code=400,
            detail={
                "end_date": end_date.isoformat(),
                "current_business_date": current_business_date.isoformat(),
                "date_availability_notice": "Sales confirmation dates may only be queryable after Coupang completes historical recognition.",
            },
        )
    return start_date, end_date


def _ensure_financial_date_window(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise ApiError(
            message="start_date must be less than or equal to end_date",
            error_code="INVALID_SYNC_PREVIEW_WINDOW",
            status_code=400,
            detail={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
    day_span = (end_date - start_date).days + 1
    if day_span > COUPANG_FINANCIAL_PREVIEW_MAX_DAYS:
        raise ApiError(
            message="Financial preview date window must be 7 KST days or less for this system phase",
            error_code="INVALID_SYNC_PREVIEW_WINDOW",
            status_code=400,
            detail={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "max_days": COUPANG_FINANCIAL_PREVIEW_MAX_DAYS,
                "limit_type": "system_phase_limit",
                "official_limit": "not asserted by Codex1 in this phase",
            },
        )


def _ensure_financial_page_limit(max_pages: int) -> None:
    if max_pages < 1 or max_pages > COUPANG_FINANCIAL_MAX_PAGES:
        raise ApiError(
            message="max_pages must be between 1 and 3 for this system phase",
            error_code="INVALID_SYNC_WINDOW",
            status_code=400,
            detail={
                "max_pages": max_pages,
                "allowed_max_pages": COUPANG_FINANCIAL_MAX_PAGES,
                "limit_type": "system_phase_limit",
            },
        )


def _settlement_months_between(start_date: date, end_date: date) -> list[str]:
    months: list[str] = []
    cursor = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while cursor <= end_month:
        months.append(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def _resolve_preview_date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    if start_date is None and end_date is None:
        target = get_business_date()
        start_date = target
        end_date = target
    elif start_date is None:
        start_date = end_date
    elif end_date is None:
        end_date = start_date

    assert start_date is not None
    assert end_date is not None

    if start_date > end_date:
        raise ApiError(
            message="start_date must be less than or equal to end_date",
            error_code="INVALID_SYNC_PREVIEW_WINDOW",
            status_code=400,
            detail={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )

    day_span = (end_date - start_date).days + 1
    if day_span > COUPANG_ORDER_PREVIEW_MAX_DAYS:
        raise ApiError(
            message="Preview date window must be 3 KST days or less",
            error_code="INVALID_SYNC_PREVIEW_WINDOW",
            status_code=400,
            detail={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "max_days": COUPANG_ORDER_PREVIEW_MAX_DAYS,
            },
        )
    return start_date, end_date


def _ensure_coupang_preview_credential(credential: DecryptedCredential) -> None:
    missing = [
        name
        for name, value in {
            "vendor_id": credential.vendor_id,
            "access_key": credential.access_key,
            "secret_key": credential.secret_key,
        }.items()
        if not value
    ]
    if missing:
        raise ApiError(
            message="Coupang credential is missing required readonly preview fields",
            error_code="CREDENTIAL_NOT_READY",
            status_code=400,
            detail={"missing_fields": missing},
        )


def _fetch_coupang_order_preview_page(
    credential: DecryptedCredential,
    start_date: date,
    end_date: date,
    next_token: str | None = None,
) -> dict:
    assert credential.vendor_id is not None
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{credential.vendor_id}/ordersheets"
    params = {
        "createdAtFrom": start_date.isoformat(),
        "createdAtTo": end_date.isoformat(),
        "status": "ACCEPT",
        "maxPerPage": str(COUPANG_ORDER_PREVIEW_PAGE_SIZE),
    }
    if next_token:
        params["nextToken"] = next_token
    response = _coupang_get_with_credential(credential, path, urlencode(params))
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                message="Coupang preview returned a non-JSON payload",
                error_code="COUPANG_PREVIEW_INVALID_RESPONSE",
                status_code=502,
            ) from exc

    if response.status_code in {401, 403}:
        error_code = "auth_failed"
    elif response.status_code == 429:
        error_code = "rate_limited"
    else:
        error_code = "readonly_request_failed"
    raise ApiError(
        message=f"Coupang preview request failed with HTTP {response.status_code}",
        error_code=error_code,
        status_code=502 if response.status_code >= 500 else response.status_code,
        detail={"http_status": response.status_code},
    )


def _coupang_get_with_credential(credential: DecryptedCredential, path: str, query_string: str) -> httpx.Response:
    if credential.access_key is None or credential.secret_key is None:
        raise ApiError(
            message="Coupang credential is missing access or secret key",
            error_code="CREDENTIAL_NOT_READY",
            status_code=400,
        )
    signed_date = get_utc_now().strftime("%y%m%dT%H%M%SZ")
    message = f"{signed_date}GET{path}{query_string}"
    signature = hmac.new(
        credential.secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"CEA algorithm=HmacSHA256, access-key={credential.access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )
    url = f"https://api-gateway.coupang.com{path}?{query_string}"
    with httpx.Client(timeout=15.0) as client:
        return client.get(url, headers={"Authorization": authorization})


def _extract_order_ids_from_preview_payload(payload: object) -> list[str]:
    items = _extract_preview_items(payload)
    return [_resolve_preview_order_id(item) for item in items]


def _extract_preview_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
        items: list[dict] = []
        for item in payload:
            nested = _extract_preview_items(item)
            if nested:
                items.extend(nested)
        return items

    if isinstance(payload, dict):
        for key in ("data", "items", "content", "orderSheets", "orderSheetList", "orderSheetDtos"):
            value = payload.get(key)
            nested = _extract_preview_items(value)
            if nested:
                return nested
        for value in payload.values():
            nested = _extract_preview_items(value)
            if nested:
                return nested
    return []


def _extract_next_token(payload: object) -> str | None:
    if isinstance(payload, dict):
        for key in ("nextToken", "next_token", "nextPageToken"):
            value = payload.get(key)
            if value:
                return str(value)
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("nextToken", "next_token", "nextPageToken"):
                value = data.get(key)
                if value:
                    return str(value)
    return None


def _resolve_preview_order_id(item: dict) -> str:
    value = _extract_scalar_by_keys(
        item,
        ("orderId", "orderID", "orderNumber", "orderSheetId", "shipmentBoxId", "vendorOrderId"),
    )
    if value:
        return value
    serialized = json.dumps(item, sort_keys=True, ensure_ascii=True, default=str)
    return f"preview-hash-{hashlib.md5(serialized.encode('utf-8')).hexdigest()[:12]}"


def _extract_scalar_by_keys(payload: object, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value is not None and value != "" and not isinstance(value, (dict, list)):
                return str(value)
        for value in payload.values():
            found = _extract_scalar_by_keys(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_scalar_by_keys(item, keys)
            if found:
                return found
    return None


def _resolve_financial_row_id(item: dict) -> str:
    value = _extract_scalar_by_keys(
        item,
        (
            "revenueId",
            "settlementId",
            "orderId",
            "orderSheetId",
            "shipmentBoxId",
            "vendorItemId",
            "sellerProductId",
        ),
    )
    if value:
        return _bounded_text(value, 120) or value

    serialized = json.dumps(item, sort_keys=True, ensure_ascii=True, default=str)
    digest = hashlib.md5(serialized.encode("utf-8")).hexdigest()[:12]
    date_value = _extract_scalar_by_keys(
        item,
        (
            "recognitionDate",
            "revenueRecognitionDate",
            "revenueRecognitionYearMonth",
        ),
    )
    if date_value:
        return _bounded_text(f"{date_value}-{digest}", 120) or f"{date_value}-{digest}"
    return f"financial-preview-hash-{digest}"


def _sanitize_financial_sample_row(item: dict, settlement: bool = False) -> dict:
    if not isinstance(item, dict):
        return {"value": _bounded_text(str(item), 120)}

    result: dict[str, str | int | float | bool | None] = {}
    allowed_exact = {
        "orderId",
        "orderSheetId",
        "shipmentBoxId",
        "vendorItemId",
        "sellerProductId",
        "productId",
        "recognitionDate",
        "revenueRecognitionDate",
        "revenueRecognitionYearMonth",
        "settlementDate",
        "saleType",
        "salesType",
        "settlementType",
        "status",
        "statusName",
    }
    allowed_fragments = (
        "amount",
        "price",
        "sales",
        "sale",
        "revenue",
        "settlement",
        "commission",
        "fee",
        "tax",
        "date",
        "month",
        "type",
        "status",
        "orderid",
        "ordersheetid",
        "shipmentboxid",
        "productid",
        "itemid",
    )

    for key, value in item.items():
        normalized_key = str(key).replace("_", "").replace("-", "").lower()
        if _is_forbidden_financial_sample_field(normalized_key):
            continue
        if isinstance(value, (dict, list)):
            continue
        if key not in allowed_exact and not any(fragment in normalized_key for fragment in allowed_fragments):
            continue
        if value is None or isinstance(value, (int, float, bool)):
            result[key] = value
        else:
            result[key] = _bounded_text(str(value), 120)
        if len(result) >= 30:
            break

    if settlement:
        for key in list(result.keys()):
            normalized_key = str(key).replace("_", "").replace("-", "").lower()
            if normalized_key in COUPANG_SETTLEMENT_FORBIDDEN_FIELDS:
                result.pop(key, None)
    return result


def _is_forbidden_financial_sample_field(normalized_key: str) -> bool:
    forbidden_fragments = (
        "accesskey",
        "secretkey",
        "authorization",
        "signature",
        "token",
        "clientsecret",
        "bankaccountholder",
        "bankname",
        "bankaccount",
    )
    return any(fragment in normalized_key for fragment in forbidden_fragments)


def _build_financial_summary_totals(items: list[dict]) -> dict:
    totals: dict[str, Decimal] = {}
    monetary_fragments = ("amount", "price", "sale", "sales", "revenue", "settlement", "commission", "fee", "tax")
    non_monetary_fragments = ("date", "month", "status", "type", "id", "count", "no", "number")

    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            normalized_key = str(key).replace("_", "").replace("-", "").lower()
            if _is_forbidden_financial_sample_field(normalized_key):
                continue
            if not any(fragment in normalized_key for fragment in monetary_fragments):
                continue
            if any(fragment in normalized_key for fragment in non_monetary_fragments):
                continue
            amount = _to_decimal(value)
            if amount is None:
                continue
            totals[key] = totals.get(key, Decimal("0")) + amount
            if len(totals) >= 20:
                break

    return {key: _decimal_to_plain_string(value) for key, value in totals.items()}


def _decimal_to_plain_string(value: Decimal) -> str:
    return format(value, "f")


def _find_existing_order_ids(
    db: Session,
    store_id: int,
    platform: str,
    external_order_ids: list[str],
) -> set[str]:
    if not external_order_ids:
        return set()
    rows = db.scalars(
        select(Order.external_order_id).where(
            Order.store_id == store_id,
            Order.platform == platform,
            Order.external_order_id.in_(external_order_ids),
        )
    ).all()
    return set(rows)


def _preview_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "page_count": result["page_count"],
        "next_cursor_exists": result["next_cursor_exists"],
        "would_create": result["would_create"],
        "would_update": result["would_update"],
        "sample_ids": result["sample_ids"],
        "window": {
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "business_timezone": result["business_timezone"],
        },
    }


def _order_sync_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "write_scope": result["write_scope"],
        "platform_write": result["platform_write"],
        "created_count": result["created_count"],
        "updated_count": result["updated_count"],
        "skipped_count": result["skipped_count"],
        "page_count": result["page_count"],
        "next_cursor_exists": result["next_cursor_exists"],
        "sample_ids": result["sample_ids"],
        "date_window": {
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "business_timezone": result["business_timezone"],
        },
    }


def _product_preview_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "status_filter": result["status_filter"],
        "status_semantic_notice": result["status_semantic_notice"],
        "max_pages": result["max_pages"],
        "page_count": result["page_count"],
        "next_cursor_exists": result["next_cursor_exists"],
        "would_create": result["would_create"],
        "would_update": result["would_update"],
        "sample_ids": result["sample_ids"],
        "per_status": result["per_status"],
    }


def _product_sync_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "write_scope": result["write_scope"],
        "platform_write": result["platform_write"],
        "status_filter": result["status_filter"],
        "status_semantic_notice": result["status_semantic_notice"],
        "max_pages": result["max_pages"],
        "created_count": result["created_count"],
        "updated_count": result["updated_count"],
        "skipped_count": result["skipped_count"],
        "page_count": result["page_count"],
        "next_cursor_exists": result["next_cursor_exists"],
        "sample_ids": result["sample_ids"],
        "per_status": result["per_status"],
    }


def _financial_preview_summary_for_log(result: dict) -> dict:
    summary = {
        "source_type": result["source_type"],
        "sync_type": result["sync_type"],
        "total_rows": result["total_rows"],
        "sample_ids": result["sample_ids"],
        "sample_rows": result["sample_rows"],
        "summary_totals": result["summary_totals"],
        "semantic_notice": result["semantic_notice"],
    }
    if "start_date" in result:
        summary["date_window"] = {
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "business_timezone": result["business_timezone"],
        }
    if "max_pages" in result:
        summary["max_pages"] = result["max_pages"]
        summary["page_count"] = result["page_count"]
        summary["next_cursor_exists"] = result["next_cursor_exists"]
        summary["system_phase_limit_days"] = COUPANG_FINANCIAL_PREVIEW_MAX_DAYS
    if "months" in result:
        summary["months"] = result["months"]
        summary["per_month"] = result["per_month"]
        summary["month_semantic_notice"] = result["month_semantic_notice"]
    return summary


def _settlement_field_mapping_suggestion() -> dict:
    return {
        "suggested_table": "settlements or platform_financial_records",
        "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
        "dedupe_keys": ["store_id", "platform", "revenueRecognitionYearMonth", "settlementId or generated external_id"],
        "candidate_fields": [
            "store_id",
            "platform",
            "source_type",
            "external_settlement_id",
            "revenue_recognition_year_month",
            "settlement_date",
            "settlement_type",
            "sales_amount",
            "commission_amount",
            "fee_amount",
            "tax_amount",
            "settlement_amount",
            "currency",
            "last_synced_at",
        ],
        "excluded_fields": ["bankAccountHolder", "bankName", "bankAccount"],
        "note": "This phase previews field shape only and does not create or write a settlement table.",
    }
