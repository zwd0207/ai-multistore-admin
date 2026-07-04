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
from app.models.financial import PlatformSalesDetail, PlatformSettlementDetail
from app.models.api_credential import ApiCredential
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.product import Product
from app.models.sync_checkpoint import SyncCheckpoint
from app.schemas.credential import DecryptedCredential
from app.services import api_credential_readiness_service
from app.services.encryption import decrypt_value
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
COUPANG_SALES_SYNC_TYPE = "sales_coupang_real"
COUPANG_SALES_CHECKPOINT_SYNC_TYPE = "sales"
COUPANG_SETTLEMENT_PREVIEW_SYNC_TYPE = "settlements_coupang_real_preview"
COUPANG_SETTLEMENT_SYNC_TYPE = "settlements_coupang_real"
COUPANG_SETTLEMENT_CHECKPOINT_SYNC_TYPE = "settlements"
NAVER_PRODUCT_PREVIEW_SOURCE_TYPE = "naver_product_preview"
NAVER_PRODUCT_SYNC_SOURCE_TYPE = "naver_real_sync"
NAVER_ORDER_PREVIEW_SOURCE_TYPE = "naver_order_preview"
NAVER_ORDER_SYNC_SOURCE_TYPE = "naver_real_order_sync"
NAVER_ORDER_TIMELINE_MAPPING_VERSION = "naver_order_status_timeline_mock_mapper_v1"
COUPANG_ORDER_SOURCE_TYPE = "real_coupang"
COUPANG_PRODUCT_SOURCE_TYPE = "real_coupang"
COUPANG_FINANCIAL_SOURCE_TYPE = "real_coupang"
COUPANG_ORDER_PREVIEW_MAX_DAYS = 3
COUPANG_FINANCIAL_PREVIEW_MAX_DAYS = 7
NAVER_ORDER_PREVIEW_MAX_DAYS = 7
NAVER_ORDER_SINGLE_WRITE_MAX_DAYS = 1
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
        r"(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|access[_-]?key|secret[_-]?key|api[_-]?key|authorization|signature|header|bankAccountHolder|bankName|bankAccount)",
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


def preview_naver_products(
    db: Session,
    store_id: int,
    credential_id: int | None = None,
    page: int = 1,
    size: int = 20,
    status: str | None = "ALL",
    keyword: str | None = None,
    seller_product_id: str | None = None,
    real_preview: bool = False,
    real_sync: bool = False,
) -> dict:
    normalized_status = _resolve_naver_product_preview_status(status)
    credential = _ensure_naver_product_preview_credential(
        db,
        store_id=store_id,
        credential_id=credential_id,
    )
    field_observation = _build_naver_product_preview_field_observation(credential)
    capability_meta = api_credential_readiness_service.NAVER_CAPABILITY_MAP["naver.product_read"]
    field_observation.update({
        "request_params_confirmed": capability_meta.get("request_params_confirmed") == "confirmed",
        "minimum_request_body_confirmed": bool(capability_meta.get("minimum_request_body_confirmed")),
        "safe_to_real_test": bool(capability_meta.get("safe_to_real_test")),
        "docs_reference_version": capability_meta.get("docs_reference_version"),
        "endpoint_confirmed": capability_meta.get("endpoint_confirmed"),
        "grant_confirmed": capability_meta.get("grant_confirmed"),
        "preview_endpoint_planned": capability_meta.get("preview_endpoint_planned", False),
        "preview_endpoint_implemented": capability_meta.get("preview_endpoint_implemented", False),
    })
    if real_sync and not real_preview:
        raise ApiError(
            message="Naver product local sync requires real_preview=true",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if not real_preview:
        return _build_naver_product_guardrail_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            page=page,
            size=size,
            status=normalized_status,
            keyword_configured=bool(keyword and keyword.strip()),
            seller_product_id_configured=bool(seller_product_id and seller_product_id.strip()),
            field_observation=field_observation,
            error_code="guardrail_blocked",
        )

    _ensure_naver_product_real_preview_allowed(
        store_id=store_id,
        credential_id=credential.id,
        page=page,
        size=size,
        keyword=keyword,
        seller_product_id=seller_product_id,
        field_observation=field_observation,
        real_sync=real_sync,
    )
    if not capability_meta.get("minimum_request_body_confirmed"):
        return _build_naver_product_guardrail_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            page=page,
            size=size,
            status=normalized_status,
            keyword_configured=bool(keyword and keyword.strip()),
            seller_product_id_configured=bool(seller_product_id and seller_product_id.strip()),
            field_observation={
                **field_observation,
                "product_preview_called": False,
                "http_status": None,
                "docs_pending": True,
                "minimum_request_body_confirmed": False,
            },
            error_code="docs_pending",
            real_sync=real_sync,
        )

    return _run_naver_product_real_micro_preview(
        db=db,
        credential=credential,
        store_id=store_id,
        page=page,
        size=size,
        status=normalized_status,
        field_observation=field_observation,
        real_sync=real_sync,
    )


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


def sync_coupang_sales(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    max_pages: int = 1,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API sales sync is disabled",
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
        sync_type=COUPANG_SALES_SYNC_TYPE,
        message="coupang readonly sales sync started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "write_scope": "local_platform_sales_details_only",
            "platform_write": False,
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
        synced_at = get_utc_now()
        sales_items = [
            payload
            for item in fetch_result["items"]
            if (payload := _to_coupang_sales_payload(item, synced_at=synced_at)) is not None
        ]
        write_result = _upsert_coupang_sales_details(db, store_id, sales_items)
        sample_ids = [item["external_sales_id"] for item in sales_items[:10]]
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_SALES_SYNC_TYPE,
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "write_scope": "local_platform_sales_details_only",
            "platform_write": False,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "business_timezone": str(get_business_timezone()),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "window_start_at": _utc_isoformat(get_business_day_range(start_date)[0]),
            "window_end_at": _utc_isoformat(get_business_day_range(end_date)[1]),
            "max_pages": max_pages,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": fetch_result["next_cursor_exists"],
            "total_rows": len(fetch_result["items"]),
            "created_count": write_result["created"],
            "updated_count": write_result["updated"],
            "unchanged_count": write_result["unchanged"],
            "skipped_count": len(fetch_result["items"]) - len(sales_items),
            "sample_ids": sample_ids,
            "summary_totals": _build_financial_summary_totals(fetch_result["items"]),
            "last_synced_at": synced_at.isoformat(),
            "semantic_notice": "Sales sync is readonly toward Coupang and writes only sanitized sales details to the local database. It does not call Coupang write APIs.",
            "date_availability_notice": "Sales sync only allows completed historical KST dates before the current business date. The 7-day window is this system phase limit, not Coupang's official maximum.",
            "count_semantic_notice": "updated_count means mapped business fields changed. Existing rows with identical mapped fields are counted as unchanged_count, even when last_synced_at is refreshed.",
        }
        checkpoint = _upsert_coupang_sync_checkpoint(
            db,
            store_id=store_id,
            sync_type=COUPANG_SALES_CHECKPOINT_SYNC_TYPE,
            cursor_payload={
                "date_window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                "max_pages": max_pages,
                "page_count": result["page_count"],
                "next_cursor_exists": result["next_cursor_exists"],
                "total_rows": result["total_rows"],
            },
            synced_at=synced_at,
            notes_payload={
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "last_success_at": synced_at.isoformat(),
                "write_scope": "local_platform_sales_details_only",
                "platform_write": False,
                "date_availability_notice": result["date_availability_notice"],
            },
            window_start_at=get_business_day_range(start_date)[0],
            window_end_at=get_business_day_range(end_date)[1],
        )
        result["checkpoint"] = checkpoint
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly sales sync success",
            raw_summary=_sales_sync_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly sales sync failed",
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
            message="coupang readonly sales sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": "COUPANG_SALES_SYNC_FAILED",
            },
        )
        raise ApiError(
            message="Coupang sales sync failed",
            error_code="COUPANG_SALES_SYNC_FAILED",
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


def sync_coupang_settlements(
    db: Session,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    settings = get_settings()
    if not settings.real_api_test_enabled:
        raise ApiError(
            message="Readonly real API settlement sync is disabled",
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
        sync_type=COUPANG_SETTLEMENT_SYNC_TYPE,
        message="coupang readonly settlement sync started",
        raw_summary={
            "stage": "started",
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "write_scope": "local_platform_settlement_details_only",
            "platform_write": False,
            "months": months,
            "date_window": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "business_timezone": str(get_business_timezone()),
            },
            "month_semantic_notice": "Settlement sync queries revenueRecognitionYearMonth=YYYY-MM. start_date/end_date only derive queried months and the response is not day-precisely truncated.",
        },
    )

    try:
        fetch_result = _fetch_coupang_settlement_months(credential=credential, months=months)
        synced_at = get_utc_now()
        settlement_items = [
            payload
            for item in fetch_result["items"]
            if (payload := _to_coupang_settlement_payload(item, synced_at=synced_at)) is not None
        ]
        write_result = _upsert_coupang_settlement_details(db, store_id, settlement_items)
        sample_ids = [item["external_settlement_id"] for item in settlement_items[:10]]
        result = {
            "store_id": store_id,
            "platform": "coupang",
            "sync_type": COUPANG_SETTLEMENT_SYNC_TYPE,
            "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
            "write_scope": "local_platform_settlement_details_only",
            "platform_write": False,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "business_timezone": str(get_business_timezone()),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "months": months,
            "page_count": fetch_result["page_count"],
            "next_cursor_exists": False,
            "total_rows": len(fetch_result["items"]),
            "created_count": write_result["created"],
            "updated_count": write_result["updated"],
            "unchanged_count": write_result["unchanged"],
            "skipped_count": len(fetch_result["items"]) - len(settlement_items),
            "sample_ids": sample_ids,
            "per_month": fetch_result["per_month"],
            "summary_totals": _build_financial_summary_totals(fetch_result["items"]),
            "last_synced_at": synced_at.isoformat(),
            "semantic_notice": "Settlement sync is readonly toward Coupang and writes only sanitized settlement details to the local database. It does not call Coupang write APIs.",
            "month_semantic_notice": "Settlement sync queries revenueRecognitionYearMonth=YYYY-MM. start_date/end_date only derive queried months and the response is not day-precisely truncated.",
            "count_semantic_notice": "updated_count means mapped business fields changed. Existing rows with identical mapped fields are counted as unchanged_count, even when last_synced_at is refreshed.",
        }
        checkpoint = _upsert_coupang_sync_checkpoint(
            db,
            store_id=store_id,
            sync_type=COUPANG_SETTLEMENT_CHECKPOINT_SYNC_TYPE,
            cursor_payload={
                "months": months,
                "date_window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                "total_rows": result["total_rows"],
            },
            synced_at=synced_at,
            notes_payload={
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "last_success_at": synced_at.isoformat(),
                "write_scope": "local_platform_settlement_details_only",
                "platform_write": False,
                "month_semantic_notice": result["month_semantic_notice"],
            },
            window_start_at=get_business_day_range(start_date)[0],
            window_end_at=get_business_day_range(end_date)[1],
        )
        result["checkpoint"] = checkpoint
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly settlement sync success",
            raw_summary=_settlement_sync_summary_for_log(result),
        )
        result["sync_log"] = finished_log
        return result
    except ApiError as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="coupang readonly settlement sync failed",
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
            message="coupang readonly settlement sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "source_type": COUPANG_FINANCIAL_SOURCE_TYPE,
                "error_code": "COUPANG_SETTLEMENT_SYNC_FAILED",
            },
        )
        raise ApiError(
            message="Coupang settlement sync failed",
            error_code="COUPANG_SETTLEMENT_SYNC_FAILED",
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


def preview_naver_orders(
    db: Session,
    store_id: int,
    credential_id: int | None,
    start_datetime: datetime,
    end_datetime: datetime,
    order_status: str | None = "ALL",
    page: int = 1,
    size: int = 1,
    real_preview: bool = False,
    include_detail: bool = False,
    complete_field_preview: bool = False,
    real_sync: bool = False,
) -> dict:
    normalized_status = _resolve_naver_order_preview_status(order_status)
    start_kst, end_kst = _resolve_naver_order_preview_window(start_datetime, end_datetime)
    credential = _ensure_naver_product_preview_credential(
        db,
        store_id=store_id,
        credential_id=credential_id,
    )
    field_observation = _build_naver_order_preview_field_observation(credential)
    if real_sync and not real_preview:
        raise ApiError(
            message="Naver order single local write requires real_preview=true",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if real_sync and not include_detail:
        raise ApiError(
            message="Naver order single local write requires include_detail=true",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if complete_field_preview and not include_detail:
        raise ApiError(
            message="Naver complete order field preview requires include_detail=true",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if real_sync and complete_field_preview:
        raise ApiError(
            message="Naver complete order field preview is readonly-only",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if not real_preview:
        return _build_naver_order_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            start_datetime=start_kst.isoformat(),
            end_datetime=end_kst.isoformat(),
            page=page,
            size=size,
            order_status=normalized_status,
            guardrail_status="blocked",
            preview_status="blocked",
            test_status="not_tested",
            error_code="guardrail_blocked",
            field_observation=field_observation,
            sample_ids=[],
            has_more=False,
            would_create=0,
            would_update=0,
            local_sync_result=_default_naver_order_local_sync_result(real_sync),
        )

    _ensure_naver_order_real_preview_allowed(
        store_id=store_id,
        credential_id=credential.id,
        page=page,
        size=size,
        start_kst=start_kst,
        end_kst=end_kst,
        field_observation=field_observation,
        real_sync=real_sync,
    )
    return _run_naver_order_real_micro_preview(
        db=db,
        credential=credential,
        store_id=store_id,
        start_kst=start_kst,
        end_kst=end_kst,
        order_status=normalized_status,
        page=page,
        size=size,
        include_detail=include_detail,
        complete_field_preview=complete_field_preview,
        field_observation=field_observation,
        real_sync=real_sync,
    )


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


def _ensure_naver_product_preview_credential(db: Session, store_id: int, credential_id: int | None):
    store = ensure_store_exists(db, store_id)
    if normalize_platform(store.platform) != "naver":
        raise ApiError(
            message="Naver product preview requires a Naver store",
            error_code="STORE_PLATFORM_MISMATCH",
            status_code=400,
            detail={"store_id": store_id, "store_platform": store.platform, "expected_platform": "naver"},
        )

    if credential_id is None:
        credential = db.scalars(
            select(ApiCredential)
            .where(
                ApiCredential.store_id == store_id,
                ApiCredential.platform == "naver",
                ApiCredential.status == "active",
            )
            .order_by(ApiCredential.id.desc())
        ).first()
    else:
        credential = db.get(ApiCredential, credential_id)
        if credential is not None and credential.store_id != store_id:
            raise ApiError(
                message="Credential does not belong to the selected store",
                error_code="credential_not_ready",
                status_code=400,
                detail={"store_id": store_id, "credential_id": credential_id},
            )

    if credential is None or credential.platform != "naver" or credential.status != "active":
        raise ApiError(
            message="Active Naver credential is required for product preview scaffold",
            error_code="credential_not_ready",
            status_code=400,
            detail={"store_id": store_id, "credential_id": credential_id},
        )
    if not credential.client_id:
        raise ApiError(
            message="Naver client_id is required for product preview scaffold",
            error_code="credential_not_ready",
            status_code=400,
            detail={"store_id": store_id, "credential_id": credential.id},
        )
    if not credential.encrypted_secret_key:
        raise ApiError(
            message="Naver client secret is required for product preview scaffold",
            error_code="credential_not_ready",
            status_code=400,
            detail={"store_id": store_id, "credential_id": credential.id},
        )
    try:
        secret_key = decrypt_value(credential.encrypted_secret_key)
    except ApiError as exc:
        if exc.error_code == "CREDENTIAL_DECRYPT_FAILED":
            raise ApiError(
                message="Naver credential secret could not be decrypted for product preview scaffold",
                error_code="credential_decrypt_failed",
                status_code=400,
                detail={"store_id": store_id, "credential_id": credential.id},
            ) from exc
        raise
    if not secret_key:
        raise ApiError(
            message="Naver client secret is required for product preview scaffold",
            error_code="credential_not_ready",
            status_code=400,
            detail={"store_id": store_id, "credential_id": credential.id},
        )
    return credential


def _resolve_naver_product_preview_status(status: str | None) -> str:
    if status is None:
        return "ALL"
    normalized = status.strip().upper()
    if normalized == "ALL":
        return "ALL"
    raise ApiError(
        message="Naver product preview status is not supported in this scaffold phase",
        error_code="unsupported_status_filter",
        status_code=400,
        detail={"status": status, "allowed_statuses": ["ALL"]},
    )


def _naver_channel_no_configured(extra_config: dict | None) -> bool:
    if not isinstance(extra_config, dict):
        return False
    channel_no = extra_config.get("channel_no")
    return isinstance(channel_no, str) and bool(channel_no.strip())


def _build_naver_product_preview_field_observation(credential) -> dict:
    return {
        "channel_no_configured": _naver_channel_no_configured(credential.extra_config),
        "credential_decryptable": True,
    }


def _build_naver_product_preview_business_status_summary() -> list[str]:
    return [
        "商品读取暂未开放真实测试",
        "当前系统已完成 Naver 账号与频道前置检测",
        "为避免误触真实业务数据，商品接口仍处于保护状态",
        "后续需要完成商品 preview 小流量真实测试后，才可进入本地同步",
    ]


def _build_naver_product_guardrail_preview_result(
    *,
    store_id: int,
    credential_id: int,
    page: int,
    size: int,
    status: str,
    keyword_configured: bool,
    seller_product_id_configured: bool,
    field_observation: dict,
) -> dict:
    return {
        "store_id": store_id,
        "credential_id": credential_id,
        "platform": "naver",
        "preview_type": "products",
        "source_type": NAVER_PRODUCT_PREVIEW_SOURCE_TYPE,
        "guardrail_status": "blocked",
        "test_status": "not_tested",
        "error_code": "guardrail_blocked",
        "page": page,
        "size": size,
        "status_filter": status,
        "keyword_configured": keyword_configured,
        "seller_product_id_configured": seller_product_id_configured,
        "has_more": False,
        "would_create": 0,
        "would_update": 0,
        "sample_ids": [],
        "field_observation": field_observation,
        "business_status_summary": _build_naver_product_preview_business_status_summary(),
        "semantic_notice": "Readonly preview scaffold only. No local product rows were written.",
    }


def _build_naver_product_preview_field_observation(credential) -> dict:
    return {
        "channel_no_configured": _naver_channel_no_configured(credential.extra_config),
        "credential_decryptable": True,
        "product_preview_called": False,
        "http_status": None,
        "safe_keyword_flags": api_credential_readiness_service._empty_naver_safe_keyword_flags(),
        "business_error_hint": None,
        "product_id_observed": False,
        "origin_product_no_observed": False,
        "group_product_no_observed": False,
        "channel_products_observed": False,
        "channel_product_id_observed": False,
        "seller_product_id_observed": False,
        "product_name_observed": False,
        "sale_status_observed": False,
        "display_status_observed": False,
        "price_observed": False,
        "stock_observed": False,
        "raw_response_saved": False,
        "products_written": False,
        "request_body_shape": "page_size_only",
        "product_status_filter_sent": False,
        "channel_no_sent": False,
    }


def _build_naver_product_preview_business_status_summary(preview_status: str = "blocked") -> list[str]:
    if preview_status == "success":
        return [
            "商品只读微量预览已完成",
            "本次未写入本地商品数据",
            "本次未保存商品原始响应",
            "正式商品同步仍未开放",
        ]
    if preview_status == "success_empty":
        return [
            "当前暂无商品数据",
            "本次未写入本地商品数据",
            "本次未保存商品原始响应",
            "正式商品同步仍未开放",
        ]
    if preview_status == "failed":
        return [
            "商品预览失败",
            "本次未写入本地商品数据",
            "本次未保存商品原始响应",
            "请检查 Naver API 权限、IP 白名单或请求参数确认状态",
        ]
    return [
        "商品读取暂未开放真实测试",
        "当前系统已完成 Naver 账号与频道前置检测",
        "为避免误触真实业务数据，商品接口仍处于保护状态",
        "后续需要完成商品 preview 小流量真实测试后，才可进入本地同步",
    ]


def _ensure_naver_product_real_preview_allowed(
    *,
    store_id: int,
    credential_id: int,
    page: int,
    size: int,
    keyword: str | None,
    seller_product_id: str | None,
    field_observation: dict,
    real_sync: bool = False,
) -> None:
    settings = get_settings()
    if not settings.real_api_test_enabled or settings.real_api_write_enabled or store_id != 8 or credential_id != 7:
        raise ApiError(
            message="Naver product real micro preview is guardrail blocked",
            error_code="guardrail_blocked",
            status_code=400,
            detail={
                "store_id": store_id,
                "credential_id": credential_id,
                "real_api_test_enabled": bool(settings.real_api_test_enabled),
                "real_api_write_enabled": bool(settings.real_api_write_enabled),
            },
        )
    max_size = 5
    allowed_pages = (1,) if real_sync else (1, 2)
    if page not in allowed_pages or size < 1 or size > max_size:
        raise ApiError(
            message=(
                "Naver product local sync small-batch test only allows page=1 and size<=5"
                if real_sync
                else "Naver product real preview only allows page in {1,2} and size<=5"
            ),
            error_code="guardrail_blocked",
            status_code=400,
            detail={"page": page, "size": size, "allowed_pages": list(allowed_pages), "max_size": max_size},
        )
    if keyword or seller_product_id:
        raise ApiError(
            message="Naver product real micro preview does not accept keyword or seller_product_id yet",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if not field_observation.get("channel_no_configured"):
        raise ApiError(
            message="Naver product real micro preview requires configured channel_no",
            error_code="channel_no_missing",
            status_code=400,
        )


def _build_naver_product_guardrail_preview_result(
    *,
    store_id: int,
    credential_id: int,
    page: int,
    size: int,
    status: str,
    keyword_configured: bool,
    seller_product_id_configured: bool,
    field_observation: dict,
    error_code: str = "guardrail_blocked",
    real_sync: bool = False,
) -> dict:
    return _build_naver_product_preview_result(
        store_id=store_id,
        credential_id=credential_id,
        page=page,
        size=size,
        status=status,
        guardrail_status="blocked",
        preview_status="blocked",
        test_status="not_tested",
        error_code=error_code,
        field_observation=field_observation,
        sample_ids=[],
        has_more=False,
        keyword_configured=keyword_configured,
        seller_product_id_configured=seller_product_id_configured,
        local_sync_result=_default_naver_product_local_sync_result(real_sync),
    )


def _run_naver_product_real_micro_preview(
    *,
    db: Session,
    credential,
    store_id: int,
    page: int,
    size: int,
    status: str,
    field_observation: dict,
    real_sync: bool = False,
) -> dict:
    context = _build_naver_token_context_from_credential(credential)
    try:
        access_token, token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        field_observation["token_http_status"] = token_status
        field_observation["request_body_shape"] = "page_size_only"
        field_observation["product_status_filter_sent"] = False
        field_observation["channel_no_sent"] = False
        headers = {"Authorization": f"Bearer {access_token}"}
        product_result = _request_naver_product_search(
            api_base=context["api_base"],
            headers=headers,
            page=page,
            size=size,
        )
        field_observation["product_preview_called"] = True
        field_observation["http_status"] = product_result.get("http_status")
        if not product_result["success"]:
            error_code = product_result.get("error_code") or "readonly_request_failed"
            field_observation["safe_keyword_flags"] = product_result.get("safe_keyword_flags") or api_credential_readiness_service._empty_naver_safe_keyword_flags()
            field_observation["business_error_hint"] = api_credential_readiness_service._naver_business_error_hint(error_code)
            return _build_naver_product_preview_result(
                store_id=store_id,
                credential_id=credential.id,
                page=page,
                size=size,
                status=status,
                guardrail_status="allowed",
                preview_status="failed",
                test_status="preview_failed",
                error_code=error_code,
                field_observation=field_observation,
                sample_ids=[],
                has_more=False,
            )
        payload = product_result["payload"]
        sample_ids = [_mask_external_identifier(item) for item in _extract_naver_product_preview_ids(payload)[:5]]
        field_observation.update(_summarize_naver_product_preview_fields(payload))
        mapping_summary = _summarize_naver_product_mapping(payload)
        dry_run_diff = _build_naver_product_dry_run_diff(
            db,
            store_id=store_id,
            payload=payload,
            page=page,
            size=size,
        )
        local_sync_result = _sync_naver_product_preview_candidate(
            db,
            store_id=store_id,
            payload=payload,
            dry_run_diff=dry_run_diff,
            real_sync=real_sync,
        )
        field_observation["products_written"] = local_sync_result["products_written"]
        preview_status = "success" if sample_ids else "success_empty"
        return _build_naver_product_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            page=page,
            size=size,
            status=status,
            guardrail_status="allowed",
            preview_status=preview_status,
            test_status="preview_success",
            error_code=None,
            field_observation=field_observation,
            sample_ids=sample_ids,
            has_more=_naver_product_preview_has_more(payload),
            mapping_summary=mapping_summary,
            dry_run_diff=dry_run_diff,
            local_sync_result=local_sync_result,
        )
    except ApiError:
        raise
    except api_credential_readiness_service.NaverReadonlyAuthError as exc:
        return _build_naver_product_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            page=page,
            size=size,
            status=status,
            guardrail_status="allowed",
            preview_status="failed",
            test_status="preview_failed",
            error_code=exc.error_code,
            field_observation={
                **field_observation,
                "http_status": exc.http_status,
                "safe_keyword_flags": exc.safe_keyword_flags,
                "business_error_hint": exc.business_error_hint,
            },
            sample_ids=[],
            has_more=False,
        )
    except Exception as exc:
        http_status = getattr(exc, "http_status", None)
        error_code = "auth_failed" if str(exc) == "token_auth_failed" else "readonly_request_failed"
        return _build_naver_product_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            page=page,
            size=size,
            status=status,
            guardrail_status="allowed",
            preview_status="failed",
            test_status="preview_failed",
            error_code=error_code,
            field_observation={**field_observation, "http_status": http_status},
            sample_ids=[],
            has_more=False,
        )


def _request_naver_product_search(
    *,
    api_base: str,
    headers: dict[str, str],
    page: int,
    size: int,
) -> dict:
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base}/v1/products/search",
            headers=headers,
            json={"page": page, "size": size},
        )
    if response.status_code >= 400:
        return {
            "success": False,
            "http_status": response.status_code,
            "error_code": _naver_readonly_error_code(response, scope="product"),
            "safe_keyword_flags": api_credential_readiness_service._naver_safe_keyword_flags_from_text(response.text),
        }
    return {
        "success": True,
        "http_status": response.status_code,
        "payload": response.json(),
    }


def _extract_naver_product_preview_ids(payload: object) -> list[str]:
    ids: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"productId", "originProductNo", "channelProductNo", "sellerProductId", "itemId"} and value:
                ids.append(str(value))
            else:
                ids.extend(_extract_naver_product_preview_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            ids.extend(_extract_naver_product_preview_ids(item))
    unique: list[str] = []
    for value in ids:
        if value not in unique:
            unique.append(value)
    return unique


def _summarize_naver_product_preview_fields(payload: object) -> dict:
    field_names = _collect_json_field_names(payload)
    lower_names = [name.lower() for name in field_names]
    return {
        "product_id_observed": any(name in {"productid", "originproductno", "channelproductno", "itemid"} for name in lower_names),
        "origin_product_no_observed": "originproductno" in lower_names,
        "group_product_no_observed": "groupproductno" in lower_names,
        "channel_products_observed": "channelproducts" in lower_names,
        "channel_product_id_observed": any(name in {"channelproductno", "channelproductid"} for name in lower_names),
        "seller_product_id_observed": any("sellerproductid" in name for name in lower_names),
        "product_name_observed": any("productname" in name or name == "name" for name in lower_names),
        "sale_status_observed": any(name in {"statustype", "salestatus"} or "productstatus" in name or name == "status" for name in lower_names),
        "display_status_observed": any("displaystatus" in name for name in lower_names),
        "price_observed": any("price" in name for name in lower_names),
        "stock_observed": any("stock" in name or "quantity" in name for name in lower_names),
        "raw_response_saved": False,
        "products_written": False,
        "request_body_shape": "page_size_only",
        "product_status_filter_sent": False,
        "channel_no_sent": False,
    }


def _summarize_naver_product_mapping(payload: object | None) -> dict:
    field_names = _safe_naver_product_observed_field_names(payload)
    lower_names = {name.lower() for name in field_names}
    channel_summary = _summarize_naver_channel_products(payload)
    observed = {
        "origin_product_no": "originproductno" in lower_names,
        "channel_product_id": any(name in {"channelproductno", "channelproductid"} for name in lower_names),
        "product_name": any(name in {"productname", "name"} for name in lower_names),
        "sale_status": any(name in {"statustype", "salestatus", "status"} or "productstatus" in name for name in lower_names),
        "display_status": any("displaystatus" in name for name in lower_names),
        "price": any("price" in name for name in lower_names),
        "stock": any("stock" in name or "quantity" in name for name in lower_names),
    }
    missing = [name for name, present in observed.items() if not present]
    return {
        "product_field_mapping_summary": _build_naver_product_field_mapping_summary(channel_summary),
        "observed_field_names": field_names,
        "missing_field_names": missing,
        "mapping_readiness": {
            "ready_for_preview": True,
            "ready_for_local_sync": False,
            "local_sync_blocked_reason": "field_mapping_and_multi_channel_rules_pending",
        },
        "channel_products_summary": channel_summary,
    }


def _build_naver_product_field_mapping_summary(channel_summary: dict) -> dict:
    return {
        "external_product_id": {
            "source_priority": ["contents[].channelProducts[].channelProductNo", "contents[].originProductNo"],
            "target": "products.external_product_id",
            "rule": "Prefer channelProductNo only when a single channel product is observed; do not auto-select when multiple channelProducts exist.",
        },
        "platform_origin_product_no": {
            "source": "contents[].originProductNo",
            "target": "products.raw_data.platform_origin_product_no",
            "storage": "sanitized_metadata_only",
        },
        "platform_channel_product_id": {
            "source": "contents[].channelProducts[].channelProductNo",
            "target": "products.raw_data.platform_channel_product_id",
            "storage": "sanitized_metadata_only",
        },
        "name": {
            "source": "contents[].channelProducts[].productName",
            "target": "products.name",
            "max_length": 300,
        },
        "status": {
            "source": "contents[].channelProducts[].statusType",
            "target": "products.status",
            "normalization": "platform_status_candidate",
        },
        "display_status": {
            "source": "contents[].channelProducts[].channelProductDisplayStatusType",
            "target": "products.raw_data.display_status",
            "storage": "sanitized_metadata_only",
        },
        "price": {
            "source_priority": ["salePrice", "discountPrice", "price"],
            "target": "products.price",
            "normalization": "Decimal",
            "currency": "KRW",
        },
        "stock_quantity": {
            "source_priority": ["stockQuantity", "quantity", "inventory"],
            "target": "products.stock_quantity",
            "normalization": "int",
        },
        "source_type": {
            "preview": NAVER_PRODUCT_PREVIEW_SOURCE_TYPE,
            "future_sync": "naver_real_sync",
        },
        "multi_channel_rule": {
            "multiple_observed": bool(channel_summary.get("multiple_observed")),
            "local_sync_allowed": False,
            "rule": "Preview counts multiple channelProducts but does not expand them or write multiple products.",
        },
    }


def _safe_naver_product_observed_field_names(payload: object | None) -> list[str]:
    forbidden_fragments = (
        "html",
        "image",
        "detail",
        "token",
        "authorization",
        "header",
        "signature",
        "secret",
        "clientsecret",
        "channelno",
        "channel_no",
    )
    allowed: list[str] = []
    for name in _collect_json_field_names(payload):
        normalized = name.replace("_", "").replace("-", "").lower()
        if any(fragment in normalized for fragment in forbidden_fragments):
            if normalized not in {"channelproductno", "channelproductid"}:
                continue
        allowed.append(name[:80])
        if len(allowed) >= 40:
            break
    return sorted(dict.fromkeys(allowed))


def _summarize_naver_channel_products(payload: object | None) -> dict:
    counts: list[int] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "channelProducts" and isinstance(value, list):
                counts.append(len(value))
            elif isinstance(value, (dict, list)):
                nested = _summarize_naver_channel_products(value)
                counts.extend(nested.get("counts_by_content", []))
    elif isinstance(payload, list):
        for item in payload:
            nested = _summarize_naver_channel_products(item)
            counts.extend(nested.get("counts_by_content", []))
    total = sum(counts)
    return {
        "observed": bool(counts),
        "count": total,
        "multiple_observed": any(count > 1 for count in counts) or total > 1,
        "counts_by_content": counts[:10],
        "raw_payload_expanded": False,
        "products_written": False,
    }


def _build_naver_product_dry_run_diff(
    db: Session,
    *,
    store_id: int,
    payload: object | None,
    page: int = 1,
    size: int = 0,
) -> dict:
    candidate_ids: list[str] = []
    valid_candidates: list[dict] = []
    candidate_summaries: list[dict] = []
    create_reasons = {"external_product_id_not_found_locally": 0}
    update_reasons = {"business_fields_changed": 0}
    no_change_reasons = {"business_fields_unchanged": 0}
    refresh_only_reasons = {"sync_metadata_only": 0}
    skip_reasons = _empty_naver_product_skip_reasons()
    seen_external_product_ids: set[str] = set()
    single_channel_product_count = 0
    multiple_channel_products_count = 0
    missing_external_product_id_count = 0
    missing_product_name_count = 0
    missing_price_count = 0
    missing_stock_count = 0
    changed_fields: set[str] = set()
    unchanged_fields: set[str] = set()
    missing_optional_field_names: set[str] = set()
    risk_flags: set[str] = set()
    synced_at = get_utc_now()
    for index, content in enumerate(_iter_naver_product_contents(payload)):
        content_risk_flags = _naver_product_content_risk_flags(content)
        risk_flags.update(content_risk_flags)
        channel_products = content.get("channelProducts")
        if not isinstance(channel_products, list) or len(channel_products) == 0:
            skip_reasons["missing_external_product_id"] += 1
            missing_external_product_id_count += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="missing_external_product_id",
                risk_flags=content_risk_flags,
            ))
            continue
        if len(channel_products) > 1:
            skip_reasons["multiple_channel_products"] += 1
            multiple_channel_products_count += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="multiple_channel_products",
                risk_flags=content_risk_flags,
            ))
            continue
        channel_product = channel_products[0]
        if not isinstance(channel_product, dict):
            skip_reasons["missing_external_product_id"] += 1
            missing_external_product_id_count += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="missing_external_product_id",
                risk_flags=content_risk_flags,
            ))
            continue
        if _has_invalid_direct_shape(channel_product, ("statusType", "saleStatus", "status")):
            skip_reasons["invalid_status_shape"] += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="invalid_status_shape",
                risk_flags=content_risk_flags,
            ))
            continue
        external_product_id = _bounded_text(_extract_scalar_by_keys(channel_product, ("channelProductNo", "channelProductId")), 120)
        if not external_product_id:
            skip_reasons["missing_external_product_id"] += 1
            missing_external_product_id_count += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="missing_external_product_id",
                risk_flags=content_risk_flags,
            ))
            continue
        if external_product_id in seen_external_product_ids:
            skip_reasons["duplicate_external_product_id_in_same_batch"] += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="duplicate_external_product_id_in_same_batch",
                sample_id=_mask_external_identifier(external_product_id),
                risk_flags=content_risk_flags,
            ))
            continue
        product_name = _bounded_text(_extract_scalar_by_keys(channel_product, ("productName", "name")), 300)
        if not product_name:
            skip_reasons["missing_product_name"] += 1
            missing_product_name_count += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="missing_product_name",
                sample_id=_mask_external_identifier(external_product_id),
                risk_flags=content_risk_flags,
            ))
            continue
        if _has_invalid_numeric_value(channel_product, ("salePrice", "discountPrice", "price")):
            skip_reasons["invalid_numeric_shape_for_price"] += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="invalid_numeric_shape_for_price",
                sample_id=_mask_external_identifier(external_product_id),
                risk_flags=content_risk_flags,
            ))
            continue
        if _has_invalid_numeric_value(channel_product, ("stockQuantity", "quantity", "inventory")):
            skip_reasons["invalid_numeric_shape_for_stock"] += 1
            candidate_summaries.append(_build_naver_product_skip_candidate_summary(
                index=index,
                reason="invalid_numeric_shape_for_stock",
                sample_id=_mask_external_identifier(external_product_id),
                risk_flags=content_risk_flags,
            ))
            continue

        seen_external_product_ids.add(external_product_id)
        missing_optional_fields = False
        if _extract_decimal_by_keys(channel_product, ("salePrice", "discountPrice", "price")) is None:
            missing_price_count += 1
            missing_optional_fields = True
            missing_optional_field_names.add("price")
        if _extract_int_by_keys(channel_product, ("stockQuantity", "quantity", "inventory")) is None:
            missing_stock_count += 1
            missing_optional_fields = True
            missing_optional_field_names.add("stock_quantity")
        if missing_optional_fields:
            skip_reasons["missing_optional_fields"] += 1
        single_channel_product_count += 1
        candidate_ids.append(external_product_id)
        valid_candidates.append({
            "index": index,
            "sample_id": _mask_external_identifier(external_product_id),
            "risk_flags": content_risk_flags,
            "candidate": _build_naver_product_sync_candidate(
                content=content,
                channel_product=channel_product,
                external_product_id=external_product_id,
                product_name=product_name,
                synced_at=synced_at,
            ),
        })

    unique_candidate_ids = list(dict.fromkeys(candidate_ids))
    existing_products = _find_existing_products_by_external_ids(
        db,
        store_id=store_id,
        platform="naver",
        external_product_ids=unique_candidate_ids,
    )
    existing_ids = set(existing_products)
    for valid_candidate in valid_candidates:
        candidate = valid_candidate["candidate"]
        sample_id = valid_candidate["sample_id"]
        existing_product = existing_products.get(candidate["external_product_id"])
        if existing_product is None:
            create_reasons["external_product_id_not_found_locally"] += 1
            candidate_summaries.append({
                "candidate_type": "create",
                "sample_id": sample_id,
                "local_product_id": None,
                "reason": "external_product_id_not_found_locally",
                "match_basis": ["store_id", "platform=naver", "external_product_id"],
                "upsert_key_source": "channelProductNo|channelProductId",
                "product_name_matching_used": False,
                "fuzzy_matching_used": False,
                "raw_payload_saved": False,
                "full_external_id_returned": False,
            })
            continue

        update_summary = _build_naver_product_update_diff_summary(existing_product, candidate)
        changed_fields.update(update_summary["changed_fields"])
        unchanged_fields.update(update_summary["unchanged_fields"])
        missing_optional_field_names.update(update_summary["missing_optional_fields"])
        risk_flags.update(set(valid_candidate["risk_flags"]) | set(update_summary["risk_flags"]))
        comparison_result = update_summary["comparison_result"]
        if comparison_result == "update":
            update_reasons["business_fields_changed"] += 1
        elif comparison_result == "refresh_only":
            refresh_only_reasons["sync_metadata_only"] += 1
        else:
            no_change_reasons["business_fields_unchanged"] += 1
        candidate_summaries.append({
            "candidate_type": comparison_result,
            "sample_id": sample_id,
            "local_product_id": existing_product.id,
            "reason": update_summary["reason"],
            "match_basis": ["store_id", "platform=naver", "external_product_id"],
            "changed_fields": update_summary["changed_fields"],
            "unchanged_fields": update_summary["unchanged_fields"],
            "missing_optional_fields": update_summary["missing_optional_fields"],
            "refresh_only_fields": update_summary["refresh_only_fields"],
            "refresh_only_fields_unchanged": update_summary["refresh_only_fields_unchanged"],
            "risk_flags": sorted(set(valid_candidate["risk_flags"]) | set(update_summary["risk_flags"])),
            "high_risk_fields_observed_but_not_auto_overwritten": update_summary["high_risk_fields_observed_but_not_auto_overwritten"],
            "raw_payload_saved": False,
            "full_external_id_returned": False,
        })

    would_update = update_reasons["business_fields_changed"]
    would_no_change = no_change_reasons["business_fields_unchanged"]
    would_refresh_only = refresh_only_reasons["sync_metadata_only"]
    would_create = sum(1 for product_id in unique_candidate_ids if product_id not in existing_ids)
    would_skip = (
        skip_reasons["multiple_channel_products"]
        + skip_reasons["missing_external_product_id"]
        + skip_reasons["missing_product_name"]
        + skip_reasons["duplicate_external_product_id_in_same_batch"]
        + skip_reasons["invalid_status_shape"]
        + skip_reasons["invalid_numeric_shape_for_price"]
        + skip_reasons["invalid_numeric_shape_for_stock"]
    )
    return {
        "would_create": would_create,
        "would_update": would_update,
        "would_no_change": would_no_change,
        "would_refresh_only": would_refresh_only,
        "would_skip": would_skip,
        "skip_reasons": skip_reasons,
        "create_reasons": create_reasons,
        "update_reasons": update_reasons,
        "no_change_reasons": no_change_reasons,
        "refresh_only_reasons": refresh_only_reasons,
        "changed_fields": sorted(changed_fields),
        "unchanged_fields": sorted(unchanged_fields),
        "missing_optional_fields": sorted(missing_optional_field_names),
        "risk_flags": sorted(risk_flags | {"high_risk_fields_observed_but_not_auto_overwritten"}),
        "diff_summary": _build_naver_product_diff_summary(
            would_create=would_create,
            would_update=would_update,
            would_no_change=would_no_change,
            would_refresh_only=would_refresh_only,
            would_skip=would_skip,
            candidate_summaries=candidate_summaries,
        ),
        "pagination_overlap_summary": _build_naver_product_pagination_overlap_summary(
            page=page,
            size=size,
            candidate_summaries=candidate_summaries,
            matched_existing_count=len(existing_ids),
            would_update=would_update,
            would_no_change=would_no_change,
            would_refresh_only=would_refresh_only,
        ),
        "upsert_key_summary": _naver_product_upsert_key_summary(),
        "write_safety_summary": _naver_product_write_safety_summary(),
        "matched_existing_count": len(existing_ids),
        "incoming_candidate_count": len(unique_candidate_ids),
        "ready_for_local_sync": False,
        "single_channel_product_count": single_channel_product_count,
        "multiple_channel_products_count": multiple_channel_products_count,
        "missing_external_product_id_count": missing_external_product_id_count,
        "missing_product_name_count": missing_product_name_count,
        "missing_price_count": missing_price_count,
        "missing_stock_count": missing_stock_count,
        "source_type": "naver_product_preview_dry_run",
    }


def _build_naver_product_skip_candidate_summary(
    *,
    index: int,
    reason: str,
    sample_id: str | None = None,
    risk_flags: list[str] | None = None,
) -> dict:
    return {
        "candidate_type": "skip",
        "sample_id": sample_id or f"content-index-{index}",
        "reason": reason,
        "risk_flags": sorted(set(risk_flags or [])),
        "raw_payload_saved": False,
        "full_external_id_returned": False,
    }


def _build_naver_product_update_diff_summary(product: Product, candidate: dict) -> dict:
    changed_fields: list[str] = []
    unchanged_fields: list[str] = []
    missing_optional_fields: list[str] = []
    refresh_only_fields: list[str] = []
    refresh_only_fields_unchanged: list[str] = []
    comparable_fields = ("name", "status", "price", "currency", "stock_quantity")
    for field in comparable_fields:
        incoming = candidate.get(field)
        if incoming is None:
            if field in {"price", "stock_quantity"}:
                missing_optional_fields.append(field)
            continue
        existing = getattr(product, field)
        if field == "price":
            incoming = Decimal(str(incoming))
            existing = Decimal(str(existing))
        if incoming == existing:
            unchanged_fields.append(field)
        else:
            changed_fields.append(field)
    for field in ("source_type", "last_synced_at", "raw_data"):
        incoming = candidate.get(field)
        existing = getattr(product, field)
        if _naver_product_compare_values(field, existing, incoming):
            refresh_only_fields_unchanged.append(field)
        else:
            refresh_only_fields.append(field)
    if changed_fields:
        comparison_result = "update"
        reason = "business_fields_changed"
    elif refresh_only_fields:
        comparison_result = "refresh_only"
        reason = "sync_metadata_only"
    else:
        comparison_result = "no_change"
        reason = "business_fields_unchanged"
    return {
        "comparison_result": comparison_result,
        "reason": reason,
        "changed_fields": sorted(changed_fields),
        "unchanged_fields": sorted(unchanged_fields),
        "missing_optional_fields": sorted(missing_optional_fields),
        "refresh_only_fields": sorted(refresh_only_fields),
        "refresh_only_fields_unchanged": sorted(refresh_only_fields_unchanged),
        "risk_flags": [
            "high_risk_fields_observed_but_not_auto_overwritten",
            "raw_payload_not_saved",
            "full_external_id_masked",
        ],
        "high_risk_fields_observed_but_not_auto_overwritten": _naver_product_high_risk_fields(),
    }


def _build_naver_product_diff_summary(
    *,
    would_create: int,
    would_update: int,
    would_no_change: int,
    would_refresh_only: int,
    would_skip: int,
    candidate_summaries: list[dict],
) -> dict:
    return {
        "would_create": would_create,
        "would_update": would_update,
        "would_no_change": would_no_change,
        "would_refresh_only": would_refresh_only,
        "would_skip": would_skip,
        "candidate_summaries": candidate_summaries[:10],
        "values_returned": "field_names_counts_and_masked_ids_only",
        "raw_payload_saved": False,
        "full_external_id_returned": False,
    }


def _build_naver_product_pagination_overlap_summary(
    *,
    page: int,
    size: int,
    candidate_summaries: list[dict],
    matched_existing_count: int,
    would_update: int,
    would_no_change: int,
    would_refresh_only: int,
) -> dict:
    matched_existing_summaries = [
        item
        for item in candidate_summaries
        if item.get("candidate_type") in {"update", "no_change", "refresh_only"}
    ]
    overlap_risk_detected = page > 1 and matched_existing_count > 0
    return {
        "requested_page": page,
        "requested_size": size,
        "overlap_risk_detected": overlap_risk_detected,
        "overlap_review_required": overlap_risk_detected,
        "recommended_action": "stop_and_review_pagination" if overlap_risk_detected else "continue_readonly_review",
        "matched_existing_candidate_count": matched_existing_count,
        "matched_existing_candidate_types": {
            "would_update": would_update,
            "would_no_change": would_no_change,
            "would_refresh_only": would_refresh_only,
        },
        "masked_existing_match_sample_ids": [
            item["sample_id"]
            for item in matched_existing_summaries
            if item.get("sample_id")
        ][:5],
        "raw_payload_saved": False,
        "full_external_id_returned": False,
    }


def _naver_product_compare_values(field: str, existing: object, incoming: object) -> bool:
    if field == "price":
        if existing is None or incoming is None:
            return existing is incoming
        return Decimal(str(existing)) == Decimal(str(incoming))
    if field == "last_synced_at":
        return _normalize_naver_product_compare_datetime(existing) == _normalize_naver_product_compare_datetime(incoming)
    if field == "raw_data":
        return _normalize_naver_product_raw_data(existing) == _normalize_naver_product_raw_data(incoming)
    return existing == incoming


def _normalize_naver_product_raw_data(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    return {
        key: value.get(key)
        for key in _naver_product_raw_data_whitelist()
        if key in value
    }


def _normalize_naver_product_compare_datetime(value: object) -> object:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _naver_product_upsert_key_summary() -> dict:
    return {
        "match_basis": ["store_id", "platform=naver", "external_product_id"],
        "external_product_id_source": "channelProductNo|channelProductId",
        "product_name_matching_used": False,
        "fuzzy_matching_used": False,
        "origin_product_no_matching_used": False,
    }


def _naver_product_update_whitelist() -> list[str]:
    return [
        "name",
        "status",
        "price",
        "currency",
        "stock_quantity",
        "last_synced_at",
        "source_type",
    ]


def _naver_product_raw_data_whitelist() -> list[str]:
    return [
        "platform_origin_product_no",
        "platform_channel_product_id",
        "display_status",
        "channel_products_count",
        "source_preview_id_hash",
        "mapping_version",
        "synced_from",
        "raw_response_saved",
    ]


def _naver_product_high_risk_fields() -> list[str]:
    return [
        "external_product_id",
        "store_id",
        "platform",
        "raw_data.* outside sanitized whitelist",
        "html",
        "image_detail",
        "product_detail_raw_content",
        "original_raw_response",
        "request_metadata",
        "auth_material",
        "signing_material",
        "full_channel_identifier",
        "unmapped_platform_fields",
    ]


def _naver_product_write_safety_summary() -> dict:
    return {
        "ready_for_local_sync": False,
        "real_sync_required_for_writes": True,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "missing_optional_fields_block_write_approval": True,
        "non_first_page_match_requires_manual_review": True,
        "update_whitelist": _naver_product_update_whitelist(),
        "raw_data_whitelist": _naver_product_raw_data_whitelist(),
        "high_risk_fields_not_auto_overwritten": _naver_product_high_risk_fields(),
    }


def _naver_product_content_risk_flags(content: dict) -> list[str]:
    field_names = _collect_json_field_names(content)
    normalized = {name.replace("_", "").replace("-", "").lower() for name in field_names}
    flags: set[str] = set()
    if any("html" in name or "detail" in name for name in normalized):
        flags.add("detail_or_html_field_observed")
    if any("image" in name for name in normalized):
        flags.add("image_field_observed")
    if any(name in {"authorization", "header", "headers", "token", "signature", "bcrypt", "secret"} for name in normalized):
        flags.add("sensitive_material_observed_and_suppressed")
    flags.add("high_risk_fields_observed_but_not_auto_overwritten")
    return sorted(flags)


def _has_invalid_direct_shape(payload: dict, keys: tuple[str, ...]) -> bool:
    return any(isinstance(payload.get(key), (dict, list)) for key in keys if key in payload)


def _has_invalid_numeric_value(payload: dict, keys: tuple[str, ...]) -> bool:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            return True
        if _to_decimal(value) is None:
            return True
    return False


def _empty_naver_product_skip_reasons() -> dict[str, int]:
    return {
        "multiple_channel_products": 0,
        "missing_external_product_id": 0,
        "missing_product_name": 0,
        "missing_optional_fields": 0,
        "duplicate_external_product_id_in_same_batch": 0,
        "invalid_status_shape": 0,
        "invalid_numeric_shape_for_price": 0,
        "invalid_numeric_shape_for_stock": 0,
    }


def _default_naver_product_dry_run_diff(page: int = 1, size: int = 0) -> dict:
    return {
        "would_create": 0,
        "would_update": 0,
        "would_no_change": 0,
        "would_refresh_only": 0,
        "would_skip": 0,
        "skip_reasons": _empty_naver_product_skip_reasons(),
        "create_reasons": {"external_product_id_not_found_locally": 0},
        "update_reasons": {"business_fields_changed": 0},
        "no_change_reasons": {"business_fields_unchanged": 0},
        "refresh_only_reasons": {"sync_metadata_only": 0},
        "changed_fields": [],
        "unchanged_fields": [],
        "missing_optional_fields": [],
        "risk_flags": [],
        "diff_summary": _build_naver_product_diff_summary(
            would_create=0,
            would_update=0,
            would_no_change=0,
            would_refresh_only=0,
            would_skip=0,
            candidate_summaries=[],
        ),
        "pagination_overlap_summary": _build_naver_product_pagination_overlap_summary(
            page=page,
            size=size,
            candidate_summaries=[],
            matched_existing_count=0,
            would_update=0,
            would_no_change=0,
            would_refresh_only=0,
        ),
        "upsert_key_summary": _naver_product_upsert_key_summary(),
        "write_safety_summary": _naver_product_write_safety_summary(),
        "matched_existing_count": 0,
        "incoming_candidate_count": 0,
        "ready_for_local_sync": False,
        "single_channel_product_count": 0,
        "multiple_channel_products_count": 0,
        "missing_external_product_id_count": 0,
        "missing_product_name_count": 0,
        "missing_price_count": 0,
        "missing_stock_count": 0,
        "source_type": "naver_product_preview_dry_run",
    }


def _default_naver_product_local_sync_result(real_sync: bool = False) -> dict:
    return {
        "requested": bool(real_sync),
        "status": "not_requested" if not real_sync else "blocked",
        "source_type": NAVER_PRODUCT_SYNC_SOURCE_TYPE,
        "created_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "skip_reasons": _empty_naver_product_skip_reasons(),
        "sample_ids": [],
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "write_limit": 5,
    }


def _sync_naver_product_preview_candidate(
    db: Session,
    *,
    store_id: int,
    payload: object | None,
    dry_run_diff: dict,
    real_sync: bool,
) -> dict:
    result = _default_naver_product_local_sync_result(real_sync)
    if not real_sync:
        return result

    candidates, skip_reasons = _extract_naver_product_sync_candidates(payload)
    hard_skip_reasons = (
        "multiple_channel_products",
        "missing_external_product_id",
        "missing_product_name",
        "duplicate_external_product_id_in_same_batch",
        "invalid_status_shape",
        "invalid_numeric_shape_for_price",
        "invalid_numeric_shape_for_stock",
    )
    dry_run_skip_reasons = dry_run_diff.get("skip_reasons") or {}
    if any(
        int(skip_reasons.get(reason, 0)) > 0 or int(dry_run_skip_reasons.get(reason, 0)) > 0
        for reason in hard_skip_reasons
    ):
        result["status"] = "skipped"
        result["skipped_count"] = int(dry_run_diff.get("would_skip") or 0)
        result["skip_reasons"] = {
            reason: max(int(skip_reasons.get(reason, 0)), int(dry_run_skip_reasons.get(reason, 0)))
            for reason in _empty_naver_product_skip_reasons()
        }
        return result

    created_count = 0
    updated_count = 0
    sample_ids: list[str] = []
    update_fields = set(_naver_product_update_whitelist()) | {"raw_data"}
    for candidate in candidates[:5]:
        product = db.scalar(
            select(Product).where(
                Product.store_id == store_id,
                Product.platform == "naver",
                Product.external_product_id == candidate["external_product_id"],
            )
        )
        if product is None:
            db.add(Product(
                store_id=store_id,
                platform="naver",
                external_product_id=candidate["external_product_id"],
                **{field: value for field, value in candidate.items() if field != "external_product_id"},
            ))
            created_count += 1
        else:
            for field, value in candidate.items():
                if field in update_fields:
                    setattr(product, field, value)
            updated_count += 1
        sample_ids.append(_mask_external_identifier(candidate["external_product_id"]))
    db.commit()

    result["status"] = "success"
    result["products_written"] = True
    result["created_count"] = created_count
    result["updated_count"] = updated_count
    result["sample_ids"] = sample_ids[:5]
    result["skip_reasons"] = skip_reasons
    return result


def _build_naver_product_sync_candidate(
    *,
    content: dict,
    channel_product: dict,
    external_product_id: str,
    product_name: str,
    synced_at: datetime,
) -> dict:
    price = _extract_decimal_by_keys(channel_product, ("salePrice", "discountPrice", "price"))
    stock_quantity = _extract_int_by_keys(channel_product, ("stockQuantity", "quantity", "inventory"))
    origin_product_no = _bounded_text(_extract_scalar_by_keys(content, ("originProductNo",)), 120)
    display_status = _bounded_text(_extract_scalar_by_keys(channel_product, ("channelProductDisplayStatusType", "displayStatus")), 30)
    return {
        "external_product_id": external_product_id,
        "name": product_name,
        "sku": None,
        "brand": None,
        "category": None,
        "status": _bounded_text(_extract_scalar_by_keys(channel_product, ("statusType", "saleStatus", "status")) or "unknown", 30),
        "price": price or Decimal("0"),
        "currency": "KRW",
        "stock_quantity": stock_quantity if stock_quantity is not None else 0,
        "source_type": NAVER_PRODUCT_SYNC_SOURCE_TYPE,
        "last_synced_at": synced_at,
        "raw_data": {
            "platform_origin_product_no": _mask_external_identifier(origin_product_no) if origin_product_no else None,
            "platform_channel_product_id": _mask_external_identifier(external_product_id),
            "display_status": display_status,
            "channel_products_count": 1,
            "source_preview_id_hash": _mask_external_identifier(external_product_id),
            "mapping_version": "naver_product_v1",
            "synced_from": NAVER_PRODUCT_PREVIEW_SOURCE_TYPE,
            "raw_response_saved": False,
        },
    }


def _extract_naver_product_sync_candidates(payload: object | None) -> tuple[list[dict], dict[str, int]]:
    candidates: list[dict] = []
    skip_reasons = _empty_naver_product_skip_reasons()
    synced_at = get_utc_now()
    for content in _iter_naver_product_contents(payload):
        channel_products = content.get("channelProducts")
        if not isinstance(channel_products, list) or len(channel_products) == 0:
            skip_reasons["missing_external_product_id"] += 1
            continue
        if len(channel_products) > 1:
            skip_reasons["multiple_channel_products"] += 1
            continue
        channel_product = channel_products[0]
        if not isinstance(channel_product, dict):
            skip_reasons["missing_external_product_id"] += 1
            continue
        external_product_id = _bounded_text(_extract_scalar_by_keys(channel_product, ("channelProductNo", "channelProductId")), 120)
        if not external_product_id:
            skip_reasons["missing_external_product_id"] += 1
            continue
        product_name = _bounded_text(_extract_scalar_by_keys(channel_product, ("productName", "name")), 300)
        if not product_name:
            skip_reasons["missing_product_name"] += 1
            continue

        price = _extract_decimal_by_keys(channel_product, ("salePrice", "discountPrice", "price"))
        stock_quantity = _extract_int_by_keys(channel_product, ("stockQuantity", "quantity", "inventory"))
        if price is None or stock_quantity is None:
            skip_reasons["missing_optional_fields"] += 1
        candidates.append(_build_naver_product_sync_candidate(
            content=content,
            channel_product=channel_product,
            external_product_id=external_product_id,
            product_name=product_name,
            synced_at=synced_at,
        ))
    return candidates[:5], skip_reasons


def _iter_naver_product_contents(payload: object | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    contents = payload.get("contents")
    if isinstance(contents, list):
        return [item for item in contents if isinstance(item, dict)]
    return []


def _naver_product_preview_has_more(payload: object) -> bool:
    if isinstance(payload, dict):
        for key in ("hasMore", "hasNext", "more"):
            if isinstance(payload.get(key), bool):
                return payload[key]
        if isinstance(payload.get("last"), bool):
            return not payload["last"]
    return False


def _extend_naver_product_mapping_business_summary(preview_status: str) -> list[str]:
    summary = list(_build_naver_product_preview_business_status_summary(preview_status))
    if preview_status == "success":
        for message in [
            "商品只读微量预览成功",
            "已观察到商品名称、状态、价格、库存等关键字段",
            "本阶段未写入本地商品数据",
            "正式商品同步仍需完成字段映射与入库规则确认",
        ]:
            if message not in summary:
                summary.append(message)
    if preview_status in {"success", "success_empty"}:
        for message in [
            "已完成本地同步影响预估",
            "本阶段未写入本地商品数据",
            "正式商品同步仍需确认后执行",
        ]:
            if message not in summary:
                summary.append(message)
    return summary


def _build_naver_product_preview_result(
    *,
    store_id: int,
    credential_id: int,
    page: int,
    size: int,
    status: str,
    guardrail_status: str,
    preview_status: str,
    test_status: str,
    error_code: str | None,
    field_observation: dict,
    sample_ids: list[str],
    has_more: bool,
    keyword_configured: bool = False,
    seller_product_id_configured: bool = False,
    mapping_summary: dict | None = None,
    dry_run_diff: dict | None = None,
    local_sync_result: dict | None = None,
) -> dict:
    safe_mapping_summary = mapping_summary or _summarize_naver_product_mapping(None)
    safe_dry_run_diff = dry_run_diff or _default_naver_product_dry_run_diff(page=page, size=size)
    safe_local_sync_result = local_sync_result or _default_naver_product_local_sync_result(False)
    safe_keyword_flags = dict(
        field_observation.get("safe_keyword_flags")
        or api_credential_readiness_service._empty_naver_safe_keyword_flags()
    )
    business_error_hint = field_observation.get("business_error_hint") or api_credential_readiness_service._naver_business_error_hint(error_code)
    semantic_notice = "Readonly preview scaffold only. No local product rows were written."
    if safe_local_sync_result.get("products_written"):
        written_count = int(safe_local_sync_result.get("created_count") or 0) + int(safe_local_sync_result.get("updated_count") or 0)
        semantic_notice = f"Naver product local sync small-batch test wrote {written_count} sanitized local product rows."
    return {
        "store_id": store_id,
        "credential_id": credential_id,
        "platform": "naver",
        "preview_type": "products",
        "source_type": NAVER_PRODUCT_PREVIEW_SOURCE_TYPE,
        "guardrail_status": guardrail_status,
        "preview_status": preview_status,
        "test_status": test_status,
        "error_code": error_code,
        "safe_keyword_flags": safe_keyword_flags,
        "business_error_hint": business_error_hint,
        "product_preview_called": bool(field_observation.get("product_preview_called")),
        "http_status": field_observation.get("http_status"),
        "page": page,
        "size": size,
        "status_filter": status,
        "keyword_configured": keyword_configured,
        "seller_product_id_configured": seller_product_id_configured,
        "has_more": has_more,
        "would_create": safe_dry_run_diff["would_create"],
        "would_update": safe_dry_run_diff["would_update"],
        "would_no_change": safe_dry_run_diff["would_no_change"],
        "would_refresh_only": safe_dry_run_diff["would_refresh_only"],
        "sample_ids": sample_ids,
        "field_observation": field_observation,
        "dry_run_diff": safe_dry_run_diff,
        "local_sync_result": safe_local_sync_result,
        "product_field_mapping_summary": safe_mapping_summary["product_field_mapping_summary"],
        "observed_field_names": safe_mapping_summary["observed_field_names"],
        "missing_field_names": safe_mapping_summary["missing_field_names"],
        "mapping_readiness": safe_mapping_summary["mapping_readiness"],
        "channel_products_summary": safe_mapping_summary["channel_products_summary"],
        "business_status_summary": _extend_naver_product_mapping_business_summary(preview_status),
        "semantic_notice": semantic_notice,
    }


def _build_naver_product_fake_preview_summary(
    db: Session,
    store_id: int,
    items: list[dict],
    page: int = 1,
    size: int = 20,
    has_more: bool = False,
) -> dict:
    unique_product_ids = [_resolve_product_id(item) for item in items if _resolve_product_id(item)]
    existing_ids = _find_existing_product_ids(db, store_id=store_id, platform="naver", external_product_ids=unique_product_ids)
    return {
        "platform": "naver",
        "preview_type": "products",
        "source_type": NAVER_PRODUCT_PREVIEW_SOURCE_TYPE,
        "page": page,
        "size": size,
        "has_more": bool(has_more),
        "would_create": sum(1 for product_id in unique_product_ids if product_id not in existing_ids),
        "would_update": sum(1 for product_id in unique_product_ids if product_id in existing_ids),
        "sample_ids": unique_product_ids[:10],
        "field_observation": {
            "raw_payload_saved": False,
            "fake_summary_only": True,
        },
    }


def _resolve_naver_order_preview_status(order_status: str | None) -> str:
    if order_status is None:
        return "ALL"
    normalized = order_status.strip().upper()
    if normalized == "ALL":
        return "ALL"
    raise ApiError(
        message="Naver order preview status is not supported in this micro preview phase",
        error_code="unsupported_status_filter",
        status_code=400,
        detail={"order_status": order_status, "allowed_statuses": ["ALL"]},
    )


def _resolve_naver_order_preview_window(start_datetime: datetime, end_datetime: datetime) -> tuple[datetime, datetime]:
    business_tz = get_business_timezone()
    if start_datetime.tzinfo is None:
        start_kst = start_datetime.replace(tzinfo=business_tz)
    else:
        start_kst = start_datetime.astimezone(business_tz)
    if end_datetime.tzinfo is None:
        end_kst = end_datetime.replace(tzinfo=business_tz)
    else:
        end_kst = end_datetime.astimezone(business_tz)
    if end_kst <= start_kst:
        raise ApiError(
            message="Naver order preview end_datetime must be greater than start_datetime",
            error_code="date_range_invalid",
            status_code=400,
        )
    if end_kst - start_kst > timedelta(days=NAVER_ORDER_PREVIEW_MAX_DAYS):
        raise ApiError(
            message="Naver order micro preview window must be 7 KST days or less",
            error_code="date_range_invalid",
            status_code=400,
            detail={
                "start_datetime": start_kst.isoformat(),
                "end_datetime": end_kst.isoformat(),
                "max_window": f"P{NAVER_ORDER_PREVIEW_MAX_DAYS}D",
            },
        )
    return start_kst, end_kst


def _build_naver_order_preview_field_observation(credential) -> dict:
    return {
        "channel_no_configured": _naver_channel_no_configured(credential.extra_config),
        "preferred_preview_strategy": "last_changed_feed_then_detail_query",
        "feed_called": False,
        "detail_called": False,
        "detail_limit": 0,
        "safe_keyword_flags": api_credential_readiness_service._empty_naver_safe_keyword_flags(),
        "business_error_hint": None,
        "raw_response_saved": False,
        "orders_written": False,
        "safe_to_real_test": False,
    }


def _default_naver_order_local_sync_result(real_sync: bool = False) -> dict:
    return {
        "requested": bool(real_sync),
        "status": "not_requested" if not real_sync else "blocked",
        "created_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "already_exists": False,
        "no_duplicate_created": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "write_limit": 1,
        "skip_reason": None,
        "sample_ids": [],
    }


def _ensure_naver_order_real_preview_allowed(
    *,
    store_id: int,
    credential_id: int,
    page: int,
    size: int,
    start_kst: datetime,
    end_kst: datetime,
    field_observation: dict,
    real_sync: bool = False,
) -> None:
    settings = get_settings()
    if not settings.real_api_test_enabled or settings.real_api_write_enabled or store_id != 8 or credential_id != 7:
        raise ApiError(
            message="Naver order real micro preview is guardrail blocked",
            error_code="guardrail_blocked",
            status_code=400,
            detail={
                "store_id": store_id,
                "credential_id": credential_id,
                "real_api_test_enabled": bool(settings.real_api_test_enabled),
                "real_api_write_enabled": bool(settings.real_api_write_enabled),
            },
        )
    if page != 1 or size != 1:
        raise ApiError(
            message="Naver order real micro preview only allows page=1 and size=1",
            error_code="guardrail_blocked",
            status_code=400,
            detail={"page": page, "size": size},
        )
    if end_kst - start_kst > timedelta(days=NAVER_ORDER_PREVIEW_MAX_DAYS):
        raise ApiError(
            message="Naver order micro preview window must be 7 KST days or less",
            error_code="date_range_invalid",
            status_code=400,
        )
    if real_sync and end_kst - start_kst > timedelta(days=NAVER_ORDER_SINGLE_WRITE_MAX_DAYS):
        raise ApiError(
            message="Naver order single local write window must be 24 hours or less",
            error_code="date_range_invalid",
            status_code=400,
            detail={"max_window": f"P{NAVER_ORDER_SINGLE_WRITE_MAX_DAYS}D"},
        )
    if not field_observation.get("channel_no_configured"):
        raise ApiError(
            message="Naver order micro preview requires configured channel_no",
            error_code="channel_no_missing",
            status_code=400,
        )


def _build_naver_token_context_from_credential(credential) -> dict:
    secret_key = decrypt_value(credential.encrypted_secret_key)
    extra_config = credential.extra_config if isinstance(credential.extra_config, dict) else {}
    api_base = extra_config.get("api_base") or api_credential_readiness_service.NAVER_DEFAULT_API_BASE
    grant_type = extra_config.get("grant_type")
    grant_type_used = grant_type.strip().upper() if isinstance(grant_type, str) and grant_type.strip().upper() in {"SELF", "SELLER"} else "SELF"
    seller_account_id = extra_config.get("seller_account_id")
    return {
        "store_id": credential.store_id,
        "credential_id": credential.id,
        "client_id": credential.client_id,
        "secret_key": secret_key,
        "api_base": str(api_base).rstrip("/"),
        "grant_type_used": grant_type_used,
        "seller_account_id": seller_account_id if isinstance(seller_account_id, str) and seller_account_id.strip() else None,
    }


def _run_naver_order_real_micro_preview(
    *,
    db: Session,
    credential,
    store_id: int,
    start_kst: datetime,
    end_kst: datetime,
    order_status: str,
    page: int,
    size: int,
    include_detail: bool,
    complete_field_preview: bool,
    field_observation: dict,
    real_sync: bool = False,
) -> dict:
    context = _build_naver_token_context_from_credential(credential)
    local_sync_result = _default_naver_order_local_sync_result(real_sync)
    try:
        access_token, token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        field_observation["token_http_status"] = token_status
        headers = {"Authorization": f"Bearer {access_token}"}
        field_observation["feed_called"] = True
        feed_result = _request_naver_order_last_changed_feed(
            api_base=context["api_base"],
            headers=headers,
            start_kst=start_kst,
            end_kst=end_kst,
            size=size,
            attempt="fixed_attempt_b",
            include_last_changed_to=False,
            datetime_format_shape="offset_milliseconds",
        )
        field_observation["feed_attempts"] = [feed_result["diagnostics"]]
        field_observation["feed_http_status"] = feed_result.get("http_status")
        field_observation["detail_called"] = False
        field_observation["detail_limit"] = 0
        if not feed_result["success"]:
            status_code = feed_result.get("http_status")
            error_code = feed_result.get("error_code") or "readonly_request_failed"
            return _build_naver_order_preview_result(
                store_id=store_id,
                credential_id=credential.id,
                start_datetime=start_kst.isoformat(),
                end_datetime=end_kst.isoformat(),
                page=page,
                size=size,
                order_status=order_status,
                guardrail_status="allowed",
                preview_status="failed",
                test_status="preview_failed",
                error_code=error_code,
                field_observation={**field_observation, "http_status": status_code},
                sample_ids=[],
                has_more=False,
                would_create=0,
                would_update=0,
                local_sync_result=local_sync_result,
            )
        feed_payload = feed_result["payload"]
        product_order_ids = _extract_naver_product_order_ids(feed_payload)
        sample_ids = [_mask_external_identifier(item) for item in product_order_ids[:1]]
        if not product_order_ids:
            if real_sync:
                local_sync_result["status"] = "skipped"
                local_sync_result["skipped_count"] = 1
                local_sync_result["skip_reason"] = "no_changed_orders"
            field_observation["detail_skipped_reason"] = "no_changed_orders" if include_detail else "detail_not_requested"
            return _build_naver_order_preview_result(
                store_id=store_id,
                credential_id=credential.id,
                start_datetime=start_kst.isoformat(),
                end_datetime=end_kst.isoformat(),
                page=page,
                size=size,
                order_status=order_status,
                guardrail_status="allowed",
                preview_status="success_empty",
                test_status="preview_success",
                error_code=None,
                field_observation=field_observation,
                sample_ids=[],
                has_more=_naver_order_feed_has_more(feed_payload),
                would_create=0,
                would_update=0,
                local_sync_result=local_sync_result,
            )
        if include_detail:
            field_observation["detail_called"] = True
            field_observation["detail_limit"] = 1
            detail_result = _request_naver_order_detail_query(
                api_base=context["api_base"],
                headers=headers,
                product_order_id=product_order_ids[0],
            )
            field_observation["detail_http_status"] = detail_result["http_status"]
            if not detail_result["success"]:
                error_code = detail_result.get("error_code") or "readonly_request_failed"
                if real_sync:
                    local_sync_result["status"] = "blocked"
                    local_sync_result["skip_reason"] = "detail_request_failed"
                field_observation["detail_error"] = detail_result["diagnostics"]
                return _build_naver_order_preview_result(
                    store_id=store_id,
                    credential_id=credential.id,
                    start_datetime=start_kst.isoformat(),
                    end_datetime=end_kst.isoformat(),
                    page=page,
                    size=size,
                    order_status=order_status,
                    guardrail_status="allowed",
                    preview_status="failed",
                    test_status="preview_failed",
                    error_code=error_code,
                    field_observation={**field_observation, "http_status": detail_result.get("http_status")},
                    sample_ids=sample_ids,
                    has_more=_naver_order_feed_has_more(feed_payload),
                    would_create=0,
                    would_update=0,
                    local_sync_result=local_sync_result,
                )
            detail_preview = _build_naver_order_detail_preview(detail_result["payload"], store_id=store_id)
            field_observation["detail_fields_observed"] = _summarize_naver_order_detail_fields(detail_result["payload"])
            field_observation["detail_preview"] = detail_preview
            field_observation["complete_field_preview"] = _build_naver_order_complete_field_preview(
                detail_result["payload"],
                store_id=store_id,
                requested=complete_field_preview,
            )
            local_sync_result = _sync_naver_order_detail_preview(
                db,
                detail_preview=detail_preview,
                real_sync=real_sync,
            )
            field_observation["privacy_gate"] = local_sync_result.get("privacy_gate")
            field_observation["orders_written"] = bool(local_sync_result.get("orders_written"))
            field_observation["local_sync_status"] = local_sync_result.get("status")
        else:
            field_observation["detail_skipped_reason"] = "detail_not_requested"
        return _build_naver_order_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            start_datetime=start_kst.isoformat(),
            end_datetime=end_kst.isoformat(),
            page=page,
            size=size,
            order_status=order_status,
            guardrail_status="allowed",
            preview_status="success",
            test_status="preview_success",
            error_code=None,
            field_observation=field_observation,
            sample_ids=sample_ids,
            has_more=_naver_order_feed_has_more(feed_payload),
            would_create=int(local_sync_result.get("created_count") or 0),
            would_update=0,
            local_sync_result=local_sync_result,
        )
    except ApiError:
        raise
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error_code = _naver_readonly_error_code(exc.response, scope="order")
        return _build_naver_order_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            start_datetime=start_kst.isoformat(),
            end_datetime=end_kst.isoformat(),
            page=page,
            size=size,
            order_status=order_status,
            guardrail_status="allowed",
            preview_status="failed",
            test_status="preview_failed",
            error_code=error_code,
            field_observation={
                **field_observation,
                "http_status": status_code,
                "safe_keyword_flags": api_credential_readiness_service._naver_safe_keyword_flags_from_text(exc.response.text),
                "business_error_hint": api_credential_readiness_service._naver_business_error_hint(error_code),
            },
            sample_ids=[],
            has_more=False,
            would_create=0,
            would_update=0,
            local_sync_result=local_sync_result,
        )
    except api_credential_readiness_service.NaverReadonlyAuthError as exc:
        return _build_naver_order_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            start_datetime=start_kst.isoformat(),
            end_datetime=end_kst.isoformat(),
            page=page,
            size=size,
            order_status=order_status,
            guardrail_status="allowed",
            preview_status="failed",
            test_status="preview_failed",
            error_code=exc.error_code,
            field_observation={
                **field_observation,
                "http_status": exc.http_status,
                "safe_keyword_flags": exc.safe_keyword_flags,
                "business_error_hint": exc.business_error_hint,
            },
            sample_ids=[],
            has_more=False,
            would_create=0,
            would_update=0,
            local_sync_result=local_sync_result,
        )
    except Exception as exc:
        http_status = getattr(exc, "http_status", None)
        error_code = "auth_failed" if str(exc) == "token_auth_failed" else "readonly_request_failed"
        return _build_naver_order_preview_result(
            store_id=store_id,
            credential_id=credential.id,
            start_datetime=start_kst.isoformat(),
            end_datetime=end_kst.isoformat(),
            page=page,
            size=size,
            order_status=order_status,
            guardrail_status="allowed",
            preview_status="failed",
            test_status="preview_failed",
            error_code=error_code,
            field_observation={**field_observation, "http_status": http_status},
            sample_ids=[],
            has_more=False,
            would_create=0,
            would_update=0,
            local_sync_result=local_sync_result,
        )


def _request_naver_order_last_changed_feed(
    *,
    api_base: str,
    headers: dict[str, str],
    start_kst: datetime,
    end_kst: datetime,
    size: int,
    attempt: str,
    include_last_changed_to: bool,
    datetime_format_shape: str,
) -> dict:
    params: dict[str, str | int] = {
        "lastChangedFrom": _format_naver_order_feed_datetime(start_kst, datetime_format_shape),
        "limitCount": int(size),
    }
    if include_last_changed_to:
        params["lastChangedTo"] = _format_naver_order_feed_datetime(end_kst, datetime_format_shape)
    diagnostics = _build_naver_order_feed_request_diagnostics(
        params=params,
        attempt=attempt,
        datetime_format_shape=datetime_format_shape,
    )
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            f"{api_base}/v1/pay-order/seller/product-orders/last-changed-statuses",
            headers=headers,
            params=params,
        )
    diagnostics["http_status"] = response.status_code
    if response.status_code >= 400:
        diagnostics.update(_extract_naver_error_diagnostics(response))
        return {
            "attempt": attempt,
            "success": False,
            "http_status": response.status_code,
            "error_code": _naver_readonly_error_code(response),
            "diagnostics": diagnostics,
        }
    return {
        "attempt": attempt,
        "success": True,
        "http_status": response.status_code,
        "payload": response.json(),
        "diagnostics": diagnostics,
    }


def _format_naver_order_feed_datetime(value: datetime, datetime_format_shape: str) -> str:
    if datetime_format_shape == "offset_milliseconds":
        return value.isoformat(timespec="milliseconds")
    return value.isoformat(timespec="seconds")


def _build_naver_order_feed_request_diagnostics(
    *,
    params: dict[str, str | int],
    attempt: str,
    datetime_format_shape: str,
) -> dict:
    encoded_query = urlencode(params)
    return {
        "attempt": attempt,
        "feed_request_param_keys": list(params.keys()),
        "datetime_format_shape": datetime_format_shape,
        "last_changed_from_present": "lastChangedFrom" in params,
        "last_changed_to_present": "lastChangedTo" in params,
        "limit_count_present": "limitCount" in params,
        "query_encoded_plus_safely": "%2B" in encoded_query and "+09" not in encoded_query,
    }


def _extract_naver_error_diagnostics(response: httpx.Response) -> dict:
    diagnostics: dict[str, object] = {}
    payload: object | None = None
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        error_code = _find_first_string_value(
            payload,
            {"code", "errorCode", "error_code", "error", "returnCode"},
        )
        error_message = _find_first_string_value(
            payload,
            {"message", "errorMessage", "error_message", "detail", "returnMessage"},
        )
        error_fields = _find_error_field_names(payload)
        if error_code:
            diagnostics["naver_error_code"] = _sanitize_naver_error_text(error_code, max_length=80)
        if error_message:
            diagnostics["naver_error_message_masked"] = _sanitize_naver_error_text(error_message, max_length=120)
        if error_fields:
            diagnostics["naver_error_fields"] = error_fields[:10]
    elif response.text:
        diagnostics["naver_error_message_masked"] = _sanitize_naver_error_text(response.text, max_length=120)
    return diagnostics


def _find_first_string_value(payload: object, keys: set[str]) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, (str, int)):
                return str(value)
        for value in payload.values():
            found = _find_first_string_value(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_string_value(item, keys)
            if found:
                return found
    return None


def _find_error_field_names(payload: object) -> list[str]:
    field_names: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key)
            if normalized_key in {"field", "fieldName", "parameter", "param", "name"} and isinstance(value, str):
                field_names.append(value)
            elif normalized_key in {"errors", "fieldErrors", "invalidParams"}:
                field_names.extend(_find_error_field_names(value))
            elif isinstance(value, (dict, list)):
                field_names.extend(_find_error_field_names(value))
    elif isinstance(payload, list):
        for item in payload:
            field_names.extend(_find_error_field_names(item))
    unique: list[str] = []
    for value in field_names:
        sanitized = re.sub(r"[^A-Za-z0-9_.-]", "", value)[:80]
        if sanitized and sanitized not in unique:
            unique.append(sanitized)
    return unique


def _sanitize_naver_error_text(value: str, *, max_length: int) -> str:
    text = _mask_sensitive_text(value)
    text = re.sub(r"\b\d{2,4}-\d{3,4}-\d{4}\b", "[masked-phone]", text)
    text = re.sub(r"\b\d{10,}\b", "[masked-id]", text)
    text = re.sub(r"(?i)(productOrderId|orderId|channelNo)=?['\"]?[A-Za-z0-9_-]+", r"\1=[masked]", text)
    text = re.sub(r"https?://\S+", "[masked-url]", text)
    return text[:max_length]


def _request_naver_order_detail_query(
    *,
    api_base: str,
    headers: dict[str, str],
    product_order_id: str,
) -> dict:
    diagnostics = {
        "detail_limit": 1,
        "body_field_keys": ["productOrderIds"],
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base}/v1/pay-order/seller/product-orders/query",
            headers=headers,
            json={"productOrderIds": [product_order_id]},
        )
    diagnostics["http_status"] = response.status_code
    if response.status_code >= 400:
        diagnostics.update(_extract_naver_error_diagnostics(response))
        return {
            "success": False,
            "http_status": response.status_code,
            "error_code": _naver_readonly_error_code(response),
            "diagnostics": diagnostics,
        }
    return {
        "success": True,
        "http_status": response.status_code,
        "payload": response.json(),
        "diagnostics": diagnostics,
    }


def _extract_naver_product_order_ids(payload: object) -> list[str]:
    ids: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"productOrderId", "productOrderNo"} and value:
                ids.append(str(value))
            else:
                ids.extend(_extract_naver_product_order_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            ids.extend(_extract_naver_product_order_ids(item))
    seen: set[str] = set()
    unique: list[str] = []
    for value in ids:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _naver_order_feed_has_more(payload: object) -> bool:
    if isinstance(payload, dict):
        for key in ("hasMore", "hasNext", "more"):
            if isinstance(payload.get(key), bool):
                return payload[key]
    return False


def _mask_external_identifier(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"id-hash-{digest}"


def _summarize_naver_order_detail_fields(payload: object) -> dict:
    field_names = _collect_json_field_names(payload)
    lower_names = [name.lower() for name in field_names]
    safe_field_names = [
        name
        for name in field_names
        if not any(token in name.lower() for token in (
            "buyer",
            "receiver",
            "recipient",
            "address",
            "phone",
            "tel",
            "delivery",
            "payment",
            "orderer",
            "zip",
            "postal",
            "memo",
            "channel",
            "productorderid",
            "orderid",
            "originalproductid",
        ))
    ][:30]
    return {
        "detail_record_observed": _json_payload_has_record(payload),
        "observed_field_names": safe_field_names,
        "order_status_observed": any("orderstatus" in name or name == "status" for name in lower_names),
        "payment_status_observed": any("paymentstatus" in name or "paystatus" in name for name in lower_names),
        "delivery_status_observed": any("deliverystatus" in name or "deliverycompany" in name for name in lower_names),
        "product_name_observed": any("productname" in name or "itemname" in name for name in lower_names),
        "buyer_info_present": any("buyer" in name for name in lower_names),
        "receiver_info_present": any("receiver" in name or "recipient" in name for name in lower_names),
        "address_info_present": any("address" in name or "zip" in name or "postal" in name for name in lower_names),
        "privacy_fields_suppressed": True,
        "raw_response_saved": False,
        "orders_written": False,
    }


NAVER_ORDER_STATUS_LABELS_ZH = {
    "PAYED": "已付款 / 新订单",
    "결제완료": "已付款 / 新订单",
    "PLACE_PRODUCT_ORDER": "已确认订单",
    "발주확인": "已确认订单",
    "READY": "待发货",
    "DELIVERY_READY": "待发货",
    "DISPATCHED": "已发货 / 配送中",
    "DELIVERING": "已发货 / 配送中",
    "SHIPPING": "已发货 / 配送中",
    "IN_DELIVERY": "已发货 / 配送中",
    "배송중": "已发货 / 配送中",
    "DELIVERED": "配送完成",
    "DELIVERY_COMPLETION": "配送完成",
    "DELIVERY_COMPLETED": "配送完成",
    "DELIVERY_COMPLETE": "配送完成",
    "COMPLETED_DELIVERY": "配送完成",
    "SHIPPING_COMPLETED": "配送完成",
    "배송완료": "配送完成",
    "CANCELED": "已取消",
    "CANCELLED": "已取消",
    "취소": "已取消",
    "CANCEL_REQUEST": "取消请求",
    "취소요청": "取消请求",
    "RETURN_REQUEST": "退货请求",
    "반품요청": "退货请求",
    "RETURNED": "退货完成",
    "RETURN_DONE": "退货完成",
    "EXCHANGE_REQUEST": "换货请求",
    "교환요청": "换货请求",
    "EXCHANGED": "换货完成",
    "EXCHANGE_DONE": "换货完成",
    "COLLECT_REQUEST": "售后取件请求",
    "COLLECTING": "售后取件中",
    "COLLECT_DONE": "售后取件完成",
    "PURCHASE_DECIDED": "已确认购买",
    "구매확정": "已确认购买",
}


def _status_label_zh(value: str | None) -> tuple[str | None, bool]:
    if not value:
        return None, False
    text = str(value).strip()
    label = NAVER_ORDER_STATUS_LABELS_ZH.get(text) or NAVER_ORDER_STATUS_LABELS_ZH.get(text.upper())
    if label:
        return label, False
    return "未识别状态，需人工确认", True


def _mask_person_name(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= 1:
        return "*"
    return text[0] + "*" * min(len(text) - 1, 4)


def _safe_order_text(value: str | None, max_length: int = 120) -> str | None:
    if not value:
        return None
    text = _sanitize_naver_error_text(str(value), max_length=max_length)
    return text or None


def _datetime_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _order_status_summary(raw_value: str | None) -> dict:
    label, unknown = _status_label_zh(raw_value)
    return {
        "raw": _safe_order_text(raw_value, max_length=40),
        "label_zh": label,
        "unknown_status_observed": unknown,
    }


def _delivery_status_summary(raw_value: str | None, order_value: str | None = None) -> dict:
    delivery_summary = _order_status_summary(raw_value)
    order_summary = _order_status_summary(order_value)
    if delivery_summary.get("label_zh") in {None, "未识别状态，需人工确认"}:
        if order_summary.get("label_zh") in {"待发货", "已确认订单", "已发货 / 配送中", "配送完成"}:
            return {
                "raw": delivery_summary.get("raw") or order_summary.get("raw"),
                "label_zh": order_summary.get("label_zh"),
                "unknown_status_observed": False,
                "derived_from_order_status": True,
            }
    return {
        **delivery_summary,
        "derived_from_order_status": False,
    }


def _payload_has_key_token(payload: object, tokens: tuple[str, ...]) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if any(token in normalized for token in tokens):
                return True
            if _payload_has_key_token(value, tokens):
                return True
    elif isinstance(payload, list):
        return any(_payload_has_key_token(item, tokens) for item in payload)
    return False


def _build_naver_order_detail_preview(payload: object, *, store_id: int | None = None) -> dict:
    product_order_id = _extract_scalar_by_keys(payload, ("productOrderId", "productOrderNo"))
    order_id = _extract_scalar_by_keys(payload, ("orderId", "orderNo", "orderNumber"))
    order_status = _extract_scalar_by_keys(payload, ("orderStatus", "productOrderStatus", "status"))
    payment_status = _extract_scalar_by_keys(payload, ("paymentStatus", "payStatus", "paymentState"))
    delivery_status = _extract_scalar_by_keys(payload, ("deliveryStatus", "shippingStatus", "deliveryState"))
    claim_status = _extract_scalar_by_keys(payload, ("claimStatus", "claimType", "claimRequestStatus", "claimStatusType"))
    product_name = _extract_scalar_by_keys(payload, ("productName", "productOrderName", "itemName"))
    option_name = _extract_scalar_by_keys(payload, ("optionName", "productOption", "optionInfo"))
    amount = _extract_decimal_by_keys(payload, (
        "totalPaymentAmount",
        "paymentAmount",
        "totalOrderAmount",
        "orderAmount",
        "productOrderAmount",
        "salePrice",
    ))
    buyer_name = _extract_scalar_by_keys(payload, ("buyerName", "ordererName"))
    buyer_phone = _extract_scalar_by_keys(payload, ("buyerTelNo", "buyerTelNo1", "buyerPhone", "ordererTelNo", "ordererPhone"))
    buyer_id = _extract_scalar_by_keys(payload, ("buyerId", "buyerMemberId", "ordererId", "ordererNo"))
    receiver_name = _extract_scalar_by_keys(payload, ("receiverName", "recipientName"))
    receiver_phone = _extract_scalar_by_keys(payload, ("receiverTelNo", "receiverTelNo1", "receiverPhone", "recipientPhone"))
    order_summary = _order_status_summary(order_status)
    delivery_summary = _delivery_status_summary(delivery_status, order_status)
    claim_summary = _order_status_summary(claim_status)
    product_order_id_hash = _mask_external_identifier(product_order_id) if product_order_id else None
    order_id_hash = _mask_external_identifier(order_id) if order_id else None
    safe_status_samples = [
        item["raw"]
        for item in (order_summary, delivery_summary, claim_summary)
        if item.get("raw")
    ]
    return {
        "store_id": store_id,
        "platform": "naver",
        "external_order_id_hash": order_id_hash,
        "external_product_order_id_hash": product_order_id_hash,
        "product_order_id_hash": product_order_id_hash,
        "order_id_hash": order_id_hash,
        "order_status": order_summary,
        "order_status_label_zh": order_summary.get("label_zh"),
        "payment_status": _safe_order_text(payment_status, max_length=40),
        "product_name": _safe_order_text(product_name, max_length=160),
        "option_name": _safe_order_text(option_name, max_length=160),
        "quantity": _extract_int_by_keys(payload, ("quantity", "orderQuantity", "productOrderQuantity", "count")),
        "order_amount": _decimal_to_plain_string(amount) if amount is not None else None,
        "currency": "KRW",
        "ordered_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("orderedAt", "orderDate", "orderedDate"))),
        "paid_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("paidAt", "paymentDate", "payDate"))),
        "last_changed_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("lastChangedAt", "lastChangedDate", "lastChangeDate"))),
        "delivery_status": delivery_summary,
        "delivery_status_label_zh": delivery_summary.get("label_zh"),
        "claim_status": claim_summary,
        "claim_status_label_zh": claim_summary.get("label_zh"),
        "buyer_name_masked": _mask_person_name(buyer_name),
        "buyer_phone_masked": _mask_phone(buyer_phone),
        "buyer_id_hash": _mask_external_identifier(buyer_id) if buyer_id else None,
        "receiver_name_masked": _mask_person_name(receiver_name),
        "receiver_phone_masked": _mask_phone(receiver_phone),
        "address_observed": _payload_has_key_token(payload, ("address", "zipcode", "zip_code", "postalcode", "postal_code")),
        "address_saved": False,
        "source_type": NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        "last_synced_at": get_utc_now().isoformat(),
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "orders_written": False,
        "mapping_version": "naver_order_detail_preview_v1",
        "unknown_status_observed": any(item.get("unknown_status_observed") for item in (order_summary, delivery_summary, claim_summary)),
        "safe_status_samples": sorted(dict.fromkeys(safe_status_samples)),
    }


def _complete_order_field_value(payload: object, keys: tuple[str, ...], max_length: int = 160) -> str | None:
    value = _extract_scalar_by_keys(payload, keys)
    return _bounded_text(value, max_length)


def _default_naver_order_complete_field_preview(requested: bool = False) -> dict:
    return {
        "requested": bool(requested),
        "preview_only": True,
        "available": False,
        "complete_fields": {},
        "field_availability": {},
        "save_plan": {
            "phase": "Naver-ERP-5D",
            "codex1_schema_write_enabled": False,
            "requires_user_approval": True,
            "requires_db_backup": True,
            "store_id_limit": 8,
            "one_order_limit": True,
            "formal_order_sync_open": False,
            "platform_writes_enabled": False,
            "orders_written": False,
            "sync_log_written": False,
            "tested_success_written": False,
            "raw_response_saved": False,
        },
        "blocked_destinations": [
            "Dashboard summary cards",
            "SyncLog",
            "ApiCapabilityTestResult",
            "error messages",
            "technical logs",
            "upstream payload storage",
        ],
    }


def _build_naver_order_complete_field_preview(
    payload: object,
    *,
    store_id: int | None = None,
    requested: bool = False,
) -> dict:
    preview = _default_naver_order_complete_field_preview(requested)
    if not requested:
        return preview

    order_amount = _extract_decimal_by_keys(payload, (
        "totalPaymentAmount",
        "paymentAmount",
        "totalOrderAmount",
        "orderAmount",
        "productOrderAmount",
        "salePrice",
    ))
    order_status = _extract_scalar_by_keys(payload, ("orderStatus", "productOrderStatus", "status"))
    delivery_status = _extract_scalar_by_keys(payload, ("deliveryStatus", "shippingStatus", "deliveryState"))
    delivery_summary = _delivery_status_summary(delivery_status, order_status)
    complete_fields = {
        "store_id": store_id,
        "platform": "naver",
        "external_order_id": _complete_order_field_value(payload, ("orderId", "orderNo", "orderNumber"), 120),
        "external_product_order_id": _complete_order_field_value(payload, ("productOrderId", "productOrderNo"), 120),
        "platform_product_id": _complete_order_field_value(payload, (
            "productId",
            "productNo",
            "productNumber",
            "originProductNo",
            "channelProductNo",
            "sellerProductCode",
        ), 120),
        "product_name": _complete_order_field_value(payload, ("productName", "productOrderName", "itemName"), 160),
        "option_name": _complete_order_field_value(payload, ("optionName", "productOption", "optionInfo"), 160),
        "quantity": _extract_int_by_keys(payload, ("quantity", "orderQuantity", "productOrderQuantity", "count")),
        "order_amount": _decimal_to_plain_string(order_amount) if order_amount is not None else None,
        "currency": "KRW",
        "order_status": _bounded_text(order_status, 40),
        "order_status_label_zh": _status_label_zh(order_status)[0],
        "payment_status": _complete_order_field_value(payload, ("paymentStatus", "payStatus", "paymentState"), 40),
        "delivery_status": _bounded_text(delivery_status, 40),
        "delivery_status_label_zh": delivery_summary.get("label_zh"),
        "delivery_status_derived_from_order_status": delivery_summary.get("derived_from_order_status"),
        "claim_status": _complete_order_field_value(payload, ("claimStatus", "claimType", "claimRequestStatus", "claimStatusType"), 40),
        "claim_status_label_zh": _status_label_zh(_extract_scalar_by_keys(payload, ("claimStatus", "claimType", "claimRequestStatus", "claimStatusType")))[0],
        "buyer_name": _complete_order_field_value(payload, ("buyerName", "ordererName"), 120),
        "buyer_phone": _complete_order_field_value(payload, ("buyerTelNo", "buyerTelNo1", "buyerPhone", "ordererTelNo", "ordererPhone"), 40),
        "receiver_name": _complete_order_field_value(payload, ("receiverName", "recipientName"), 120),
        "receiver_phone": _complete_order_field_value(payload, ("receiverTelNo", "receiverTelNo1", "receiverPhone", "recipientPhone"), 40),
        "receiver_address": _complete_order_field_value(payload, (
            "receiverAddress",
            "recipientAddress",
            "shippingAddress",
            "baseAddress",
            "roadNameAddress",
            "detailedAddress",
        ), 240),
        "zip_code": _complete_order_field_value(payload, ("zipCode", "zipcode", "postalCode", "postal_code"), 20),
        "ordered_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("orderedAt", "orderDate", "orderedDate"))),
        "paid_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("paidAt", "paymentDate", "payDate"))),
        "last_changed_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("lastChangedAt", "lastChangedDate", "lastChangeDate"))),
        "raw_response_saved": False,
        "mapping_version": "naver_order_complete_field_preview_v1",
    }
    complete_fields = {key: value for key, value in complete_fields.items() if value is not None}
    preview.update({
        "available": bool(complete_fields.get("external_order_id") or complete_fields.get("external_product_order_id")),
        "complete_fields": complete_fields,
        "field_availability": {
            key: key in complete_fields and complete_fields.get(key) not in {None, ""}
            for key in (
                "external_order_id",
                "external_product_order_id",
                "platform_product_id",
                "buyer_name",
                "buyer_phone",
                "receiver_name",
                "receiver_phone",
                "receiver_address",
                "zip_code",
            )
        },
    })
    return preview


def _parse_preview_iso_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_hash_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"id-hash-[0-9a-f]{10}", value))


def _is_masked_name(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or "*" in text


def _is_masked_phone(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or bool(re.fullmatch(r"\*{4}\d{0,4}", text))


def _validate_naver_order_detail_preview_for_local_write(detail_preview: dict | None) -> dict:
    reasons: list[str] = []
    if not isinstance(detail_preview, dict):
        return {"passed": False, "reasons": ["missing_detail_preview"]}
    if detail_preview.get("store_id") != 8:
        reasons.append("invalid_store_id")
    if detail_preview.get("platform") != "naver":
        reasons.append("invalid_platform")
    if not _is_hash_identifier(detail_preview.get("external_product_order_id_hash")):
        reasons.append("missing_external_product_order_id_hash")
    if not _is_hash_identifier(detail_preview.get("external_order_id_hash")):
        reasons.append("missing_external_order_id_hash")
    if detail_preview.get("raw_response_saved") is not False:
        reasons.append("raw_response_not_suppressed")
    if detail_preview.get("privacy_fields_redacted") is not True:
        reasons.append("privacy_fields_not_redacted")
    if detail_preview.get("address_saved") is not False:
        reasons.append("address_saved_not_allowed")
    if not _is_masked_name(detail_preview.get("buyer_name_masked")):
        reasons.append("buyer_name_not_masked")
    if not _is_masked_name(detail_preview.get("receiver_name_masked")):
        reasons.append("receiver_name_not_masked")
    if not _is_masked_phone(detail_preview.get("buyer_phone_masked")):
        reasons.append("buyer_phone_not_masked")
    if not _is_masked_phone(detail_preview.get("receiver_phone_masked")):
        reasons.append("receiver_phone_not_masked")
    if detail_preview.get("buyer_id_hash") is not None and not _is_hash_identifier(detail_preview.get("buyer_id_hash")):
        reasons.append("buyer_id_not_hashed")

    serialized = json.dumps(detail_preview, ensure_ascii=False, default=str).lower()
    for forbidden in ("authorization", "client_secret", "signature", "bcrypt", "raw response"):
        if forbidden in serialized:
            reasons.append(f"forbidden_text_{forbidden.replace(' ', '_')}")
    return {"passed": not reasons, "reasons": sorted(dict.fromkeys(reasons))}


def _naver_order_sanitized_raw_data(detail_preview: dict) -> dict:
    allowed_keys = (
        "external_order_id_hash",
        "external_product_order_id_hash",
        "order_status",
        "order_status_label_zh",
        "payment_status",
        "option_name",
        "delivery_status",
        "delivery_status_label_zh",
        "claim_status",
        "claim_status_label_zh",
        "buyer_id_hash",
        "receiver_name_masked",
        "receiver_phone_masked",
        "address_observed",
        "address_saved",
        "source_type",
        "last_synced_at",
        "mapping_version",
        "unknown_status_observed",
        "safe_status_samples",
        "raw_response_saved",
        "privacy_fields_redacted",
    )
    raw_data = {key: detail_preview.get(key) for key in allowed_keys if key in detail_preview}
    raw_data.update({
        "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
        "synced_from": NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        "orders_written": True,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
    })
    return raw_data


def _sync_naver_order_detail_preview(
    db: Session,
    *,
    detail_preview: dict | None,
    real_sync: bool,
) -> dict:
    result = _default_naver_order_local_sync_result(real_sync)
    if not real_sync:
        return result

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(detail_preview)
    result["privacy_gate"] = privacy_gate
    if not privacy_gate["passed"]:
        result["status"] = "blocked"
        result["skip_reason"] = "privacy_gate_failed"
        return result

    assert detail_preview is not None
    external_order_id = str(detail_preview["external_product_order_id_hash"])
    existing = db.scalar(
        select(Order).where(
            Order.store_id == 8,
            Order.platform == "naver",
            Order.external_order_id == external_order_id,
        )
    )
    if existing is not None:
        result["status"] = "already_exists"
        result["already_exists"] = True
        result["no_duplicate_created"] = True
        result["skip_reason"] = "duplicate_external_product_order_id_hash"
        result["sample_ids"] = [external_order_id]
        return result

    synced_at = _parse_preview_iso_datetime(detail_preview.get("last_synced_at")) or get_utc_now()
    ordered_at = _parse_preview_iso_datetime(detail_preview.get("ordered_at")) or synced_at
    paid_at = _parse_preview_iso_datetime(detail_preview.get("paid_at"))
    amount = _to_decimal(detail_preview.get("order_amount")) or Decimal("0")
    order_status = (detail_preview.get("order_status") or {}).get("raw") if isinstance(detail_preview.get("order_status"), dict) else None
    order = Order(
        store_id=8,
        platform="naver",
        external_order_id=external_order_id,
        buyer_name=_bounded_text(detail_preview.get("buyer_name_masked"), 120),
        buyer_masked_phone=_bounded_text(detail_preview.get("buyer_phone_masked"), 30),
        product_name=_bounded_text(detail_preview.get("product_name"), 300) or f"Naver order {external_order_id}",
        quantity=_extract_int_by_keys(detail_preview, ("quantity",)) or 1,
        order_amount=amount,
        currency="KRW",
        order_status=_bounded_text(order_status or "UNKNOWN", 30) or "UNKNOWN",
        paid_at=paid_at,
        ordered_at=ordered_at,
        source_type=NAVER_ORDER_SYNC_SOURCE_TYPE,
        last_synced_at=synced_at,
        raw_data=_naver_order_sanitized_raw_data(detail_preview),
    )
    db.add(order)
    db.commit()

    result.update({
        "status": "success",
        "created_count": 1,
        "orders_written": True,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "sample_ids": [external_order_id],
    })
    return result


def _evaluate_naver_selected_new_order_write_gate(
    db: Session,
    *,
    selected_candidate_hash: str | None,
    candidate_previews: list[dict] | None,
    write_enabled: bool = False,
    fresh_readonly_preview: bool = True,
) -> dict:
    """Mock-testable 11B gate; not wired to the public preview endpoint."""
    result = {
        "phase": "Naver-ERP-11B",
        "selected_candidate_write": True,
        "write_enabled": bool(write_enabled),
        "fresh_readonly_preview": bool(fresh_readonly_preview),
        "status": "blocked",
        "candidate_count": len(candidate_previews) if isinstance(candidate_previews, list) else 0,
        "matched_candidate_count": 0,
        "created_count": 0,
        "already_exists": False,
        "no_duplicate_created": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
        "skip_reason": None,
        "sample_ids": [],
    }
    if not fresh_readonly_preview:
        result["skip_reason"] = "selected_candidate_stale_preview"
        return result
    if not _is_hash_identifier(selected_candidate_hash):
        result["skip_reason"] = "selected_candidate_missing"
        return result
    safe_candidates = candidate_previews if isinstance(candidate_previews, list) else []
    matched = [
        candidate
        for candidate in safe_candidates
        if isinstance(candidate, dict)
        and candidate.get("external_product_order_id_hash") == selected_candidate_hash
    ]
    result["matched_candidate_count"] = len(matched)
    if not matched:
        result["skip_reason"] = "selected_candidate_missing"
        return result
    if len(matched) > 1:
        result["skip_reason"] = "selected_candidate_not_unique"
        return result

    candidate = matched[0]
    candidate_classification = candidate.get("candidate_classification")
    if candidate_classification not in (None, "candidate_new"):
        result["skip_reason"] = "selected_candidate_changed"
        return result

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(candidate)
    result["privacy_gate"] = privacy_gate
    if not privacy_gate["passed"]:
        result["skip_reason"] = "selected_candidate_privacy_blocked"
        return result

    existing = db.scalar(
        select(Order).where(
            Order.store_id == 8,
            Order.platform == "naver",
            Order.external_order_id == selected_candidate_hash,
        )
    )
    if existing is not None:
        result.update({
            "status": "selected_candidate_duplicate",
            "already_exists": True,
            "no_duplicate_created": True,
            "skip_reason": "selected_candidate_duplicate",
            "sample_ids": [selected_candidate_hash],
        })
        return result

    if not write_enabled:
        result.update({
            "status": "selected_candidate_write_not_requested",
            "would_create": 1,
            "sample_ids": [selected_candidate_hash],
        })
        return result

    sync_result = _sync_naver_order_detail_preview(
        db,
        detail_preview=candidate,
        real_sync=True,
    )
    result.update({
        **sync_result,
        "status": "selected_candidate_write_created" if sync_result.get("status") == "success" else sync_result.get("status"),
        "selected_candidate_write": True,
        "write_enabled": True,
        "fresh_readonly_preview": True,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result


def _extract_naver_order_status_raw(detail_preview: dict) -> str:
    order_status = detail_preview.get("order_status")
    if isinstance(order_status, dict):
        return _bounded_text(order_status.get("raw"), 30) or "UNKNOWN"
    return _bounded_text(order_status, 30) or "UNKNOWN"


def _naver_order_refresh_sanitized_raw_data(detail_preview: dict) -> dict:
    raw_data = _naver_order_sanitized_raw_data(detail_preview)
    raw_data.update({
        "orders_written": False,
        "orders_refreshed": True,
        "refreshed_from": NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
    })
    return raw_data


def _build_naver_order_refresh_payload(detail_preview: dict) -> dict:
    synced_at = _parse_preview_iso_datetime(detail_preview.get("last_synced_at")) or get_utc_now()
    ordered_at = _parse_preview_iso_datetime(detail_preview.get("ordered_at")) or synced_at
    paid_at = _parse_preview_iso_datetime(detail_preview.get("paid_at"))
    external_order_id = str(detail_preview["external_product_order_id_hash"])
    return {
        "external_order_id": external_order_id,
        "buyer_name": _bounded_text(detail_preview.get("buyer_name_masked"), 120),
        "buyer_masked_phone": _bounded_text(detail_preview.get("buyer_phone_masked"), 30),
        "product_name": _bounded_text(detail_preview.get("product_name"), 300) or f"Naver order {external_order_id}",
        "quantity": _extract_int_by_keys(detail_preview, ("quantity",)) or 1,
        "order_amount": _to_decimal(detail_preview.get("order_amount")) or Decimal("0"),
        "currency": "KRW",
        "order_status": _extract_naver_order_status_raw(detail_preview),
        "paid_at": paid_at,
        "ordered_at": ordered_at,
        "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
        "last_synced_at": synced_at,
        "raw_data": _naver_order_refresh_sanitized_raw_data(detail_preview),
    }


def _same_naver_refresh_datetime(current: object, incoming: object) -> bool:
    if current is None or incoming is None:
        return current is incoming
    if not isinstance(current, datetime) or not isinstance(incoming, datetime):
        return current == incoming
    if current.tzinfo is None or incoming.tzinfo is None:
        return current.replace(tzinfo=None) == incoming.replace(tzinfo=None)
    return current.astimezone(timezone.utc) == incoming.astimezone(timezone.utc)


def _changed_naver_order_refresh_fields(order: Order, payload: dict) -> list[str]:
    changed: list[str] = []
    comparable_fields = (
        "buyer_name",
        "buyer_masked_phone",
        "product_name",
        "quantity",
        "order_amount",
        "currency",
        "order_status",
        "paid_at",
        "ordered_at",
    )
    for field in comparable_fields:
        current = getattr(order, field)
        incoming = payload.get(field)
        if field == "order_amount":
            current_value = Decimal(str(current or "0"))
            incoming_value = Decimal(str(incoming or "0"))
            if current_value != incoming_value:
                changed.append(field)
            continue
        if field in {"paid_at", "ordered_at"}:
            if not _same_naver_refresh_datetime(current, incoming):
                changed.append(field)
            continue
        if current != incoming:
            changed.append(field)
    return changed


def _evaluate_naver_order_local_refresh_mock_gate(
    db: Session,
    *,
    selected_order_hash: str | None,
    refresh_preview: dict | None,
    write_enabled: bool = False,
    manual_approval: bool = False,
    fresh_readonly_preview: bool = True,
) -> dict:
    """Mock-testable 13A refresh gate; not wired to the public preview endpoint."""
    result = {
        "phase": "Naver-ERP-13A",
        "local_refresh_mock_gate": True,
        "write_enabled": bool(write_enabled),
        "manual_approval": bool(manual_approval),
        "fresh_readonly_preview": bool(fresh_readonly_preview),
        "status": "blocked",
        "matched_local_count": 0,
        "identity_matched": False,
        "would_update": 0,
        "changed_fields": [],
        "refreshed_count": 0,
        "orders_written": False,
        "orders_created": False,
        "orders_updated": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
        "skip_reason": None,
        "sample_ids": [],
    }
    if not fresh_readonly_preview:
        result["skip_reason"] = "local_refresh_stale_preview"
        return result
    if not _is_hash_identifier(selected_order_hash):
        result["skip_reason"] = "selected_order_missing"
        return result
    if not isinstance(refresh_preview, dict):
        result["skip_reason"] = "refresh_preview_missing"
        return result
    preview_hash = refresh_preview.get("external_product_order_id_hash")
    if preview_hash != selected_order_hash:
        result["skip_reason"] = "refresh_identity_mismatch"
        return result
    result["identity_matched"] = True
    result["sample_ids"] = [selected_order_hash]

    existing_orders = db.scalars(
        select(Order).where(
            Order.store_id == 8,
            Order.platform == "naver",
            Order.external_order_id == selected_order_hash,
        )
    ).all()
    result["matched_local_count"] = len(existing_orders)
    if not existing_orders:
        result["skip_reason"] = "local_order_not_found"
        return result
    if len(existing_orders) > 1:
        result["skip_reason"] = "local_order_not_unique"
        return result

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(refresh_preview)
    result["privacy_gate"] = privacy_gate
    if not privacy_gate["passed"]:
        result["skip_reason"] = "local_refresh_privacy_blocked"
        return result

    existing = existing_orders[0]
    payload = _build_naver_order_refresh_payload(refresh_preview)
    changed_fields = _changed_naver_order_refresh_fields(existing, payload)
    result["changed_fields"] = changed_fields
    result["would_update"] = 1 if changed_fields else 0

    if not changed_fields:
        result["status"] = "local_refresh_no_change"
        return result
    if not write_enabled:
        result["status"] = "local_refresh_not_requested"
        return result
    if not manual_approval:
        result["skip_reason"] = "manual_approval_required"
        return result

    for field, value in payload.items():
        setattr(existing, field, value)
    db.commit()
    result.update({
        "status": "local_refresh_updated",
        "refreshed_count": 1,
        "orders_written": True,
        "orders_updated": True,
        "orders_created": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result


def _naver_order_refresh_batch_forbidden_field_names(payload: object) -> list[str]:
    allowed_names = {
        "addressobserved",
        "addresssaved",
        "buyeridhash",
        "buyerid_hash",
        "buyerphonemasked",
        "buyer_phone_masked",
        "buyernamemasked",
        "buyer_name_masked",
        "externalorderidhash",
        "external_order_id_hash",
        "externalproductorderidhash",
        "external_product_order_id_hash",
        "orderidhash",
        "order_id_hash",
        "privacyfieldsredacted",
        "privacy_fields_redacted",
        "productorderidhash",
        "product_order_id_hash",
        "rawresponsesaved",
        "raw_response_saved",
        "receivernamemasked",
        "receiver_name_masked",
        "receiverphonemasked",
        "receiver_phone_masked",
    }
    forbidden_fragments = {
        "authorization",
        "bcrypt",
        "buyername",
        "buyerphone",
        "clientsecret",
        "client_secret",
        "completefield",
        "complete_field",
        "header",
        "orderid",
        "orderno",
        "phone",
        "postal",
        "productorderid",
        "productorderno",
        "rawdata",
        "raw_data",
        "rawresponse",
        "raw_response",
        "receiveraddress",
        "receivername",
        "receiverphone",
        "secret",
        "signature",
        "token",
        "zip",
        "zip_code",
        "zipcode",
    }
    normalized_names = {
        name.replace("-", "").replace("_", "").replace(" ", "").lower()
        for name in _collect_json_field_names(payload)
    } - allowed_names
    return sorted(
        name
        for name in normalized_names
        if any(fragment in name for fragment in forbidden_fragments)
    )


def _naver_order_refresh_preview_unknown_status(refresh_preview: dict) -> bool:
    status_values = (
        refresh_preview.get("order_status"),
        refresh_preview.get("delivery_status"),
        refresh_preview.get("claim_status"),
    )
    return bool(refresh_preview.get("unknown_status_observed")) or any(
        _naver_order_timeline_status_unknown(value)
        for value in status_values
        if _naver_order_timeline_status_raw(value)
    )


def _default_naver_order_refresh_batch_mock_gate_result(
    *,
    refresh_previews: list[dict] | tuple[dict, ...] | None,
    approved_order_hashes: list[str] | tuple[str, ...] | None,
    write_enabled: bool,
    manual_approval: bool,
    fresh_readonly_preview: bool,
    max_batch_size: int,
) -> dict:
    return {
        "phase": "Naver-ERP-15B",
        "order_refresh_batch_mock_gate": True,
        "write_enabled": bool(write_enabled),
        "manual_approval": bool(manual_approval),
        "fresh_readonly_preview": bool(fresh_readonly_preview),
        "max_batch_size": max_batch_size,
        "candidate_count": len(refresh_previews) if isinstance(refresh_previews, (list, tuple)) else 0,
        "approved_order_hash_count": len(approved_order_hashes) if isinstance(approved_order_hashes, (list, tuple)) else 0,
        "status": "blocked",
        "skip_reason": None,
        "sample_ids": [],
        "backup_evidence_required": False,
        "backup_evidence_verified": False,
        "duplicate_candidate_hashes": [],
        "candidate_results": [],
        "matched_local_count": 0,
        "would_update": 0,
        "no_change_count": 0,
        "changed_fields_by_hash": {},
        "refreshed_count": 0,
        "orders_written": False,
        "orders_created": False,
        "orders_updated": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "partial_writes_allowed": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    }


def _validate_naver_order_refresh_backup_evidence(
    backup_evidence: dict | None,
    *,
    require_backup: bool,
) -> dict:
    result = {
        "phase": "Naver-ERP-18A",
        "order_refresh_backup_evidence_gate": True,
        "require_backup": bool(require_backup),
        "backup_evidence_verified": False,
        "status": "backup_not_required" if not require_backup else "blocked",
        "skip_reason": None,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "secrets_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    }
    if not require_backup:
        return result
    if not isinstance(backup_evidence, dict):
        result["skip_reason"] = "backup_evidence_missing"
        return result
    backup_sha256 = str(backup_evidence.get("backup_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", backup_sha256):
        result["skip_reason"] = "invalid_backup_sha256"
        return result
    if backup_evidence.get("sqlite_integrity_check") != "ok":
        result["skip_reason"] = "backup_integrity_not_verified"
        return result
    required_flags = {
        "backup_created": True,
        "manifest_written": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }
    for key, expected in required_flags.items():
        if backup_evidence.get(key) is not expected:
            result.update({
                "skip_reason": "backup_evidence_safety_flags_failed",
                "failed_flag": key,
            })
            return result
    serialized = json.dumps(backup_evidence, ensure_ascii=False, default=str).lower()
    for forbidden in (
        "authorization",
        "client_secret",
        "signature",
        "bcrypt",
        "raw response",
        "raw_request",
        "rawresponse",
        "buyername",
        "buyerphone",
        "receivername",
        "receiverphone",
        "zipcode",
        "productorderid",
        "orderid-must-not-leak",
    ):
        if forbidden in serialized:
            result["skip_reason"] = "backup_evidence_sensitive_field_blocked"
            return result
    result.update({
        "status": "backup_evidence_verified",
        "backup_evidence_verified": True,
        "backup_sha256_abbrev": f"{backup_sha256[:12]}...",
        "backup_path_present": bool(backup_evidence.get("backup_path")),
    })
    return result


def _evaluate_naver_order_refresh_batch_with_backup_evidence_gate(
    db: Session,
    *,
    refresh_previews: list[dict] | tuple[dict, ...] | None,
    approved_order_hashes: list[str] | tuple[str, ...] | None = None,
    write_enabled: bool = False,
    manual_approval: bool = False,
    fresh_readonly_preview: bool = True,
    max_batch_size: int = 2,
    backup_evidence: dict | None = None,
    require_backup: bool = True,
) -> dict:
    backup_gate = _validate_naver_order_refresh_backup_evidence(
        backup_evidence,
        require_backup=require_backup and bool(write_enabled),
    )
    if write_enabled and require_backup and backup_gate["status"] != "backup_evidence_verified":
        result = _default_naver_order_refresh_batch_mock_gate_result(
            refresh_previews=refresh_previews,
            approved_order_hashes=approved_order_hashes,
            write_enabled=write_enabled,
            manual_approval=manual_approval,
            fresh_readonly_preview=fresh_readonly_preview,
            max_batch_size=max_batch_size,
        )
        result.update({
            "phase": "Naver-ERP-18A",
            "order_refresh_backup_evidence_gate": True,
            "backup_evidence_required": True,
            "backup_evidence_verified": False,
            "skip_reason": backup_gate["skip_reason"],
            "backup_gate": backup_gate,
            "orders_written": False,
            "formal_order_sync_open": False,
            "platform_writes_enabled": False,
        })
        return result

    result = _evaluate_naver_order_refresh_batch_mock_gate(
        db,
        refresh_previews=refresh_previews,
        approved_order_hashes=approved_order_hashes,
        write_enabled=write_enabled,
        manual_approval=manual_approval,
        fresh_readonly_preview=fresh_readonly_preview,
        max_batch_size=max_batch_size,
    )
    result.update({
        "phase": "Naver-ERP-18A",
        "order_refresh_backup_evidence_gate": True,
        "backup_evidence_required": bool(require_backup and write_enabled),
        "backup_evidence_verified": bool(backup_gate["backup_evidence_verified"]),
        "backup_gate": backup_gate,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result


FORMAL_BATCH_SYNC_GATE_KINDS = {
    "naver_order_refresh_batch": {
        "platform": "naver",
        "target": "orders",
        "required_action": "orders.refresh_batch_write",
        "max_batch_size": 20,
    },
    "naver_order_batch": {
        "platform": "naver",
        "target": "orders",
        "required_action": "orders.batch_sync_write",
        "max_batch_size": 20,
    },
    "naver_product_batch": {
        "platform": "naver",
        "target": "products",
        "required_action": "products.batch_sync_write",
        "max_batch_size": 10,
    },
}


def _formal_batch_sync_sensitive_marker_found(payload: object) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, default=str).lower()
    return any(
        marker in serialized
        for marker in (
            "authorization:",
            "bearer ",
            "client_secret",
            "access_token",
            "refresh_token",
            "headers",
            "signature",
            "bcrypt",
            "raw response",
            "rawresponse",
            "buyername",
            "buyerphone",
            "receivername",
            "receiverphone",
            "detailedaddress",
            "zipcode",
            "channelno",
            "productorderid",
            "external_product_id_full",
        )
    )


def _normalize_formal_batch_store_ids(store_ids: object) -> list[int] | None:
    if not isinstance(store_ids, (list, tuple, set)) or not store_ids:
        return None
    normalized: list[int] = []
    for store_id in store_ids:
        try:
            safe_store_id = int(store_id)
        except (TypeError, ValueError):
            return None
        if safe_store_id <= 0:
            return None
        normalized.append(safe_store_id)
    return sorted(set(normalized))


def _validate_formal_batch_readonly_evidence(readonly_evidence: dict | None) -> dict:
    result = {
        "readonly_evidence_verified": False,
        "skip_reason": None,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "real_sync": False,
        "formal_sync_open": False,
    }
    if not isinstance(readonly_evidence, dict):
        result["skip_reason"] = "readonly_evidence_missing"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_evidence):
        result["skip_reason"] = "readonly_evidence_sensitive_field_blocked"
        return result
    if readonly_evidence.get("fresh_readonly_preview") is not True:
        result["skip_reason"] = "fresh_readonly_preview_required"
        return result
    if readonly_evidence.get("real_sync") is True:
        result["skip_reason"] = "real_sync_not_allowed_in_gate"
        return result
    if readonly_evidence.get("raw_response_saved") is not False:
        result["skip_reason"] = "raw_response_saved_not_allowed"
        return result
    if readonly_evidence.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result
    if readonly_evidence.get("duplicate_check_passed") is not True:
        result["skip_reason"] = "duplicate_check_required"
        return result
    if readonly_evidence.get("field_whitelist_verified") is not True:
        result["skip_reason"] = "field_whitelist_required"
        return result
    if readonly_evidence.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    result.update({
        "readonly_evidence_verified": True,
        "candidate_hash_count": int(readonly_evidence.get("candidate_hash_count") or 0),
        "source_window_label": str(readonly_evidence.get("source_window_label") or "readonly preview").strip()[:120],
    })
    return result


def _evaluate_formal_batch_sync_production_gate(
    *,
    sync_kind: str,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    audit_plan_ready: bool,
    rollback_plan_ready: bool,
    duplicate_protection_ready: bool,
    failure_isolation_ready: bool,
    multi_store_isolation_ready: bool,
    verification_scope: str | None,
    write_requested: bool = False,
) -> dict:
    """Private production gate model for formal batch sync planning; not wired to real sync."""

    from app.services.permission_service import (
        VERIFICATION_SCOPE,
        evaluate_sensitive_action_approval_mock_gate,
    )

    config = FORMAL_BATCH_SYNC_GATE_KINDS.get(str(sync_kind or "").strip())
    normalized_store_ids = _normalize_formal_batch_store_ids(store_ids)
    result = {
        "phase": "ERP-Batch-1B",
        "formal_batch_sync_production_gate": True,
        "sync_kind": sync_kind,
        "platform": config["platform"] if config else None,
        "target": config["target"] if config else None,
        "required_action": config["required_action"] if config else None,
        "status": "blocked",
        "skip_reason": None,
        "write_requested": bool(write_requested),
        "manual_approval": bool(manual_approval),
        "store_ids": normalized_store_ids or [],
        "target_store_count": len(normalized_store_ids or []),
        "candidate_count": candidate_count,
        "batch_size": batch_size,
        "max_batch_size": config["max_batch_size"] if config else None,
        "readonly_evidence_verified": False,
        "backup_evidence_verified": False,
        "permission_verified": False,
        "approval_role_verified": False,
        "all_store_scopes_verified": False,
        "audit_plan_ready": bool(audit_plan_ready),
        "rollback_plan_ready": bool(rollback_plan_ready),
        "duplicate_protection_ready": bool(duplicate_protection_ready),
        "failure_isolation_ready": bool(failure_isolation_ready),
        "multi_store_isolation_ready": bool(multi_store_isolation_ready),
        "approval_gate_by_store": [],
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "real_database_written": False,
        "real_api_called": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
        "public_endpoint_enabled": False,
    }
    if config is None:
        result["skip_reason"] = "sync_kind_not_allowed"
        return result
    if verification_scope != VERIFICATION_SCOPE:
        result["skip_reason"] = "verification_scope_required"
        return result
    if normalized_store_ids is None:
        result["skip_reason"] = "store_ids_required"
        return result
    if len(normalized_store_ids) > 20:
        result["skip_reason"] = "store_count_limit_exceeded"
        return result
    if not isinstance(candidate_count, int) or candidate_count <= 0:
        result["skip_reason"] = "candidate_count_required"
        return result
    if not isinstance(batch_size, int) or batch_size <= 0:
        result["skip_reason"] = "batch_size_required"
        return result
    if batch_size > int(config["max_batch_size"]):
        result["skip_reason"] = "batch_size_limit_exceeded"
        return result
    if candidate_count < batch_size:
        result["skip_reason"] = "candidate_count_less_than_batch_size"
        return result

    readonly_gate = _validate_formal_batch_readonly_evidence(readonly_evidence)
    result["readonly_gate"] = readonly_gate
    result["readonly_evidence_verified"] = bool(readonly_gate["readonly_evidence_verified"])
    if not result["readonly_evidence_verified"]:
        result["skip_reason"] = readonly_gate["skip_reason"]
        return result

    backup_gate = _validate_naver_order_refresh_backup_evidence(backup_evidence, require_backup=True)
    result["backup_gate"] = backup_gate
    result["backup_evidence_verified"] = bool(backup_gate["backup_evidence_verified"])
    if not result["backup_evidence_verified"]:
        result["skip_reason"] = backup_gate["skip_reason"]
        return result

    if not all([
        audit_plan_ready,
        rollback_plan_ready,
        duplicate_protection_ready,
        failure_isolation_ready,
        multi_store_isolation_ready,
    ]):
        result["skip_reason"] = "production_safety_plan_incomplete"
        return result

    for store_id in normalized_store_ids:
        approval_gate = evaluate_sensitive_action_approval_mock_gate(
            actor_context=actor_context,
            requested_store_id=store_id,
            action_key=str(config["required_action"]),
            manual_approval=manual_approval,
            verification_scope=verification_scope,
        )
        result["approval_gate_by_store"].append({
            "store_id": store_id,
            "status": approval_gate.get("status"),
            "skip_reason": approval_gate.get("skip_reason"),
            "store_scope_verified": approval_gate.get("store_scope_verified"),
            "permission_verified": approval_gate.get("permission_verified"),
            "approval_role_verified": approval_gate.get("approval_role_verified"),
            "actor_id_hash": approval_gate.get("actor_id_hash"),
        })
        if approval_gate.get("status") != "approval_allowed_mock":
            result["skip_reason"] = approval_gate.get("skip_reason") or "permission_approval_gate_failed"
            return result

    result.update({
        "status": "formal_batch_gate_ready_for_later_execution" if write_requested else "formal_batch_gate_plan_ready",
        "permission_verified": True,
        "approval_role_verified": True,
        "all_store_scopes_verified": True,
        "business_message": (
            "正式批量同步生产门禁已在 mock gate 中通过；仍需单独执行阶段，当前没有开放正式同步。"
        ),
    })
    return result


def _normalize_safe_changed_fields(changed_fields: object) -> list[str] | None:
    if not isinstance(changed_fields, (list, tuple, set)):
        return None
    normalized: list[str] = []
    for field in changed_fields:
        if not isinstance(field, str):
            return None
        safe_field = field.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{1,80}", safe_field):
            return None
        normalized.append(safe_field)
    return sorted(set(normalized))


def _evaluate_naver_product_stock_change_mock_write_gate(
    *,
    dry_run_diff: dict | None,
    actor_context: dict | None,
    store_id: int,
    approved_changed_fields: list[str] | tuple[str, ...] | set[str] | None,
    manual_approval: bool,
    backup_evidence: dict | None,
    audit_plan_ready: bool,
    rollback_plan_ready: bool,
    verification_scope: str | None,
    write_requested: bool = False,
) -> dict:
    """Private mock gate for later stock-only local product updates; never writes products."""

    from app.services.permission_service import (
        evaluate_sensitive_action_approval_mock_gate,
    )

    result = {
        "phase": "Naver-Product-Batch-1D",
        "product_stock_change_mock_write_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "store_id": store_id,
        "write_requested": bool(write_requested),
        "manual_approval": bool(manual_approval),
        "approved_changed_fields": [],
        "observed_changed_fields": [],
        "would_update": 0,
        "would_create": 0,
        "would_refresh_only": 0,
        "would_skip": 0,
        "stock_only_change": False,
        "backup_evidence_verified": False,
        "permission_verified": False,
        "approval_role_verified": False,
        "audit_plan_ready": bool(audit_plan_ready),
        "rollback_plan_ready": bool(rollback_plan_ready),
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "real_database_written": False,
        "real_api_called": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if store_id != 8:
        result["skip_reason"] = "store_scope_not_approved_for_stock_gate"
        return result
    if not isinstance(dry_run_diff, dict):
        result["skip_reason"] = "dry_run_diff_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(dry_run_diff):
        result["skip_reason"] = "dry_run_diff_sensitive_field_blocked"
        return result

    observed_changed_fields = _normalize_safe_changed_fields(dry_run_diff.get("changed_fields"))
    approved_fields = _normalize_safe_changed_fields(approved_changed_fields)
    if observed_changed_fields is None or approved_fields is None:
        result["skip_reason"] = "changed_fields_invalid"
        return result
    result["observed_changed_fields"] = observed_changed_fields
    result["approved_changed_fields"] = approved_fields
    if observed_changed_fields != ["stock_quantity"]:
        result["skip_reason"] = "non_stock_field_change_requires_separate_plan"
        return result
    if approved_fields != observed_changed_fields:
        result["skip_reason"] = "approved_changed_fields_mismatch"
        return result

    try:
        would_update = int(dry_run_diff.get("would_update") or 0)
        would_create = int(dry_run_diff.get("would_create") or 0)
        would_refresh_only = int(dry_run_diff.get("would_refresh_only") or 0)
        would_skip = int(dry_run_diff.get("would_skip") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "dry_run_counts_invalid"
        return result
    result.update({
        "would_update": would_update,
        "would_create": would_create,
        "would_refresh_only": would_refresh_only,
        "would_skip": would_skip,
    })
    if would_update <= 0:
        result["skip_reason"] = "stock_change_candidates_missing"
        return result
    if would_create != 0:
        result["skip_reason"] = "product_create_not_allowed_in_stock_gate"
        return result
    if would_skip != 0:
        result["skip_reason"] = "skipped_candidates_require_review"
        return result
    if dry_run_diff.get("write_safety_summary", {}).get("products_written") is not False:
        result["skip_reason"] = "dry_run_write_safety_invalid"
        return result

    backup_gate = _validate_naver_order_refresh_backup_evidence(backup_evidence, require_backup=True)
    result["backup_gate"] = backup_gate
    result["backup_evidence_verified"] = bool(backup_gate["backup_evidence_verified"])
    if not result["backup_evidence_verified"]:
        result["skip_reason"] = backup_gate["skip_reason"]
        return result
    if not audit_plan_ready:
        result["skip_reason"] = "audit_plan_required"
        return result
    if not rollback_plan_ready:
        result["skip_reason"] = "rollback_plan_required"
        return result

    approval_gate = evaluate_sensitive_action_approval_mock_gate(
        actor_context=actor_context,
        requested_store_id=store_id,
        action_key="products.batch_sync_write",
        manual_approval=manual_approval,
        verification_scope=verification_scope,
    )
    result["approval_gate"] = {
        "status": approval_gate.get("status"),
        "skip_reason": approval_gate.get("skip_reason"),
        "actor_role": approval_gate.get("actor_role"),
        "actor_id_hash": approval_gate.get("actor_id_hash"),
        "store_scope_verified": approval_gate.get("store_scope_verified"),
        "permission_verified": approval_gate.get("permission_verified"),
        "approval_role_verified": approval_gate.get("approval_role_verified"),
    }
    if approval_gate.get("status") != "approval_allowed_mock":
        result["skip_reason"] = approval_gate.get("skip_reason") or "stock_change_approval_blocked"
        return result

    result.update({
        "status": "stock_change_mock_gate_ready_for_later_write_phase",
        "stock_only_change": True,
        "permission_verified": True,
        "approval_role_verified": True,
        "business_message": "Stock-only Naver product changes passed the private mock gate. No product rows were written.",
    })
    return result


def _evaluate_naver_product_stock_change_real_write_approval(
    *,
    dry_run_diff: dict | None,
    actor_context: dict | None,
    store_id: int,
    approved_changed_fields: list[str] | tuple[str, ...] | set[str] | None,
    manual_approval: bool,
    backup_evidence: dict | None,
    audit_plan_ready: bool,
    rollback_plan_ready: bool,
) -> dict:
    """Controlled local-write approval wrapper; does not open formal batch sync."""

    from app.services.permission_service import VERIFICATION_SCOPE

    gate = _evaluate_naver_product_stock_change_mock_write_gate(
        dry_run_diff=dry_run_diff,
        actor_context=actor_context,
        store_id=store_id,
        approved_changed_fields=approved_changed_fields,
        manual_approval=manual_approval,
        backup_evidence=backup_evidence,
        audit_plan_ready=audit_plan_ready,
        rollback_plan_ready=rollback_plan_ready,
        verification_scope=VERIFICATION_SCOPE,
        write_requested=True,
    )
    result = {
        **gate,
        "phase": "Naver-Product-Batch-1E",
        "product_stock_change_real_write_approval": True,
        "permission_model": "current_mock_role_metadata_only",
        "real_database_write_allowed": False,
        "products_written": False,
        "real_database_written": False,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if gate.get("status") != "stock_change_mock_gate_ready_for_later_write_phase":
        return result
    result.update({
        "status": "stock_change_real_write_approved",
        "real_database_write_allowed": True,
        "business_message": (
            "Controlled stock-only local write is approved for this phase. "
            "Formal product batch sync remains closed."
        ),
    })
    return result


def _sync_naver_product_stock_change_local_write(
    db: Session,
    *,
    store_id: int,
    payload: object | None,
    dry_run_diff: dict | None,
    approval_gate: dict | None,
    backup_evidence: dict | None,
    max_write_count: int = 3,
) -> dict:
    """Apply a narrow stock-only local write for existing Naver products."""

    result = {
        "phase": "Naver-Product-Batch-1F",
        "product_stock_change_local_write": True,
        "status": "blocked",
        "skip_reason": None,
        "store_id": store_id,
        "max_write_count": max_write_count,
        "updated_count": 0,
        "created_count": 0,
        "skipped_count": 0,
        "stock_only_write": False,
        "product_fields_written": [],
        "updated_products": [],
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "real_database_written": False,
        "real_api_called": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if store_id != 8:
        result["skip_reason"] = "store_scope_not_approved_for_stock_write"
        return result
    if not isinstance(approval_gate, dict) or approval_gate.get("status") not in {
        "stock_change_mock_gate_ready_for_later_write_phase",
        "stock_change_real_write_approved",
    }:
        result["skip_reason"] = "stock_change_approval_gate_required"
        return result
    if approval_gate.get("status") == "stock_change_real_write_approved" and approval_gate.get("real_database_write_allowed") is not True:
        result["skip_reason"] = "stock_change_real_write_not_allowed"
        return result
    backup_gate = _validate_naver_order_refresh_backup_evidence(backup_evidence, require_backup=True)
    result["backup_gate"] = backup_gate
    if backup_gate.get("status") != "backup_evidence_verified":
        result["skip_reason"] = backup_gate.get("skip_reason") or "backup_evidence_required"
        return result
    if not isinstance(dry_run_diff, dict):
        result["skip_reason"] = "dry_run_diff_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(dry_run_diff):
        result["skip_reason"] = "dry_run_diff_sensitive_field_blocked"
        return result

    observed_changed_fields = _normalize_safe_changed_fields(dry_run_diff.get("changed_fields"))
    if observed_changed_fields != ["stock_quantity"]:
        result["skip_reason"] = "non_stock_field_change_requires_separate_plan"
        return result
    try:
        would_update = int(dry_run_diff.get("would_update") or 0)
        would_create = int(dry_run_diff.get("would_create") or 0)
        would_skip = int(dry_run_diff.get("would_skip") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "dry_run_counts_invalid"
        return result
    if would_update <= 0:
        result["skip_reason"] = "stock_change_candidates_missing"
        return result
    if would_update > max_write_count:
        result["skip_reason"] = "stock_change_write_limit_exceeded"
        return result
    if would_create != 0:
        result["skip_reason"] = "product_create_not_allowed_in_stock_write"
        return result
    if would_skip != 0:
        result["skip_reason"] = "skipped_candidates_require_review"
        return result

    candidates, skip_reasons = _extract_naver_product_sync_candidates(payload)
    hard_skip_total = sum(
        int(skip_reasons.get(reason, 0) or 0)
        for reason in (
            "multiple_channel_products",
            "missing_external_product_id",
            "missing_product_name",
            "duplicate_external_product_id_in_same_batch",
            "invalid_status_shape",
            "invalid_numeric_shape_for_price",
            "invalid_numeric_shape_for_stock",
        )
    )
    if hard_skip_total:
        result["skip_reason"] = "payload_candidates_not_safe_for_stock_write"
        result["skipped_count"] = hard_skip_total
        return result

    pending_updates: list[tuple[Product, int, int, str]] = []
    non_stock_changed_fields: set[str] = set()
    seen_external_product_ids: set[str] = set()
    for candidate in candidates[:5]:
        external_product_id = candidate.get("external_product_id")
        if not isinstance(external_product_id, str) or not external_product_id:
            result["skip_reason"] = "candidate_external_product_id_missing"
            return result
        if external_product_id in seen_external_product_ids:
            result["skip_reason"] = "duplicate_external_product_id_in_same_batch"
            return result
        seen_external_product_ids.add(external_product_id)
        product = db.scalar(
            select(Product).where(
                Product.store_id == store_id,
                Product.platform == "naver",
                Product.external_product_id == external_product_id,
            )
        )
        if product is None:
            result["skip_reason"] = "product_create_not_allowed_in_stock_write"
            return result
        for field in ("name", "status", "currency"):
            if candidate.get(field) is not None and getattr(product, field) != candidate.get(field):
                non_stock_changed_fields.add(field)
        if candidate.get("price") is not None and Decimal(str(product.price)) != Decimal(str(candidate.get("price"))):
            non_stock_changed_fields.add("price")
        incoming_stock = candidate.get("stock_quantity")
        if incoming_stock is None:
            result["skip_reason"] = "stock_quantity_missing"
            return result
        safe_stock = int(incoming_stock)
        existing_stock = int(product.stock_quantity)
        if safe_stock != existing_stock:
            pending_updates.append((product, existing_stock, safe_stock, _mask_external_identifier(external_product_id)))

    if non_stock_changed_fields:
        result["skip_reason"] = "non_stock_field_change_requires_separate_plan"
        result["blocked_changed_fields"] = sorted(non_stock_changed_fields)
        return result
    if len(pending_updates) != would_update:
        result["skip_reason"] = "stock_change_candidate_count_mismatch"
        result["observed_update_count"] = len(pending_updates)
        result["dry_run_would_update"] = would_update
        return result

    for product, before_stock, after_stock, sample_id in pending_updates:
        product.stock_quantity = after_stock
        result["updated_products"].append({
            "local_product_id": product.id,
            "sample_id": sample_id,
            "stock_quantity_before": before_stock,
            "stock_quantity_after": after_stock,
        })
    db.commit()

    result.update({
        "status": "success",
        "updated_count": len(pending_updates),
        "stock_only_write": True,
        "product_fields_written": ["stock_quantity"] if pending_updates else [],
        "products_written": bool(pending_updates),
        "real_database_written": bool(pending_updates),
        "business_message": "Controlled Naver stock-only local product update completed. Formal product batch sync remains closed.",
    })
    return result


def _evaluate_naver_product_batch_rollback_drill_mock_gate(
    *,
    product_write_summary: dict | None,
    backup_evidence: dict | None,
    rollback_checklist: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private rollback drill gate for Naver product batch planning; never restores or writes rows."""

    result = {
        "phase": "Naver-Product-Batch-1J",
        "product_batch_rollback_drill_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "rollback_drill_ready": False,
        "backup_evidence_verified": False,
        "required_checklist_flags": [
            "backup_manifest_available",
            "pre_write_counts_captured",
            "changed_product_hashes_available",
            "rollback_sql_reviewed",
            "temporary_restore_dry_run_planned",
            "post_rollback_readback_planned",
            "sensitive_scan_planned",
            "formal_sync_remains_closed",
        ],
        "missing_checklist_flags": [],
        "updated_count": 0,
        "created_count": 0,
        "stock_only_write_verified": False,
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "real_database_written": False,
        "real_api_called": False,
        "rollback_executed": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(product_write_summary, dict):
        result["skip_reason"] = "product_write_summary_required"
        return result
    if not isinstance(rollback_checklist, dict):
        result["skip_reason"] = "rollback_checklist_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "product_write_summary": product_write_summary,
        "backup_evidence": backup_evidence,
        "rollback_checklist": rollback_checklist,
    }):
        result["skip_reason"] = "rollback_drill_sensitive_field_blocked"
        return result

    backup_gate = _validate_naver_order_refresh_backup_evidence(backup_evidence, require_backup=True)
    result["backup_gate"] = backup_gate
    result["backup_evidence_verified"] = bool(backup_gate["backup_evidence_verified"])
    if not result["backup_evidence_verified"]:
        result["skip_reason"] = backup_gate["skip_reason"]
        return result

    required_flags = result["required_checklist_flags"]
    missing_flags = [flag for flag in required_flags if rollback_checklist.get(flag) is not True]
    result["missing_checklist_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "rollback_checklist_incomplete"
        return result
    if rollback_checklist.get("real_restore_requested") is True:
        result["skip_reason"] = "real_restore_request_not_allowed_in_mock_gate"
        return result
    if rollback_checklist.get("restore_target_is_production_db") is True:
        result["skip_reason"] = "production_restore_target_not_allowed_in_mock_gate"
        return result
    if product_write_summary.get("phase") != "Naver-Product-Batch-1F":
        result["skip_reason"] = "product_write_phase_mismatch"
        return result
    if product_write_summary.get("stock_only_write") is not True:
        result["skip_reason"] = "stock_only_write_required"
        return result
    if product_write_summary.get("formal_product_sync_open") is True or product_write_summary.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_product_sync_open_not_allowed"
        return result
    if product_write_summary.get("raw_response_saved") is not False:
        result["skip_reason"] = "raw_response_saved_not_allowed"
        return result
    try:
        updated_count = int(product_write_summary.get("updated_count") or 0)
        created_count = int(product_write_summary.get("created_count") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "product_write_counts_invalid"
        return result
    result["updated_count"] = updated_count
    result["created_count"] = created_count
    if updated_count <= 0:
        result["skip_reason"] = "updated_product_count_required"
        return result
    if updated_count > 3:
        result["skip_reason"] = "rollback_drill_product_limit_exceeded"
        return result
    if created_count != 0:
        result["skip_reason"] = "product_create_not_allowed_in_rollback_drill"
        return result

    result.update({
        "status": "product_batch_rollback_drill_mock_ready",
        "rollback_drill_ready": True,
        "stock_only_write_verified": True,
        "business_message": "Naver product rollback drill gate passed in mock mode. No restore or product write was executed.",
    })
    return result


def _evaluate_batch_readonly_evidence_api_mock_gate(
    *,
    evidence_items: list[dict] | tuple[dict, ...] | None,
    verification_scope: str | None,
    max_items: int = 10,
) -> dict:
    """Private mock gate for a future readonly evidence API; never exposes a public route."""

    result = {
        "phase": "ERP-Batch-1E",
        "readonly_evidence_api_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "max_items": max_items,
        "evidence_count": 0,
        "items": [],
        "public_endpoint_enabled": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(evidence_items, (list, tuple)):
        result["skip_reason"] = "evidence_items_required"
        return result
    if len(evidence_items) > max_items:
        result["skip_reason"] = "evidence_item_limit_exceeded"
        return result

    allowed_sync_kinds = set(FORMAL_BATCH_SYNC_GATE_KINDS)
    normalized_items: list[dict] = []
    for index, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            result["skip_reason"] = "evidence_item_shape_invalid"
            return result
        if _formal_batch_sync_sensitive_marker_found(item):
            result["skip_reason"] = "evidence_item_sensitive_field_blocked"
            result["blocked_index"] = index
            return result
        sync_kind = str(item.get("sync_kind") or "")
        if sync_kind not in allowed_sync_kinds:
            result["skip_reason"] = "sync_kind_not_allowed"
            return result
        try:
            store_id = int(item.get("store_id"))
            candidate_count = int(item.get("candidate_count") or 0)
            would_create = int(item.get("would_create") or 0)
            would_update = int(item.get("would_update") or 0)
            would_refresh_only = int(item.get("would_refresh_only") or 0)
            would_skip = int(item.get("would_skip") or 0)
        except (TypeError, ValueError):
            result["skip_reason"] = "evidence_counts_invalid"
            return result
        if store_id <= 0 or candidate_count < 0:
            result["skip_reason"] = "evidence_counts_invalid"
            return result
        changed_fields = _normalize_safe_changed_fields(item.get("changed_field_names", []))
        if changed_fields is None:
            result["skip_reason"] = "changed_field_names_invalid"
            return result
        if item.get("real_sync") is True or item.get("raw_response_saved") is not False:
            result["skip_reason"] = "readonly_evidence_safety_flags_invalid"
            return result
        if item.get("privacy_fields_redacted") is not True:
            result["skip_reason"] = "privacy_redaction_required"
            return result
        if item.get("formal_sync_open") is True:
            result["skip_reason"] = "formal_sync_already_open_not_allowed"
            return result
        normalized_items.append({
            "evidence_id": str(item.get("evidence_id") or f"evidence-{index + 1}")[:120],
            "store_id": store_id,
            "platform": FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["platform"],
            "sync_kind": sync_kind,
            "target": FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["target"],
            "window_label": str(item.get("window_label") or "readonly window")[:120],
            "candidate_count": candidate_count,
            "would_create": would_create,
            "would_update": would_update,
            "would_refresh_only": would_refresh_only,
            "would_skip": would_skip,
            "changed_field_names": changed_fields,
            "duplicate_check_passed": bool(item.get("duplicate_check_passed")),
            "field_whitelist_verified": bool(item.get("field_whitelist_verified")),
            "backup_required": True,
            "permission_required": True,
            "audit_required": True,
            "business_message": str(item.get("business_message") or "Readonly batch evidence is ready for review.")[:240],
            "next_action": str(item.get("next_action") or "manual_review_required")[:160],
        })

    result.update({
        "status": "readonly_evidence_api_mock_ready",
        "evidence_count": len(normalized_items),
        "items": normalized_items,
    })
    return result


def evaluate_batch_readonly_evidence_api_local(
    *,
    evidence_items: list[dict] | tuple[dict, ...] | None,
    max_items: int = 10,
) -> dict:
    """Public local readonly evidence normalizer; never calls platforms or writes rows."""

    result = _evaluate_batch_readonly_evidence_api_mock_gate(
        evidence_items=evidence_items,
        verification_scope="verify_all_temp_db",
        max_items=max_items,
    )
    result.update({
        "phase": "ERP-Batch-1H",
        "readonly_evidence_api_local": True,
        "public_endpoint_enabled": True,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "operation_audit_rows_written": False,
        "timeline_events_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "readonly_evidence_api_mock_ready":
        result.update({
            "status": "readonly_evidence_api_ready",
            "business_message": "Readonly batch evidence is ready for approval review. No sync or write was executed.",
        })
    return result


def _evaluate_naver_order_refresh_batch_mock_gate(
    db: Session,
    *,
    refresh_previews: list[dict] | tuple[dict, ...] | None,
    approved_order_hashes: list[str] | tuple[str, ...] | None = None,
    write_enabled: bool = False,
    manual_approval: bool = False,
    fresh_readonly_preview: bool = True,
    max_batch_size: int = 2,
) -> dict:
    """Mock-testable 15B batch refresh gate; not wired to public endpoints or real sync."""
    result = _default_naver_order_refresh_batch_mock_gate_result(
        refresh_previews=refresh_previews,
        approved_order_hashes=approved_order_hashes,
        write_enabled=write_enabled,
        manual_approval=manual_approval,
        fresh_readonly_preview=fresh_readonly_preview,
        max_batch_size=max_batch_size,
    )
    if not fresh_readonly_preview:
        result["skip_reason"] = "batch_refresh_stale_preview"
        return result
    if not isinstance(refresh_previews, (list, tuple)) or not refresh_previews:
        result["skip_reason"] = "batch_refresh_candidates_missing"
        return result
    if len(refresh_previews) > max_batch_size:
        result["skip_reason"] = "batch_refresh_candidate_limit_exceeded"
        return result

    candidate_hashes: list[str] = []
    for item in refresh_previews:
        candidate_hash = item.get("external_product_order_id_hash") if isinstance(item, dict) else None
        if not _is_hash_identifier(candidate_hash):
            result["skip_reason"] = "batch_refresh_missing_safe_hash"
            return result
        candidate_hashes.append(str(candidate_hash))
    result["sample_ids"] = candidate_hashes

    duplicate_hashes = sorted({item for item in candidate_hashes if candidate_hashes.count(item) > 1})
    result["duplicate_candidate_hashes"] = duplicate_hashes
    if duplicate_hashes:
        result["skip_reason"] = "duplicate_external_product_order_hash_in_batch"
        return result

    if approved_order_hashes is not None:
        if not isinstance(approved_order_hashes, (list, tuple)) or not approved_order_hashes:
            result["skip_reason"] = "approved_order_hashes_missing"
            return result
        approved_hashes = [str(item) for item in approved_order_hashes if _is_hash_identifier(item)]
        if len(approved_hashes) != len(approved_order_hashes):
            result["skip_reason"] = "approved_order_hash_invalid"
            return result
        if set(approved_hashes) != set(candidate_hashes):
            result["skip_reason"] = "approved_order_hashes_mismatch"
            return result

    prepared_updates: list[tuple[Order, dict, str, list[str]]] = []
    for refresh_preview in refresh_previews:
        safe_hash = str(refresh_preview["external_product_order_id_hash"])
        candidate_result = {
            "safe_hash": safe_hash,
            "matched_local_count": 0,
            "would_update": 0,
            "changed_fields": [],
            "privacy_gate_passed": False,
            "skip_reason": None,
        }

        forbidden_fields = _naver_order_refresh_batch_forbidden_field_names(refresh_preview)
        if forbidden_fields:
            candidate_result["skip_reason"] = "batch_refresh_sensitive_field_blocked"
            candidate_result["forbidden_field_names"] = forbidden_fields
            result["candidate_results"].append(candidate_result)
            result["skip_reason"] = "batch_refresh_sensitive_field_blocked"
            return result

        existing_orders = db.scalars(
            select(Order).where(
                Order.store_id == 8,
                Order.platform == "naver",
                Order.source_type == NAVER_ORDER_SYNC_SOURCE_TYPE,
                Order.external_order_id == safe_hash,
            )
        ).all()
        candidate_result["matched_local_count"] = len(existing_orders)
        result["matched_local_count"] += len(existing_orders)
        if not existing_orders:
            candidate_result["skip_reason"] = "batch_refresh_new_order_candidate"
            result["candidate_results"].append(candidate_result)
            result["skip_reason"] = "batch_refresh_new_order_candidate"
            return result
        if len(existing_orders) > 1:
            candidate_result["skip_reason"] = "batch_refresh_local_order_not_unique"
            result["candidate_results"].append(candidate_result)
            result["skip_reason"] = "batch_refresh_local_order_not_unique"
            return result

        privacy_gate = _validate_naver_order_detail_preview_for_local_write(refresh_preview)
        candidate_result["privacy_gate_passed"] = privacy_gate["passed"]
        candidate_result["privacy_gate_reasons"] = privacy_gate["reasons"]
        if not privacy_gate["passed"]:
            candidate_result["skip_reason"] = "batch_refresh_privacy_blocked"
            result["candidate_results"].append(candidate_result)
            result["skip_reason"] = "batch_refresh_privacy_blocked"
            return result

        if _naver_order_refresh_preview_unknown_status(refresh_preview):
            candidate_result["skip_reason"] = "batch_refresh_unknown_status_observed"
            result["candidate_results"].append(candidate_result)
            result["skip_reason"] = "batch_refresh_unknown_status_observed"
            return result

        existing = existing_orders[0]
        payload = _build_naver_order_refresh_payload(refresh_preview)
        changed_fields = _changed_naver_order_refresh_fields(existing, payload)
        candidate_result["changed_fields"] = changed_fields
        candidate_result["would_update"] = 1 if changed_fields else 0
        result["changed_fields_by_hash"][safe_hash] = changed_fields
        result["would_update"] += candidate_result["would_update"]
        if changed_fields:
            prepared_updates.append((existing, payload, safe_hash, changed_fields))
        else:
            result["no_change_count"] += 1
        result["candidate_results"].append(candidate_result)

    if not result["would_update"]:
        result["status"] = "batch_refresh_no_change"
        return result
    if not write_enabled:
        result["status"] = "batch_refresh_not_requested"
        return result
    if not manual_approval:
        result["skip_reason"] = "manual_approval_required"
        return result

    for existing, payload, _safe_hash, _changed_fields in prepared_updates:
        for field, value in payload.items():
            setattr(existing, field, value)
    db.commit()
    result.update({
        "status": "batch_refresh_updated",
        "refreshed_count": len(prepared_updates),
        "orders_written": bool(prepared_updates),
        "orders_updated": bool(prepared_updates),
        "orders_created": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result


NAVER_ORDER_TIMELINE_EVENT_TYPES = {
    "PAYED": "order_paid",
    "PLACE_PRODUCT_ORDER": "order_confirmed",
    "READY": "dispatch_ready",
    "DELIVERY_READY": "dispatch_ready",
    "DISPATCHED": "dispatched",
    "DELIVERING": "delivering",
    "SHIPPING": "delivering",
    "IN_DELIVERY": "delivering",
    "DELIVERED": "delivered",
    "DELIVERY_COMPLETION": "delivered",
    "DELIVERY_COMPLETED": "delivered",
    "DELIVERY_COMPLETE": "delivered",
    "COMPLETED_DELIVERY": "delivered",
    "SHIPPING_COMPLETED": "delivered",
    "CANCEL_REQUEST": "cancel_requested",
    "CANCELED": "canceled",
    "CANCELLED": "canceled",
    "RETURN_REQUEST": "return_requested",
    "RETURNED": "returned",
    "RETURN_DONE": "returned",
    "EXCHANGE_REQUEST": "exchange_requested",
    "EXCHANGED": "exchanged",
    "EXCHANGE_DONE": "exchanged",
    "COLLECT_REQUEST": "claim_collect_requested",
    "COLLECTING": "claim_collecting",
    "COLLECT_DONE": "claim_collected",
    "PURCHASE_DECIDED": "purchase_decided",
}

NAVER_ORDER_TIMELINE_LABEL_CANONICALS = (
    ("PAYED", "order_paid"),
    ("PLACE_PRODUCT_ORDER", "order_confirmed"),
    ("READY", "dispatch_ready"),
    ("DELIVERING", "delivering"),
    ("DISPATCHED", "dispatched"),
    ("DELIVERED", "delivered"),
    ("CANCEL_REQUEST", "cancel_requested"),
    ("CANCELED", "canceled"),
    ("RETURN_REQUEST", "return_requested"),
    ("EXCHANGE_REQUEST", "exchange_requested"),
    ("COLLECT_DONE", "claim_collected"),
    ("PURCHASE_DECIDED", "purchase_decided"),
)


def _naver_order_timeline_status_raw(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("raw")
    return _safe_order_text(value, max_length=40)


def _naver_order_timeline_status_unknown(value: object) -> bool:
    if isinstance(value, dict) and value.get("unknown_status_observed") is not None:
        return bool(value.get("unknown_status_observed"))
    raw_value = _naver_order_timeline_status_raw(value)
    return bool(raw_value and _status_label_zh(raw_value)[1])


def _naver_order_timeline_event_type(raw_value: str | None) -> str:
    if not raw_value:
        return "unknown_status_observed"
    normalized = str(raw_value).strip()
    event_type = NAVER_ORDER_TIMELINE_EVENT_TYPES.get(normalized) or NAVER_ORDER_TIMELINE_EVENT_TYPES.get(normalized.upper())
    if event_type:
        return event_type
    label, unknown = _status_label_zh(normalized)
    if unknown or not label:
        return "unknown_status_observed"
    for canonical_status, canonical_event_type in NAVER_ORDER_TIMELINE_LABEL_CANONICALS:
        canonical_label, _ = _status_label_zh(canonical_status)
        if label == canonical_label:
            return canonical_event_type
    return "unknown_status_observed"


def _naver_order_timeline_snapshot_statuses(snapshot: object) -> dict:
    if snapshot is None:
        return {"order_status": None, "payment_status": None, "delivery_status": None, "claim_status": None}
    if isinstance(snapshot, dict):
        raw_data = snapshot.get("raw_data") if isinstance(snapshot.get("raw_data"), dict) else {}
        return {
            "order_status": _naver_order_timeline_status_raw(snapshot.get("order_status"))
            or _naver_order_timeline_status_raw(raw_data.get("order_status")),
            "payment_status": _naver_order_timeline_status_raw(snapshot.get("payment_status"))
            or _naver_order_timeline_status_raw(raw_data.get("payment_status")),
            "delivery_status": _naver_order_timeline_status_raw(snapshot.get("delivery_status"))
            or _naver_order_timeline_status_raw(raw_data.get("delivery_status")),
            "claim_status": _naver_order_timeline_status_raw(snapshot.get("claim_status"))
            or _naver_order_timeline_status_raw(raw_data.get("claim_status")),
        }
    raw_data = getattr(snapshot, "raw_data", None)
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    return {
        "order_status": _naver_order_timeline_status_raw(getattr(snapshot, "order_status", None))
        or _naver_order_timeline_status_raw(raw_data.get("order_status")),
        "payment_status": _naver_order_timeline_status_raw(raw_data.get("payment_status")),
        "delivery_status": _naver_order_timeline_status_raw(raw_data.get("delivery_status")),
        "claim_status": _naver_order_timeline_status_raw(raw_data.get("claim_status")),
    }


def _naver_order_timeline_status_label(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    return _status_label_zh(raw_value)[0]


def _naver_order_timeline_dedupe_key(event: dict) -> str:
    parts = (
        event.get("store_id"),
        event.get("platform"),
        event.get("external_product_order_id_hash"),
        event.get("event_type"),
        event.get("status_raw"),
        event.get("delivery_status_raw"),
        event.get("claim_status_raw"),
    )
    return "|".join("" if item is None else str(item) for item in parts)


def _build_naver_order_timeline_mock_event(
    *,
    selected_order_hash: str,
    refresh_preview: dict,
    event_type: str,
    status_raw: str | None,
    source_phase: str = "Naver-ERP-14B",
) -> dict:
    delivery_raw = _naver_order_timeline_status_raw(refresh_preview.get("delivery_status"))
    claim_raw = _naver_order_timeline_status_raw(refresh_preview.get("claim_status"))
    payment_raw = _naver_order_timeline_status_raw(refresh_preview.get("payment_status"))
    event = {
        "store_id": 8,
        "platform": "naver",
        "external_order_id_hash": refresh_preview.get("external_order_id_hash")
        if _is_hash_identifier(refresh_preview.get("external_order_id_hash"))
        else None,
        "external_product_order_id_hash": selected_order_hash,
        "event_type": event_type,
        "status_raw": status_raw,
        "status_label_zh": _naver_order_timeline_status_label(status_raw),
        "payment_status_raw": payment_raw,
        "payment_status_label_zh": _naver_order_timeline_status_label(payment_raw),
        "delivery_status_raw": delivery_raw,
        "delivery_status_label_zh": _naver_order_timeline_status_label(delivery_raw),
        "claim_status_raw": claim_raw,
        "claim_status_label_zh": _naver_order_timeline_status_label(claim_raw),
        "observed_at": refresh_preview.get("last_changed_at") or refresh_preview.get("last_synced_at") or get_utc_now().isoformat(),
        "source_phase": source_phase,
        "source_type": NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        "mapping_version": NAVER_ORDER_TIMELINE_MAPPING_VERSION,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
    }
    event["dedupe_key"] = _naver_order_timeline_dedupe_key(event)
    return event


def _evaluate_naver_order_status_timeline_mock_mapper(
    *,
    selected_order_hash: str | None,
    previous_snapshot: object,
    refresh_preview: dict | None,
    existing_event_keys: list[str] | set[str] | tuple[str, ...] | None = None,
    fresh_readonly_preview: bool = True,
    identity_matched: bool = True,
) -> dict:
    """Mock-testable 14B timeline mapper; not wired to public endpoints or persistence."""
    result = {
        "phase": "Naver-ERP-14B",
        "timeline_mock_mapper": True,
        "fresh_readonly_preview": bool(fresh_readonly_preview),
        "identity_matched": bool(identity_matched),
        "status": "blocked",
        "selected_order_hash": selected_order_hash if _is_hash_identifier(selected_order_hash) else None,
        "changed_status_fields": [],
        "planned_events": [],
        "event_count": 0,
        "deduped_event_count": 0,
        "manual_review_required": False,
        "unknown_status_observed": False,
        "orders_written": False,
        "timeline_rows_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
        "skip_reason": None,
    }
    if not fresh_readonly_preview:
        result["skip_reason"] = "timeline_stale_preview"
        return result
    if not _is_hash_identifier(selected_order_hash):
        result["skip_reason"] = "selected_order_missing"
        return result
    if not isinstance(refresh_preview, dict):
        result["skip_reason"] = "refresh_preview_missing"
        return result
    if not identity_matched or refresh_preview.get("external_product_order_id_hash") != selected_order_hash:
        result["skip_reason"] = "timeline_identity_mismatch"
        return result

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(refresh_preview)
    result["privacy_gate"] = privacy_gate
    if not privacy_gate["passed"]:
        result["skip_reason"] = "timeline_privacy_gate_failed"
        return result

    previous_statuses = _naver_order_timeline_snapshot_statuses(previous_snapshot)
    current_statuses = _naver_order_timeline_snapshot_statuses(refresh_preview)
    result["previous_statuses"] = previous_statuses
    result["current_statuses"] = current_statuses
    existing_keys = set(existing_event_keys or [])

    status_values = (
        refresh_preview.get("order_status"),
        refresh_preview.get("delivery_status"),
        refresh_preview.get("claim_status"),
    )
    unknown_status = bool(refresh_preview.get("unknown_status_observed")) or any(
        _naver_order_timeline_status_unknown(value)
        for value in status_values
        if _naver_order_timeline_status_raw(value)
    )
    if unknown_status:
        raw_value = (
            current_statuses.get("order_status")
            or current_statuses.get("delivery_status")
            or current_statuses.get("claim_status")
        )
        event = _build_naver_order_timeline_mock_event(
            selected_order_hash=selected_order_hash,
            refresh_preview=refresh_preview,
            event_type="unknown_status_observed",
            status_raw=raw_value,
        )
        result.update({
            "status": "blocked_unknown_status",
            "skip_reason": "unknown_status_observed",
            "manual_review_required": True,
            "unknown_status_observed": True,
        })
        if event["dedupe_key"] in existing_keys:
            result["deduped_event_count"] = 1
        else:
            result["planned_events"] = [event]
            result["event_count"] = 1
        return result

    seen_event_types: set[str] = set()
    for field_name in ("order_status", "delivery_status", "claim_status", "payment_status"):
        current_raw = current_statuses.get(field_name)
        previous_raw = previous_statuses.get(field_name)
        if not current_raw or current_raw == previous_raw:
            continue
        event_type = _naver_order_timeline_event_type(current_raw)
        if event_type == "unknown_status_observed":
            result.update({
                "status": "blocked_unknown_status",
                "skip_reason": "unknown_status_observed",
                "manual_review_required": True,
                "unknown_status_observed": True,
            })
            return result
        if event_type in seen_event_types:
            result["changed_status_fields"].append(field_name)
            continue
        seen_event_types.add(event_type)
        event = _build_naver_order_timeline_mock_event(
            selected_order_hash=selected_order_hash,
            refresh_preview=refresh_preview,
            event_type=event_type,
            status_raw=current_raw,
        )
        result["changed_status_fields"].append(field_name)
        if event["dedupe_key"] in existing_keys:
            result["deduped_event_count"] += 1
            continue
        result["planned_events"].append(event)

    result["event_count"] = len(result["planned_events"])
    if result["event_count"]:
        result["status"] = "timeline_events_planned"
    elif result["deduped_event_count"]:
        result["status"] = "timeline_events_deduped"
    else:
        result["status"] = "no_timeline_event"
        result["skip_reason"] = "no_status_change"
    return result


def _naver_order_timeline_event_forbidden_field_names(payload: object) -> list[str]:
    allowed_names = {
        "addresssaved",
        "address_saved",
        "privacyfieldsredacted",
        "privacy_fields_redacted",
        "rawresponsesaved",
        "raw_response_saved",
    }
    forbidden_fragments = {
        "authorization",
        "bcrypt",
        "buyer",
        "clientsecret",
        "client_secret",
        "completefield",
        "complete_field",
        "header",
        "phone",
        "rawdata",
        "rawresponse",
        "raw_data",
        "raw_response",
        "receiver",
        "secret",
        "signature",
        "token",
        "zipcode",
        "zip_code",
    }
    normalized_names = {
        name.replace("-", "").replace("_", "").replace(" ", "").lower()
        for name in _collect_json_field_names(payload)
    } - allowed_names
    return sorted(
        name
        for name in normalized_names
        if any(fragment in name for fragment in forbidden_fragments)
    )


def _evaluate_naver_order_timeline_event_single_write_mock_gate(
    db: Session,
    *,
    selected_order_hash: str | None,
    planned_events: list[dict] | tuple[dict, ...] | None,
    write_enabled: bool = False,
    manual_approval: bool = False,
    fresh_readonly_preview: bool = True,
) -> dict:
    """Mock-testable 14H event write gate; not wired to public endpoints or real sync."""
    result = {
        "phase": "Naver-ERP-14H",
        "timeline_event_single_write_mock_gate": True,
        "write_enabled": bool(write_enabled),
        "manual_approval": bool(manual_approval),
        "fresh_readonly_preview": bool(fresh_readonly_preview),
        "status": "blocked",
        "selected_order_hash": selected_order_hash if _is_hash_identifier(selected_order_hash) else None,
        "matched_local_count": 0,
        "planned_event_count": len(planned_events) if isinstance(planned_events, (list, tuple)) else 0,
        "event_rows_written": 0,
        "timeline_rows_written": False,
        "orders_written": False,
        "orders_created": False,
        "orders_updated": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
        "skip_reason": None,
        "event_type": None,
        "dedupe_key": None,
        "event_row_id": None,
        "safe_metadata": None,
    }
    if not fresh_readonly_preview:
        result["skip_reason"] = "timeline_event_stale_preview"
        return result
    if not _is_hash_identifier(selected_order_hash):
        result["skip_reason"] = "selected_order_missing"
        return result
    if not isinstance(planned_events, (list, tuple)):
        result["skip_reason"] = "planned_events_missing"
        return result
    if len(planned_events) != 1:
        result["skip_reason"] = "planned_event_count_not_one"
        return result
    event = planned_events[0]
    if not isinstance(event, dict):
        result["skip_reason"] = "planned_event_invalid"
        return result

    forbidden_names = _naver_order_timeline_event_forbidden_field_names(event)
    if forbidden_names:
        result["skip_reason"] = "timeline_event_sensitive_field_blocked"
        result["forbidden_field_names"] = forbidden_names
        return result

    if event.get("store_id") != 8 or event.get("platform") != "naver":
        result["skip_reason"] = "timeline_event_scope_mismatch"
        return result
    if event.get("external_product_order_id_hash") != selected_order_hash:
        result["skip_reason"] = "timeline_event_identity_mismatch"
        return result
    if event.get("external_order_id_hash") is not None and not _is_hash_identifier(event.get("external_order_id_hash")):
        result["skip_reason"] = "timeline_event_order_hash_invalid"
        return result
    event_type = _safe_order_text(event.get("event_type"), max_length=50)
    allowed_event_types = set(NAVER_ORDER_TIMELINE_EVENT_TYPES.values()) | {"unknown_status_observed"}
    if event_type not in allowed_event_types:
        result["skip_reason"] = "timeline_event_type_not_allowed"
        return result
    if event_type == "unknown_status_observed":
        result["skip_reason"] = "timeline_event_unknown_status_blocked"
        result["manual_review_required"] = True
        return result
    if event.get("source_type") != NAVER_ORDER_PREVIEW_SOURCE_TYPE:
        result["skip_reason"] = "timeline_event_source_type_invalid"
        return result
    if event.get("mapping_version") != NAVER_ORDER_TIMELINE_MAPPING_VERSION:
        result["skip_reason"] = "timeline_event_mapping_version_invalid"
        return result
    if event.get("raw_response_saved") is not False:
        result["skip_reason"] = "timeline_event_raw_response_flag_invalid"
        return result
    if event.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "timeline_event_privacy_flag_invalid"
        return result
    if event.get("address_saved") is not False:
        result["skip_reason"] = "timeline_event_address_flag_invalid"
        return result

    expected_dedupe_key = _naver_order_timeline_dedupe_key(event)
    if event.get("dedupe_key") != expected_dedupe_key:
        result["skip_reason"] = "timeline_event_dedupe_key_invalid"
        return result
    result["event_type"] = event_type
    result["dedupe_key"] = expected_dedupe_key

    existing_orders = db.scalars(
        select(Order).where(
            Order.store_id == 8,
            Order.platform == "naver",
            Order.external_order_id == selected_order_hash,
        )
    ).all()
    result["matched_local_count"] = len(existing_orders)
    if not existing_orders:
        result["skip_reason"] = "local_order_not_found"
        return result
    if len(existing_orders) > 1:
        result["skip_reason"] = "local_order_not_unique"
        return result
    existing_order = existing_orders[0]

    existing_events = db.scalars(
        select(OrderStatusEvent).where(
            OrderStatusEvent.store_id == 8,
            OrderStatusEvent.platform == "naver",
            OrderStatusEvent.dedupe_key == expected_dedupe_key,
        )
    ).all()
    if existing_events:
        result.update({
            "status": "timeline_event_already_exists",
            "deduped_event_count": len(existing_events),
        })
        return result
    if not write_enabled:
        result["status"] = "timeline_event_write_not_requested"
        return result
    if not manual_approval:
        result["skip_reason"] = "manual_approval_required"
        return result

    safe_metadata = {
        "source_window": "mock_single_event_write_gate",
        "candidate_classification": "selected_local_refresh_candidate",
        "refresh_gate_phase": "Naver-ERP-13C",
        "timeline_mapper_phase": event.get("source_phase"),
        "write_gate_phase": "Naver-ERP-14H",
        "unknown_status_observed": False,
        "deduped_event_count": 0,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "address_saved": False,
    }
    observed_at = _parse_preview_iso_datetime(event.get("observed_at")) or get_utc_now()
    row = OrderStatusEvent(
        store_id=8,
        order_id=existing_order.id,
        platform="naver",
        external_order_id_hash=event.get("external_order_id_hash"),
        external_product_order_id_hash=selected_order_hash,
        event_type=event_type,
        status_raw=_safe_order_text(event.get("status_raw"), max_length=60),
        status_label_zh=_safe_order_text(event.get("status_label_zh"), max_length=120),
        payment_status_raw=_safe_order_text(event.get("payment_status_raw"), max_length=60),
        payment_status_label_zh=_safe_order_text(event.get("payment_status_label_zh"), max_length=120),
        delivery_status_raw=_safe_order_text(event.get("delivery_status_raw"), max_length=60),
        delivery_status_label_zh=_safe_order_text(event.get("delivery_status_label_zh"), max_length=120),
        claim_status_raw=_safe_order_text(event.get("claim_status_raw"), max_length=60),
        claim_status_label_zh=_safe_order_text(event.get("claim_status_label_zh"), max_length=120),
        observed_at=observed_at,
        source_phase="Naver-ERP-14H",
        source_type=NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        mapping_version=NAVER_ORDER_TIMELINE_MAPPING_VERSION,
        dedupe_key=expected_dedupe_key,
        raw_response_saved=False,
        privacy_fields_redacted=True,
        address_saved=False,
        safe_metadata=safe_metadata,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    result.update({
        "status": "timeline_event_written",
        "event_rows_written": 1,
        "timeline_rows_written": True,
        "event_row_id": row.id,
        "safe_metadata": safe_metadata,
    })
    return result


def _collect_json_field_names(payload: object) -> list[str]:
    names: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            sanitized = re.sub(r"[^A-Za-z0-9_.-]", "", str(key))[:80]
            if sanitized:
                names.append(sanitized)
            names.extend(_collect_json_field_names(value))
    elif isinstance(payload, list):
        for item in payload:
            names.extend(_collect_json_field_names(item))
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return unique


def _json_payload_has_record(payload: object) -> bool:
    if isinstance(payload, dict):
        if any(isinstance(value, dict) for value in payload.values()):
            return True
        return any(isinstance(value, list) and bool(value) for value in payload.values())
    if isinstance(payload, list):
        return bool(payload)
    return payload is not None


def _naver_readonly_error_code(response: httpx.Response, *, scope: str | None = None) -> str:
    if response.status_code in {401, 403}:
        return api_credential_readiness_service._classify_naver_forbidden_response(
            response,
            stage="readonly",
            scope=scope,
        )[0]
    return "readonly_request_failed"


def _build_naver_order_preview_business_status_summary(preview_status: str) -> list[str]:
    if preview_status == "success_empty":
        return [
            "本时间窗口暂无订单变更",
            "本次未写入本地订单数据",
            "本次未保存订单原始响应",
            "正式订单同步仍未开放",
        ]
    if preview_status == "success":
        return [
            "订单读取已完成微量只读预览",
            "本次未写入本地订单数据",
            "本次未保存订单原始响应",
            "正式订单同步仍未开放",
        ]
    if preview_status == "failed":
        return [
            "订单微量只读预览失败",
            "本次未写入本地订单数据",
            "本次未保存订单原始响应",
            "请检查 Naver API 权限、IP 白名单或时间窗口",
        ]
    return [
        "订单读取暂未开放真实测试",
        "默认不会请求 Naver 订单接口",
        "正式订单同步仍未开放",
    ]


def _build_naver_order_preview_business_message(preview_status: str) -> str:
    if preview_status == "success_empty":
        return "Naver 订单接口已连接。当前时间范围内没有新的订单变更，暂时不需要处理订单同步。"
    if preview_status == "success":
        return "Naver 订单接口已连接。本次只完成订单只读预览，没有写入本地订单。"
    if preview_status == "failed":
        return "Naver 订单只读预览失败，请检查 Naver API 权限、允许 IP 或连接资料。"
    return "Naver 订单只读预览尚未开放真实请求。"


def _build_naver_order_preview_result(
    *,
    store_id: int,
    credential_id: int,
    start_datetime: str,
    end_datetime: str,
    page: int,
    size: int,
    order_status: str,
    guardrail_status: str,
    preview_status: str,
    test_status: str,
    error_code: str | None,
    field_observation: dict,
    sample_ids: list[str],
    has_more: bool,
    would_create: int,
    would_update: int,
    local_sync_result: dict | None = None,
) -> dict:
    safe_keyword_flags = dict(
        field_observation.get("safe_keyword_flags")
        or api_credential_readiness_service._empty_naver_safe_keyword_flags()
    )
    business_error_hint = field_observation.get("business_error_hint") or api_credential_readiness_service._naver_business_error_hint(error_code)
    return {
        "store_id": store_id,
        "credential_id": credential_id,
        "platform": "naver",
        "preview_type": "orders",
        "source_type": NAVER_ORDER_PREVIEW_SOURCE_TYPE,
        "guardrail_status": guardrail_status,
        "preview_status": preview_status,
        "test_status": test_status,
        "error_code": error_code,
        "safe_keyword_flags": safe_keyword_flags,
        "business_error_hint": business_error_hint,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "order_status": order_status,
        "page": page,
        "size": size,
        "has_more": has_more,
        "would_create": would_create,
        "would_update": would_update,
        "local_sync_result": local_sync_result or _default_naver_order_local_sync_result(False),
        "sample_ids": sample_ids,
        "field_observation": field_observation,
        "detail_preview": field_observation.get("detail_preview"),
        "complete_field_preview": field_observation.get("complete_field_preview")
        or _default_naver_order_complete_field_preview(False),
        "business_message": _build_naver_order_preview_business_message(preview_status),
        "business_status_summary": _build_naver_order_preview_business_status_summary(preview_status),
        "semantic_notice": "Readonly micro preview only. No local order rows were written.",
    }


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


def _to_coupang_sales_payload(item: dict, synced_at: datetime) -> dict | None:
    if not isinstance(item, dict):
        return None
    recognition_date = _extract_date_by_keys(item, ("recognitionDate", "revenueRecognitionDate"))
    if recognition_date is None:
        return None
    external_sales_id = _resolve_sales_external_id(item, recognition_date)
    if external_sales_id is None:
        return None
    return {
        "external_sales_id": external_sales_id,
        "recognition_date": recognition_date,
        "order_id": _bounded_text(_extract_scalar_by_keys(item, ("orderId", "orderID")), 120),
        "order_sheet_id": _bounded_text(_extract_scalar_by_keys(item, ("orderSheetId", "order_sheet_id")), 120),
        "shipment_box_id": _bounded_text(_extract_scalar_by_keys(item, ("shipmentBoxId", "shipment_box_id")), 120),
        "product_id": _bounded_text(_extract_scalar_by_keys(item, ("productId", "sellerProductId", "product_id")), 120),
        "vendor_item_id": _bounded_text(_extract_scalar_by_keys(item, ("vendorItemId", "vendor_item_id")), 120),
        "sale_type": _bounded_text(_extract_scalar_by_keys(item, ("saleType", "salesType", "sale_type")), 60),
        "status": _bounded_text(_extract_scalar_by_keys(item, ("status", "statusName")), 60),
        "currency": _extract_scalar_by_keys(item, ("currency", "currencyCode")) or "KRW",
        "sale_amount": _extract_krw_amount_by_keys(item, ("saleAmount", "salesAmount", "sale_amount")),
        "total_sale": _extract_krw_amount_by_keys(item, ("totalSale", "total_sale")),
        "discount_amount": _extract_krw_amount_by_keys(item, ("discountAmount", "discount_amount")),
        "refund_amount": _extract_krw_amount_by_keys(item, ("refundAmount", "refund_amount")),
        "commission_amount": _extract_krw_amount_by_keys(item, ("commissionAmount", "commission_amount")),
        "fee_amount": _extract_krw_amount_by_keys(item, ("feeAmount", "serviceFee", "fee_amount")),
        "settlement_target_amount": _extract_krw_amount_by_keys(item, ("settlementTargetAmount", "settlement_target_amount")),
        "settlement_amount": _extract_krw_amount_by_keys(item, ("settlementAmount", "settlement_amount")),
        "observed_fields": _extract_allowed_observed_fields(item),
        "last_synced_at": synced_at,
    }


def _resolve_sales_external_id(item: dict, recognition_date: date) -> str | None:
    stable_id = _extract_scalar_by_keys(
        item,
        (
            "revenueId",
            "salesId",
            "saleId",
            "transactionId",
            "revenueHistoryId",
            "salesHistoryId",
        ),
    )
    if stable_id:
        return _bounded_text(str(stable_id), 160) or str(stable_id)

    identity_fields = {
        "recognitionDate": recognition_date.isoformat(),
        "orderId": _extract_scalar_by_keys(item, ("orderId", "orderID")),
        "orderSheetId": _extract_scalar_by_keys(item, ("orderSheetId",)),
        "shipmentBoxId": _extract_scalar_by_keys(item, ("shipmentBoxId",)),
        "productId": _extract_scalar_by_keys(item, ("productId", "sellerProductId")),
        "vendorItemId": _extract_scalar_by_keys(item, ("vendorItemId",)),
        "saleType": _extract_scalar_by_keys(item, ("saleType", "salesType")),
        "status": _extract_scalar_by_keys(item, ("status", "statusName")),
    }
    hash_payload = {key: value for key, value in identity_fields.items() if value not in {None, ""}}
    has_platform_identity = any(
        hash_payload.get(key)
        for key in ("orderId", "orderSheetId", "shipmentBoxId", "productId", "vendorItemId")
    )
    has_classification = bool(hash_payload.get("saleType") or hash_payload.get("status"))
    if not has_platform_identity or not has_classification:
        return None

    # Amount fields are a last-resort collision reducer only; if Coupang later corrects
    # amounts, this fallback id can change. Stable platform ids remain preferred.
    for key in (
        "saleAmount",
        "salesAmount",
        "totalSale",
        "discountAmount",
        "refundAmount",
        "commissionAmount",
        "feeAmount",
        "serviceFee",
        "settlementTargetAmount",
        "settlementAmount",
    ):
        value = _extract_scalar_by_keys(item, (key,))
        if value not in {None, ""}:
            hash_payload[key] = value

    serialized = json.dumps(hash_payload, sort_keys=True, ensure_ascii=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
    return f"coupang_sales_v1:{digest}"


def _upsert_coupang_sales_details(db: Session, store_id: int, items: list[dict]) -> dict:
    created = 0
    updated = 0
    unchanged = 0
    business_fields = (
        "recognition_date",
        "order_id",
        "order_sheet_id",
        "shipment_box_id",
        "product_id",
        "vendor_item_id",
        "sale_type",
        "status",
        "currency",
        "sale_amount",
        "total_sale",
        "discount_amount",
        "refund_amount",
        "commission_amount",
        "fee_amount",
        "settlement_target_amount",
        "settlement_amount",
        "observed_fields",
    )
    for item in items:
        external_sales_id = item["external_sales_id"]
        existing = db.scalar(
            select(PlatformSalesDetail).where(
                PlatformSalesDetail.store_id == store_id,
                PlatformSalesDetail.platform == "coupang",
                PlatformSalesDetail.external_sales_id == external_sales_id,
            )
        )
        if existing is None:
            db.add(PlatformSalesDetail(
                store_id=store_id,
                platform="coupang",
                source_type=COUPANG_FINANCIAL_SOURCE_TYPE,
                **item,
            ))
            created += 1
            continue

        business_changed = False
        for field in business_fields:
            new_value = item.get(field)
            if getattr(existing, field) != new_value:
                setattr(existing, field, new_value)
                business_changed = True
        existing.source_type = COUPANG_FINANCIAL_SOURCE_TYPE
        existing.last_synced_at = item["last_synced_at"]
        if business_changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return {"created": created, "updated": updated, "unchanged": unchanged}


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


def _to_coupang_settlement_payload(item: dict, synced_at: datetime) -> dict | None:
    if not isinstance(item, dict):
        return None
    revenue_month = _bounded_text(
        _extract_scalar_by_keys(item, ("revenueRecognitionYearMonth", "revenue_recognition_year_month")),
        7,
    )
    if not revenue_month:
        from_date = _extract_date_by_keys(item, ("revenueRecognitionDateFrom", "recognitionDateFrom"))
        revenue_month = from_date.isoformat()[:7] if from_date else None
    if not revenue_month:
        return None

    external_settlement_id = _resolve_settlement_external_id(item)
    return {
        "external_settlement_id": external_settlement_id,
        "revenue_recognition_year_month": revenue_month,
        "settlement_type": _bounded_text(_extract_scalar_by_keys(item, ("settlementType", "settlement_type")), 60),
        "settlement_date": _extract_date_by_keys(item, ("settlementDate", "settlement_date")),
        "revenue_recognition_date_from": _extract_date_by_keys(
            item,
            ("revenueRecognitionDateFrom", "revenue_recognition_date_from", "recognitionDateFrom"),
        ),
        "revenue_recognition_date_to": _extract_date_by_keys(
            item,
            ("revenueRecognitionDateTo", "revenue_recognition_date_to", "recognitionDateTo"),
        ),
        "currency": _extract_scalar_by_keys(item, ("currency", "currencyCode")) or "KRW",
        "total_sale": _extract_krw_amount_by_keys(item, ("totalSale", "total_sale")),
        "service_fee": _extract_krw_amount_by_keys(item, ("serviceFee", "service_fee")),
        "settlement_target_amount": _extract_krw_amount_by_keys(item, ("settlementTargetAmount", "settlement_target_amount")),
        "settlement_amount": _extract_krw_amount_by_keys(item, ("settlementAmount", "settlement_amount")),
        "last_amount": _extract_krw_amount_by_keys(item, ("lastAmount", "last_amount")),
        "pending_released_amount": _extract_krw_amount_by_keys(item, ("pendingReleasedAmount", "pending_released_amount")),
        "dedicated_delivery_amount": _extract_krw_amount_by_keys(item, ("dedicatedDeliveryAmount", "dedicated_delivery_amount")),
        "seller_service_fee": _extract_krw_amount_by_keys(item, ("sellerServiceFee", "seller_service_fee")),
        "courantee_fee": _extract_krw_amount_by_keys(item, ("couranteeFee", "courantee_fee")),
        "deduction_amount": _extract_krw_amount_by_keys(item, ("deductionAmount", "deduction_amount")),
        "final_amount": _extract_krw_amount_by_keys(item, ("finalAmount", "final_amount")),
        "observed_fields": _extract_allowed_observed_fields(item),
        "last_synced_at": synced_at,
    }


def _resolve_settlement_external_id(item: dict) -> str:
    stable_id = _extract_scalar_by_keys(
        item,
        (
            "settlementId",
            "settlementID",
            "settlementNo",
            "settlementNumber",
            "settlementSequence",
            "settlementSeq",
            "paymentId",
            "transactionId",
        ),
    )
    if stable_id:
        return _bounded_text(str(stable_id), 160) or str(stable_id)

    stable_identity = {
        "revenueRecognitionYearMonth": _extract_scalar_by_keys(item, ("revenueRecognitionYearMonth",)),
        "settlementType": _extract_scalar_by_keys(item, ("settlementType",)),
        "settlementDate": _extract_scalar_by_keys(item, ("settlementDate",)),
        "revenueRecognitionDateFrom": _extract_scalar_by_keys(item, ("revenueRecognitionDateFrom",)),
        "revenueRecognitionDateTo": _extract_scalar_by_keys(item, ("revenueRecognitionDateTo",)),
        "vendorItemId": _extract_scalar_by_keys(item, ("vendorItemId",)),
        "sellerProductId": _extract_scalar_by_keys(item, ("sellerProductId",)),
        "orderId": _extract_scalar_by_keys(item, ("orderId",)),
        "orderSheetId": _extract_scalar_by_keys(item, ("orderSheetId",)),
    }
    hash_payload = {key: value for key, value in stable_identity.items() if value not in {None, ""}}

    has_core_stable_identity = all(
        hash_payload.get(key)
        for key in (
            "revenueRecognitionYearMonth",
            "settlementType",
            "settlementDate",
            "revenueRecognitionDateFrom",
            "revenueRecognitionDateTo",
        )
    )
    if not has_core_stable_identity:
        for key in (
            "totalSale",
            "serviceFee",
            "settlementTargetAmount",
            "settlementAmount",
            "lastAmount",
            "pendingReleasedAmount",
            "dedicatedDeliveryAmount",
            "sellerServiceFee",
            "couranteeFee",
            "deductionAmount",
            "finalAmount",
        ):
            value = _extract_scalar_by_keys(item, (key,))
            if value not in {None, ""}:
                hash_payload[key] = value

    serialized = json.dumps(hash_payload, sort_keys=True, ensure_ascii=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
    return f"coupang_settlement_v1:{digest}"


def _extract_allowed_observed_fields(item: dict) -> list[str]:
    fields: list[str] = []
    for key, value in item.items():
        normalized_key = str(key).replace("_", "").replace("-", "").lower()
        if _is_forbidden_financial_sample_field(normalized_key):
            continue
        if isinstance(value, (dict, list)):
            continue
        fields.append(str(key))
    return sorted(dict.fromkeys(fields))


def _extract_krw_amount_by_keys(payload: object, keys: tuple[str, ...]) -> int | None:
    amount = _extract_decimal_by_keys(payload, keys)
    if amount is None:
        return None
    return int(amount)


def _extract_date_by_keys(payload: object, keys: tuple[str, ...]) -> date | None:
    value = _extract_scalar_by_keys(payload, keys)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _upsert_coupang_settlement_details(db: Session, store_id: int, items: list[dict]) -> dict:
    created = 0
    updated = 0
    unchanged = 0
    business_fields = (
        "revenue_recognition_year_month",
        "settlement_type",
        "settlement_date",
        "revenue_recognition_date_from",
        "revenue_recognition_date_to",
        "currency",
        "total_sale",
        "service_fee",
        "settlement_target_amount",
        "settlement_amount",
        "last_amount",
        "pending_released_amount",
        "dedicated_delivery_amount",
        "seller_service_fee",
        "courantee_fee",
        "deduction_amount",
        "final_amount",
        "observed_fields",
    )
    for item in items:
        external_settlement_id = item["external_settlement_id"]
        existing = db.scalar(
            select(PlatformSettlementDetail).where(
                PlatformSettlementDetail.store_id == store_id,
                PlatformSettlementDetail.platform == "coupang",
                PlatformSettlementDetail.external_settlement_id == external_settlement_id,
            )
        )
        if existing is None:
            db.add(PlatformSettlementDetail(
                store_id=store_id,
                platform="coupang",
                source_type=COUPANG_FINANCIAL_SOURCE_TYPE,
                **item,
            ))
            created += 1
            continue

        business_changed = False
        for field in business_fields:
            new_value = item.get(field)
            if getattr(existing, field) != new_value:
                setattr(existing, field, new_value)
                business_changed = True
        existing.source_type = COUPANG_FINANCIAL_SOURCE_TYPE
        existing.last_synced_at = item["last_synced_at"]
        if business_changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return {"created": created, "updated": updated, "unchanged": unchanged}


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


def _find_existing_products_by_external_ids(
    db: Session,
    store_id: int,
    platform: str,
    external_product_ids: list[str],
) -> dict[str, Product]:
    if not external_product_ids:
        return {}
    products = db.scalars(
        select(Product).where(
            Product.store_id == store_id,
            Product.platform == platform,
            Product.external_product_id.in_(external_product_ids),
        )
    ).all()
    return {product.external_product_id: product for product in products}


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
        "key",
        "accesskey",
        "header",
        "secret",
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


def _sales_sync_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "sync_type": result["sync_type"],
        "write_scope": result["write_scope"],
        "platform_write": result["platform_write"],
        "date_window": {
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "business_timezone": result["business_timezone"],
        },
        "max_pages": result["max_pages"],
        "page_count": result["page_count"],
        "next_cursor_exists": result["next_cursor_exists"],
        "total_rows": result["total_rows"],
        "created_count": result["created_count"],
        "updated_count": result["updated_count"],
        "unchanged_count": result["unchanged_count"],
        "skipped_count": result["skipped_count"],
        "sample_ids": result["sample_ids"],
        "summary_totals": result["summary_totals"],
        "semantic_notice": result["semantic_notice"],
        "date_availability_notice": result["date_availability_notice"],
        "count_semantic_notice": result["count_semantic_notice"],
    }


def _settlement_sync_summary_for_log(result: dict) -> dict:
    return {
        "source_type": result["source_type"],
        "sync_type": result["sync_type"],
        "write_scope": result["write_scope"],
        "platform_write": result["platform_write"],
        "months": result["months"],
        "date_window": {
            "start_date": result["start_date"],
            "end_date": result["end_date"],
            "business_timezone": result["business_timezone"],
        },
        "total_rows": result["total_rows"],
        "created_count": result["created_count"],
        "updated_count": result["updated_count"],
        "unchanged_count": result["unchanged_count"],
        "skipped_count": result["skipped_count"],
        "sample_ids": result["sample_ids"],
        "summary_totals": result["summary_totals"],
        "per_month": result["per_month"],
        "semantic_notice": result["semantic_notice"],
        "month_semantic_notice": result["month_semantic_notice"],
        "count_semantic_notice": result["count_semantic_notice"],
    }


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
