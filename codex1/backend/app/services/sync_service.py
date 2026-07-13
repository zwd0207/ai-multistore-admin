import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
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
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.product import Product
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.store import Store
from app.schemas.credential import DecryptedCredential
from app.services import api_credential_readiness_service
from app.services.encryption import decrypt_value
from app.services import (
    credential_service,
    customer_inquiry_service,
    operation_audit_service,
    order_service,
    product_service,
    sync_log_service,
)
from app.services.operator_trial_service import assert_legacy_naver_customer_inquiry_sync_closed
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
NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE = "naver_customer_inquiry_real_sync"
NAVER_ORDER_TIMELINE_MAPPING_VERSION = "naver_order_status_timeline_mock_mapper_v1"
COUPANG_ORDER_SOURCE_TYPE = "real_coupang"
COUPANG_PRODUCT_SOURCE_TYPE = "real_coupang"
COUPANG_FINANCIAL_SOURCE_TYPE = "real_coupang"
COUPANG_ORDER_PREVIEW_MAX_DAYS = 3
COUPANG_FINANCIAL_PREVIEW_MAX_DAYS = 7
NAVER_ORDER_PREVIEW_MAX_DAYS = 7
NAVER_ORDER_SINGLE_WRITE_MAX_DAYS = 1
NAVER_ORDER_MANUAL_BATCH_MAX_COUNT = 20
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
    manual_approval: bool = False,
    backup_path: str | None = None,
    backup_sha256: str | None = None,
    actor_context: dict | None = None,
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
        manual_approval=manual_approval,
        backup_path=backup_path,
        backup_sha256=backup_sha256,
        actor_context=actor_context,
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
        manual_approval=manual_approval,
        backup_path=backup_path,
        backup_sha256=backup_sha256,
        actor_context=actor_context,
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


def _default_naver_customer_inquiry_date_range(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    safe_end = end_date or get_business_date()
    safe_start = start_date or (safe_end - timedelta(days=7))
    if safe_start > safe_end:
        raise ApiError(
            message="Naver customer inquiry start_date must be less than or equal to end_date",
            error_code="date_range_invalid",
            status_code=400,
        )
    if safe_end - safe_start > timedelta(days=31):
        raise ApiError(
            message="Naver customer inquiry sync window must be 31 days or less",
            error_code="date_range_invalid",
            status_code=400,
            detail={"max_window_days": 31},
        )
    return safe_start, safe_end


def _request_naver_customer_inquiries(
    *,
    api_base: str,
    headers: dict[str, str],
    start_date: date,
    end_date: date,
    answered: bool | None,
    page: int,
    size: int,
) -> dict:
    params: dict[str, str | int] = {
        "page": int(page),
        "size": max(10, min(int(size), 200)),
        "startSearchDate": start_date.isoformat(),
        "endSearchDate": end_date.isoformat(),
    }
    if answered is not None:
        params["answered"] = "true" if answered else "false"
    diagnostics = {
        "endpoint": "/v1/pay-user/inquiries",
        "query_param_keys": list(params.keys()),
        "date_format": "YYYY-MM-DD",
        "answered_filter_used": answered is not None,
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            f"{api_base}/v1/pay-user/inquiries",
            headers=headers,
            params=params,
        )
    diagnostics["http_status"] = response.status_code
    if response.status_code >= 400:
        diagnostics.update(_extract_naver_error_diagnostics(response))
        return {
            "success": False,
            "http_status": response.status_code,
            "error_code": _naver_readonly_error_code(response, scope="customer_inquiry"),
            "safe_error": {
                "platform_error_code": diagnostics.get("naver_error_code"),
                "platform_error_fields": diagnostics.get("naver_error_fields") or [],
            },
            "diagnostics": diagnostics,
        }
    return {
        "success": True,
        "http_status": response.status_code,
        "payload": response.json(),
        "diagnostics": diagnostics,
    }


def _extract_naver_customer_inquiry_items(payload: object) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        return [item for item in payload["content"] if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return _extract_naver_customer_inquiry_items(payload["data"])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _split_naver_product_order_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_bounded_text(str(item).strip(), 120) for item in value if str(item or "").strip()]
    return [
        _bounded_text(part.strip(), 120)
        for part in str(value).split(",")
        if part.strip()
    ]


def _naver_customer_inquiry_status(item: dict) -> str:
    if bool(item.get("answered")):
        return "answered"
    return "open"


def _map_naver_customer_inquiry(item: dict) -> dict:
    inquiry_no = _extract_scalar_by_keys(item, ("inquiryNo", "inquiry_no"))
    registered_at = _parse_preview_iso_datetime(
        _extract_scalar_by_keys(item, ("inquiryRegistrationDateTime", "registeredAt", "createdAt"))
    ) or get_utc_now()
    answered_at = _parse_preview_iso_datetime(
        _extract_scalar_by_keys(item, ("answerRegistrationDateTime", "answeredAt"))
    )
    product_order_ids = _split_naver_product_order_ids(
        item.get("productOrderIdList") or item.get("product_order_id_list")
    )
    answer_content = _bounded_text(_extract_scalar_by_keys(item, ("answerContent", "answer_content")), 1000)
    return {
        "external_inquiry_id": _bounded_text(str(inquiry_no or ""), 120) or "unknown-inquiry",
        "inquiry_type": _bounded_text(_extract_scalar_by_keys(item, ("category", "inquiryType")), 50) or "platform_message",
        "customer_name": _bounded_text(_extract_scalar_by_keys(item, ("customerName", "customer_name")), 120),
        "title": _bounded_text(_extract_scalar_by_keys(item, ("title",)), 300) or "Naver customer inquiry",
        "content": _bounded_text(_extract_scalar_by_keys(item, ("inquiryContent", "content")), 4000) or "",
        "status": _naver_customer_inquiry_status(item),
        "received_at": registered_at,
        "answered_at": answered_at,
        "raw_data": {
            "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
            "mapping_version": "naver_customer_inquiry_v1",
            "raw_response_saved": False,
            "platform_write": False,
            "technical_sensitive_fields_suppressed": True,
            "order_id": _bounded_text(_extract_scalar_by_keys(item, ("orderId", "order_id")), 120),
            "product_order_id_list": product_order_ids,
            "product_no": _bounded_text(_extract_scalar_by_keys(item, ("productNo", "product_no")), 120),
            "product_name": _bounded_text(_extract_scalar_by_keys(item, ("productName", "product_name")), 300),
            "product_order_option": _bounded_text(_extract_scalar_by_keys(item, ("productOrderOption", "product_order_option")), 300),
            "answered": bool(item.get("answered")),
            "answer_content": answer_content,
            "answer_registration_date_time": answered_at.isoformat() if answered_at else None,
        },
    }


def _customer_inquiry_sync_result_from_error(
    *,
    store_id: int,
    error_code: str,
    message: str | None = None,
) -> dict:
    return {
        "status": "failed",
        "store_id": store_id,
        "platform": "naver",
        "resource": "customer_inquiries",
        "message": message or _manual_batch_message_for_error("naver", error_code, "Naver 客服消息同步失败"),
        "error_code": error_code,
        "created_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "deleted_count": 0,
        "platform_write": False,
        "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
        "raw_response_saved": False,
    }


def sync_naver_customer_inquiries(
    db: Session,
    *,
    store_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    answered: bool | None = None,
    page: int = 1,
    size: int = 50,
) -> dict:
    assert_legacy_naver_customer_inquiry_sync_closed(get_settings())
    credential = _ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
    safe_start, safe_end = _default_naver_customer_inquiry_date_range(start_date, end_date)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="naver",
        sync_type=NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
        message="naver customer inquiry sync started",
        raw_summary={
            "stage": "started",
            "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
            "endpoint": "/v1/pay-user/inquiries",
            "start_date": safe_start.isoformat(),
            "end_date": safe_end.isoformat(),
            "platform_write": False,
            "raw_response_saved": False,
        },
    )
    try:
        context = _build_naver_token_context_from_credential(credential)
        access_token, token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        request_result = _request_naver_customer_inquiries(
            api_base=context["api_base"],
            headers={"Authorization": f"Bearer {access_token}"},
            start_date=safe_start,
            end_date=safe_end,
            answered=answered,
            page=page,
            size=size,
        )
        if not request_result.get("success"):
            error_code = str(request_result.get("error_code") or "readonly_request_failed")
            result = _customer_inquiry_sync_result_from_error(store_id=store_id, error_code=error_code)
            result["http_status"] = request_result.get("http_status")
            result["sync_log"] = sync_log_service.fail_sync_log(
                db,
                sync_log_id=sync_log["id"],
                message="naver customer inquiry sync failed",
                error_detail=_mask_sensitive_text(result["message"]),
                raw_summary={
                    "stage": "failed",
                    "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
                    "error_code": error_code,
                    "http_status": request_result.get("http_status"),
                    "platform_write": False,
                    "raw_response_saved": False,
                },
            )
            return result

        items = [_map_naver_customer_inquiry(item) for item in _extract_naver_customer_inquiry_items(request_result.get("payload"))]
        write_result = customer_inquiry_service.upsert_customer_inquiries(db, store_id, "naver", items)
        result = {
            "status": "success",
            "store_id": store_id,
            "platform": "naver",
            "resource": "customer_inquiries",
            "message": (
                f"Naver 客服消息本地同步完成：新增 {int(write_result.get('created') or 0)}，"
                f"更新 {int(write_result.get('updated') or 0)}。"
            ),
            "error_code": None,
            "created_count": int(write_result.get("created") or 0),
            "updated_count": int(write_result.get("updated") or 0),
            "skipped_count": 0,
            "deleted_count": 0,
            "platform_write": False,
            "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
            "raw_response_saved": False,
            "token_http_status": token_status,
            "http_status": request_result.get("http_status"),
            "page": page,
            "size": size,
            "start_date": safe_start.isoformat(),
            "end_date": safe_end.isoformat(),
        }
        result["sync_log"] = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver customer inquiry sync completed",
            raw_summary={
                "stage": "completed",
                "status": "success",
                "created_count": result["created_count"],
                "updated_count": result["updated_count"],
                "source_type": NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
                "platform_write": False,
                "raw_response_saved": False,
            },
        )
        return result
    except api_credential_readiness_service.NaverReadonlyAuthError as exc:
        db.rollback()
        result = _customer_inquiry_sync_result_from_error(
            store_id=store_id,
            error_code=exc.error_code,
            message=_manual_batch_message_for_error("naver", exc.error_code),
        )
        result["http_status"] = exc.http_status
        result["sync_log"] = sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver customer inquiry sync auth failed",
            error_detail=_mask_sensitive_text(result["message"]),
            raw_summary={
                "stage": "failed",
                "status": "failed",
                "error_code": exc.error_code,
                "http_status": exc.http_status,
                "platform_write": False,
                "raw_response_saved": False,
            },
        )
        return result
    except Exception as exc:
        db.rollback()
        error_code = getattr(exc, "error_code", None) or "customer_inquiry_sync_failed"
        result = _customer_inquiry_sync_result_from_error(
            store_id=store_id,
            error_code=str(error_code),
            message=getattr(exc, "message", None) or "Naver 客服消息同步失败",
        )
        result["sync_log"] = sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver customer inquiry sync failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "status": "failed",
                "error_code": str(error_code),
                "platform_write": False,
                "raw_response_saved": False,
            },
        )
        return result


def _find_customer_inquiry_for_reply(
    db: Session,
    *,
    store_id: int,
    inquiry_id: int | None,
    external_inquiry_id: str | None,
) -> CustomerInquiry:
    statement = select(CustomerInquiry).where(
        CustomerInquiry.store_id == store_id,
        CustomerInquiry.platform == "naver",
    )
    if inquiry_id is not None:
        statement = statement.where(CustomerInquiry.id == inquiry_id)
    else:
        statement = statement.where(CustomerInquiry.external_inquiry_id == str(external_inquiry_id or "").strip())
    inquiry = db.scalar(statement)
    if inquiry is None:
        raise ApiError(
            message="Naver customer inquiry is not found in local ERP",
            error_code="customer_inquiry_not_found",
            status_code=404,
            detail={"store_id": store_id, "inquiry_id": inquiry_id, "external_inquiry_id": external_inquiry_id},
        )
    return inquiry


def _request_naver_customer_inquiry_reply(
    *,
    api_base: str,
    headers: dict[str, str],
    inquiry_no: str,
    answer_comment: str,
    answer_template_id: str | None,
) -> dict:
    payload: dict[str, str] = {"answerComment": answer_comment}
    if answer_template_id:
        payload["answerTemplateId"] = answer_template_id
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base}/v1/pay-merchant/inquiries/{inquiry_no}/answer",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
        )
    diagnostics = {
        "endpoint": "/v1/pay-merchant/inquiries/{inquiryNo}/answer",
        "http_status": response.status_code,
        "body_field_keys": list(payload.keys()),
        "answerComment": True,
    }
    if response.status_code >= 400:
        diagnostics.update(_extract_naver_error_diagnostics(response))
        text = response.text or ""
        error_code = _naver_readonly_error_code(response, scope="customer_inquiry_reply")
        if "ERR-NC-101010" in text:
            error_code = "already_answered"
        return {
            "success": False,
            "http_status": response.status_code,
            "error_code": error_code,
            "diagnostics": diagnostics,
        }
    return {
        "success": True,
        "http_status": response.status_code,
        "diagnostics": diagnostics,
    }


def reply_naver_customer_inquiry(
    db: Session,
    *,
    store_id: int,
    inquiry_id: int | None = None,
    external_inquiry_id: str | None = None,
    answer_comment: str,
    answer_template_id: str | None = None,
    manual_approval: bool = False,
    final_operator_confirmation: bool = False,
    actor_context: dict | None = None,
) -> dict:
    ensure_store_exists(db, store_id)
    safe_answer = _bounded_text(str(answer_comment or "").strip(), 4000)
    inquiry = _find_customer_inquiry_for_reply(
        db,
        store_id=store_id,
        inquiry_id=inquiry_id,
        external_inquiry_id=external_inquiry_id,
    )
    base_result = {
        "status": "blocked",
        "store_id": store_id,
        "platform": "naver",
        "resource": "customer_inquiries",
        "inquiry_id": inquiry.id,
        "external_inquiry_id": inquiry.external_inquiry_id,
        "message": "Naver 客服回复未提交：需要人工确认发送。",
        "error_code": None,
        "platform_write": False,
        "platform_write_attempted": False,
        "manual_approval": bool(manual_approval),
        "final_operator_confirmation": bool(final_operator_confirmation),
        "raw_response_saved": False,
        "secrets_saved": False,
        "answerComment": True,
    }
    if manual_approval is not True or final_operator_confirmation is not True:
        return {**base_result, "error_code": "manual_confirmation_required"}
    if not safe_answer:
        return {**base_result, "error_code": "answer_comment_required", "message": "Naver 客服回复未提交：回复内容不能为空。"}

    inquiry_no = str(inquiry.external_inquiry_id or "").strip()
    if not re.fullmatch(r"\d{1,30}", inquiry_no):
        return {**base_result, "error_code": "invalid_inquiry_no", "message": "Naver 客服回复未提交：本地消息编号不是有效的 Naver inquiryNo。"}

    credential = _ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="naver",
        sync_type="naver_customer_inquiry_reply",
        message="naver customer inquiry reply started",
        raw_summary={
            "stage": "started",
            "endpoint": "/v1/pay-merchant/inquiries/{inquiryNo}/answer",
            "platform_write": True,
            "manual_approval": True,
            "final_operator_confirmation": True,
            "raw_response_saved": False,
        },
    )
    try:
        context = _build_naver_token_context_from_credential(credential)
        access_token, token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        request_result = _request_naver_customer_inquiry_reply(
            api_base=context["api_base"],
            headers={"Authorization": f"Bearer {access_token}"},
            inquiry_no=inquiry_no,
            answer_comment=safe_answer,
            answer_template_id=_bounded_text(answer_template_id, 120),
        )
        now = get_utc_now()
        if request_result.get("success") or request_result.get("error_code") == "already_answered":
            safe_raw = dict(inquiry.raw_data or {})
            safe_raw.update({
                "platform_reply_submitted": request_result.get("success") is True,
                "platform_reply_already_existed": request_result.get("error_code") == "already_answered",
                "platform_reply_endpoint": "/v1/pay-merchant/inquiries/{inquiryNo}/answer",
                "platform_write": request_result.get("success") is True,
                "manual_approval": True,
                "final_operator_confirmation": True,
                "answer_content": safe_answer,
                "answer_registration_date_time": now.isoformat(),
                "raw_response_saved": False,
                "secrets_saved": False,
            })
            inquiry.status = "answered"
            inquiry.answered_at = now
            inquiry.raw_data = safe_raw
            db.commit()
            result_status = "success" if request_result.get("success") else "already_answered"
            result = {
                **base_result,
                "status": result_status,
                "message": (
                    "Naver 客服回复已提交。"
                    if result_status == "success"
                    else "Naver 平台提示该消息已有回复，本地已标记为已回复。"
                ),
                "error_code": None if result_status == "success" else "already_answered",
                "platform_write": result_status == "success",
                "platform_write_attempted": True,
                "token_http_status": token_status,
                "http_status": request_result.get("http_status"),
            }
            result["sync_log"] = sync_log_service.finish_sync_log(
                db,
                sync_log_id=sync_log["id"],
                message="naver customer inquiry reply completed",
                raw_summary={
                    "stage": "completed",
                    "status": result_status,
                    "platform_write": result["platform_write"],
                    "platform_write_attempted": True,
                    "manual_approval": True,
                    "final_operator_confirmation": True,
                    "raw_response_saved": False,
                },
            )
            return result

        error_code = str(request_result.get("error_code") or "customer_inquiry_reply_failed")
        result = {
            **base_result,
            "status": "failed",
            "message": _manual_batch_message_for_error("naver", error_code, "Naver 客服回复提交失败"),
            "error_code": error_code,
            "platform_write": False,
            "platform_write_attempted": True,
            "http_status": request_result.get("http_status"),
        }
        result["sync_log"] = sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver customer inquiry reply failed",
            error_detail=_mask_sensitive_text(result["message"]),
            raw_summary={
                "stage": "failed",
                "status": "failed",
                "error_code": error_code,
                "http_status": request_result.get("http_status"),
                "platform_write": False,
                "platform_write_attempted": True,
                "raw_response_saved": False,
            },
        )
        return result
    except Exception as exc:
        db.rollback()
        error_code = getattr(exc, "error_code", None) or "customer_inquiry_reply_failed"
        result = {
            **base_result,
            "status": "failed",
            "message": getattr(exc, "message", None) or "Naver 客服回复提交失败",
            "error_code": str(error_code),
            "platform_write": False,
            "platform_write_attempted": True,
        }
        result["sync_log"] = sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver customer inquiry reply failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "status": "failed",
                "error_code": str(error_code),
                "platform_write": False,
                "platform_write_attempted": True,
                "raw_response_saved": False,
            },
        )
        return result


MANUAL_BATCH_SYNC_TYPE = "manual_batch_sync"
MANUAL_BATCH_SUPPORTED_PLATFORMS = {"naver", "coupang"}
MANUAL_BATCH_RESOURCE_LABELS = {
    "products": "商品",
    "orders": "订单",
    "customer_inquiries": "客服消息",
}
MANUAL_BATCH_PLATFORM_LABELS = {
    "naver": "Naver",
    "coupang": "Coupang",
}
MANUAL_BATCH_CONNECTION_BLOCKER_CODES = {
    "ip_not_allowed",
    "auth_failed",
    "permission_forbidden",
    "product_api_not_allowed",
    "order_api_not_allowed",
    "credential_not_ready",
    "credential_invalid",
    "credential_not_found",
    "channel_no_missing",
    "channel_selection_required",
}
MANUAL_BATCH_READ_RESOURCES = {"products", "orders", "customer_inquiries"}
MANUAL_BATCH_CONNECTION_BLOCKED_MESSAGES = {
    "products": "未执行商品同步：平台连接未通过，请先重新同步验证",
    "orders": "未执行订单同步：平台连接未通过，请先重新同步验证",
    "customer_inquiries": "客服消息暂未接入真实平台；本次平台连接也未通过",
}


def _manual_batch_platforms(platforms: list[str] | None, store_platform: str) -> list[str]:
    requested = []
    for platform in platforms or []:
        normalized = normalize_platform(platform)
        if normalized in MANUAL_BATCH_SUPPORTED_PLATFORMS and normalized not in requested:
            requested.append(normalized)
    if requested:
        return requested
    return [store_platform] if store_platform in MANUAL_BATCH_SUPPORTED_PLATFORMS else []


def _manual_batch_item(
    *,
    platform: str,
    resource: str,
    status: str,
    message: str,
    error_code: str | None = None,
    created_count: int = 0,
    updated_count: int = 0,
    skipped_count: int = 0,
    deleted_count: int = 0,
    full_snapshot: bool = False,
    delete_executed: bool = False,
    source_type: str | None = None,
    raw_status: str | None = None,
) -> dict:
    return {
        "status": status,
        "platform": platform,
        "resource": resource,
        "message": message,
        "error_code": error_code,
        "created_count": int(created_count or 0),
        "updated_count": int(updated_count or 0),
        "skipped_count": int(skipped_count or 0),
        "deleted_count": int(deleted_count or 0),
        "full_snapshot": bool(full_snapshot),
        "delete_executed": bool(delete_executed),
        "platform_write": False,
        "source_type": source_type,
        "raw_status": raw_status,
    }


def _manual_batch_message_for_error(platform: str, error_code: str | None, fallback: str | None = None) -> str:
    label = MANUAL_BATCH_PLATFORM_LABELS.get(platform, platform)
    code = str(error_code or "").lower()
    if code == "ip_not_allowed":
        return f"{label}：IP 白名单未通过"
    if code in {"auth_failed", "permission_forbidden", "product_api_not_allowed", "order_api_not_allowed"} or "permission" in code:
        return f"{label}：API 权限未开通"
    if code == "channel_no_missing":
        return f"{label}：未识别到店铺频道编号，请重新同步自动识别"
    if code == "channel_selection_required":
        return f"{label}：识别到多个店铺频道，请先选择当前店铺对应的频道"
    if code in {"credential_not_ready", "credential_invalid"}:
        return f"{label}：API 资料未配置完整"
    if code == "blocked_by_connection":
        return "未执行同步：平台连接未通过，请先重新同步验证"
    if code in {"real_api_test_disabled", "guardrail_blocked"}:
        return f"{label}：当前同步门禁未开放"
    if code == "store_platform_mismatch":
        return f"当前店铺不是 {label} 店铺，已跳过"
    return fallback or f"{label}：同步失败"


def _manual_batch_item_from_error(platform: str, resource: str, exc: Exception) -> dict:
    raw_code = getattr(exc, "error_code", None) or "manual_sync_failed"
    error_code = "ip_not_allowed" if platform == "coupang" and str(raw_code).lower() == "auth_failed" else raw_code
    message = _manual_batch_message_for_error(platform, error_code, getattr(exc, "message", str(exc)))
    skipped_codes = {"store_platform_mismatch", "real_api_test_disabled", "guardrail_blocked"}
    status = "skipped" if str(raw_code).lower() in skipped_codes else "failed"
    return _manual_batch_item(
        platform=platform,
        resource=resource,
        status=status,
        message=message,
        error_code=error_code,
    )


def _manual_batch_is_connection_blocker(item: dict) -> bool:
    code = str(item.get("error_code") or "").lower()
    return code in MANUAL_BATCH_CONNECTION_BLOCKER_CODES


def _manual_batch_connection_blocked_message(resource: str) -> str:
    return MANUAL_BATCH_CONNECTION_BLOCKED_MESSAGES.get(
        resource,
        "未执行数据同步：平台连接未通过，请先重新同步验证",
    )


def _manual_batch_apply_connection_blockers(items: list[dict], platform: str) -> list[dict]:
    platform_blocked = any(
        item.get("platform") == platform and _manual_batch_is_connection_blocker(item)
        for item in items
    )
    if not platform_blocked:
        return items

    normalized: list[dict] = []
    for item in items:
        if item.get("platform") != platform or item.get("status") == "success" or _manual_batch_is_connection_blocker(item):
            normalized.append(item)
            continue

        resource = item.get("resource")
        if resource in MANUAL_BATCH_READ_RESOURCES:
            normalized.append({
                **item,
                "status": "failed",
                "message": _manual_batch_connection_blocked_message(str(resource or "")),
                "error_code": "blocked_by_connection",
                "full_snapshot": False,
                "delete_executed": False,
                "platform_write": False,
            })
            continue

        if resource == "customer_inquiries" and str(item.get("error_code") or "").lower() == "not_open":
            normalized.append({
                **item,
                "message": _manual_batch_connection_blocked_message("customer_inquiries"),
                "platform_write": False,
            })
            continue

        normalized.append(item)
    return normalized


def _manual_batch_result_status(items: list[dict]) -> str:
    if not items:
        return "skipped"
    statuses = {item.get("status") for item in items}
    if statuses == {"success"}:
        return "success"
    if "success" in statuses:
        return "partial_success"
    if "failed" in statuses:
        return "failed"
    return "skipped"


def _manual_batch_resource_message(platform: str, resource: str, result: dict) -> str:
    label = MANUAL_BATCH_PLATFORM_LABELS.get(platform, platform)
    resource_label = MANUAL_BATCH_RESOURCE_LABELS.get(resource, resource)
    created = int(result.get("created_count") or 0)
    updated = int(result.get("updated_count") or 0)
    return f"{label}{resource_label}本地同步完成：新增 {created}，更新 {updated}"


def _ensure_naver_manual_sync_channel_no(db: Session, store_id: int) -> None:
    credential = _ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
    if _naver_channel_no_configured(credential.extra_config):
        return

    smoke_result = api_credential_readiness_service.run_api_credential_smoke_test(
        db=db,
        platform="naver",
        mode="readonly",
        store_id=store_id,
        credential_id=credential.id,
        capability_scope="seller_channels",
        persist_channel_no=True,
    )
    result = (smoke_result.get("results") or [{}])[0]
    refreshed = db.get(ApiCredential, credential.id)
    if refreshed is not None and _naver_channel_no_configured(refreshed.extra_config):
        return

    if result.get("multiple_channels_observed"):
        raise ApiError(
            message="Multiple Naver seller channels require an explicit channel selection",
            error_code="channel_selection_required",
            status_code=400,
            detail={"store_id": store_id, "credential_id": credential.id},
        )
    raise ApiError(
        message="Naver seller channel could not be detected for manual sync",
        error_code=result.get("error_code") or "channel_no_missing",
        status_code=400,
        detail={"store_id": store_id, "credential_id": credential.id},
    )


def _manual_sync_naver_products(db: Session, store_id: int) -> dict:
    result = preview_naver_products(
        db,
        store_id=store_id,
        credential_id=None,
        page=1,
        size=5,
        status="ALL",
        real_preview=True,
        real_sync=True,
        manual_approval=False,
    )
    local_result = result.get("local_sync_result") or {}
    if result.get("preview_status") == "failed":
        error_code = result.get("error_code") or "readonly_request_failed"
        return _manual_batch_item(
            platform="naver",
            resource="products",
            status="failed",
            message=_manual_batch_message_for_error("naver", error_code),
            error_code=error_code,
        )
    if local_result.get("status") == "success":
        return _manual_batch_item(
            platform="naver",
            resource="products",
            status="success",
            message=_manual_batch_resource_message("naver", "products", local_result),
            created_count=local_result.get("created_count", 0),
            updated_count=local_result.get("updated_count", 0),
            skipped_count=local_result.get("skipped_count", 0),
            source_type=local_result.get("source_type") or NAVER_PRODUCT_SYNC_SOURCE_TYPE,
            raw_status=local_result.get("status"),
        )
    error_code = local_result.get("skip_reason") or result.get("error_code") or "local_sync_not_ready"
    return _manual_batch_item(
        platform="naver",
        resource="products",
        status="skipped",
        message=_manual_batch_message_for_error("naver", error_code, "Naver商品暂未写入本地"),
        error_code=error_code,
        skipped_count=local_result.get("skipped_count", 0),
        source_type=local_result.get("source_type") or NAVER_PRODUCT_SYNC_SOURCE_TYPE,
        raw_status=local_result.get("status"),
    )


def _manual_sync_naver_orders(db: Session, store_id: int) -> dict:
    end_kst = get_utc_now().astimezone(get_business_timezone())
    start_kst = end_kst - timedelta(hours=24)
    result = preview_naver_orders(
        db,
        store_id=store_id,
        credential_id=None,
        start_datetime=start_kst,
        end_datetime=end_kst,
        order_status="ALL",
        page=1,
        size=NAVER_ORDER_MANUAL_BATCH_MAX_COUNT,
        real_preview=True,
        include_detail=True,
        complete_field_preview=False,
        real_sync=True,
    )
    local_result = result.get("local_sync_result") or {}
    if result.get("preview_status") == "failed":
        error_code = result.get("error_code") or "readonly_request_failed"
        return _manual_batch_item(
            platform="naver",
            resource="orders",
            status="failed",
            message=_manual_batch_message_for_error("naver", error_code),
            error_code=error_code,
            source_type=NAVER_ORDER_SYNC_SOURCE_TYPE,
            raw_status=result.get("preview_status"),
        )

    local_status = str(local_result.get("status") or "").lower()
    safe_success_statuses = {"success", "already_exists", "skipped"}
    safe_success_reasons = {None, "", "no_changed_orders", "duplicate_external_product_order_id_hash"}
    if result.get("preview_status") in {"success", "success_empty"} and (
        local_status in safe_success_statuses
        and local_result.get("skip_reason") in safe_success_reasons
    ):
        return _manual_batch_item(
            platform="naver",
            resource="orders",
            status="success",
            message=_manual_batch_resource_message("naver", "orders", local_result),
            created_count=local_result.get("created_count", 0),
            updated_count=local_result.get("updated_count", 0),
            skipped_count=local_result.get("skipped_count", 0),
            source_type=NAVER_ORDER_SYNC_SOURCE_TYPE,
            raw_status=local_status or result.get("preview_status"),
        )

    error_code = local_result.get("skip_reason") or result.get("error_code") or "local_order_sync_not_ready"
    return _manual_batch_item(
        platform="naver",
        resource="orders",
        status="skipped",
        message=_manual_batch_message_for_error("naver", error_code, "Naver订单本地同步暂未完成"),
        error_code=error_code,
        skipped_count=local_result.get("skipped_count", 0),
        source_type=NAVER_ORDER_SYNC_SOURCE_TYPE,
        raw_status=local_status or result.get("preview_status"),
    )


def _naver_order_raw_text(raw_data: object, keys: tuple[str, ...]) -> str | None:
    if not isinstance(raw_data, dict):
        return None
    return _extract_scalar_by_keys(raw_data, keys)


def _naver_order_needs_detail_refresh(order: Order) -> bool:
    raw_data = order.raw_data if isinstance(order.raw_data, dict) else {}
    if not order.receiver_phone and not _naver_order_raw_text(raw_data, (
        "receiver_phone",
        "receiverPhone",
        "receiverTelNo",
        "receiverTelNo1",
        "receiverTelNo2",
        "tel1",
        "tel2",
    )):
        return True
    status_text = " ".join([
        str(order.order_status or ""),
        str(_naver_order_raw_text(raw_data, ("delivery_status_label_zh", "deliveryStatusLabelZh")) or ""),
        str(_naver_order_raw_text(raw_data, ("delivery_status", "deliveryStatus")) or ""),
    ]).upper()
    shipped_like = any(flag in status_text for flag in (
        "DISPATCHED",
        "DELIVERING",
        "DELIVERY",
        "SHIPPING",
        "PURCHASE_DECIDED",
        "已发货",
        "配送中",
        "配送完成",
        "已确认购买",
    ))
    has_tracking = bool(_naver_order_raw_text(raw_data, (
        "tracking_number",
        "trackingNumber",
        "shipping_tracking_number",
        "invoiceNo",
        "invoiceNumber",
        "waybillNo",
    )))
    return shipped_like and not has_tracking


def _manual_refresh_existing_naver_order_details(
    db: Session,
    *,
    store_id: int,
    max_count: int,
) -> dict:
    result = _default_naver_order_local_sync_result(True)
    result.update({
        "status": "skipped",
        "candidate_count": 0,
        "detail_refresh_existing_local_orders": True,
        "refresh_existing_local_orders": True,
        "platform_write": False,
        "platform_writes_enabled": False,
    })

    local_orders = db.scalars(
        select(Order)
        .where(
            Order.store_id == store_id,
            Order.platform == "naver",
            Order.external_product_order_id.is_not(None),
        )
        .order_by(Order.updated_at.desc(), Order.id.desc())
    ).all()
    candidates = [order for order in local_orders if _naver_order_needs_detail_refresh(order)][:max_count]
    result["candidate_count"] = len(candidates)
    if not candidates:
        result["skip_reason"] = "no_existing_orders_need_detail_refresh"
        return result

    credential = _ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
    try:
        context = _build_naver_token_context_from_credential(credential)
        access_token, _token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        headers = {"Authorization": f"Bearer {access_token}"}
        product_order_ids = [
            str(order.external_product_order_id).strip()
            for order in candidates
            if str(order.external_product_order_id or "").strip()
        ][:max_count]
        detail_result = _request_naver_order_detail_query(
            api_base=context["api_base"],
            headers=headers,
            product_order_ids=product_order_ids,
        )
        result["detail_http_status"] = detail_result.get("http_status")
        if not detail_result["success"]:
            result.update({
                "status": "blocked",
                "skip_reason": detail_result.get("error_code") or "detail_request_failed",
                "error_code": detail_result.get("error_code") or "detail_request_failed",
                "privacy_fields_redacted": True,
                "raw_response_saved": False,
            })
            return result
        detail_records = _extract_naver_order_detail_records(detail_result["payload"], product_order_ids)
        detail_previews = [
            _build_naver_order_internal_detail(item, store_id=store_id)
            for item in detail_records
        ]
        refreshed = _sync_naver_order_detail_previews_batch(
            db,
            store_id=store_id,
            detail_previews=detail_previews,
            real_sync=True,
        )
        refreshed.update({
            "detail_refresh_existing_local_orders": True,
            "refresh_existing_local_orders": True,
            "candidate_count": len(candidates),
            "detail_record_count": len(detail_records),
            "platform_write": False,
            "platform_writes_enabled": False,
            "raw_response_saved": False,
        })
        return refreshed
    except Exception as exc:
        error_code = getattr(exc, "error_code", None) or "existing_order_detail_refresh_failed"
        result.update({
            "status": "blocked",
            "skip_reason": error_code,
            "error_code": error_code,
            "privacy_fields_redacted": True,
            "raw_response_saved": False,
        })
        return result


def _naver_order_detail_field_availability(detail_preview: dict | None) -> dict[str, bool]:
    detail_preview = detail_preview if isinstance(detail_preview, dict) else {}
    return {
        "receiver_name": bool(detail_preview.get("receiver_name")),
        "receiver_phone": bool(detail_preview.get("receiver_phone")),
        "receiver_address": bool(detail_preview.get("receiver_address")),
        "delivery_company": bool(detail_preview.get("delivery_company")),
        "tracking_number": bool(detail_preview.get("tracking_number")),
    }


def refresh_single_naver_order_detail(
    db: Session,
    *,
    store_id: int,
    order_id: int,
) -> dict:
    result = {
        "status": "skipped",
        "store_id": store_id,
        "platform": "naver",
        "resource": "orders",
        "order_id": order_id,
        "created_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
        "no_change_count": 0,
        "platform_write": False,
        "platform_writes_enabled": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "field_availability": {},
    }

    store = ensure_store_exists(db, store_id)
    if normalize_platform(store.platform) != "naver":
        result.update({
            "status": "skipped",
            "skip_reason": "STORE_PLATFORM_MISMATCH",
            "error_code": "STORE_PLATFORM_MISMATCH",
            "message": "当前店铺不是 Naver 店铺，无法刷新 Naver 订单详情。",
            "skipped_count": 1,
        })
        return result

    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.store_id == store_id,
            Order.platform == "naver",
        )
    )
    if order is None:
        result.update({
            "status": "failed",
            "skip_reason": "order_not_found",
            "error_code": "order_not_found",
            "message": "订单不存在或不属于当前店铺。",
            "skipped_count": 1,
        })
        return result

    product_order_id = str(order.external_product_order_id or order.external_order_id or "").strip()
    if not product_order_id:
        result.update({
            "status": "skipped",
            "skip_reason": "product_order_id_missing",
            "error_code": "product_order_id_missing",
            "message": "本地订单缺少 Naver productOrderId，无法读取官方订单详情。",
            "skipped_count": 1,
        })
        return result

    try:
        credential = _ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
        context = _build_naver_token_context_from_credential(credential)
        access_token, _token_status = api_credential_readiness_service._request_naver_token_from_context(context)
        detail_result = _request_naver_order_detail_query(
            api_base=context["api_base"],
            headers={"Authorization": f"Bearer {access_token}"},
            product_order_ids=[product_order_id],
        )
    except Exception as exc:
        error_code = getattr(exc, "error_code", None) or "single_order_detail_refresh_failed"
        result.update({
            "status": "blocked",
            "skip_reason": error_code,
            "error_code": error_code,
            "message": _manual_batch_message_for_error(
                "naver",
                error_code,
                "Naver 订单详情刷新失败，请检查店铺 API 权限或 IP 白名单。",
            ),
            "skipped_count": 1,
            "privacy_fields_redacted": True,
        })
        return result

    result["detail_http_status"] = detail_result.get("http_status")
    if not detail_result.get("success"):
        error_code = detail_result.get("error_code") or "detail_request_failed"
        result.update({
            "status": "blocked",
            "skip_reason": error_code,
            "error_code": error_code,
            "message": _manual_batch_message_for_error(
                "naver",
                error_code,
                "Naver 订单详情读取失败，请检查店铺 API 权限或 IP 白名单。",
            ),
            "skipped_count": 1,
            "privacy_fields_redacted": True,
        })
        return result

    detail_records = _extract_naver_order_detail_records(detail_result.get("payload"), [product_order_id])
    result["detail_record_count"] = len(detail_records)
    if not detail_records:
        result.update({
            "status": "skipped",
            "skip_reason": "detail_record_missing",
            "error_code": "detail_record_missing",
            "message": "已请求 Naver 订单详情，但本次响应未返回该订单详情记录。",
            "skipped_count": 1,
        })
        return result

    detail_preview = _build_naver_order_internal_detail(detail_records[0], store_id=store_id)
    result["field_availability"] = _naver_order_detail_field_availability(detail_preview)
    privacy_gate = _validate_naver_order_detail_preview_for_local_write(
        detail_preview,
        expected_store_id=store_id,
    )
    result["privacy_gate_passed"] = privacy_gate["passed"]
    result["privacy_gate_reasons"] = privacy_gate["reasons"]
    if not privacy_gate["passed"]:
        result.update({
            "status": "blocked",
            "skip_reason": "privacy_gate_failed",
            "error_code": "privacy_gate_failed",
            "message": "Naver 订单详情读取成功，但本地写入安全校验未通过。",
            "skipped_count": 1,
            "privacy_fields_redacted": True,
        })
        return result

    payload = _build_naver_order_refresh_payload(detail_preview)
    payload["external_order_id"] = order.external_order_id
    payload["external_product_order_id"] = _bounded_text(product_order_id, 120)
    changed_fields = _changed_naver_order_refresh_fields(order, payload)
    result["changed_fields"] = changed_fields

    if changed_fields:
        for field, value in payload.items():
            setattr(order, field, value)
        db.commit()
        db.refresh(order)
        result.update({
            "status": "success",
            "updated_count": 1,
            "message": "订单详情已读取官方 API 并刷新到本地；不会回填平台。",
        })
    else:
        result.update({
            "status": "success",
            "no_change_count": 1,
            "message": "已重新读取官方订单详情，本地字段没有变化。",
        })

    if not (result["field_availability"].get("receiver_phone") or result["field_availability"].get("tracking_number")):
        result["message"] = "已读取官方订单详情，但本次平台响应未返回电话或物流单号。"

    result["refreshed_order"] = order_service.serialize_order(order)
    return result


def _sum_naver_order_refresh_count(*results: dict, key: str) -> int:
    return sum(int((item or {}).get(key) or 0) for item in results)


def manual_refresh_naver_orders(
    db: Session,
    *,
    store_id: int,
    max_count: int = NAVER_ORDER_MANUAL_BATCH_MAX_COUNT,
    hours: int = 24,
) -> dict:
    store = ensure_store_exists(db, store_id)
    store_platform = normalize_platform(store.platform)
    if store_platform != "naver":
        return {
            "status": "skipped",
            "store_id": store_id,
            "platform": "naver",
            "resource": "orders",
            "message": _manual_batch_message_for_error("naver", "STORE_PLATFORM_MISMATCH"),
            "error_code": "STORE_PLATFORM_MISMATCH",
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 1,
            "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            "platform_write": False,
            "platform_writes_enabled": False,
        }

    safe_max_count = max(1, min(int(max_count or NAVER_ORDER_MANUAL_BATCH_MAX_COUNT), NAVER_ORDER_MANUAL_BATCH_MAX_COUNT))
    safe_hours = max(1, min(int(hours or 24), 24))
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform="naver",
        sync_type=NAVER_ORDER_SYNC_SOURCE_TYPE,
        message="naver manual order local refresh started",
        raw_summary={
            "stage": "started",
            "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            "write_scope": "local_orders_only",
            "platform_write": False,
            "platform_writes_enabled": False,
            "max_count": safe_max_count,
            "hours": safe_hours,
        },
    )
    try:
        end_kst = get_utc_now().astimezone(get_business_timezone())
        start_kst = end_kst - timedelta(hours=safe_hours)
        preview_result = preview_naver_orders(
            db,
            store_id=store_id,
            credential_id=None,
            start_datetime=start_kst,
            end_datetime=end_kst,
            order_status="ALL",
            page=1,
            size=safe_max_count,
            real_preview=True,
            include_detail=True,
            complete_field_preview=False,
            real_sync=True,
        )
        local_result = preview_result.get("local_sync_result") or {}
        preview_status = preview_result.get("preview_status")
        existing_detail_result = {}
        if preview_status != "failed":
            existing_detail_result = _manual_refresh_existing_naver_order_details(
                db,
                store_id=store_id,
                max_count=safe_max_count,
            )

        local_status = str(local_result.get("status") or "").lower()
        existing_status = str(existing_detail_result.get("status") or "skipped").lower()
        error_code = preview_result.get("error_code") or local_result.get("skip_reason")
        if existing_status in {"blocked", "failed"} and not error_code:
            error_code = existing_detail_result.get("error_code") or existing_detail_result.get("skip_reason")

        safe_success_statuses = {"success", "skipped", "already_exists"}
        recent_refresh_ok = local_status in safe_success_statuses
        existing_refresh_ok = existing_status in safe_success_statuses

        if preview_status == "failed":
            status = "failed"
            message = _manual_batch_message_for_error("naver", error_code)
        elif preview_status in {"success", "success_empty"} and recent_refresh_ok and existing_refresh_ok:
            status = "success"
            created_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="created_count")
            updated_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="updated_count")
            skipped_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="skipped_count")
            message = (
                f"本地订单刷新完成：新增 {created_count}，更新 {updated_count}，"
                f"跳过 {skipped_count}。已补刷已有订单详情字段，不会回填平台。"
            )
            error_code = None if status == "success" else error_code
        else:
            status = "skipped"
            message = _manual_batch_message_for_error("naver", error_code, "Naver订单本地刷新暂未完成")

        created_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="created_count")
        updated_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="updated_count")
        skipped_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="skipped_count")
        no_change_count = _sum_naver_order_refresh_count(local_result, existing_detail_result, key="no_change_count")
        sample_ids = [
            *list(local_result.get("sample_ids") or preview_result.get("sample_ids") or []),
            *list(existing_detail_result.get("sample_ids") or []),
        ][:10]

        result = {
            "status": status,
            "store_id": store_id,
            "platform": "naver",
            "resource": "orders",
            "message": message,
            "error_code": error_code,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "no_change_count": no_change_count,
            "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            "raw_status": local_status or existing_status or preview_status,
            "platform_write": False,
            "platform_writes_enabled": False,
            "raw_response_saved": False,
            "privacy_fields_redacted": bool(local_result.get("privacy_fields_redacted") or existing_detail_result.get("privacy_fields_redacted")),
            "business_contact_fields_saved": bool(local_result.get("business_contact_fields_saved") or existing_detail_result.get("business_contact_fields_saved")),
            "address_saved": bool(local_result.get("address_saved") or existing_detail_result.get("address_saved")),
            "sample_ids": sample_ids,
            "preview_status": preview_status,
            "existing_detail_refresh_status": existing_status,
            "existing_detail_refresh_count": int(existing_detail_result.get("candidate_count") or 0),
            "detail_record_count": int(existing_detail_result.get("detail_record_count") or 0),
            "has_more": bool(preview_result.get("has_more")),
        }
        result["sync_log"] = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver manual order local refresh completed",
            raw_summary={
                "stage": "completed",
                "status": status,
                "platform_write": False,
                "platform_writes_enabled": False,
                "created_count": result["created_count"],
                "updated_count": result["updated_count"],
                "skipped_count": result["skipped_count"],
                "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            },
        )
        return result
    except Exception as exc:
        db.rollback()
        error_code = getattr(exc, "error_code", None) or "manual_order_refresh_failed"
        result = {
            "status": "failed",
            "store_id": store_id,
            "platform": "naver",
            "resource": "orders",
            "message": _manual_batch_message_for_error("naver", error_code, "Naver订单本地刷新失败"),
            "error_code": error_code,
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            "platform_write": False,
            "platform_writes_enabled": False,
            "raw_response_saved": False,
            "privacy_fields_redacted": False,
            "business_contact_fields_saved": False,
            "address_saved": False,
        }
        result["sync_log"] = sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message="naver manual order local refresh failed",
            error_detail=_mask_sensitive_text(str(exc)),
            raw_summary={
                "stage": "failed",
                "status": "failed",
                "error_code": str(error_code),
                "platform_write": False,
                "platform_writes_enabled": False,
                "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
            },
        )
        return result


def _manual_sync_coupang_products(db: Session, store_id: int) -> dict:
    result = sync_coupang_products(db, store_id=store_id, status="APPROVED", max_pages=1)
    return _manual_batch_item(
        platform="coupang",
        resource="products",
        status="success",
        message=_manual_batch_resource_message("coupang", "products", result),
        created_count=result.get("created_count", 0),
        updated_count=result.get("updated_count", 0),
        skipped_count=result.get("skipped_count", 0),
        full_snapshot=False,
        delete_executed=False,
        source_type=result.get("source_type") or COUPANG_PRODUCT_SOURCE_TYPE,
        raw_status=result.get("sync_type"),
    )


def _manual_sync_coupang_orders(db: Session, store_id: int) -> dict:
    result = sync_coupang_orders(db, store_id=store_id, max_pages=1)
    return _manual_batch_item(
        platform="coupang",
        resource="orders",
        status="success",
        message=_manual_batch_resource_message("coupang", "orders", result),
        created_count=result.get("created_count", 0),
        updated_count=result.get("updated_count", 0),
        skipped_count=result.get("skipped_count", 0),
        full_snapshot=False,
        delete_executed=False,
        source_type=result.get("source_type") or COUPANG_ORDER_SOURCE_TYPE,
        raw_status=result.get("sync_type"),
    )


def _manual_sync_customer_inquiries(db: Session, store_id: int, platform: str, *, actor_id: str | None = None) -> dict:
    if platform == "naver":
        from app.services.naver_readonly_inquiry_service import refresh_naver_readonly_inquiries
        result = refresh_naver_readonly_inquiries(db, store_id=store_id, actor_id=actor_id)
        status = result.get("status") or "skipped"
        return _manual_batch_item(
            platform="naver",
            resource="customer_inquiries",
            status="success" if status == "success" else "failed",
            message=result.get("message") or "Naver 客服消息本地同步完成",
            error_code=result.get("error_code"),
            created_count=result.get("created_count", 0),
            updated_count=result.get("updated_count", 0),
            skipped_count=result.get("skipped_count", 0),
            source_type=result.get("source_type") or NAVER_CUSTOMER_INQUIRY_SOURCE_TYPE,
            raw_status=status,
        )
    return _manual_batch_item(
        platform=platform,
        resource="customer_inquiries",
        status="skipped",
        message="客服消息暂未接入真实平台",
        error_code="not_open",
    )


def manual_batch_sync(
    db: Session,
    *,
    store_id: int,
    platforms: list[str] | None = None,
    include_products: bool = True,
    include_orders: bool = True,
    include_customer_inquiries: bool = True,
    replace_policy: str = "delete_absent_when_full_snapshot",
    actor_id: str | None = None,
) -> dict:
    store = ensure_store_exists(db, store_id)
    store_platform = normalize_platform(store.platform)
    requested_platforms = _manual_batch_platforms(platforms, store_platform)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform=store_platform or "manual",
        sync_type=MANUAL_BATCH_SYNC_TYPE,
        message="manual batch sync started",
        raw_summary={
            "stage": "started",
            "requested_platforms": requested_platforms,
            "replace_policy": replace_policy,
            "platform_write": False,
        },
    )
    items: list[dict] = []

    for platform in requested_platforms:
        if platform != store_platform:
            for resource, included in (
                ("products", include_products),
                ("orders", include_orders),
                ("customer_inquiries", include_customer_inquiries),
            ):
                if included:
                    items.append(_manual_batch_item(
                        platform=platform,
                        resource=resource,
                        status="skipped",
                        message=_manual_batch_message_for_error(platform, "STORE_PLATFORM_MISMATCH"),
                        error_code="STORE_PLATFORM_MISMATCH",
                    ))
            continue

        naver_preflight_error: Exception | None = None
        if platform == "naver" and (include_products or include_orders):
            try:
                _ensure_naver_manual_sync_channel_no(db, store_id)
            except Exception as exc:
                db.rollback()
                naver_preflight_error = exc

        if include_products:
            if platform == "naver" and naver_preflight_error is not None:
                items.append(_manual_batch_item_from_error(platform, "products", naver_preflight_error))
            else:
                try:
                    if platform == "naver":
                        items.append(_manual_sync_naver_products(db, store_id))
                    elif platform == "coupang":
                        items.append(_manual_sync_coupang_products(db, store_id))
                except Exception as exc:
                    db.rollback()
                    items.append(_manual_batch_item_from_error(platform, "products", exc))

        if include_orders:
            if platform == "naver" and naver_preflight_error is not None:
                items.append(_manual_batch_item_from_error(platform, "orders", naver_preflight_error))
            else:
                try:
                    if platform == "naver":
                        items.append(_manual_sync_naver_orders(db, store_id))
                    elif platform == "coupang":
                        items.append(_manual_sync_coupang_orders(db, store_id))
                except Exception as exc:
                    db.rollback()
                    items.append(_manual_batch_item_from_error(platform, "orders", exc))

        if include_customer_inquiries:
            try:
                items.append(_manual_sync_customer_inquiries(db, store_id, platform, actor_id=actor_id))
            except Exception as exc:
                db.rollback()
                items.append(_manual_batch_item_from_error(platform, "customer_inquiries", exc))

        items = _manual_batch_apply_connection_blockers(items, platform)

    status = _manual_batch_result_status(items)
    result = {
        "status": status,
        "store_id": store_id,
        "store_platform": store_platform,
        "requested_platforms": requested_platforms,
        "replace_policy": replace_policy,
        "delete_policy": "delete_absent_only_when_full_snapshot_confirmed",
        "platform_write": False,
        "items": items,
        "summary": {
            "success_count": sum(1 for item in items if item.get("status") == "success"),
            "failed_count": sum(1 for item in items if item.get("status") == "failed"),
            "skipped_count": sum(1 for item in items if item.get("status") == "skipped"),
            "created_count": sum(int(item.get("created_count") or 0) for item in items),
            "updated_count": sum(int(item.get("updated_count") or 0) for item in items),
            "deleted_count": sum(int(item.get("deleted_count") or 0) for item in items),
        },
    }
    result["sync_log"] = sync_log_service.finish_sync_log(
        db,
        sync_log_id=sync_log["id"],
        message="manual batch sync completed",
        raw_summary={
            "stage": "completed",
            "status": status,
            "platform_write": False,
            "items": items,
            "summary": result["summary"],
        },
    )
    return result


def manual_batch_sync_all_stores(
    db: Session,
    *,
    platforms: list[str] | None = None,
    include_products: bool = True,
    include_orders: bool = True,
    include_customer_inquiries: bool = True,
    include_inactive: bool = False,
    replace_policy: str = "delete_absent_when_full_snapshot",
    actor_id: str | None = None,
) -> dict:
    requested_platforms: list[str] = []
    for platform in platforms or []:
        try:
            normalized = normalize_platform(platform)
        except ApiError:
            continue
        if normalized not in requested_platforms:
            requested_platforms.append(normalized)
    if not requested_platforms:
        requested_platforms = sorted(MANUAL_BATCH_SUPPORTED_PLATFORMS)

    stores = db.scalars(select(Store).order_by(Store.id.asc())).all()
    if not include_inactive:
        stores = [store for store in stores if store.status != "inactive"]

    store_results: list[dict] = []
    for store in stores:
        try:
            store_platform = normalize_platform(store.platform)
        except ApiError:
            store_results.append({
                "store_id": store.id,
                "store_name": store.name,
                "platform": store.platform,
                "status": "skipped",
                "message": "该平台暂未接入真实读取同步",
                "platform_write": False,
                "items": [],
                "summary": {"success_count": 0, "failed_count": 0, "skipped_count": 1, "created_count": 0, "updated_count": 0, "deleted_count": 0},
            })
            continue
        if store_platform not in requested_platforms:
            continue
        try:
            result = manual_batch_sync(
                db,
                store_id=store.id,
                platforms=[store_platform],
                include_products=include_products,
                include_orders=include_orders,
                include_customer_inquiries=include_customer_inquiries,
                replace_policy=replace_policy,
                actor_id=actor_id,
            )
            store_results.append({
                **result,
                "store_name": store.name,
                "platform_write": False,
            })
        except Exception as exc:
            db.rollback()
            items: list[dict] = []
            if include_products:
                items.append(_manual_batch_item_from_error(store_platform, "products", exc))
            if include_orders:
                items.append(_manual_batch_item_from_error(store_platform, "orders", exc))
            if include_customer_inquiries:
                items.append(_manual_batch_item_from_error(store_platform, "customer_inquiries", exc))
            items = _manual_batch_apply_connection_blockers(items, store_platform)
            status = _manual_batch_result_status(items)
            store_results.append({
                "store_id": store.id,
                "store_name": store.name,
                "store_platform": store_platform,
                "platform": store_platform,
                "status": status,
                "message": _manual_batch_message_for_error(store_platform, getattr(exc, "error_code", None), getattr(exc, "message", str(exc))),
                "platform_write": False,
                "items": items,
                "summary": {
                    "success_count": sum(1 for item in items if item.get("status") == "success"),
                    "failed_count": sum(1 for item in items if item.get("status") == "failed"),
                    "skipped_count": sum(1 for item in items if item.get("status") == "skipped"),
                    "created_count": 0,
                    "updated_count": 0,
                    "deleted_count": 0,
                },
            })

    summary = {
        "store_count": len(store_results),
        "success_count": sum(1 for item in store_results if item.get("status") == "success"),
        "partial_success_count": sum(1 for item in store_results if item.get("status") == "partial_success"),
        "failed_count": sum(1 for item in store_results if item.get("status") == "failed"),
        "skipped_count": sum(1 for item in store_results if item.get("status") == "skipped"),
        "created_count": sum(int(item.get("summary", {}).get("created_count") or 0) for item in store_results),
        "updated_count": sum(int(item.get("summary", {}).get("updated_count") or 0) for item in store_results),
        "deleted_count": 0,
    }
    return {
        "status": "success" if summary["failed_count"] == 0 else ("partial_success" if summary["success_count"] or summary["partial_success_count"] else "failed"),
        "requested_platforms": requested_platforms,
        "replace_policy": replace_policy,
        "delete_policy": "delete_absent_only_when_full_snapshot_confirmed",
        "platform_write": False,
        "store_results": store_results,
        "summary": summary,
    }


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
    readonly_window_max_days: int = NAVER_ORDER_PREVIEW_MAX_DAYS,
) -> dict:
    normalized_status = _resolve_naver_order_preview_status(order_status)
    start_kst, end_kst = _resolve_naver_order_preview_window(
        start_datetime,
        end_datetime,
        max_window_days=readonly_window_max_days,
    )
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
        readonly_window_max_days=readonly_window_max_days,
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
    manual_approval: bool = False,
    backup_path: str | None = None,
    backup_sha256: str | None = None,
    actor_context: dict | None = None,
) -> None:
    settings = get_settings()
    if not settings.real_api_test_enabled or settings.real_api_write_enabled:
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
    if real_sync and manual_approval:
        if not backup_path or not backup_sha256:
            raise ApiError(
                message="Naver product audit-linked local sync requires backup evidence",
                error_code="backup_evidence_required",
                status_code=400,
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(backup_sha256)):
            raise ApiError(
                message="Naver product audit-linked local sync requires a valid backup sha256",
                error_code="invalid_backup_sha256",
                status_code=400,
            )
        if actor_context is not None and not isinstance(actor_context, dict):
            raise ApiError(
                message="Naver product audit-linked local sync requires safe actor context",
                error_code="invalid_actor_context",
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
    manual_approval: bool = False,
    backup_path: str | None = None,
    backup_sha256: str | None = None,
    actor_context: dict | None = None,
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
            manual_approval=manual_approval,
            backup_path=backup_path,
            backup_sha256=backup_sha256,
            actor_context=actor_context,
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
        "operation_audit_rows_written": False,
        "operation_audit_log_id": None,
        "audit_correlation_id": None,
        "operation_audit_skip_reason": None,
        "raw_response_saved": False,
        "write_limit": 5,
    }


def _product_batch_target_hash(sample_ids: list[str]) -> str:
    source = "|".join(str(item) for item in sample_ids[:5]) or "empty"
    return "product-batch-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def _build_naver_product_local_sync_audit_row(
    *,
    store_id: int,
    local_sync_result: dict,
    dry_run_diff: dict,
    backup_path: str | None,
    backup_sha256: str | None,
    actor_context: dict | None,
) -> dict[str, Any]:
    now = get_utc_now()
    sample_ids = [str(item) for item in (local_sync_result.get("sample_ids") or [])][:5]
    target_hash = _product_batch_target_hash(sample_ids)
    correlation_id = f"naver-product-sync-{target_hash[-16:]}"
    actor_context = actor_context or {}
    actor_id = _bounded_text(actor_context.get("actor_id") or "operator-safe-hash-product-sync", 120)
    actor_label = _bounded_text(actor_context.get("actor_label") or "Local operator", 160)
    actor_role = _bounded_text(actor_context.get("actor_role") or "owner", 80)
    changed_fields = sorted(set(dry_run_diff.get("changed_fields") or []))
    if not changed_fields and int(dry_run_diff.get("would_refresh_only") or 0) > 0:
        changed_fields = ["last_synced_at"]
    return {
        "created_at": now,
        "updated_at": now,
        "store_id": store_id,
        "platform": "naver",
        "environment": "local",
        "actor_type": "human",
        "actor_id": actor_id,
        "actor_label": actor_label,
        "actor_role": actor_role,
        "action": "product_batch_local_sync_succeeded",
        "operation_phase": "Naver-Product-Batch-Exec-1A",
        "correlation_id": correlation_id,
        "request_id": f"naver-product-sync-{target_hash[-12:]}",
        "status": "success",
        "reason_code": "product_batch_local_sync_audit_linked",
        "target_type": "product",
        "target_id": None,
        "target_hash": target_hash,
        "target_label": "Naver product local sync batch",
        "changed_field_names": changed_fields,
        "before_summary": {
            "dry_run_would_create": int(dry_run_diff.get("would_create") or 0),
            "dry_run_would_update": int(dry_run_diff.get("would_update") or 0),
            "dry_run_would_refresh_only": int(dry_run_diff.get("would_refresh_only") or 0),
            "dry_run_would_skip": int(dry_run_diff.get("would_skip") or 0),
        },
        "after_summary": {
            "local_sync_status": local_sync_result.get("status"),
            "source_type": NAVER_PRODUCT_SYNC_SOURCE_TYPE,
            "raw_response_saved": False,
            "platform_writes_enabled": False,
        },
        "counts_summary": {
            "created_count": int(local_sync_result.get("created_count") or 0),
            "updated_count": int(local_sync_result.get("updated_count") or 0),
            "skipped_count": int(local_sync_result.get("skipped_count") or 0),
            "products_written": (
                int(local_sync_result.get("created_count") or 0)
                + int(local_sync_result.get("updated_count") or 0)
            ),
            "orders_written": 0,
            "sync_logs_written": 0,
            "capability_results_written": 0,
            "operation_audit_rows_written": 1,
        },
        "safety_flags": {
            "real_api_called": True,
            "real_api_write_enabled": False,
            "platform_writes_enabled": False,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "formal_product_sync_open": False,
            "full_product_ids_saved": False,
            "sample_ids_masked": True,
        },
        "backup_path": _bounded_text(backup_path, 500) if backup_path else None,
        "backup_sha256": backup_sha256,
        "restore_source_path": None,
        "restore_source_sha256": None,
        "sensitive_scan_passed": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "notes": "Naver product local sync wrote sanitized product rows only; Naver platform product writes remain closed.",
    }


def _sync_naver_product_preview_candidate(
    db: Session,
    *,
    store_id: int,
    payload: object | None,
    dry_run_diff: dict,
    real_sync: bool,
    manual_approval: bool = False,
    backup_path: str | None = None,
    backup_sha256: str | None = None,
    actor_context: dict | None = None,
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
    if manual_approval is True:
        audit_row = _build_naver_product_local_sync_audit_row(
            store_id=store_id,
            local_sync_result=result,
            dry_run_diff=dry_run_diff,
            backup_path=backup_path,
            backup_sha256=backup_sha256,
            actor_context=actor_context,
        )
        audit_result = operation_audit_service.write_operation_audit_log_local(
            db,
            audit_row,
            write_enabled=True,
            manual_approval=True,
            local_write_scope=operation_audit_service.LOCAL_WRITER_SCOPE,
        )
        result["operation_audit_rows_written"] = bool(audit_result.get("audit_rows_written"))
        result["operation_audit_log_id"] = audit_result.get("audit_log_id")
        result["audit_correlation_id"] = audit_row["correlation_id"]
        result["operation_audit_skip_reason"] = audit_result.get("skip_reason")
    else:
        result["operation_audit_skip_reason"] = "manual_approval_required_for_audit_linkage"
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


def _resolve_naver_order_preview_window(
    start_datetime: datetime,
    end_datetime: datetime,
    *,
    max_window_days: int = NAVER_ORDER_PREVIEW_MAX_DAYS,
) -> tuple[datetime, datetime]:
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
    if max_window_days not in {NAVER_ORDER_PREVIEW_MAX_DAYS, 30}:
        raise ApiError(
            message="Naver order readonly preview window policy is invalid",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if end_kst - start_kst > timedelta(days=max_window_days):
        raise ApiError(
            message=f"Naver order micro preview window must be {max_window_days} KST days or less",
            error_code="date_range_invalid",
            status_code=400,
            detail={
                "start_datetime": start_kst.isoformat(),
                "end_datetime": end_kst.isoformat(),
                "max_window": f"P{max_window_days}D",
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
        "write_limit": NAVER_ORDER_MANUAL_BATCH_MAX_COUNT,
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
    readonly_window_max_days: int = NAVER_ORDER_PREVIEW_MAX_DAYS,
) -> None:
    settings = get_settings()
    if not settings.real_api_test_enabled or settings.real_api_write_enabled:
        raise ApiError(
            message="Naver order real readonly local sync is guardrail blocked",
            error_code="guardrail_blocked",
            status_code=400,
            detail={
                "store_id": store_id,
                "credential_id": credential_id,
                "real_api_test_enabled": bool(settings.real_api_test_enabled),
                "real_api_write_enabled": bool(settings.real_api_write_enabled),
            },
        )
    if page != 1 or size < 1 or size > NAVER_ORDER_MANUAL_BATCH_MAX_COUNT:
        raise ApiError(
            message="Naver order real readonly local sync only allows page=1 and size<=20",
            error_code="guardrail_blocked",
            status_code=400,
            detail={"page": page, "size": size, "max_size": NAVER_ORDER_MANUAL_BATCH_MAX_COUNT},
        )
    if readonly_window_max_days not in {NAVER_ORDER_PREVIEW_MAX_DAYS, 30}:
        raise ApiError(
            message="Naver order readonly preview window policy is invalid",
            error_code="guardrail_blocked",
            status_code=400,
        )
    if end_kst - start_kst > timedelta(days=readonly_window_max_days):
        raise ApiError(
            message=f"Naver order micro preview window must be {readonly_window_max_days} KST days or less",
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
        product_order_ids = _extract_naver_product_order_ids(feed_payload)[:size]
        sample_ids = [_mask_external_identifier(item) for item in product_order_ids[:10]]
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
            field_observation["detail_limit"] = len(product_order_ids[:size])
            detail_result = _request_naver_order_detail_query(
                api_base=context["api_base"],
                headers=headers,
                product_order_ids=product_order_ids[:size],
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
            detail_records = _extract_naver_order_detail_records(detail_result["payload"], product_order_ids[:size])
            internal_details = [
                _build_naver_order_internal_detail(item, store_id=store_id)
                for item in detail_records
            ]
            detail_previews = [
                _build_naver_order_detail_preview(item, store_id=store_id)
                for item in detail_records
            ]
            field_observation["detail_fields_observed"] = _summarize_naver_order_detail_fields(detail_result["payload"])
            field_observation["detail_preview"] = detail_previews[0] if len(detail_previews) == 1 else {
                "batch_count": len(detail_previews),
                "items": detail_previews[:5],
                "raw_response_saved": False,
                "privacy_fields_redacted": True,
            }
            field_observation["complete_field_preview"] = _build_naver_order_complete_field_preview(
                detail_result["payload"],
                store_id=store_id,
                requested=complete_field_preview,
            )
            local_sync_result = _sync_naver_order_detail_previews_batch(
                db,
                store_id=store_id,
                detail_previews=internal_details,
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
            would_update=int(local_sync_result.get("updated_count") or 0),
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
    product_order_id: str | None = None,
    product_order_ids: list[str] | tuple[str, ...] | None = None,
) -> dict:
    if product_order_ids is None:
        product_order_ids = [product_order_id] if product_order_id else []
    safe_product_order_ids = [
        str(item).strip()
        for item in product_order_ids
        if str(item or "").strip()
    ][:NAVER_ORDER_MANUAL_BATCH_MAX_COUNT]
    diagnostics = {
        "detail_limit": len(safe_product_order_ids),
        "body_field_keys": ["productOrderIds"],
    }
    if not safe_product_order_ids:
        return {
            "success": False,
            "http_status": None,
            "error_code": "detail_product_order_ids_missing",
            "diagnostics": diagnostics,
        }
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base}/v1/pay-order/seller/product-orders/query",
            headers=headers,
            json={"productOrderIds": safe_product_order_ids},
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


def _extract_naver_order_detail_records(
    payload: object,
    product_order_ids: list[str] | tuple[str, ...],
) -> list[dict]:
    requested_ids = [str(item) for item in product_order_ids if str(item or "").strip()]
    requested_set = set(requested_ids)
    if not requested_set:
        return []

    candidates: list[dict] = []

    def walk(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    item_ids = set(_extract_naver_product_order_ids(item))
                    if item_ids & requested_set:
                        candidates.append(item)
                walk(item)
            return
        if isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(payload)
    if not candidates and isinstance(payload, dict):
        payload_ids = set(_extract_naver_product_order_ids(payload))
        if payload_ids & requested_set:
            candidates.append(payload)

    by_id: dict[str, dict] = {}
    for candidate in candidates:
        for candidate_id in _extract_naver_product_order_ids(candidate):
            if candidate_id in requested_set and candidate_id not in by_id:
                by_id[candidate_id] = candidate

    return [by_id[item] for item in requested_ids if item in by_id]


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


def _safe_order_business_text(value: str | None, max_length: int = 160) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"(?i)(authorization|bearer|client_secret|signature|access_token|refresh_token)", "[suppressed]", text)
    return _bounded_text(text, max_length)


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


def _extract_naver_receiver_address(payload: object) -> str | None:
    base_address = _extract_scalar_by_keys(payload, (
        "receiverAddress",
        "recipientAddress",
        "baseAddress",
        "roadNameAddress",
    ))
    detail_address = _extract_scalar_by_keys(payload, (
        "detailedAddress",
        "detailAddress",
    ))
    address = _clean_joined_text(base_address, detail_address, max_length=300) or base_address or detail_address
    return _safe_order_business_text(address, max_length=300)


NAVER_DELIVERY_COMPANY_LABELS = {
    "CJ": "CJ대한통운",
    "CJGLS": "CJ대한통운",
}


def _display_naver_delivery_company(value: object) -> str | None:
    text = _safe_order_business_text(value, max_length=120)
    if not text:
        return None
    return NAVER_DELIVERY_COMPANY_LABELS.get(text.upper(), text)


def _extract_naver_delivery_company(payload: object) -> str | None:
    return _display_naver_delivery_company(_extract_scalar_by_keys(payload, (
        "deliveryCompany",
        "deliveryCompanyName",
        "delivery_company",
        "delivery_company_name",
        "courierCompany",
        "courier",
        "carrier",
    )))


def _extract_naver_delivery_company_code(payload: object) -> str | None:
    return _safe_order_business_text(_extract_scalar_by_keys(payload, (
        "deliveryCompanyCode",
        "deliveryCompanyCd",
        "delivery_company_code",
        "courierCode",
        "carrierCode",
    )), max_length=80)


def _extract_naver_tracking_number(payload: object) -> str | None:
    return _safe_order_business_text(_extract_scalar_by_keys(payload, (
        "trackingNumber",
        "tracking_number",
        "invoiceNo",
        "invoiceNumber",
        "waybillNo",
        "waybillNumber",
    )), max_length=120)


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
    receiver_phone = _extract_scalar_by_keys(payload, (
        "receiverTelNo",
        "receiverTelNo1",
        "receiverTelNo2",
        "receiverPhone",
        "recipientPhone",
        "tel1",
        "tel2",
    ))
    receiver_address = _extract_naver_receiver_address(payload)
    zip_code = _extract_scalar_by_keys(payload, ("zipCode", "zipcode", "postalCode", "postal_code"))
    delivery_company = _extract_naver_delivery_company(payload)
    delivery_company_code = _extract_naver_delivery_company_code(payload)
    tracking_number = _extract_naver_tracking_number(payload)
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


def _build_naver_order_internal_detail(payload: object, *, store_id: int | None = None) -> dict:
    detail = _build_naver_order_detail_preview(payload, store_id=store_id)
    receiver_address = _extract_naver_receiver_address(payload)
    zip_code = _extract_scalar_by_keys(payload, ("zipCode", "zipcode", "postalCode", "postal_code"))
    detail.update({
        "external_order_id_full": _safe_order_business_text(
            _extract_scalar_by_keys(payload, ("orderId", "orderNo", "orderNumber")), max_length=120,
        ),
        "external_product_order_id": _safe_order_business_text(
            _extract_scalar_by_keys(payload, ("productOrderId", "productOrderNo")), max_length=120,
        ),
        # Products are keyed locally by Naver channelProductNo/channelProductId.
        # Do not infer a match from a similarly named origin product identifier.
        "platform_product_id": _safe_order_business_text(_extract_scalar_by_keys(payload, (
            "channelProductNo", "channelProductId",
        )), max_length=120),
        "option_name": _safe_order_business_text(
            _extract_scalar_by_keys(payload, ("optionName", "productOption", "optionInfo")), max_length=160,
        ),
        "receiver_name": _safe_order_business_text(
            _extract_scalar_by_keys(payload, ("receiverName", "recipientName")), max_length=120,
        ),
        "receiver_phone": _safe_order_business_text(
            _extract_scalar_by_keys(payload, (
                "receiverTelNo", "receiverTelNo1", "receiverTelNo2", "receiverPhone", "recipientPhone", "tel1", "tel2",
            )),
            max_length=40,
        ),
        "receiver_address": receiver_address,
        "zip_code": _safe_order_business_text(zip_code, max_length=30),
        "delivery_company": _extract_naver_delivery_company(payload),
        "delivery_company_code": _extract_naver_delivery_company_code(payload),
        "tracking_number": _extract_naver_tracking_number(payload),
        "shipped_at": _datetime_to_iso(_extract_datetime_by_keys(
            payload, ("shippedAt", "sendDate", "dispatchDate", "dispatchedAt"),
        )),
        "address_saved": bool(receiver_address or zip_code),
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "mapping_version": "naver_order_internal_fulfillment_v1",
    })
    return detail


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
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "orders_written": False,
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
        "receiver_phone": _complete_order_field_value(payload, (
            "receiverTelNo",
            "receiverTelNo1",
            "receiverTelNo2",
            "receiverPhone",
            "recipientPhone",
            "tel1",
            "tel2",
        ), 40),
        "receiver_address": _complete_order_field_value(payload, (
            "receiverAddress",
            "recipientAddress",
            "shippingAddress",
            "baseAddress",
            "roadNameAddress",
            "detailedAddress",
        ), 240),
        "zip_code": _complete_order_field_value(payload, ("zipCode", "zipcode", "postalCode", "postal_code"), 20),
        "delivery_company": _extract_naver_delivery_company(payload),
        "delivery_company_code": _extract_naver_delivery_company_code(payload),
        "tracking_number": _extract_naver_tracking_number(payload),
        "shipped_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("shippedAt", "sendDate", "dispatchDate", "dispatchedAt"))),
        "ordered_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("orderedAt", "orderDate", "orderedDate"))),
        "paid_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("paidAt", "paymentDate", "payDate"))),
        "last_changed_at": _datetime_to_iso(_extract_datetime_by_keys(payload, ("lastChangedAt", "lastChangedDate", "lastChangeDate"))),
        "raw_response_saved": False,
        "mapping_version": "naver_order_complete_field_preview_v1",
    }
    complete_fields = {key: value for key, value in complete_fields.items() if value is not None}
    preview.update({
        "available": bool(complete_fields.get("external_order_id") or complete_fields.get("external_product_order_id")),
        "complete_fields": {},
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
                "delivery_company",
                "delivery_company_code",
                "tracking_number",
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


def _validate_naver_order_detail_preview_for_local_write(
    detail_preview: dict | None,
    *,
    expected_store_id: int = 8,
    require_external_product_order_id: bool = True,
) -> dict:
    reasons: list[str] = []
    if not isinstance(detail_preview, dict):
        return {"passed": False, "reasons": ["missing_detail_preview"]}
    if detail_preview.get("store_id") != expected_store_id:
        reasons.append("invalid_store_id")
    if detail_preview.get("platform") != "naver":
        reasons.append("invalid_platform")
    if not _is_hash_identifier(detail_preview.get("external_product_order_id_hash")):
        reasons.append("missing_external_product_order_id_hash")
    if not _is_hash_identifier(detail_preview.get("external_order_id_hash")):
        reasons.append("missing_external_order_id_hash")
    if require_external_product_order_id and not detail_preview.get("external_product_order_id"):
        reasons.append("missing_external_product_order_id")
    if detail_preview.get("raw_response_saved") is not False:
        reasons.append("raw_response_not_suppressed")
    if detail_preview.get("buyer_id_hash") is not None and not _is_hash_identifier(detail_preview.get("buyer_id_hash")):
        reasons.append("buyer_id_not_hashed")

    serialized = json.dumps(detail_preview, ensure_ascii=False, default=str).lower()
    for forbidden in ("authorization", "client_secret", "signature", "bcrypt", "raw response", "access_token", "refresh_token", "bearer "):
        if forbidden in serialized:
            reasons.append(f"forbidden_text_{forbidden.replace(' ', '_')}")
    return {"passed": not reasons, "reasons": sorted(dict.fromkeys(reasons))}


def _naver_order_sanitized_raw_data(detail_preview: dict) -> dict:
    allowed_keys = (
        "external_order_id_hash",
        "external_product_order_id_hash",
        "external_order_id_full",
        "external_product_order_id",
        "order_status",
        "order_status_label_zh",
        "payment_status",
        "option_name",
        "delivery_status",
        "delivery_status_label_zh",
        "claim_status",
        "claim_status_label_zh",
        "buyer_id_hash",
        "buyer_name",
        "buyer_phone",
        "receiver_name_masked",
        "receiver_name",
        "receiver_phone",
        "receiver_phone_masked",
        "receiver_address",
        "zip_code",
        "delivery_company",
        "delivery_company_code",
        "tracking_number",
        "shipped_at",
        "address_observed",
        "address_saved",
        "business_contact_fields_saved",
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
        "technical_sensitive_fields_suppressed": True,
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "address_saved": bool(detail_preview.get("receiver_address") or detail_preview.get("zip_code")),
    })
    return raw_data


def _sync_naver_order_detail_preview(
    db: Session,
    *,
    detail_preview: dict | None,
    real_sync: bool,
    store_id: int = 8,
) -> dict:
    result = _default_naver_order_local_sync_result(real_sync)
    if not real_sync:
        return result

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(
        detail_preview,
        expected_store_id=store_id,
    )
    result["privacy_gate"] = privacy_gate
    if not privacy_gate["passed"]:
        result["status"] = "blocked"
        result["skip_reason"] = "privacy_gate_failed"
        return result

    assert detail_preview is not None
    external_order_id = str(detail_preview["external_product_order_id_hash"])
    existing = db.scalar(
        select(Order).where(
            Order.store_id == store_id,
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
        store_id=store_id,
        platform="naver",
        external_order_id=external_order_id,
        external_product_order_id=_bounded_text(detail_preview.get("external_product_order_id"), 120),
        buyer_name=_bounded_text(detail_preview.get("buyer_name"), 120),
        buyer_phone=_bounded_text(detail_preview.get("buyer_phone"), 40),
        buyer_masked_phone=_bounded_text(detail_preview.get("buyer_phone_masked"), 30),
        receiver_name=_bounded_text(detail_preview.get("receiver_name"), 120),
        receiver_phone=_bounded_text(detail_preview.get("receiver_phone"), 40),
        receiver_address=_bounded_text(detail_preview.get("receiver_address"), 300),
        zip_code=_bounded_text(detail_preview.get("zip_code"), 30),
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
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "address_saved": bool(detail_preview.get("receiver_address") or detail_preview.get("zip_code")),
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
        "technical_sensitive_fields_suppressed": True,
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "address_saved": bool(detail_preview.get("receiver_address") or detail_preview.get("zip_code")),
    })
    return raw_data


def _build_naver_order_refresh_payload(detail_preview: dict) -> dict:
    synced_at = _parse_preview_iso_datetime(detail_preview.get("last_synced_at")) or get_utc_now()
    ordered_at = _parse_preview_iso_datetime(detail_preview.get("ordered_at")) or synced_at
    paid_at = _parse_preview_iso_datetime(detail_preview.get("paid_at"))
    external_order_id = str(detail_preview["external_product_order_id_hash"])
    return {
        "external_order_id": external_order_id,
        "external_product_order_id": _bounded_text(detail_preview.get("external_product_order_id"), 120),
        "buyer_name": _bounded_text(detail_preview.get("buyer_name"), 120),
        "buyer_phone": _bounded_text(detail_preview.get("buyer_phone"), 40),
        "buyer_masked_phone": _bounded_text(detail_preview.get("buyer_phone_masked"), 30),
        "receiver_name": _bounded_text(detail_preview.get("receiver_name"), 120),
        "receiver_phone": _bounded_text(detail_preview.get("receiver_phone"), 40),
        "receiver_address": _bounded_text(detail_preview.get("receiver_address"), 300),
        "zip_code": _bounded_text(detail_preview.get("zip_code"), 30),
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


def _build_naver_order_create_payload(detail_preview: dict) -> dict:
    payload = _build_naver_order_refresh_payload(detail_preview)
    payload["raw_data"] = _naver_order_sanitized_raw_data(detail_preview)
    return payload


def _sync_naver_order_detail_previews_batch(
    db: Session,
    *,
    store_id: int,
    detail_previews: list[dict] | tuple[dict, ...] | None,
    real_sync: bool,
) -> dict:
    result = _default_naver_order_local_sync_result(real_sync)
    result.update({
        "candidate_count": len(detail_previews) if isinstance(detail_previews, (list, tuple)) else 0,
        "write_limit": NAVER_ORDER_MANUAL_BATCH_MAX_COUNT,
        "no_change_count": 0,
        "candidate_results": [],
        "platform_write": False,
        "platform_writes_enabled": False,
    })
    if not real_sync:
        return result
    if not isinstance(detail_previews, (list, tuple)) or not detail_previews:
        result["status"] = "skipped"
        result["skip_reason"] = "detail_previews_missing"
        return result
    if len(detail_previews) > NAVER_ORDER_MANUAL_BATCH_MAX_COUNT:
        result["status"] = "blocked"
        result["skip_reason"] = "order_batch_limit_exceeded"
        return result

    created_count = 0
    updated_count = 0
    skipped_count = 0
    sample_ids: list[str] = []

    for detail_preview in detail_previews:
        safe_hash = detail_preview.get("external_product_order_id_hash") if isinstance(detail_preview, dict) else None
        candidate_result = {
            "safe_hash": safe_hash if _is_hash_identifier(safe_hash) else None,
            "status": "skipped",
            "changed_fields": [],
            "skip_reason": None,
        }
        privacy_gate = _validate_naver_order_detail_preview_for_local_write(
            detail_preview,
            expected_store_id=store_id,
        )
        candidate_result["privacy_gate_passed"] = privacy_gate["passed"]
        candidate_result["privacy_gate_reasons"] = privacy_gate["reasons"]
        if not privacy_gate["passed"]:
            skipped_count += 1
            candidate_result["skip_reason"] = "privacy_gate_failed"
            result["candidate_results"].append(candidate_result)
            continue

        assert isinstance(detail_preview, dict)
        external_order_id = str(detail_preview["external_product_order_id_hash"])
        legacy_hash_id = str(detail_preview["external_product_order_id_hash"])
        sample_ids.append(external_order_id)
        existing = db.scalar(
            select(Order).where(
                Order.store_id == store_id,
                Order.platform == "naver",
                Order.external_order_id == external_order_id,
            )
        )
        if existing is None:
            existing = db.scalar(
                select(Order).where(
                    Order.store_id == store_id,
                    Order.platform == "naver",
                    Order.external_order_id == legacy_hash_id,
                )
            )
        if existing is None:
            payload = _build_naver_order_create_payload(detail_preview)
            db.add(Order(store_id=store_id, platform="naver", **payload))
            created_count += 1
            candidate_result["status"] = "created"
            result["candidate_results"].append(candidate_result)
            continue

        payload = _build_naver_order_refresh_payload(detail_preview)
        changed_fields = _changed_naver_order_refresh_fields(existing, payload)
        candidate_result["changed_fields"] = changed_fields
        if not changed_fields:
            skipped_count += 1
            result["no_change_count"] += 1
            candidate_result["status"] = "no_change"
            candidate_result["skip_reason"] = "no_business_field_change"
            result["candidate_results"].append(candidate_result)
            continue

        for field, value in payload.items():
            setattr(existing, field, value)
        updated_count += 1
        candidate_result["status"] = "updated"
        result["candidate_results"].append(candidate_result)

    if created_count or updated_count:
        db.commit()
    result.update({
        "status": "success",
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "already_exists": bool(skipped_count and not created_count and not updated_count),
        "no_duplicate_created": True,
        "orders_written": bool(created_count or updated_count),
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "privacy_fields_redacted": False,
        "business_contact_fields_saved": True,
        "address_saved": any(
            isinstance(item, dict) and bool(item.get("receiver_address") or item.get("zip_code"))
            for item in detail_previews
        ),
        "source_type": NAVER_ORDER_SYNC_SOURCE_TYPE,
        "sample_ids": sample_ids[:10],
    })
    return result


def _same_naver_refresh_datetime(current: object, incoming: object) -> bool:
    if current is None or incoming is None:
        return current is incoming
    if not isinstance(current, datetime) or not isinstance(incoming, datetime):
        return current == incoming
    if current.tzinfo is None or incoming.tzinfo is None:
        return current.replace(tzinfo=None) == incoming.replace(tzinfo=None)
    return current.astimezone(timezone.utc) == incoming.astimezone(timezone.utc)


def _naver_order_refresh_raw_data_changed(current: object, incoming: object) -> bool:
    current_data = current if isinstance(current, dict) else {}
    incoming_data = incoming if isinstance(incoming, dict) else {}
    watched_keys = (
        "delivery_status",
        "delivery_status_label_zh",
        "claim_status",
        "claim_status_label_zh",
        "payment_status",
        "option_name",
        "receiver_phone",
        "receiver_address",
        "zip_code",
        "delivery_company",
        "delivery_company_code",
        "tracking_number",
        "shipped_at",
    )
    return any(current_data.get(key) != incoming_data.get(key) for key in watched_keys)


def _changed_naver_order_refresh_fields(order: Order, payload: dict) -> list[str]:
    changed: list[str] = []
    comparable_fields = (
        "external_order_id",
        "external_product_order_id",
        "buyer_name",
        "buyer_phone",
        "buyer_masked_phone",
        "receiver_name",
        "receiver_phone",
        "receiver_address",
        "zip_code",
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
    if _naver_order_refresh_raw_data_changed(getattr(order, "raw_data", None), payload.get("raw_data")):
        changed.append("raw_data")
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

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(
        refresh_preview,
        require_external_product_order_id=write_enabled,
    )
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
        "businesscontactfieldssaved",
        "buyeridhash",
        "buyerid_hash",
        "buyerphonemasked",
        "buyer_phone_masked",
        "buyernamemasked",
        "buyer_name_masked",
        "externalorderidhash",
        "external_order_id_hash",
        "externalorderidfull",
        "externalproductorderidhash",
        "external_product_order_id_hash",
        "externalproductorderid",
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
        "receivername",
        "receiverphonemasked",
        "receiver_phone_masked",
        "receiverphone",
        "receiveraddress",
        "zipcode",
        "deliverycompany",
        "deliverycompanycode",
        "trackingnumber",
        "shippedat",
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


def _evaluate_naver_product_batch_rollback_drill_readonly_report_mock_gate(
    *,
    rollback_drill_gate: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private readonly report gate for product rollback drill evidence; never restores or writes rows."""

    result = {
        "phase": "Naver-Product-Batch-1L",
        "product_rollback_drill_readonly_report_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "report_ready": False,
        "report_sections": [],
        "rollback_drill_ready": False,
        "backup_evidence_verified": False,
        "updated_count": 0,
        "created_count": 0,
        "stock_only_write_verified": False,
        "temporary_restore_required": True,
        "real_restore_executed": False,
        "rollback_executed": False,
        "production_db_touched": False,
        "real_api_called": False,
        "real_database_written": False,
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "operation_audit_rows_written": False,
        "timeline_events_written": False,
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
    if not isinstance(rollback_drill_gate, dict):
        result["skip_reason"] = "rollback_drill_gate_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(rollback_drill_gate):
        result["skip_reason"] = "rollback_report_sensitive_field_blocked"
        return result
    if rollback_drill_gate.get("status") != "product_batch_rollback_drill_mock_ready":
        result["skip_reason"] = rollback_drill_gate.get("skip_reason") or "rollback_drill_not_ready"
        return result
    if rollback_drill_gate.get("rollback_executed") is not False:
        result["skip_reason"] = "rollback_execution_not_allowed_in_report"
        return result
    if rollback_drill_gate.get("real_restore_executed") is not False:
        result["skip_reason"] = "real_restore_not_allowed_in_report"
        return result
    if rollback_drill_gate.get("products_written") is not False:
        result["skip_reason"] = "product_write_not_allowed_in_report"
        return result

    result.update({
        "status": "product_rollback_drill_readonly_report_ready",
        "report_ready": True,
        "rollback_drill_ready": True,
        "backup_evidence_verified": bool(rollback_drill_gate.get("backup_evidence_verified")),
        "updated_count": int(rollback_drill_gate.get("updated_count") or 0),
        "created_count": int(rollback_drill_gate.get("created_count") or 0),
        "stock_only_write_verified": bool(rollback_drill_gate.get("stock_only_write_verified")),
        "report_sections": [
            "备份证据",
            "库存变更摘要",
            "回滚清单",
            "临时恢复演练计划",
            "回读校验计划",
            "敏感字段扫描计划",
        ],
        "business_message": "Naver 商品回滚演练只读报告已整理。当前不会恢复数据库，也不会写入商品。",
    })
    return result


def evaluate_naver_product_rollback_readonly_report_backend_route_mock_gate(
    *,
    rollback_drill_gate: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly product rollback report route; no route or restore is exposed."""

    result = _evaluate_naver_product_batch_rollback_drill_readonly_report_mock_gate(
        rollback_drill_gate=rollback_drill_gate,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "Naver-Product-Batch-1P",
        "product_rollback_readonly_report_backend_route_mock_gate": True,
        "backend_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/naver/products/rollback-readonly-report",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "real_restore_executed": False,
        "rollback_executed": False,
        "production_db_touched": False,
        "real_api_called": False,
        "real_database_written": False,
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "operation_audit_rows_written": False,
        "timeline_events_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "product_rollback_drill_readonly_report_ready":
        result["business_message"] = (
            "Naver 商品回滚只读报告 backend route mock gate 已通过；当前不会开放接口、不会恢复数据库，也不会写入商品。"
        )
        result["next_action"] = "后续可单独规划只读 route，本阶段继续保持恢复和批量同步关闭。"
    return result


def evaluate_naver_product_rollback_readonly_report_route_local(
    *,
    rollback_drill_gate: dict | None,
) -> dict:
    """Public local readonly rollback-report route helper; never restores or writes product rows."""

    result = evaluate_naver_product_rollback_readonly_report_backend_route_mock_gate(
        rollback_drill_gate=rollback_drill_gate,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "Naver-Product-Batch-1R",
        "product_rollback_readonly_report_route_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/naver/products/rollback-readonly-report",
        "http_method": "POST",
        "real_restore_executed": False,
        "rollback_executed": False,
        "production_db_touched": False,
        "real_api_called": False,
        "real_database_written": False,
        "products_written": False,
        "orders_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "operation_audit_rows_written": False,
        "timeline_events_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_product_sync_open": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "product_rollback_drill_readonly_report_ready":
        result["business_message"] = (
            "Naver product rollback readonly report is available for local review. "
            "No restore, product write, audit write, or formal batch sync is opened."
        )
        result["next_action"] = (
            "Review backup, rollback checklist, readback, and sensitive-scan evidence before any later production decision."
        )
    return result


def _batch_readonly_default_business_message(sync_kind: str) -> str:
    if sync_kind == "naver_order_batch":
        return "Naver 订单批量只读证据已整理，等待人工审核。"
    if sync_kind == "naver_order_refresh_batch":
        return "Naver 订单刷新只读证据已整理，等待人工审核。"
    if sync_kind == "naver_product_batch":
        return "只读批量证据已整理，等待人工审核。"
    return "只读批量证据已整理，等待人工审核。"


def _batch_readonly_default_next_action(sync_kind: str) -> str:
    if sync_kind in {"naver_order_batch", "naver_order_refresh_batch"}:
        return "继续人工审核订单证据；正式订单批量同步仍未开放。"
    if sync_kind == "naver_product_batch":
        return "继续人工审核商品证据；正式商品批量同步仍未开放。"
    return "manual_review_required"


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
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
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
            "operation_audit_rows_planned": True,
            "business_message": str(
                item.get("business_message") or _batch_readonly_default_business_message(sync_kind)
            )[:240],
            "next_action": str(item.get("next_action") or _batch_readonly_default_next_action(sync_kind))[:160],
        })

    result.update({
        "status": "readonly_evidence_api_mock_ready",
        "evidence_count": len(normalized_items),
        "items": normalized_items,
    })
    return result


def _evaluate_batch_approval_audit_evidence_mock_gate(
    *,
    readonly_evidence: dict | None,
    approval_context: dict | None,
    audit_evidence_plan: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private mock gate for future batch-approval audit readiness; never writes audit rows."""

    result = {
        "phase": "ERP-Batch-1N",
        "batch_approval_audit_evidence_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "audit_evidence_ready": False,
        "evidence_count": 0,
        "store_ids": [],
        "sync_kinds": [],
        "required_actions": [],
        "required_audit_plan_flags": [
            "approval_record_planned",
            "backup_verification_record_planned",
            "permission_check_record_planned",
            "write_attempt_record_planned",
            "post_write_verification_record_planned",
            "sensitive_scan_record_planned",
            "rollback_reference_planned",
            "failure_record_planned",
            "formal_sync_remains_closed",
        ],
        "missing_audit_plan_flags": [],
        "manual_approval_planned": False,
        "permission_evidence_planned": False,
        "backup_evidence_required": True,
        "rollback_evidence_required": True,
        "post_write_readback_required": True,
        "sensitive_scan_required": True,
        "public_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_evidence, dict):
        result["skip_reason"] = "readonly_evidence_required"
        return result
    if not isinstance(approval_context, dict):
        result["skip_reason"] = "approval_context_required"
        return result
    if not isinstance(audit_evidence_plan, dict):
        result["skip_reason"] = "audit_evidence_plan_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "readonly_evidence": readonly_evidence,
        "approval_context": approval_context,
        "audit_evidence_plan": audit_evidence_plan,
    }):
        result["skip_reason"] = "batch_approval_audit_sensitive_field_blocked"
        return result

    if readonly_evidence.get("status") not in {"readonly_evidence_api_mock_ready", "readonly_evidence_api_ready"}:
        result["skip_reason"] = "readonly_evidence_not_ready"
        return result
    if readonly_evidence.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if readonly_evidence.get("real_database_written") is True:
        result["skip_reason"] = "readonly_evidence_already_wrote_database"
        return result
    if readonly_evidence.get("orders_written") is True or readonly_evidence.get("products_written") is True:
        result["skip_reason"] = "readonly_evidence_business_write_not_allowed"
        return result
    if readonly_evidence.get("sync_log_written") is True or readonly_evidence.get("capability_tested_success_written") is True:
        result["skip_reason"] = "readonly_evidence_side_effect_not_allowed"
        return result
    if readonly_evidence.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "readonly_evidence_audit_write_not_allowed"
        return result
    if readonly_evidence.get("operation_audit_rows_planned") is not True:
        result["skip_reason"] = "readonly_evidence_audit_plan_required"
        return result
    if readonly_evidence.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result
    if readonly_evidence.get("raw_response_saved") is not False:
        result["skip_reason"] = "raw_response_saved_not_allowed"
        return result

    items = readonly_evidence.get("items")
    if not isinstance(items, list) or not items:
        result["skip_reason"] = "readonly_evidence_items_required"
        return result

    store_ids: set[int] = set()
    sync_kinds: set[str] = set()
    required_actions: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            result["skip_reason"] = "readonly_evidence_item_shape_invalid"
            result["blocked_index"] = index
            return result
        if _formal_batch_sync_sensitive_marker_found(item):
            result["skip_reason"] = "readonly_evidence_item_sensitive_field_blocked"
            result["blocked_index"] = index
            return result
        sync_kind = str(item.get("sync_kind") or "")
        config = FORMAL_BATCH_SYNC_GATE_KINDS.get(sync_kind)
        if config is None:
            result["skip_reason"] = "sync_kind_not_allowed"
            result["blocked_index"] = index
            return result
        try:
            store_id = int(item.get("store_id"))
        except (TypeError, ValueError):
            result["skip_reason"] = "readonly_evidence_store_id_invalid"
            result["blocked_index"] = index
            return result
        if store_id <= 0:
            result["skip_reason"] = "readonly_evidence_store_id_invalid"
            result["blocked_index"] = index
            return result
        if item.get("duplicate_check_passed") is not True:
            result["skip_reason"] = "duplicate_check_required"
            result["blocked_index"] = index
            return result
        if item.get("field_whitelist_verified") is not True:
            result["skip_reason"] = "field_whitelist_required"
            result["blocked_index"] = index
            return result
        if item.get("audit_required") is not True or item.get("operation_audit_rows_planned") is not True:
            result["skip_reason"] = "item_audit_plan_required"
            result["blocked_index"] = index
            return result
        if item.get("backup_required") is not True or item.get("permission_required") is not True:
            result["skip_reason"] = "item_backup_permission_plan_required"
            result["blocked_index"] = index
            return result
        store_ids.add(store_id)
        sync_kinds.add(sync_kind)
        required_actions.add(str(config["required_action"]))

    actor_store_ids = _normalize_formal_batch_store_ids(approval_context.get("store_ids"))
    if actor_store_ids is None:
        result["skip_reason"] = "approval_store_scope_required"
        return result
    if not set(store_ids).issubset(set(actor_store_ids)):
        result["skip_reason"] = "approval_store_scope_mismatch"
        return result
    if approval_context.get("manual_approval_planned") is not True:
        result["skip_reason"] = "manual_approval_plan_required"
        return result

    approved_actions_raw = approval_context.get("approved_actions") or approval_context.get("permission_keys") or []
    if not isinstance(approved_actions_raw, (list, tuple, set)):
        result["skip_reason"] = "approval_actions_invalid"
        return result
    approved_actions = {str(action) for action in approved_actions_raw}
    missing_actions = sorted(required_actions - approved_actions)
    if missing_actions:
        result["skip_reason"] = "approval_action_missing"
        result["missing_actions"] = missing_actions
        return result

    missing_flags = [
        flag for flag in result["required_audit_plan_flags"]
        if audit_evidence_plan.get(flag) is not True
    ]
    result["missing_audit_plan_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "audit_evidence_plan_incomplete"
        return result
    if audit_evidence_plan.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "audit_write_not_allowed_in_mock_gate"
        return result
    if audit_evidence_plan.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if audit_evidence_plan.get("platform_writes_enabled") is True:
        result["skip_reason"] = "platform_write_not_allowed_in_mock_gate"
        return result

    result.update({
        "status": "batch_approval_audit_evidence_mock_ready",
        "audit_evidence_ready": True,
        "evidence_count": len(items),
        "store_ids": sorted(store_ids),
        "sync_kinds": sorted(sync_kinds),
        "required_actions": sorted(required_actions),
        "manual_approval_planned": True,
        "permission_evidence_planned": True,
        "business_message": (
            "批量审批的审计证据前置条件已通过 mock gate；当前不会写入审计记录，也不会开放正式批量同步。"
        ),
        "next_action": (
            "继续准备正式批量同步的审批、备份、权限、审计链、回读校验和回滚证据。"
        ),
    })
    return result


def evaluate_batch_approval_audit_evidence_local_route_mock_gate(
    *,
    readonly_evidence: dict | None,
    approval_context: dict | None,
    audit_evidence_plan: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for the future local audit-evidence route; it does not expose a write endpoint."""

    result = _evaluate_batch_approval_audit_evidence_mock_gate(
        readonly_evidence=readonly_evidence,
        approval_context=approval_context,
        audit_evidence_plan=audit_evidence_plan,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "ERP-Batch-1P",
        "batch_approval_audit_evidence_local_route_mock_gate": True,
        "local_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/approval-audit-evidence",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "batch_approval_audit_evidence_mock_ready":
        result["business_message"] = (
            "批量审批审计证据本地 route mock gate 已通过；当前不会开放接口、不会写入审计记录，也不会开启正式批量同步。"
        )
        result["next_action"] = "单独阶段再实现只读本地 route，并继续保持写入关闭。"
    return result


def evaluate_batch_approval_audit_evidence_readonly_route_local(
    *,
    readonly_evidence: dict | None,
    approval_context: dict | None,
    audit_evidence_plan: dict | None,
) -> dict:
    """Public local readonly batch approval audit-evidence route helper; never writes audit rows."""

    result = evaluate_batch_approval_audit_evidence_local_route_mock_gate(
        readonly_evidence=readonly_evidence,
        approval_context=approval_context,
        audit_evidence_plan=audit_evidence_plan,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-1S",
        "batch_approval_audit_evidence_readonly_route_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/approval-audit-evidence",
        "http_method": "POST",
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "batch_approval_audit_evidence_mock_ready":
        result["status"] = "batch_approval_audit_evidence_ready"
        result["business_message"] = (
            "Batch approval audit evidence is ready for local readonly review. "
            "No audit row, order, product, SyncLog, or tested-success record is written."
        )
        result["next_action"] = (
            "Continue manual approval review with backup, permission, readback, sensitive-scan, and rollback evidence."
        )
    return result


def evaluate_formal_batch_approval_decision_mock_gate(
    *,
    readonly_evidence: dict | None,
    approval_audit_evidence: dict | None,
    decision_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Final mock gate before a human batch-approval decision; never approves execution."""

    required_decision_flags = [
        "decision_record_planned",
        "human_approval_required",
        "backup_manifest_verified",
        "rollback_report_ready",
        "permission_gate_verified",
        "readonly_evidence_fresh",
        "field_whitelist_verified",
        "duplicate_check_passed",
        "sensitive_scan_passed",
        "post_write_readback_required",
        "audit_correlation_planned",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-2F",
        "formal_batch_approval_decision_mock_gate": True,
        "status": "blocked",
        "decision_status": "blocked",
        "skip_reason": None,
        "required_decision_flags": required_decision_flags,
        "missing_decision_flags": [],
        "evidence_count": 0,
        "store_ids": [],
        "sync_kinds": [],
        "required_actions": [],
        "decision_record_planned": False,
        "human_approval_required": True,
        "backup_manifest_verified": False,
        "rollback_report_ready": False,
        "permission_gate_verified": False,
        "readonly_evidence_fresh": False,
        "field_whitelist_verified": False,
        "duplicate_check_passed": False,
        "sensitive_scan_passed": False,
        "post_write_readback_required": True,
        "audit_correlation_planned": False,
        "execution_approved": False,
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_evidence, dict):
        result["skip_reason"] = "readonly_evidence_required"
        return result
    if not isinstance(approval_audit_evidence, dict):
        result["skip_reason"] = "approval_audit_evidence_required"
        return result
    if not isinstance(decision_context, dict):
        result["skip_reason"] = "decision_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "readonly_evidence": readonly_evidence,
        "approval_audit_evidence": approval_audit_evidence,
        "decision_context": decision_context,
    }):
        result["skip_reason"] = "formal_batch_decision_sensitive_field_blocked"
        return result

    if readonly_evidence.get("status") not in {"readonly_evidence_api_mock_ready", "readonly_evidence_api_ready"}:
        result["skip_reason"] = "readonly_evidence_not_ready"
        return result
    if readonly_evidence.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if readonly_evidence.get("real_database_written") is True:
        result["skip_reason"] = "readonly_evidence_already_wrote_database"
        return result
    if readonly_evidence.get("orders_written") is True or readonly_evidence.get("products_written") is True:
        result["skip_reason"] = "readonly_evidence_business_write_not_allowed"
        return result
    if readonly_evidence.get("sync_log_written") is True or readonly_evidence.get("capability_tested_success_written") is True:
        result["skip_reason"] = "readonly_evidence_side_effect_not_allowed"
        return result
    if readonly_evidence.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "readonly_evidence_audit_write_not_allowed"
        return result
    if readonly_evidence.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result
    if readonly_evidence.get("raw_response_saved") is not False:
        result["skip_reason"] = "raw_response_saved_not_allowed"
        return result

    if approval_audit_evidence.get("status") not in {
        "batch_approval_audit_evidence_mock_ready",
        "batch_approval_audit_evidence_ready",
    }:
        result["skip_reason"] = "approval_audit_evidence_not_ready"
        return result
    if approval_audit_evidence.get("formal_sync_open") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if approval_audit_evidence.get("real_database_written") is True:
        result["skip_reason"] = "approval_audit_evidence_wrote_database"
        return result
    if approval_audit_evidence.get("orders_written") is True or approval_audit_evidence.get("products_written") is True:
        result["skip_reason"] = "approval_audit_business_write_not_allowed"
        return result
    if approval_audit_evidence.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "approval_audit_write_not_allowed"
        return result
    if approval_audit_evidence.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result

    items = readonly_evidence.get("items")
    if not isinstance(items, list) or not items:
        result["skip_reason"] = "readonly_evidence_items_required"
        return result

    store_ids: set[int] = set()
    sync_kinds: set[str] = set()
    required_actions: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            result["skip_reason"] = "readonly_evidence_item_shape_invalid"
            result["blocked_index"] = index
            return result
        sync_kind = str(item.get("sync_kind") or "")
        config = FORMAL_BATCH_SYNC_GATE_KINDS.get(sync_kind)
        if config is None:
            result["skip_reason"] = "sync_kind_not_allowed"
            result["blocked_index"] = index
            return result
        try:
            store_id = int(item.get("store_id"))
        except (TypeError, ValueError):
            result["skip_reason"] = "readonly_evidence_store_id_invalid"
            result["blocked_index"] = index
            return result
        if store_id <= 0:
            result["skip_reason"] = "readonly_evidence_store_id_invalid"
            result["blocked_index"] = index
            return result
        if item.get("duplicate_check_passed") is not True:
            result["skip_reason"] = "duplicate_check_required"
            result["blocked_index"] = index
            return result
        if item.get("field_whitelist_verified") is not True:
            result["skip_reason"] = "field_whitelist_required"
            result["blocked_index"] = index
            return result
        store_ids.add(store_id)
        sync_kinds.add(sync_kind)
        required_actions.add(str(config["required_action"]))

    audit_store_ids = set(_normalize_formal_batch_store_ids(approval_audit_evidence.get("store_ids")) or [])
    audit_actions = set(str(action) for action in (approval_audit_evidence.get("required_actions") or []))
    if not store_ids.issubset(audit_store_ids):
        result["skip_reason"] = "approval_audit_store_scope_mismatch"
        return result
    if not required_actions.issubset(audit_actions):
        result["skip_reason"] = "approval_audit_action_scope_mismatch"
        return result

    decision_store_ids = set(_normalize_formal_batch_store_ids(decision_context.get("store_ids")) or [])
    if not store_ids.issubset(decision_store_ids):
        result["skip_reason"] = "decision_store_scope_mismatch"
        return result
    requested_status = str(decision_context.get("decision_status") or "pending_human_approval")
    if requested_status not in {"pending_human_approval", "ready_for_human_review", "not_approved"}:
        result["skip_reason"] = "decision_status_not_allowed"
        return result
    if decision_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if decision_context.get("formal_sync_open") is True or decision_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    missing_flags = [
        flag for flag in required_decision_flags
        if decision_context.get(flag) is not True
    ]
    result["missing_decision_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "approval_decision_context_incomplete"
        return result

    result.update({
        "status": "formal_batch_approval_decision_mock_ready",
        "decision_status": "ready_for_human_approval",
        "evidence_count": len(items),
        "store_ids": sorted(store_ids),
        "sync_kinds": sorted(sync_kinds),
        "required_actions": sorted(required_actions),
        "decision_record_planned": True,
        "backup_manifest_verified": True,
        "rollback_report_ready": True,
        "permission_gate_verified": True,
        "readonly_evidence_fresh": True,
        "field_whitelist_verified": True,
        "duplicate_check_passed": True,
        "sensitive_scan_passed": True,
        "audit_correlation_planned": True,
        "business_message": (
            "正式批量审批决策的 mock 门禁已通过；当前只表示材料可进入人工审批，不批准执行，也不开启商品或订单批量同步。"
        ),
        "next_action": (
            "继续由管理员人工复核审批范围、备份、权限、回滚、回读和敏感扫描证据；执行写入必须另开阶段。"
        ),
    })
    return result


def evaluate_formal_batch_approval_decision_readonly_api_mock_gate(
    *,
    readonly_evidence: dict | None,
    approval_audit_evidence: dict | None,
    decision_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly decision API contract; no route is exposed."""

    result = evaluate_formal_batch_approval_decision_mock_gate(
        readonly_evidence=readonly_evidence,
        approval_audit_evidence=approval_audit_evidence,
        decision_context=decision_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "sensitive_fields_hidden_from_main_page",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "ERP-Batch-2I",
        "formal_batch_approval_decision_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/approval-decision/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") != "formal_batch_approval_decision_mock_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "approval_decision_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["decision_status"] = "blocked"
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "formal_batch_approval_decision_readonly_api_mock_ready",
        "decision_status": "ready_for_readonly_api_planning",
        "business_message": (
            "正式批量审批决策只读 API 的 mock 门禁已通过；当前只规划只读审查接口，不开放路由、不批准执行。"
        ),
        "next_action": (
            "后续可单独规划本地只读 API 实现；执行商品或订单批量写入仍必须另开阶段。"
        ),
    })
    return result


def evaluate_formal_batch_approval_decision_readonly_api_local_route_mock_gate(
    *,
    readonly_evidence: dict | None,
    approval_audit_evidence: dict | None,
    decision_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for the future local readonly route; it still exposes no route."""

    result = evaluate_formal_batch_approval_decision_readonly_api_mock_gate(
        readonly_evidence=readonly_evidence,
        approval_audit_evidence=approval_audit_evidence,
        decision_context=decision_context,
        readonly_api_context=readonly_api_context,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "ERP-Batch-2K",
        "formal_batch_approval_decision_readonly_api_local_route_mock_gate": True,
        "local_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/approval-decision/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "formal_batch_approval_decision_readonly_api_mock_ready":
        result["business_message"] = (
            "正式批量审批决策只读 API local route mock gate 已通过；当前仍不开放路由、不批准执行。"
        )
        result["next_action"] = "后续可单独实现本地只读 route，继续保持写入和平台调用关闭。"
    return result


def evaluate_formal_batch_approval_decision_readonly_api_local(
    *,
    readonly_evidence: dict | None,
    approval_audit_evidence: dict | None,
    decision_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Local readonly approval-decision route helper; never approves execution."""

    result = evaluate_formal_batch_approval_decision_readonly_api_local_route_mock_gate(
        readonly_evidence=readonly_evidence,
        approval_audit_evidence=approval_audit_evidence,
        decision_context=decision_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-2L",
        "formal_batch_approval_decision_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/approval-decision/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "formal_batch_approval_decision_readonly_api_mock_ready":
        result["status"] = "formal_batch_approval_decision_readonly_api_ready"
        result["decision_status"] = "ready_for_local_readonly_review"
        result["business_message"] = (
            "正式批量审批决策只读检查已完成；当前只提供人工复核材料，不批准执行或写入。"
        )
        result["next_action"] = "继续人工复核审批材料；执行商品或订单批量写入必须另开阶段。"
    return result


def evaluate_formal_batch_approval_decision_audit_linkage_mock_gate(
    *,
    approval_decision: dict | None,
    audit_linkage_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for linking a future batch approval decision to audit evidence."""

    required_linkage_flags = [
        "approval_decision_id_planned",
        "readonly_evidence_hash_planned",
        "backup_manifest_reference_planned",
        "permission_evidence_reference_planned",
        "sensitive_scan_reference_planned",
        "readback_result_reference_planned",
        "rollback_report_reference_planned",
        "operator_identity_hash_planned",
        "store_scope_planned",
        "audit_correlation_id_planned",
        "append_only_audit_rows_planned",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-2P",
        "approval_decision_audit_linkage_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "audit_linkage_ready": False,
        "required_linkage_flags": required_linkage_flags,
        "missing_linkage_flags": [],
        "store_ids": [],
        "sync_kinds": [],
        "required_actions": [],
        "approval_decision_id_planned": False,
        "readonly_evidence_hash_planned": False,
        "backup_manifest_reference_planned": False,
        "permission_evidence_reference_planned": False,
        "sensitive_scan_reference_planned": False,
        "readback_result_reference_planned": False,
        "rollback_report_reference_planned": False,
        "operator_identity_hash_planned": False,
        "store_scope_planned": False,
        "audit_correlation_id_planned": False,
        "append_only_audit_rows_planned": False,
        "execution_approved": False,
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(approval_decision, dict):
        result["skip_reason"] = "approval_decision_required"
        return result
    if not isinstance(audit_linkage_context, dict):
        result["skip_reason"] = "audit_linkage_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "approval_decision": approval_decision,
        "audit_linkage_context": audit_linkage_context,
    }):
        result["skip_reason"] = "approval_decision_audit_linkage_sensitive_field_blocked"
        return result

    if approval_decision.get("status") not in {
        "formal_batch_approval_decision_mock_ready",
        "formal_batch_approval_decision_readonly_api_mock_ready",
        "formal_batch_approval_decision_readonly_api_ready",
    }:
        result["skip_reason"] = "approval_decision_not_ready"
        return result
    if approval_decision.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_linkage_mock_gate"
        return result
    if approval_decision.get("formal_sync_open") is True or approval_decision.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if approval_decision.get("real_database_written") is True:
        result["skip_reason"] = "approval_decision_wrote_database"
        return result
    if approval_decision.get("orders_written") is True or approval_decision.get("products_written") is True:
        result["skip_reason"] = "approval_decision_business_write_not_allowed"
        return result
    if approval_decision.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "approval_decision_audit_write_not_allowed"
        return result
    if approval_decision.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result

    missing_flags = [
        flag for flag in required_linkage_flags
        if audit_linkage_context.get(flag) is not True
    ]
    result["missing_linkage_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "approval_decision_audit_linkage_incomplete"
        return result
    if audit_linkage_context.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "audit_write_not_allowed_in_linkage_mock_gate"
        return result
    if audit_linkage_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_linkage_mock_gate"
        return result
    if audit_linkage_context.get("formal_sync_open") is True or audit_linkage_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    decision_store_ids = set(_normalize_formal_batch_store_ids(approval_decision.get("store_ids")) or [])
    linkage_store_ids = set(_normalize_formal_batch_store_ids(audit_linkage_context.get("store_ids")) or [])
    if not decision_store_ids or not linkage_store_ids or not decision_store_ids.issubset(linkage_store_ids):
        result["skip_reason"] = "audit_linkage_store_scope_mismatch"
        return result

    decision_actions = set(str(action) for action in (approval_decision.get("required_actions") or []))
    linkage_actions = set(str(action) for action in (audit_linkage_context.get("required_actions") or []))
    if decision_actions and not decision_actions.issubset(linkage_actions):
        result["skip_reason"] = "audit_linkage_action_scope_mismatch"
        return result

    sync_kinds = sorted(str(kind) for kind in (approval_decision.get("sync_kinds") or []))
    result.update({
        "status": "approval_decision_audit_linkage_mock_ready",
        "audit_linkage_ready": True,
        "store_ids": sorted(decision_store_ids),
        "sync_kinds": sync_kinds,
        "required_actions": sorted(decision_actions),
        "approval_decision_id_planned": True,
        "readonly_evidence_hash_planned": True,
        "backup_manifest_reference_planned": True,
        "permission_evidence_reference_planned": True,
        "sensitive_scan_reference_planned": True,
        "readback_result_reference_planned": True,
        "rollback_report_reference_planned": True,
        "operator_identity_hash_planned": True,
        "store_scope_planned": True,
        "audit_correlation_id_planned": True,
        "append_only_audit_rows_planned": True,
        "business_message": (
            "Formal batch approval decision audit linkage mock gate passed. "
            "It plans append-only audit evidence only; no audit row or business data is written."
        ),
        "next_action": (
            "Plan a readonly API for this linkage before any execution phase. "
            "Product and order batch writes remain separately approved future work."
        ),
    })
    return result


def evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_mock_gate(
    *,
    approval_decision: dict | None,
    audit_linkage_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly API that reviews approval-decision audit linkage."""

    result = evaluate_formal_batch_approval_decision_audit_linkage_mock_gate(
        approval_decision=approval_decision,
        audit_linkage_context=audit_linkage_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "sensitive_fields_hidden_from_main_page",
        "audit_row_write_excluded",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "ERP-Batch-2R",
        "approval_decision_audit_linkage_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/approval-decision/audit-linkage/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") != "approval_decision_audit_linkage_mock_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["skip_reason"] = "approval_decision_audit_linkage_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("operation_audit_rows_written") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "audit_write_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "approval_decision_audit_linkage_readonly_api_mock_ready",
        "audit_linkage_ready": True,
        "business_message": (
            "Approval decision audit linkage readonly API mock gate passed. "
            "It plans a review endpoint only; no audit row, product, order, or execution approval is written."
        ),
        "next_action": (
            "Plan the local readonly API route separately, then keep any product or order batch write in a later approved phase."
        ),
    })
    return result


def evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_local_route_mock_gate(
    *,
    approval_decision: dict | None,
    audit_linkage_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for exposing approval-decision audit linkage as a local readonly route."""

    result = evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_mock_gate(
        approval_decision=approval_decision,
        audit_linkage_context=audit_linkage_context,
        readonly_api_context=readonly_api_context,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "ERP-Batch-2T",
        "approval_decision_audit_linkage_readonly_api_local_route_mock_gate": True,
        "local_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/approval-decision/audit-linkage/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "approval_decision_audit_linkage_readonly_api_mock_ready":
        result["status"] = "approval_decision_audit_linkage_readonly_api_local_route_mock_ready"
        result["business_message"] = (
            "Approval decision audit linkage readonly route mock gate passed. "
            "It is review-only and does not approve execution, write audit rows, or write business data."
        )
        result["next_action"] = (
            "Implement the local readonly route separately; product and order batch execution stay closed."
        )
    return result


def evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_local(
    *,
    approval_decision: dict | None,
    audit_linkage_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for approval-decision audit linkage; never writes rows."""

    result = evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_local_route_mock_gate(
        approval_decision=approval_decision,
        audit_linkage_context=audit_linkage_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-2U",
        "approval_decision_audit_linkage_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/approval-decision/audit-linkage/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "approval_decision_audit_linkage_readonly_api_local_route_mock_ready":
        result["status"] = "approval_decision_audit_linkage_readonly_api_ready"
        result["business_message"] = (
            "Approval decision audit linkage is available for local readonly review. "
            "This does not approve batch execution or create audit rows."
        )
        result["next_action"] = (
            "Use the route as evidence for operator review only. A separate approved phase is still required for any batch write."
        )
    return result


def evaluate_formal_batch_execution_preflight_readonly_api_local(
    *,
    approval_decision: dict | None,
    approval_audit_linkage: dict | None,
    execution_approvals: list[dict] | tuple[dict, ...] | None,
    preflight_context: dict | None,
) -> dict:
    """Unified readonly preflight for future formal product/order batch execution."""

    required_preflight_flags = [
        "operator_checklist_reviewed",
        "approval_decision_referenced",
        "audit_linkage_referenced",
        "readonly_evidence_referenced",
        "backup_manifest_referenced",
        "permission_evidence_referenced",
        "rollback_report_referenced",
        "readback_plan_referenced",
        "sensitive_scan_referenced",
        "execution_window_limited",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-3A",
        "formal_batch_execution_preflight_readonly_api_local": True,
        "status": "blocked",
        "preflight_status": "blocked",
        "preflight_ready": False,
        "skip_reason": None,
        "required_preflight_flags": required_preflight_flags,
        "missing_preflight_flags": [],
        "execution_approval_count": 0,
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "required_actions": [],
        "route_path": "/api/v1/batch/execution-preflight/readonly-check",
        "http_method": "POST",
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
    }
    if not isinstance(approval_decision, dict):
        result["skip_reason"] = "approval_decision_required"
        return result
    if not isinstance(approval_audit_linkage, dict):
        result["skip_reason"] = "approval_audit_linkage_required"
        return result
    if not isinstance(execution_approvals, (list, tuple)) or not execution_approvals:
        result["skip_reason"] = "execution_approvals_required"
        return result
    if len(execution_approvals) > 10:
        result["skip_reason"] = "execution_approval_count_limit_exceeded"
        return result
    if not isinstance(preflight_context, dict):
        result["skip_reason"] = "preflight_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "approval_decision": approval_decision,
        "approval_audit_linkage": approval_audit_linkage,
        "execution_approvals": execution_approvals,
        "preflight_context": preflight_context,
    }):
        result["skip_reason"] = "formal_batch_execution_preflight_sensitive_field_blocked"
        return result

    if approval_decision.get("status") not in {
        "formal_batch_approval_decision_mock_ready",
        "formal_batch_approval_decision_readonly_api_mock_ready",
        "formal_batch_approval_decision_readonly_api_ready",
    }:
        result["skip_reason"] = "approval_decision_not_ready"
        return result
    if approval_decision.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_preflight"
        return result
    if approval_decision.get("real_database_written") is True:
        result["skip_reason"] = "approval_decision_wrote_database"
        return result
    if approval_decision.get("orders_written") is True or approval_decision.get("products_written") is True:
        result["skip_reason"] = "approval_decision_business_write_not_allowed"
        return result
    if approval_decision.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "approval_decision_audit_write_not_allowed"
        return result
    if approval_decision.get("formal_sync_open") is True or approval_decision.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if approval_decision.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result

    if approval_audit_linkage.get("status") not in {
        "approval_decision_audit_linkage_mock_ready",
        "approval_decision_audit_linkage_readonly_api_local_route_mock_ready",
        "approval_decision_audit_linkage_readonly_api_ready",
    }:
        result["skip_reason"] = "approval_audit_linkage_not_ready"
        return result
    if approval_audit_linkage.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_preflight"
        return result
    if approval_audit_linkage.get("real_database_written") is True:
        result["skip_reason"] = "approval_audit_linkage_wrote_database"
        return result
    if approval_audit_linkage.get("orders_written") is True or approval_audit_linkage.get("products_written") is True:
        result["skip_reason"] = "approval_audit_linkage_business_write_not_allowed"
        return result
    if approval_audit_linkage.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "approval_audit_linkage_audit_write_not_allowed"
        return result
    if approval_audit_linkage.get("formal_sync_open") is True or approval_audit_linkage.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if approval_audit_linkage.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result

    preflight_missing_flags = [
        flag for flag in required_preflight_flags
        if preflight_context.get(flag) is not True
    ]
    result["missing_preflight_flags"] = preflight_missing_flags
    if preflight_missing_flags:
        result["skip_reason"] = "execution_preflight_context_incomplete"
        return result
    if preflight_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_preflight"
        return result
    if preflight_context.get("formal_sync_open") is True or preflight_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if preflight_context.get("real_database_written") is True or preflight_context.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "write_not_allowed_in_preflight"
        return result

    decision_store_ids = set(_normalize_formal_batch_store_ids(approval_decision.get("store_ids")) or [])
    linkage_store_ids = set(_normalize_formal_batch_store_ids(approval_audit_linkage.get("store_ids")) or [])
    decision_actions = set(str(action) for action in (approval_decision.get("required_actions") or []))
    linkage_actions = set(str(action) for action in (approval_audit_linkage.get("required_actions") or []))
    if not decision_store_ids or not linkage_store_ids:
        result["skip_reason"] = "approval_store_scope_required"
        return result

    accepted_product_statuses = {
        "naver_product_batch_execution_approval_mock_ready",
        "naver_product_batch_execution_approval_readonly_api_mock_ready",
        "naver_product_batch_execution_approval_readonly_api_local_route_mock_ready",
        "naver_product_batch_execution_approval_readonly_api_ready",
    }
    accepted_order_statuses = {
        "naver_order_batch_execution_approval_mock_ready",
        "naver_order_batch_execution_approval_readonly_api_mock_ready",
        "naver_order_batch_execution_approval_readonly_api_local_route_mock_ready",
        "naver_order_batch_execution_approval_readonly_api_ready",
    }
    store_ids: set[int] = set()
    sync_kinds: set[str] = set()
    targets: set[str] = set()
    required_actions: set[str] = set()
    for index, approval in enumerate(execution_approvals):
        if not isinstance(approval, dict):
            result["skip_reason"] = "execution_approval_shape_invalid"
            result["blocked_index"] = index
            return result
        status = str(approval.get("status") or "")
        if status in accepted_product_statuses:
            sync_kind = "naver_product_batch"
            target = "products"
            ready_key = "product_batch_execution_approval_ready"
            write_flag = "products_written"
            platform_write_flag = "platform_product_writes_enabled"
            formal_target_flag = "formal_product_sync_open"
        elif status in accepted_order_statuses:
            sync_kind = "naver_order_batch"
            target = "orders"
            ready_key = "order_batch_execution_approval_ready"
            write_flag = "orders_written"
            platform_write_flag = "platform_order_writes_enabled"
            formal_target_flag = "formal_order_sync_open"
        else:
            result["skip_reason"] = "execution_approval_status_not_ready"
            result["blocked_index"] = index
            return result
        if approval.get(ready_key) is not True:
            result["skip_reason"] = "execution_approval_ready_flag_required"
            result["blocked_index"] = index
            return result
        if approval.get("execution_approved") is True:
            result["skip_reason"] = "execution_approval_not_allowed_in_preflight"
            result["blocked_index"] = index
            return result
        if approval.get("real_api_called") is True or approval.get("real_database_written") is True:
            result["skip_reason"] = "execution_approval_side_effect_not_allowed"
            result["blocked_index"] = index
            return result
        if approval.get(write_flag) is True:
            result["skip_reason"] = "execution_approval_business_write_not_allowed"
            result["blocked_index"] = index
            return result
        if approval.get("sync_log_written") is True or approval.get("capability_tested_success_written") is True:
            result["skip_reason"] = "execution_approval_side_effect_not_allowed"
            result["blocked_index"] = index
            return result
        if approval.get("timeline_events_written") is True or approval.get("operation_audit_rows_written") is True:
            result["skip_reason"] = "execution_approval_side_effect_not_allowed"
            result["blocked_index"] = index
            return result
        if approval.get("raw_response_saved") is not False or approval.get("privacy_fields_redacted") is not True:
            result["skip_reason"] = "execution_approval_privacy_boundary_invalid"
            result["blocked_index"] = index
            return result
        if approval.get("formal_sync_open") is True or approval.get(formal_target_flag) is True:
            result["skip_reason"] = "formal_sync_already_open_not_allowed"
            result["blocked_index"] = index
            return result
        if approval.get("platform_writes_enabled") is True or approval.get(platform_write_flag) is True:
            result["skip_reason"] = "platform_write_not_allowed_in_preflight"
            result["blocked_index"] = index
            return result
        approval_store_ids = set(_normalize_formal_batch_store_ids(approval.get("store_ids")) or [])
        if not approval_store_ids:
            result["skip_reason"] = "execution_approval_store_scope_required"
            result["blocked_index"] = index
            return result
        store_ids.update(approval_store_ids)
        sync_kinds.add(sync_kind)
        targets.add(target)
        required_actions.add(str(FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["required_action"]))

    if not store_ids.issubset(decision_store_ids):
        result["skip_reason"] = "approval_decision_store_scope_mismatch"
        return result
    if not store_ids.issubset(linkage_store_ids):
        result["skip_reason"] = "approval_audit_linkage_store_scope_mismatch"
        return result
    if required_actions and not required_actions.issubset(decision_actions):
        result["skip_reason"] = "approval_decision_action_scope_mismatch"
        return result
    if required_actions and not required_actions.issubset(linkage_actions):
        result["skip_reason"] = "approval_audit_linkage_action_scope_mismatch"
        return result

    result.update({
        "status": "formal_batch_execution_preflight_readonly_ready",
        "preflight_status": "ready_for_execution_phase_planning",
        "preflight_ready": True,
        "execution_approval_count": len(execution_approvals),
        "store_ids": sorted(store_ids),
        "sync_kinds": sorted(sync_kinds),
        "targets": sorted(targets),
        "required_actions": sorted(required_actions),
        "business_message": (
            "Formal batch execution preflight is ready for operator review only. "
            "It does not approve execution, write products or orders, call platform APIs, or open formal sync."
        ),
        "next_action": (
            "Use this as readonly evidence before a separately approved execution phase. "
            "Any product or order batch write still requires a new explicit approval."
        ),
    })
    return result


def evaluate_formal_batch_execution_dry_run_readonly_api_local(
    *,
    execution_preflight: dict | None,
    dry_run_context: dict | None,
    execution_plan: dict | None,
    candidate_summaries: list[dict] | tuple[dict, ...] | None,
) -> dict:
    """Readonly dry-run contract for future formal product/order batch execution."""

    required_dry_run_flags = [
        "preflight_referenced",
        "readonly_candidates_referenced",
        "backup_manifest_referenced",
        "permission_evidence_referenced",
        "audit_linkage_referenced",
        "readback_plan_referenced",
        "rollback_plan_referenced",
        "sensitive_scan_passed",
        "execution_window_limited",
        "dry_run_only",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-3D",
        "formal_batch_execution_dry_run_readonly_api_local": True,
        "status": "blocked",
        "dry_run_status": "blocked",
        "dry_run_ready": False,
        "skip_reason": None,
        "required_dry_run_flags": required_dry_run_flags,
        "missing_dry_run_flags": [],
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "candidate_summary_count": 0,
        "total_candidate_count": 0,
        "total_would_create": 0,
        "total_would_update": 0,
        "total_would_refresh_only": 0,
        "total_would_skip": 0,
        "changed_fields": [],
        "candidate_summaries": [],
        "route_path": "/api/v1/batch/execution-dry-run/readonly-check",
        "http_method": "POST",
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "dry_run_only": True,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if not isinstance(execution_preflight, dict):
        result["skip_reason"] = "execution_preflight_required"
        return result
    if not isinstance(dry_run_context, dict):
        result["skip_reason"] = "dry_run_context_required"
        return result
    if not isinstance(execution_plan, dict):
        result["skip_reason"] = "execution_plan_required"
        return result
    if not isinstance(candidate_summaries, (list, tuple)) or not candidate_summaries:
        result["skip_reason"] = "candidate_summaries_required"
        return result
    if len(candidate_summaries) > 10:
        result["skip_reason"] = "candidate_summary_count_limit_exceeded"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "execution_preflight": execution_preflight,
        "dry_run_context": dry_run_context,
        "execution_plan": execution_plan,
        "candidate_summaries": candidate_summaries,
    }):
        result["skip_reason"] = "formal_batch_execution_dry_run_sensitive_field_blocked"
        return result

    if execution_preflight.get("status") != "formal_batch_execution_preflight_readonly_ready":
        result["skip_reason"] = "execution_preflight_not_ready"
        return result
    if execution_preflight.get("preflight_ready") is not True:
        result["skip_reason"] = "execution_preflight_not_ready"
        return result
    preflight_store_ids = set(_normalize_formal_batch_store_ids(execution_preflight.get("store_ids")) or [])
    preflight_sync_kinds = set(str(kind) for kind in (execution_preflight.get("sync_kinds") or []))
    preflight_targets = set(str(target) for target in (execution_preflight.get("targets") or []))
    if not preflight_store_ids or not preflight_sync_kinds:
        result["skip_reason"] = "execution_preflight_scope_required"
        return result
    if execution_preflight.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_dry_run"
        return result
    if execution_preflight.get("real_api_called") is True or execution_preflight.get("real_database_written") is True:
        result["skip_reason"] = "execution_preflight_side_effect_not_allowed"
        return result
    if execution_preflight.get("orders_written") is True or execution_preflight.get("products_written") is True:
        result["skip_reason"] = "execution_preflight_business_write_not_allowed"
        return result
    if execution_preflight.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "execution_preflight_audit_write_not_allowed"
        return result
    if execution_preflight.get("formal_sync_open") is True or execution_preflight.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if execution_preflight.get("raw_response_saved") is not False or execution_preflight.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "execution_preflight_privacy_boundary_invalid"
        return result

    missing_flags = [flag for flag in required_dry_run_flags if dry_run_context.get(flag) is not True]
    result["missing_dry_run_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "dry_run_context_incomplete"
        return result
    if dry_run_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_dry_run"
        return result
    if dry_run_context.get("formal_sync_open") is True or dry_run_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if dry_run_context.get("real_api_called") is True or dry_run_context.get("real_database_written") is True:
        result["skip_reason"] = "write_not_allowed_in_dry_run"
        return result
    if dry_run_context.get("orders_written") is True or dry_run_context.get("products_written") is True:
        result["skip_reason"] = "write_not_allowed_in_dry_run"
        return result
    if dry_run_context.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "audit_write_not_allowed_in_dry_run"
        return result

    if execution_plan.get("mode") not in {"dry_run", "readonly_dry_run", None}:
        result["skip_reason"] = "execution_plan_mode_not_allowed"
        return result
    if execution_plan.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_dry_run"
        return result
    if execution_plan.get("formal_sync_open") is True or execution_plan.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result
    if execution_plan.get("real_api_called") is True or execution_plan.get("real_database_written") is True:
        result["skip_reason"] = "write_not_allowed_in_dry_run"
        return result

    normalized_summaries: list[dict] = []
    summary_store_ids: set[int] = set()
    summary_sync_kinds: set[str] = set()
    summary_targets: set[str] = set()
    changed_fields: set[str] = set()
    totals = {
        "candidate_count": 0,
        "would_create": 0,
        "would_update": 0,
        "would_refresh_only": 0,
        "would_skip": 0,
    }
    for index, summary in enumerate(candidate_summaries):
        if not isinstance(summary, dict):
            result["skip_reason"] = "candidate_summary_shape_invalid"
            result["blocked_index"] = index
            return result
        sync_kind = str(summary.get("sync_kind") or summary.get("syncKind") or "").strip()
        config = FORMAL_BATCH_SYNC_GATE_KINDS.get(sync_kind)
        if not config:
            result["skip_reason"] = "candidate_summary_sync_kind_invalid"
            result["blocked_index"] = index
            return result
        if sync_kind not in preflight_sync_kinds:
            result["skip_reason"] = "candidate_summary_not_in_preflight_scope"
            result["blocked_index"] = index
            return result
        target = str(summary.get("target") or config["target"])
        if target != config["target"] or target not in preflight_targets:
            result["skip_reason"] = "candidate_summary_target_mismatch"
            result["blocked_index"] = index
            return result
        summary_store_scope = set(_normalize_formal_batch_store_ids(summary.get("store_ids") or summary.get("storeIds")) or [])
        if not summary_store_scope:
            result["skip_reason"] = "candidate_summary_store_scope_required"
            result["blocked_index"] = index
            return result
        if not summary_store_scope.issubset(preflight_store_ids):
            result["skip_reason"] = "candidate_summary_store_scope_mismatch"
            result["blocked_index"] = index
            return result
        try:
            candidate_count = int(summary.get("candidate_count", summary.get("candidateCount", 0)) or 0)
            would_create = int(summary.get("would_create", summary.get("wouldCreate", 0)) or 0)
            would_update = int(summary.get("would_update", summary.get("wouldUpdate", 0)) or 0)
            would_refresh_only = int(summary.get("would_refresh_only", summary.get("wouldRefreshOnly", 0)) or 0)
            would_skip = int(summary.get("would_skip", summary.get("wouldSkip", 0)) or 0)
        except (TypeError, ValueError):
            result["skip_reason"] = "candidate_summary_counts_invalid"
            result["blocked_index"] = index
            return result
        if min(candidate_count, would_create, would_update, would_refresh_only, would_skip) < 0:
            result["skip_reason"] = "candidate_summary_counts_invalid"
            result["blocked_index"] = index
            return result
        if candidate_count > int(config["max_batch_size"]):
            result["skip_reason"] = "dry_run_candidate_count_exceeds_limit"
            result["blocked_index"] = index
            result["max_batch_size"] = int(config["max_batch_size"])
            return result
        if would_create + would_update + would_refresh_only + would_skip > candidate_count:
            result["skip_reason"] = "candidate_summary_counts_exceed_candidates"
            result["blocked_index"] = index
            return result
        safe_changed_fields = _normalize_safe_changed_fields(
            summary.get("changed_fields", summary.get("changedFields", []))
        )
        if safe_changed_fields is None:
            result["skip_reason"] = "candidate_summary_changed_fields_invalid"
            result["blocked_index"] = index
            return result
        if summary.get("execution_approved") is True:
            result["skip_reason"] = "execution_approval_not_allowed_in_dry_run"
            result["blocked_index"] = index
            return result
        if summary.get("real_api_called") is True or summary.get("real_database_written") is True:
            result["skip_reason"] = "candidate_summary_side_effect_not_allowed"
            result["blocked_index"] = index
            return result
        if summary.get("orders_written") is True or summary.get("products_written") is True:
            result["skip_reason"] = "candidate_summary_write_not_allowed"
            result["blocked_index"] = index
            return result
        if summary.get("raw_response_saved") is not False or summary.get("privacy_fields_redacted") is not True:
            result["skip_reason"] = "candidate_summary_privacy_boundary_invalid"
            result["blocked_index"] = index
            return result
        summary_store_ids.update(summary_store_scope)
        summary_sync_kinds.add(sync_kind)
        summary_targets.add(target)
        changed_fields.update(safe_changed_fields)
        totals["candidate_count"] += candidate_count
        totals["would_create"] += would_create
        totals["would_update"] += would_update
        totals["would_refresh_only"] += would_refresh_only
        totals["would_skip"] += would_skip
        normalized_summaries.append({
            "sync_kind": sync_kind,
            "target": target,
            "store_ids": sorted(summary_store_scope),
            "candidate_count": candidate_count,
            "would_create": would_create,
            "would_update": would_update,
            "would_refresh_only": would_refresh_only,
            "would_skip": would_skip,
            "changed_fields": safe_changed_fields,
        })

    if not preflight_sync_kinds.issubset(summary_sync_kinds):
        result["skip_reason"] = "candidate_summaries_missing_preflight_sync_kind"
        return result
    if not summary_store_ids.issubset(preflight_store_ids):
        result["skip_reason"] = "candidate_summary_store_scope_mismatch"
        return result

    result.update({
        "status": "formal_batch_execution_dry_run_readonly_ready",
        "dry_run_status": "ready_for_operator_review",
        "dry_run_ready": True,
        "store_ids": sorted(summary_store_ids),
        "sync_kinds": sorted(summary_sync_kinds),
        "targets": sorted(summary_targets),
        "candidate_summary_count": len(normalized_summaries),
        "total_candidate_count": totals["candidate_count"],
        "total_would_create": totals["would_create"],
        "total_would_update": totals["would_update"],
        "total_would_refresh_only": totals["would_refresh_only"],
        "total_would_skip": totals["would_skip"],
        "changed_fields": sorted(changed_fields),
        "candidate_summaries": normalized_summaries,
        "business_message": (
            "Formal batch execution dry-run evidence is ready for operator review only. "
            "No products or orders are written, no audit rows are created, no platform APIs are called, and formal sync remains closed."
        ),
        "next_action": (
            "Use this dry-run result before a separately approved execution phase. "
            "Any real product or order batch write still requires explicit approval and fresh verification."
        ),
    })
    return result


def evaluate_formal_batch_execution_approval_mock_gate(
    *,
    execution_preflight: dict | None,
    execution_dry_run: dict | None,
    final_approval_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private mock gate for the final review before any later formal batch execution."""

    required_final_approval_flags = [
        "latest_dry_run_referenced",
        "manual_execution_phase_required",
        "backup_manifest_verified",
        "permission_evidence_verified",
        "audit_linkage_verified",
        "readback_plan_verified",
        "rollback_plan_verified",
        "sensitive_scan_passed",
        "operator_identity_verified",
        "store_scope_verified",
        "execution_window_limited",
        "manual_approval_record_planned",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-3G",
        "formal_batch_execution_approval_mock_gate": True,
        "private_helper_only": True,
        "status": "blocked",
        "approval_status": "blocked",
        "final_approval_ready": False,
        "skip_reason": None,
        "required_final_approval_flags": required_final_approval_flags,
        "missing_final_approval_flags": [],
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "required_actions": [],
        "candidate_summary_count": 0,
        "total_candidate_count": 0,
        "total_would_create": 0,
        "total_would_update": 0,
        "total_would_refresh_only": 0,
        "total_would_skip": 0,
        "changed_fields": [],
        "candidate_summaries": [],
        "route_path": None,
        "http_method": None,
        "backend_route_implemented": False,
        "public_endpoint_enabled": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(execution_preflight, dict):
        result["skip_reason"] = "execution_preflight_required"
        return result
    if not isinstance(execution_dry_run, dict):
        result["skip_reason"] = "execution_dry_run_required"
        return result
    if not isinstance(final_approval_context, dict):
        result["skip_reason"] = "final_approval_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "execution_preflight": execution_preflight,
        "execution_dry_run": execution_dry_run,
        "final_approval_context": final_approval_context,
    }):
        result["skip_reason"] = "formal_batch_execution_approval_sensitive_field_blocked"
        return result

    if execution_preflight.get("status") != "formal_batch_execution_preflight_readonly_ready":
        result["skip_reason"] = "execution_preflight_not_ready"
        return result
    if execution_preflight.get("preflight_ready") is not True:
        result["skip_reason"] = "execution_preflight_not_ready"
        return result
    if execution_dry_run.get("status") != "formal_batch_execution_dry_run_readonly_ready":
        result["skip_reason"] = "execution_dry_run_not_ready"
        return result
    if execution_dry_run.get("dry_run_ready") is not True:
        result["skip_reason"] = "execution_dry_run_not_ready"
        return result

    side_effect_flags = [
        "execution_approved",
        "batch_execution_enabled",
        "write_endpoint_enabled",
        "real_api_called",
        "real_database_written",
        "orders_written",
        "products_written",
        "sync_log_written",
        "capability_tested_success_written",
        "timeline_events_written",
        "operation_audit_rows_written",
        "formal_sync_open",
        "formal_order_sync_open",
        "formal_product_sync_open",
        "platform_order_writes_enabled",
        "platform_product_writes_enabled",
        "platform_writes_enabled",
        "shipment_write_enabled",
        "cancel_write_enabled",
        "return_write_enabled",
        "exchange_write_enabled",
    ]
    for source_name, payload in (
        ("execution_preflight", execution_preflight),
        ("execution_dry_run", execution_dry_run),
        ("final_approval_context", final_approval_context),
    ):
        for flag in side_effect_flags:
            if payload.get(flag) is True:
                if flag == "execution_approved":
                    result["skip_reason"] = "execution_approval_not_allowed_in_approval_mock_gate"
                else:
                    result["skip_reason"] = "side_effect_not_allowed_in_approval_mock_gate"
                result["blocked_source"] = source_name
                result["blocked_flag"] = flag
                return result
        if payload.get("raw_response_saved") is not False and "raw_response_saved" in payload:
            result["skip_reason"] = "raw_response_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("privacy_fields_redacted") is not True and "privacy_fields_redacted" in payload:
            result["skip_reason"] = "privacy_redaction_required"
            result["blocked_source"] = source_name
            return result

    missing_flags = [
        flag for flag in required_final_approval_flags
        if final_approval_context.get(flag) is not True
    ]
    result["missing_final_approval_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "final_approval_context_incomplete"
        return result

    preflight_store_ids = set(_normalize_formal_batch_store_ids(execution_preflight.get("store_ids")) or [])
    dry_run_store_ids = set(_normalize_formal_batch_store_ids(execution_dry_run.get("store_ids")) or [])
    final_store_ids = set(_normalize_formal_batch_store_ids(final_approval_context.get("store_ids")) or [])
    if not preflight_store_ids or not dry_run_store_ids:
        result["skip_reason"] = "batch_execution_scope_required"
        return result
    if not dry_run_store_ids.issubset(preflight_store_ids):
        result["skip_reason"] = "execution_dry_run_store_scope_mismatch"
        return result
    if not final_store_ids or not dry_run_store_ids.issubset(final_store_ids):
        result["skip_reason"] = "final_approval_store_scope_mismatch"
        return result

    preflight_sync_kinds = set(str(kind) for kind in (execution_preflight.get("sync_kinds") or []))
    dry_run_sync_kinds = set(str(kind) for kind in (execution_dry_run.get("sync_kinds") or []))
    final_sync_kinds = set(str(kind) for kind in (final_approval_context.get("sync_kinds") or []))
    if not preflight_sync_kinds or not dry_run_sync_kinds:
        result["skip_reason"] = "batch_execution_sync_kind_scope_required"
        return result
    if not dry_run_sync_kinds.issubset(preflight_sync_kinds):
        result["skip_reason"] = "execution_dry_run_sync_kind_mismatch"
        return result
    if not final_sync_kinds or not dry_run_sync_kinds.issubset(final_sync_kinds):
        result["skip_reason"] = "final_approval_sync_kind_scope_mismatch"
        return result

    preflight_targets = set(str(target) for target in (execution_preflight.get("targets") or []))
    dry_run_targets = set(str(target) for target in (execution_dry_run.get("targets") or []))
    final_targets = set(str(target) for target in (final_approval_context.get("targets") or []))
    if not dry_run_targets.issubset(preflight_targets):
        result["skip_reason"] = "execution_dry_run_target_mismatch"
        return result
    if not final_targets or not dry_run_targets.issubset(final_targets):
        result["skip_reason"] = "final_approval_target_scope_mismatch"
        return result

    required_actions = set(str(action) for action in (execution_preflight.get("required_actions") or []))
    final_required_actions = set(str(action) for action in (final_approval_context.get("required_actions") or []))
    expected_required_actions = {
        str(FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["required_action"])
        for sync_kind in dry_run_sync_kinds
        if sync_kind in FORMAL_BATCH_SYNC_GATE_KINDS
    }
    if expected_required_actions and not expected_required_actions.issubset(required_actions):
        result["skip_reason"] = "execution_preflight_action_scope_mismatch"
        return result
    if expected_required_actions and not expected_required_actions.issubset(final_required_actions):
        result["skip_reason"] = "final_approval_action_scope_mismatch"
        return result

    try:
        candidate_summary_count = int(execution_dry_run.get("candidate_summary_count") or 0)
        total_candidate_count = int(execution_dry_run.get("total_candidate_count") or 0)
        total_would_create = int(execution_dry_run.get("total_would_create") or 0)
        total_would_update = int(execution_dry_run.get("total_would_update") or 0)
        total_would_refresh_only = int(execution_dry_run.get("total_would_refresh_only") or 0)
        total_would_skip = int(execution_dry_run.get("total_would_skip") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "execution_dry_run_totals_invalid"
        return result
    if min(
        candidate_summary_count,
        total_candidate_count,
        total_would_create,
        total_would_update,
        total_would_refresh_only,
        total_would_skip,
    ) < 0:
        result["skip_reason"] = "execution_dry_run_totals_invalid"
        return result
    if total_would_create + total_would_update + total_would_refresh_only + total_would_skip > total_candidate_count:
        result["skip_reason"] = "execution_dry_run_totals_exceed_candidates"
        return result
    changed_fields = _normalize_safe_changed_fields(execution_dry_run.get("changed_fields") or [])
    if changed_fields is None:
        result["skip_reason"] = "execution_dry_run_changed_fields_invalid"
        return result

    result.update({
        "status": "formal_batch_execution_approval_mock_ready",
        "approval_status": "ready_for_separate_execution_phase",
        "final_approval_ready": True,
        "store_ids": sorted(dry_run_store_ids),
        "sync_kinds": sorted(dry_run_sync_kinds),
        "targets": sorted(dry_run_targets),
        "required_actions": sorted(expected_required_actions),
        "candidate_summary_count": candidate_summary_count,
        "total_candidate_count": total_candidate_count,
        "total_would_create": total_would_create,
        "total_would_update": total_would_update,
        "total_would_refresh_only": total_would_refresh_only,
        "total_would_skip": total_would_skip,
        "changed_fields": changed_fields,
        "candidate_summaries": execution_dry_run.get("candidate_summaries") or [],
        "business_message": (
            "Formal batch execution approval mock gate passed for review only. "
            "It does not approve execution, expose a write endpoint, write products or orders, call platform APIs, or open formal sync."
        ),
        "next_action": (
            "Plan a separate explicitly approved execution phase with fresh backup, readback, rollback, audit evidence, and sensitive-field scans."
        ),
    })
    return result


def evaluate_formal_batch_execution_approval_readonly_api_local(
    *,
    execution_preflight: dict | None,
    execution_dry_run: dict | None,
    final_approval_context: dict | None,
) -> dict:
    """Public local readonly wrapper for the final formal batch execution approval gate."""

    result = evaluate_formal_batch_execution_approval_mock_gate(
        execution_preflight=execution_preflight,
        execution_dry_run=execution_dry_run,
        final_approval_context=final_approval_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-3J",
        "formal_batch_execution_approval_readonly_api_local": True,
        "private_helper_only": False,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/execution-approval/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") == "formal_batch_execution_approval_mock_ready":
        result["status"] = "formal_batch_execution_approval_readonly_api_ready"
        result["approval_status"] = "ready_for_local_readonly_review"
        result["business_message"] = (
            "Formal batch execution approval is ready for local readonly review only. "
            "This does not approve execution, expose a write endpoint, write products or orders, call platform APIs, or open formal sync."
        )
        result["next_action"] = (
            "Use this readonly API as operator evidence before a separately approved execution phase with fresh backup, readback, rollback, audit evidence, and sensitive-field scans."
        )
    return result


def evaluate_formal_batch_execution_write_boundary_approval_plan(
    *,
    execution_approval: dict | None,
    write_boundary_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private plan gate for the write boundary before any formal batch execution."""

    required_write_boundary_flags = [
        "separate_execution_phase_required",
        "fresh_approval_required",
        "fresh_backup_required",
        "dry_run_recheck_required",
        "write_scope_freeze_required",
        "max_batch_size_enforced",
        "store_scope_locked",
        "permission_recheck_required",
        "audit_write_plan_required",
        "readback_required",
        "rollback_required",
        "sensitive_scan_required",
        "partial_failure_policy_required",
        "idempotency_required",
        "operator_confirmation_required",
        "execution_window_limited",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "ERP-Batch-4A",
        "formal_batch_execution_write_boundary_approval_plan": True,
        "private_helper_only": True,
        "status": "blocked",
        "approval_status": "blocked",
        "write_boundary_plan_ready": False,
        "skip_reason": None,
        "required_write_boundary_flags": required_write_boundary_flags,
        "missing_write_boundary_flags": [],
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "required_actions": [],
        "candidate_summary_count": 0,
        "total_candidate_count": 0,
        "total_would_create": 0,
        "total_would_update": 0,
        "total_would_refresh_only": 0,
        "total_would_skip": 0,
        "changed_fields": [],
        "candidate_summaries": [],
        "route_path": None,
        "http_method": None,
        "backend_route_implemented": False,
        "public_endpoint_enabled": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(execution_approval, dict):
        result["skip_reason"] = "execution_approval_required"
        return result
    if not isinstance(write_boundary_context, dict):
        result["skip_reason"] = "write_boundary_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "execution_approval": execution_approval,
        "write_boundary_context": write_boundary_context,
    }):
        result["skip_reason"] = "formal_batch_execution_write_boundary_sensitive_field_blocked"
        return result

    if execution_approval.get("status") != "formal_batch_execution_approval_readonly_api_ready":
        result["skip_reason"] = "execution_approval_not_ready"
        return result
    if execution_approval.get("final_approval_ready") is not True:
        result["skip_reason"] = "execution_approval_not_ready"
        return result

    side_effect_flags = [
        "execution_approved",
        "batch_execution_enabled",
        "write_endpoint_enabled",
        "real_api_called",
        "real_database_written",
        "orders_written",
        "products_written",
        "sync_log_written",
        "capability_tested_success_written",
        "timeline_events_written",
        "operation_audit_rows_written",
        "formal_sync_open",
        "formal_order_sync_open",
        "formal_product_sync_open",
        "platform_order_writes_enabled",
        "platform_product_writes_enabled",
        "platform_writes_enabled",
        "shipment_write_enabled",
        "cancel_write_enabled",
        "return_write_enabled",
        "exchange_write_enabled",
    ]
    for source_name, payload in (
        ("execution_approval", execution_approval),
        ("write_boundary_context", write_boundary_context),
    ):
        for flag in side_effect_flags:
            if payload.get(flag) is True:
                if flag == "execution_approved":
                    result["skip_reason"] = "execution_approval_not_allowed_in_write_boundary_plan"
                else:
                    result["skip_reason"] = "side_effect_not_allowed_in_write_boundary_plan"
                result["blocked_source"] = source_name
                result["blocked_flag"] = flag
                return result
        if payload.get("raw_response_saved") is not False and "raw_response_saved" in payload:
            result["skip_reason"] = "raw_response_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("privacy_fields_redacted") is not True and "privacy_fields_redacted" in payload:
            result["skip_reason"] = "privacy_redaction_required"
            result["blocked_source"] = source_name
            return result

    missing_flags = [
        flag for flag in required_write_boundary_flags
        if write_boundary_context.get(flag) is not True
    ]
    result["missing_write_boundary_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "write_boundary_context_incomplete"
        return result

    approval_store_ids = set(_normalize_formal_batch_store_ids(execution_approval.get("store_ids")) or [])
    boundary_store_ids = set(_normalize_formal_batch_store_ids(write_boundary_context.get("store_ids")) or [])
    if not approval_store_ids:
        result["skip_reason"] = "execution_approval_store_scope_required"
        return result
    if not boundary_store_ids or approval_store_ids != boundary_store_ids:
        result["skip_reason"] = "write_boundary_store_scope_mismatch"
        return result

    approval_sync_kinds = set(str(kind) for kind in (execution_approval.get("sync_kinds") or []))
    boundary_sync_kinds = set(str(kind) for kind in (write_boundary_context.get("sync_kinds") or []))
    if not approval_sync_kinds:
        result["skip_reason"] = "execution_approval_sync_kind_scope_required"
        return result
    if not boundary_sync_kinds or approval_sync_kinds != boundary_sync_kinds:
        result["skip_reason"] = "write_boundary_sync_kind_scope_mismatch"
        return result

    approval_targets = set(str(target) for target in (execution_approval.get("targets") or []))
    boundary_targets = set(str(target) for target in (write_boundary_context.get("targets") or []))
    if not approval_targets:
        result["skip_reason"] = "execution_approval_target_scope_required"
        return result
    if not boundary_targets or approval_targets != boundary_targets:
        result["skip_reason"] = "write_boundary_target_scope_mismatch"
        return result

    approval_required_actions = set(str(action) for action in (execution_approval.get("required_actions") or []))
    boundary_required_actions = set(str(action) for action in (write_boundary_context.get("required_actions") or []))
    expected_required_actions = {
        str(FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["required_action"])
        for sync_kind in approval_sync_kinds
        if sync_kind in FORMAL_BATCH_SYNC_GATE_KINDS
    }
    if expected_required_actions and not expected_required_actions.issubset(approval_required_actions):
        result["skip_reason"] = "execution_approval_action_scope_mismatch"
        return result
    if expected_required_actions and boundary_required_actions != expected_required_actions:
        result["skip_reason"] = "write_boundary_action_scope_mismatch"
        return result

    try:
        candidate_summary_count = int(execution_approval.get("candidate_summary_count") or 0)
        total_candidate_count = int(execution_approval.get("total_candidate_count") or 0)
        total_would_create = int(execution_approval.get("total_would_create") or 0)
        total_would_update = int(execution_approval.get("total_would_update") or 0)
        total_would_refresh_only = int(execution_approval.get("total_would_refresh_only") or 0)
        total_would_skip = int(execution_approval.get("total_would_skip") or 0)
        max_batch_size = int(write_boundary_context.get("max_batch_size") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "write_boundary_totals_invalid"
        return result
    if min(
        candidate_summary_count,
        total_candidate_count,
        total_would_create,
        total_would_update,
        total_would_refresh_only,
        total_would_skip,
        max_batch_size,
    ) < 0:
        result["skip_reason"] = "write_boundary_totals_invalid"
        return result
    if total_would_create + total_would_update + total_would_refresh_only + total_would_skip > total_candidate_count:
        result["skip_reason"] = "execution_approval_totals_exceed_candidates"
        return result
    if max_batch_size == 0:
        result["skip_reason"] = "max_batch_size_required"
        return result
    if total_candidate_count > max_batch_size:
        result["skip_reason"] = "write_boundary_candidate_count_exceeds_limit"
        result["max_batch_size"] = max_batch_size
        return result
    changed_fields = _normalize_safe_changed_fields(execution_approval.get("changed_fields") or [])
    if changed_fields is None:
        result["skip_reason"] = "execution_approval_changed_fields_invalid"
        return result

    result.update({
        "status": "formal_batch_execution_write_boundary_approval_plan_ready",
        "approval_status": "ready_for_separate_write_execution_phase",
        "write_boundary_plan_ready": True,
        "store_ids": sorted(approval_store_ids),
        "sync_kinds": sorted(approval_sync_kinds),
        "targets": sorted(approval_targets),
        "required_actions": sorted(expected_required_actions),
        "candidate_summary_count": candidate_summary_count,
        "total_candidate_count": total_candidate_count,
        "total_would_create": total_would_create,
        "total_would_update": total_would_update,
        "total_would_refresh_only": total_would_refresh_only,
        "total_would_skip": total_would_skip,
        "changed_fields": changed_fields,
        "candidate_summaries": execution_approval.get("candidate_summaries") or [],
        "max_batch_size": max_batch_size,
        "business_message": (
            "Formal batch execution write boundary plan is ready for review only. "
            "No execution route is exposed, no products or orders are written, no audit rows are created, no platform APIs are called, and formal sync remains closed."
        ),
        "next_action": (
            "A future execution phase must refresh approval, backup, dry-run evidence, permissions, audit write plan, readback, rollback, idempotency, and sensitive scans before any local batch write."
        ),
    })
    return result


def evaluate_formal_batch_execution_write_boundary_readonly_api_mock_gate(
    *,
    execution_approval: dict | None,
    write_boundary_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly API around the formal batch write boundary."""

    result = evaluate_formal_batch_execution_write_boundary_approval_plan(
        execution_approval=execution_approval,
        write_boundary_context=write_boundary_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "product_write_endpoint_excluded",
        "order_write_endpoint_excluded",
        "audit_row_write_excluded",
        "sensitive_fields_hidden_from_main_page",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "ERP-Batch-4B",
        "formal_batch_execution_write_boundary_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/execution-write-boundary/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") != "formal_batch_execution_write_boundary_approval_plan_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "write_boundary_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if (
        readonly_api_context.get("orders_written") is True
        or readonly_api_context.get("products_written") is True
        or readonly_api_context.get("operation_audit_rows_written") is True
        or readonly_api_context.get("write_endpoint_enabled") is True
    ):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "write_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["write_boundary_plan_ready"] = False
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "formal_batch_execution_write_boundary_readonly_api_mock_ready",
        "approval_status": "ready_for_readonly_api_planning",
        "write_boundary_plan_ready": True,
        "business_message": (
            "Formal batch execution write-boundary readonly API mock gate passed. "
            "It plans review-only display; no execution route is exposed, no products or orders are written, no audit rows are created, no platform APIs are called, and formal sync remains closed."
        ),
        "next_action": (
            "Plan a local readonly route separately. Product/order batch execution still requires a later explicit approval phase with fresh backup, dry-run, audit, readback, rollback, and sensitive scans."
        ),
    })
    return result


def evaluate_formal_batch_execution_write_boundary_readonly_api_local(
    *,
    execution_approval: dict | None,
    write_boundary_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for the formal batch write-boundary review."""

    result = evaluate_formal_batch_execution_write_boundary_readonly_api_mock_gate(
        execution_approval=execution_approval,
        write_boundary_context=write_boundary_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-4C",
        "formal_batch_execution_write_boundary_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/execution-write-boundary/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") == "formal_batch_execution_write_boundary_readonly_api_mock_ready":
        result["status"] = "formal_batch_execution_write_boundary_readonly_api_ready"
        result["approval_status"] = "ready_for_local_readonly_review"
        result["business_message"] = (
            "Formal batch execution write-boundary readonly API is ready for local review only. "
            "It does not approve execution, expose a write endpoint, write products or orders, create audit rows, call platform APIs, or open formal sync."
        )
        result["next_action"] = (
            "Use this readonly API as operator evidence before a separately approved execution phase with fresh backup, dry-run, audit, readback, rollback, idempotency, and sensitive scans."
        )
    return result


def evaluate_formal_batch_pre_execution_backup_audit_refresh_gate(
    *,
    write_boundary_review: dict | None,
    backup_refresh_evidence: dict | None,
    audit_refresh_evidence: dict | None,
    verification_scope: str | None,
) -> dict:
    """Private gate requiring fresh backup and audit evidence before any later batch execution."""

    required_backup_flags = [
        "fresh_backup_created",
        "backup_manifest_verified",
        "backup_sha256_verified",
        "restore_dry_run_referenced",
        "backup_created_after_boundary_review",
        "safe_backup_reference_only",
    ]
    required_audit_flags = [
        "audit_correlation_planned",
        "append_only_audit_chain_planned",
        "actor_store_scope_verified",
        "safe_metadata_only",
        "backup_evidence_link_planned",
        "write_attempt_record_planned",
        "readback_audit_planned",
        "rollback_audit_planned",
        "no_audit_rows_written_yet",
    ]
    result = {
        "phase": "ERP-Batch-4E",
        "formal_batch_pre_execution_backup_audit_refresh_gate": True,
        "private_helper_only": True,
        "status": "blocked",
        "approval_status": "blocked",
        "pre_execution_backup_audit_refresh_gate_ready": False,
        "skip_reason": None,
        "required_backup_flags": required_backup_flags,
        "missing_backup_flags": [],
        "required_audit_flags": required_audit_flags,
        "missing_audit_flags": [],
        "backup_refresh_verified": False,
        "audit_refresh_verified": False,
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "required_actions": [],
        "candidate_summary_count": 0,
        "total_candidate_count": 0,
        "total_would_create": 0,
        "total_would_update": 0,
        "total_would_refresh_only": 0,
        "total_would_skip": 0,
        "changed_fields": [],
        "candidate_summaries": [],
        "backup_sha256_abbrev": None,
        "audit_correlation_reference": None,
        "route_path": None,
        "http_method": None,
        "backend_route_implemented": False,
        "public_endpoint_enabled": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(write_boundary_review, dict):
        result["skip_reason"] = "write_boundary_review_required"
        return result
    if not isinstance(backup_refresh_evidence, dict):
        result["skip_reason"] = "backup_refresh_evidence_required"
        return result
    if not isinstance(audit_refresh_evidence, dict):
        result["skip_reason"] = "audit_refresh_evidence_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "write_boundary_review": write_boundary_review,
        "backup_refresh_evidence": backup_refresh_evidence,
        "audit_refresh_evidence": audit_refresh_evidence,
    }):
        result["skip_reason"] = "pre_execution_refresh_sensitive_field_blocked"
        return result

    if write_boundary_review.get("status") != "formal_batch_execution_write_boundary_readonly_api_ready":
        result["skip_reason"] = "write_boundary_review_not_ready"
        return result
    if write_boundary_review.get("write_boundary_plan_ready") is not True:
        result["skip_reason"] = "write_boundary_review_not_ready"
        return result

    side_effect_flags = [
        "execution_approved",
        "batch_execution_enabled",
        "write_endpoint_enabled",
        "real_api_called",
        "real_database_written",
        "orders_written",
        "products_written",
        "sync_log_written",
        "capability_tested_success_written",
        "timeline_events_written",
        "operation_audit_rows_written",
        "formal_sync_open",
        "formal_order_sync_open",
        "formal_product_sync_open",
        "platform_order_writes_enabled",
        "platform_product_writes_enabled",
        "platform_writes_enabled",
        "shipment_write_enabled",
        "cancel_write_enabled",
        "return_write_enabled",
        "exchange_write_enabled",
    ]
    for source_name, payload in (
        ("write_boundary_review", write_boundary_review),
        ("backup_refresh_evidence", backup_refresh_evidence),
        ("audit_refresh_evidence", audit_refresh_evidence),
    ):
        for flag in side_effect_flags:
            if payload.get(flag) is True:
                result["skip_reason"] = "side_effect_not_allowed_in_pre_execution_refresh_gate"
                result["blocked_source"] = source_name
                result["blocked_flag"] = flag
                return result
        if payload.get("raw_response_saved") is not False and "raw_response_saved" in payload:
            result["skip_reason"] = "raw_response_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("secrets_saved") is not False and "secrets_saved" in payload:
            result["skip_reason"] = "secrets_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("privacy_fields_redacted") is not True and "privacy_fields_redacted" in payload:
            result["skip_reason"] = "privacy_redaction_required"
            result["blocked_source"] = source_name
            return result

    review_store_ids = set(_normalize_formal_batch_store_ids(write_boundary_review.get("store_ids")) or [])
    backup_store_ids = set(_normalize_formal_batch_store_ids(backup_refresh_evidence.get("store_ids")) or [])
    audit_store_ids = set(_normalize_formal_batch_store_ids(audit_refresh_evidence.get("store_ids")) or [])
    if not review_store_ids:
        result["skip_reason"] = "write_boundary_store_scope_required"
        return result
    if backup_store_ids != review_store_ids:
        result["skip_reason"] = "backup_refresh_store_scope_mismatch"
        return result
    if audit_store_ids != review_store_ids:
        result["skip_reason"] = "audit_refresh_store_scope_mismatch"
        return result

    review_sync_kinds = set(str(kind) for kind in (write_boundary_review.get("sync_kinds") or []))
    backup_sync_kinds = set(str(kind) for kind in (backup_refresh_evidence.get("sync_kinds") or []))
    audit_sync_kinds = set(str(kind) for kind in (audit_refresh_evidence.get("sync_kinds") or []))
    if not review_sync_kinds:
        result["skip_reason"] = "write_boundary_sync_kind_scope_required"
        return result
    if backup_sync_kinds != review_sync_kinds:
        result["skip_reason"] = "backup_refresh_sync_kind_scope_mismatch"
        return result
    if audit_sync_kinds != review_sync_kinds:
        result["skip_reason"] = "audit_refresh_sync_kind_scope_mismatch"
        return result

    review_targets = set(str(target) for target in (write_boundary_review.get("targets") or []))
    backup_targets = set(str(target) for target in (backup_refresh_evidence.get("targets") or []))
    audit_targets = set(str(target) for target in (audit_refresh_evidence.get("targets") or []))
    if not review_targets:
        result["skip_reason"] = "write_boundary_target_scope_required"
        return result
    if backup_targets != review_targets:
        result["skip_reason"] = "backup_refresh_target_scope_mismatch"
        return result
    if audit_targets != review_targets:
        result["skip_reason"] = "audit_refresh_target_scope_mismatch"
        return result

    review_required_actions = set(str(action) for action in (write_boundary_review.get("required_actions") or []))
    backup_required_actions = set(str(action) for action in (backup_refresh_evidence.get("required_actions") or []))
    audit_required_actions = set(str(action) for action in (audit_refresh_evidence.get("required_actions") or []))
    planned_action_names = set(str(action) for action in (audit_refresh_evidence.get("planned_action_names") or []))
    if not review_required_actions:
        result["skip_reason"] = "write_boundary_action_scope_required"
        return result
    if backup_required_actions != review_required_actions:
        result["skip_reason"] = "backup_refresh_action_scope_mismatch"
        return result
    if audit_required_actions != review_required_actions:
        result["skip_reason"] = "audit_refresh_action_scope_mismatch"
        return result
    if not review_required_actions.issubset(planned_action_names):
        result["skip_reason"] = "audit_refresh_planned_actions_incomplete"
        return result

    missing_backup_flags = [
        flag for flag in required_backup_flags
        if backup_refresh_evidence.get(flag) is not True
    ]
    result["missing_backup_flags"] = missing_backup_flags
    if missing_backup_flags:
        result["skip_reason"] = "backup_refresh_evidence_incomplete"
        return result
    if backup_refresh_evidence.get("sqlite_integrity_check") != "ok":
        result["skip_reason"] = "backup_sqlite_integrity_not_verified"
        return result
    backup_sha256 = str(backup_refresh_evidence.get("backup_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", backup_sha256):
        result["skip_reason"] = "backup_sha256_invalid"
        return result
    if backup_refresh_evidence.get("backup_deleted") is True:
        result["skip_reason"] = "backup_deleted_not_allowed"
        return result
    if backup_refresh_evidence.get("production_db_touched") is True:
        result["skip_reason"] = "production_db_touched_not_allowed"
        return result

    missing_audit_flags = [
        flag for flag in required_audit_flags
        if audit_refresh_evidence.get(flag) is not True
    ]
    result["missing_audit_flags"] = missing_audit_flags
    if missing_audit_flags:
        result["skip_reason"] = "audit_refresh_evidence_incomplete"
        return result

    try:
        candidate_summary_count = int(write_boundary_review.get("candidate_summary_count") or 0)
        total_candidate_count = int(write_boundary_review.get("total_candidate_count") or 0)
        total_would_create = int(write_boundary_review.get("total_would_create") or 0)
        total_would_update = int(write_boundary_review.get("total_would_update") or 0)
        total_would_refresh_only = int(write_boundary_review.get("total_would_refresh_only") or 0)
        total_would_skip = int(write_boundary_review.get("total_would_skip") or 0)
    except (TypeError, ValueError):
        result["skip_reason"] = "write_boundary_candidate_counts_invalid"
        return result
    if min(
        candidate_summary_count,
        total_candidate_count,
        total_would_create,
        total_would_update,
        total_would_refresh_only,
        total_would_skip,
    ) < 0:
        result["skip_reason"] = "write_boundary_candidate_counts_invalid"
        return result
    if total_would_create + total_would_update + total_would_refresh_only + total_would_skip > total_candidate_count:
        result["skip_reason"] = "write_boundary_candidate_totals_exceed_candidates"
        return result
    changed_fields = _normalize_safe_changed_fields(write_boundary_review.get("changed_fields") or [])
    if changed_fields is None:
        result["skip_reason"] = "write_boundary_changed_fields_invalid"
        return result

    result.update({
        "status": "formal_batch_pre_execution_backup_audit_refresh_gate_ready",
        "approval_status": "ready_for_separate_execution_phase_after_refresh_review",
        "pre_execution_backup_audit_refresh_gate_ready": True,
        "backup_refresh_verified": True,
        "audit_refresh_verified": True,
        "store_ids": sorted(review_store_ids),
        "sync_kinds": sorted(review_sync_kinds),
        "targets": sorted(review_targets),
        "required_actions": sorted(review_required_actions),
        "candidate_summary_count": candidate_summary_count,
        "total_candidate_count": total_candidate_count,
        "total_would_create": total_would_create,
        "total_would_update": total_would_update,
        "total_would_refresh_only": total_would_refresh_only,
        "total_would_skip": total_would_skip,
        "changed_fields": changed_fields,
        "candidate_summaries": write_boundary_review.get("candidate_summaries") or [],
        "backup_sha256_abbrev": f"{backup_sha256[:12]}...",
        "audit_correlation_reference": (
            str(audit_refresh_evidence.get("audit_correlation_id_hash") or "")[:24] or None
        ),
        "business_message": (
            "Formal batch pre-execution backup and audit refresh gate is ready for review only. "
            "A fresh backup and append-only audit plan are referenced, but no batch execution, product/order write, audit row write, platform call, or formal sync opening occurs."
        ),
        "next_action": (
            "A later explicit execution phase must use this refreshed evidence, then perform local writes only after backup, readback, rollback, audit, permission, and sensitive scans pass again."
        ),
    })
    return result


def evaluate_formal_batch_pre_execution_refresh_readonly_api_mock_gate(
    *,
    write_boundary_review: dict | None,
    backup_refresh_evidence: dict | None,
    audit_refresh_evidence: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly API around the pre-execution refresh review."""

    result = evaluate_formal_batch_pre_execution_backup_audit_refresh_gate(
        write_boundary_review=write_boundary_review,
        backup_refresh_evidence=backup_refresh_evidence,
        audit_refresh_evidence=audit_refresh_evidence,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "backup_creation_button_excluded",
        "audit_row_write_excluded",
        "product_write_endpoint_excluded",
        "order_write_endpoint_excluded",
        "sensitive_fields_hidden_from_main_page",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "ERP-Batch-4F",
        "formal_batch_pre_execution_refresh_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/pre-execution-refresh/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") != "formal_batch_pre_execution_backup_audit_refresh_gate_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "pre_execution_refresh_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if (
        readonly_api_context.get("orders_written") is True
        or readonly_api_context.get("products_written") is True
        or readonly_api_context.get("operation_audit_rows_written") is True
        or readonly_api_context.get("write_endpoint_enabled") is True
        or readonly_api_context.get("backup_created") is True
        or readonly_api_context.get("restore_executed") is True
    ):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "write_not_allowed_in_pre_execution_refresh_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["pre_execution_backup_audit_refresh_gate_ready"] = False
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "formal_batch_pre_execution_refresh_readonly_api_mock_ready",
        "approval_status": "ready_for_readonly_api_planning",
        "pre_execution_backup_audit_refresh_gate_ready": True,
        "business_message": (
            "Formal batch pre-execution refresh readonly API mock gate passed. "
            "It plans review-only display for refreshed backup and audit evidence; no route is exposed, no backup is created, no audit rows are written, no products or orders are written, no platform APIs are called, and formal sync remains closed."
        ),
        "next_action": (
            "Plan a local readonly route separately. Product/order batch execution still requires a later explicit execution phase with fresh evidence, readback, rollback, permissions, and sensitive scans."
        ),
    })
    return result


def evaluate_formal_batch_pre_execution_refresh_readonly_api_local(
    *,
    write_boundary_review: dict | None,
    backup_refresh_evidence: dict | None,
    audit_refresh_evidence: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for the pre-execution backup/audit refresh review."""

    result = evaluate_formal_batch_pre_execution_refresh_readonly_api_mock_gate(
        write_boundary_review=write_boundary_review,
        backup_refresh_evidence=backup_refresh_evidence,
        audit_refresh_evidence=audit_refresh_evidence,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-4G",
        "formal_batch_pre_execution_refresh_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/pre-execution-refresh/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") == "formal_batch_pre_execution_refresh_readonly_api_mock_ready":
        result["status"] = "formal_batch_pre_execution_refresh_readonly_api_ready"
        result["approval_status"] = "ready_for_local_readonly_review"
        result["business_message"] = (
            "Formal batch pre-execution refresh readonly API is ready for local review only. "
            "It does not approve execution, create backups, write audit rows, write products or orders, call platform APIs, or open formal sync."
        )
        result["next_action"] = (
            "Use this readonly route as operator evidence before a separately approved execution phase with refreshed backup, audit, readback, rollback, permission, and sensitive-scan evidence."
        )
    return result


def evaluate_formal_batch_write_execution_mock_gate(
    *,
    pre_execution_refresh_review: dict | None,
    write_execution_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Final mock gate before a separately approved formal product/order batch write."""

    required_execution_flags = [
        "explicit_human_approval_recorded",
        "approval_decision_referenced",
        "approval_audit_linkage_referenced",
        "pre_execution_refresh_referenced",
        "fresh_backup_referenced",
        "backup_manifest_verified",
        "audit_correlation_referenced",
        "permission_recheck_passed",
        "dry_run_recheck_passed",
        "write_scope_frozen",
        "max_batch_size_enforced",
        "local_write_plan_whitelisted",
        "idempotency_key_planned",
        "duplicate_protection_verified",
        "readback_plan_locked",
        "rollback_plan_locked",
        "sensitive_scan_passed",
        "operator_confirmation_recorded",
        "partial_failure_policy_locked",
        "formal_sync_remains_closed",
        "platform_writes_remain_closed",
    ]
    result = {
        "phase": "ERP-Batch-5B",
        "formal_batch_write_execution_mock_gate": True,
        "private_helper_only": True,
        "status": "blocked",
        "approval_status": "blocked",
        "batch_write_ready_for_separate_execution_phase": False,
        "execution_allowed": False,
        "skip_reason": None,
        "required_execution_flags": required_execution_flags,
        "missing_execution_flags": [],
        "store_ids": [],
        "sync_kinds": [],
        "targets": [],
        "required_actions": [],
        "candidate_summary_count": 0,
        "total_candidate_count": 0,
        "total_would_create": 0,
        "total_would_update": 0,
        "total_would_refresh_only": 0,
        "total_would_skip": 0,
        "changed_fields": [],
        "candidate_summaries": [],
        "max_batch_size": 0,
        "approval_record_reference": None,
        "backup_manifest_reference": None,
        "audit_correlation_reference": None,
        "idempotency_key_reference": None,
        "backend_route_implemented": False,
        "public_endpoint_enabled": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_call_requested": False,
        "local_database_write_requested": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(pre_execution_refresh_review, dict):
        result["skip_reason"] = "pre_execution_refresh_review_required"
        return result
    if not isinstance(write_execution_context, dict):
        result["skip_reason"] = "write_execution_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "pre_execution_refresh_review": pre_execution_refresh_review,
        "write_execution_context": write_execution_context,
    }):
        result["skip_reason"] = "formal_batch_write_execution_sensitive_field_blocked"
        return result

    if pre_execution_refresh_review.get("status") != "formal_batch_pre_execution_refresh_readonly_api_ready":
        result["skip_reason"] = "pre_execution_refresh_review_not_ready"
        return result
    if pre_execution_refresh_review.get("pre_execution_backup_audit_refresh_gate_ready") is not True:
        result["skip_reason"] = "pre_execution_refresh_review_not_ready"
        return result

    side_effect_flags = [
        "execution_approved",
        "batch_execution_enabled",
        "write_endpoint_enabled",
        "real_api_called",
        "real_database_written",
        "orders_written",
        "products_written",
        "sync_log_written",
        "capability_tested_success_written",
        "timeline_events_written",
        "operation_audit_rows_written",
        "formal_sync_open",
        "formal_order_sync_open",
        "formal_product_sync_open",
        "platform_order_writes_enabled",
        "platform_product_writes_enabled",
        "platform_writes_enabled",
        "shipment_write_enabled",
        "cancel_write_enabled",
        "return_write_enabled",
        "exchange_write_enabled",
    ]
    for source_name, payload in (
        ("pre_execution_refresh_review", pre_execution_refresh_review),
        ("write_execution_context", write_execution_context),
    ):
        for flag in side_effect_flags:
            if payload.get(flag) is True:
                if flag == "execution_approved":
                    result["skip_reason"] = "execution_approval_not_allowed_in_write_execution_mock_gate"
                else:
                    result["skip_reason"] = "side_effect_not_allowed_in_write_execution_mock_gate"
                result["blocked_source"] = source_name
                result["blocked_flag"] = flag
                return result
        if payload.get("raw_response_saved") is not False and "raw_response_saved" in payload:
            result["skip_reason"] = "raw_response_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("secrets_saved") is not False and "secrets_saved" in payload:
            result["skip_reason"] = "secrets_saved_not_allowed"
            result["blocked_source"] = source_name
            return result
        if payload.get("privacy_fields_redacted") is not True and "privacy_fields_redacted" in payload:
            result["skip_reason"] = "privacy_redaction_required"
            result["blocked_source"] = source_name
            return result

    request_flags = [
        "real_api_call_requested",
        "platform_write_requested",
        "platform_product_write_requested",
        "platform_order_write_requested",
        "naver_writeback_requested",
        "local_database_write_requested",
        "real_sync",
        "write_requested",
    ]
    for flag in request_flags:
        if write_execution_context.get(flag) is True:
            if flag == "real_api_call_requested":
                result["skip_reason"] = "real_api_call_not_allowed_in_write_execution_mock_gate"
            elif flag in {"local_database_write_requested", "real_sync", "write_requested"}:
                result["skip_reason"] = "local_write_request_not_allowed_in_write_execution_mock_gate"
            else:
                result["skip_reason"] = "platform_write_not_allowed_in_write_execution_mock_gate"
            result["blocked_flag"] = flag
            return result

    missing_flags = [
        flag for flag in required_execution_flags
        if write_execution_context.get(flag) is not True
    ]
    result["missing_execution_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "write_execution_context_incomplete"
        return result

    review_store_ids = set(_normalize_formal_batch_store_ids(pre_execution_refresh_review.get("store_ids")) or [])
    context_store_ids = set(_normalize_formal_batch_store_ids(write_execution_context.get("store_ids")) or [])
    if not review_store_ids:
        result["skip_reason"] = "pre_execution_refresh_store_scope_required"
        return result
    if context_store_ids != review_store_ids:
        result["skip_reason"] = "write_execution_store_scope_mismatch"
        return result

    review_sync_kinds = set(str(kind) for kind in (pre_execution_refresh_review.get("sync_kinds") or []))
    context_sync_kinds = set(str(kind) for kind in (write_execution_context.get("sync_kinds") or []))
    if not review_sync_kinds:
        result["skip_reason"] = "pre_execution_refresh_sync_kind_scope_required"
        return result
    if context_sync_kinds != review_sync_kinds:
        result["skip_reason"] = "write_execution_sync_kind_scope_mismatch"
        return result

    review_targets = set(str(target) for target in (pre_execution_refresh_review.get("targets") or []))
    context_targets = set(str(target) for target in (write_execution_context.get("targets") or []))
    if not review_targets:
        result["skip_reason"] = "pre_execution_refresh_target_scope_required"
        return result
    if context_targets != review_targets:
        result["skip_reason"] = "write_execution_target_scope_mismatch"
        return result

    review_required_actions = set(str(action) for action in (pre_execution_refresh_review.get("required_actions") or []))
    context_required_actions = set(str(action) for action in (write_execution_context.get("required_actions") or []))
    expected_required_actions = {
        str(FORMAL_BATCH_SYNC_GATE_KINDS[sync_kind]["required_action"])
        for sync_kind in review_sync_kinds
        if sync_kind in FORMAL_BATCH_SYNC_GATE_KINDS
    }
    if not review_required_actions:
        result["skip_reason"] = "pre_execution_refresh_action_scope_required"
        return result
    if expected_required_actions and review_required_actions != expected_required_actions:
        result["skip_reason"] = "pre_execution_refresh_action_scope_mismatch"
        return result
    if context_required_actions != review_required_actions:
        result["skip_reason"] = "write_execution_action_scope_mismatch"
        return result

    try:
        candidate_summary_count = int(pre_execution_refresh_review.get("candidate_summary_count") or 0)
        total_candidate_count = int(pre_execution_refresh_review.get("total_candidate_count") or 0)
        max_batch_size = int(write_execution_context.get("max_batch_size") or 0)
        context_candidate_summary_count = int(
            write_execution_context.get("candidate_summary_count", candidate_summary_count)
        )
        context_total_candidate_count = int(
            write_execution_context.get("total_candidate_count", total_candidate_count)
        )
    except (TypeError, ValueError):
        result["skip_reason"] = "write_execution_candidate_counts_invalid"
        return result
    if min(candidate_summary_count, total_candidate_count, max_batch_size) < 0:
        result["skip_reason"] = "write_execution_candidate_counts_invalid"
        return result
    if candidate_summary_count == 0 or total_candidate_count == 0:
        result["skip_reason"] = "write_execution_candidate_count_required"
        return result
    if context_candidate_summary_count != candidate_summary_count or context_total_candidate_count != total_candidate_count:
        result["skip_reason"] = "write_execution_candidate_count_mismatch"
        return result
    if max_batch_size == 0:
        result["skip_reason"] = "max_batch_size_required"
        return result
    if total_candidate_count > max_batch_size:
        result["skip_reason"] = "write_execution_candidate_count_exceeds_limit"
        result["max_batch_size"] = max_batch_size
        return result

    changed_fields = _normalize_safe_changed_fields(pre_execution_refresh_review.get("changed_fields") or [])
    if changed_fields is None:
        result["skip_reason"] = "pre_execution_refresh_changed_fields_invalid"
        return result
    approved_changed_fields = write_execution_context.get("approved_changed_fields")
    if approved_changed_fields is not None:
        safe_approved_changed_fields = _normalize_safe_changed_fields(approved_changed_fields)
        if safe_approved_changed_fields is None:
            result["skip_reason"] = "write_execution_approved_changed_fields_invalid"
            return result
        if not set(changed_fields).issubset(set(safe_approved_changed_fields)):
            result["skip_reason"] = "write_execution_changed_fields_not_approved"
            return result

    safe_reference_pattern = r"[a-z0-9][a-z0-9._:-]{6,127}"
    required_references = {
        "approval_record_hash": "approval_record_reference",
        "backup_manifest_reference": "backup_manifest_reference",
        "audit_correlation_id_hash": "audit_correlation_reference",
        "idempotency_key_hash": "idempotency_key_reference",
    }
    safe_references: dict[str, str] = {}
    for source_key, output_key in required_references.items():
        value = str(write_execution_context.get(source_key) or "").strip().lower()
        if not re.fullmatch(safe_reference_pattern, value):
            result["skip_reason"] = f"{source_key}_invalid"
            return result
        safe_references[output_key] = value[:32]

    result.update({
        "status": "formal_batch_write_execution_mock_gate_ready",
        "approval_status": "ready_for_separate_write_execution_phase",
        "batch_write_ready_for_separate_execution_phase": True,
        "store_ids": sorted(review_store_ids),
        "sync_kinds": sorted(review_sync_kinds),
        "targets": sorted(review_targets),
        "required_actions": sorted(review_required_actions),
        "candidate_summary_count": candidate_summary_count,
        "total_candidate_count": total_candidate_count,
        "total_would_create": int(pre_execution_refresh_review.get("total_would_create") or 0),
        "total_would_update": int(pre_execution_refresh_review.get("total_would_update") or 0),
        "total_would_refresh_only": int(pre_execution_refresh_review.get("total_would_refresh_only") or 0),
        "total_would_skip": int(pre_execution_refresh_review.get("total_would_skip") or 0),
        "changed_fields": changed_fields,
        "candidate_summaries": pre_execution_refresh_review.get("candidate_summaries") or [],
        "max_batch_size": max_batch_size,
        **safe_references,
        "business_message": (
            "Formal product/order batch write execution mock gate is ready for review only. "
            "It confirms approval, backup, audit, permission, dry-run, idempotency, readback, rollback, and sensitive-scan evidence, but it still does not allow execution, write products or orders, write audit rows, call platform APIs, or open formal sync."
        ),
        "next_action": (
            "A later separately approved execution phase may use this evidence to perform local product/order batch writes with immediate readback, rollback evidence, and audit rows. Platform writes remain closed until separately approved."
        ),
    })
    return result


def evaluate_formal_batch_write_execution_readonly_api_mock_gate(
    *,
    pre_execution_refresh_review: dict | None,
    write_execution_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for exposing final batch write-execution evidence as readonly API."""

    result = evaluate_formal_batch_write_execution_mock_gate(
        pre_execution_refresh_review=pre_execution_refresh_review,
        write_execution_context=write_execution_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "product_write_endpoint_excluded",
        "order_write_endpoint_excluded",
        "platform_write_endpoint_excluded",
        "audit_row_write_excluded",
        "sensitive_fields_hidden_from_main_page",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "ERP-Batch-5D",
        "formal_batch_write_execution_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/write-execution/readonly-check",
        "http_method_planned": "POST",
        "backend_route_implemented": False,
        "public_endpoint_enabled": False,
        "execution_allowed": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_call_requested": False,
        "local_database_write_requested": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") != "formal_batch_write_execution_mock_gate_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "write_execution_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result

    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["approval_status"] = "blocked"
        result["batch_write_ready_for_separate_execution_phase"] = False
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    blocked_flags = [
        "execution_allowed",
        "execution_approved",
        "batch_execution_enabled",
        "write_endpoint_enabled",
        "real_api_call_requested",
        "local_database_write_requested",
        "real_sync",
        "write_requested",
        "orders_written",
        "products_written",
        "operation_audit_rows_written",
        "real_api_called",
        "real_database_written",
        "formal_sync_open",
        "platform_writes_enabled",
    ]
    for flag in blocked_flags:
        if readonly_api_context.get(flag) is True:
            result["status"] = "blocked"
            result["approval_status"] = "blocked"
            result["batch_write_ready_for_separate_execution_phase"] = False
            result["skip_reason"] = "write_not_allowed_in_write_execution_readonly_api_mock_gate"
            result["blocked_flag"] = flag
            return result

    result.update({
        "status": "formal_batch_write_execution_readonly_api_mock_ready",
        "approval_status": "ready_for_readonly_api_planning",
        "batch_write_ready_for_separate_execution_phase": True,
        "business_message": (
            "Formal product/order batch write-execution readonly API mock gate passed. "
            "It plans a review-only evidence route; no execution button, write endpoint, product/order write, audit-row write, platform call, or formal sync opening is allowed."
        ),
        "next_action": (
            "Implement the local readonly route separately. Any local batch write still requires a later explicit execution phase with fresh backup, audit, readback, rollback, and sensitive scans."
        ),
    })
    return result


def evaluate_formal_batch_write_execution_readonly_api_local(
    *,
    pre_execution_refresh_review: dict | None,
    write_execution_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for final formal batch write-execution evidence."""

    result = evaluate_formal_batch_write_execution_readonly_api_mock_gate(
        pre_execution_refresh_review=pre_execution_refresh_review,
        write_execution_context=write_execution_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "ERP-Batch-5E",
        "formal_batch_write_execution_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/write-execution/readonly-check",
        "http_method": "POST",
        "execution_allowed": False,
        "execution_approved": False,
        "batch_execution_enabled": False,
        "write_endpoint_enabled": False,
        "real_api_call_requested": False,
        "local_database_write_requested": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") == "formal_batch_write_execution_readonly_api_mock_ready":
        result["status"] = "formal_batch_write_execution_readonly_api_ready"
        result["approval_status"] = "ready_for_local_readonly_review"
        result["business_message"] = (
            "Formal product/order batch write-execution evidence is available for local readonly review only. "
            "This route does not approve execution, write products or orders, write audit rows, call platform APIs, or open formal sync."
        )
        result["next_action"] = (
            "Use this route as final operator evidence before a separately approved local execution phase. Platform writes remain closed."
        )
    return result


def evaluate_naver_order_batch_execution_approval_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock approval gate for a later Naver order batch execution phase; never writes."""

    required_execution_flags = [
        "order_batch_candidates_fresh",
        "order_privacy_gate_verified",
        "order_field_whitelist_verified",
        "delivery_claim_mapping_reviewed",
        "duplicate_protection_ready",
        "audit_chain_ready",
        "post_write_readback_required",
        "rollback_plan_ready",
        "sensitive_scan_passed",
        "platform_order_write_actions_excluded",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "Naver-Order-Batch-2B",
        "naver_order_batch_execution_approval_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "required_execution_flags": required_execution_flags,
        "missing_execution_flags": [],
        "order_batch_execution_approval_ready": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(execution_context, dict):
        result["skip_reason"] = "execution_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "readonly_evidence": readonly_evidence,
        "backup_evidence": backup_evidence,
        "execution_context": execution_context,
    }):
        result["skip_reason"] = "naver_order_batch_execution_sensitive_field_blocked"
        return result

    missing_flags = [
        flag for flag in required_execution_flags
        if execution_context.get(flag) is not True
    ]
    result["missing_execution_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "order_batch_execution_context_incomplete"
        return result
    if execution_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if execution_context.get("formal_sync_open") is True or execution_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    production_gate = _evaluate_formal_batch_sync_production_gate(
        sync_kind="naver_order_batch",
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        audit_plan_ready=True,
        rollback_plan_ready=True,
        duplicate_protection_ready=True,
        failure_isolation_ready=True,
        multi_store_isolation_ready=True,
        verification_scope=verification_scope,
        write_requested=True,
    )
    result["production_gate"] = production_gate
    result.update({
        "store_ids": production_gate.get("store_ids") or [],
        "candidate_count": production_gate.get("candidate_count"),
        "batch_size": production_gate.get("batch_size"),
        "permission_verified": bool(production_gate.get("permission_verified")),
        "approval_role_verified": bool(production_gate.get("approval_role_verified")),
        "backup_evidence_verified": bool(production_gate.get("backup_evidence_verified")),
        "readonly_evidence_verified": bool(production_gate.get("readonly_evidence_verified")),
    })
    if production_gate.get("status") != "formal_batch_gate_ready_for_later_execution":
        result["skip_reason"] = production_gate.get("skip_reason") or "formal_batch_gate_not_ready"
        return result

    result.update({
        "status": "naver_order_batch_execution_approval_mock_ready",
        "order_batch_execution_approval_ready": True,
        "business_message": (
            "Naver 订单批量执行审批 mock gate 已通过；当前只表示后续执行审批材料齐备，不会写入订单或调用平台写接口。"
        ),
        "next_action": (
            "如要真正执行订单批量写入，必须另开执行阶段并再次确认备份、审计、回读和敏感扫描。"
        ),
    })
    return result


def evaluate_naver_order_batch_execution_approval_readonly_api_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly API around order batch execution approval."""

    result = evaluate_naver_order_batch_execution_approval_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "order_write_endpoint_excluded",
        "sensitive_fields_hidden_from_main_page",
        "buyer_privacy_hidden_from_main_page",
        "audit_row_write_excluded",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "Naver-Order-Batch-3A",
        "naver_order_batch_execution_approval_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/naver/orders/execution-approval/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") != "naver_order_batch_execution_approval_mock_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["skip_reason"] = "naver_order_batch_execution_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("orders_written") is True or readonly_api_context.get("operation_audit_rows_written") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "write_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "naver_order_batch_execution_approval_readonly_api_mock_ready",
        "order_batch_execution_approval_ready": True,
        "business_message": (
            "Naver order batch execution approval readonly API mock gate passed. "
            "It plans review-only display; no order write, audit row, or platform write is performed."
        ),
        "next_action": (
            "Plan a local readonly route separately. Order batch execution still requires a later explicit approval phase."
        ),
    })
    return result


def evaluate_naver_order_batch_execution_approval_readonly_api_local_route_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for exposing order batch execution approval as a local readonly route."""

    result = evaluate_naver_order_batch_execution_approval_readonly_api_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        readonly_api_context=readonly_api_context,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "Naver-Order-Batch-3B",
        "naver_order_batch_execution_approval_readonly_api_local_route_mock_gate": True,
        "local_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/naver/orders/execution-approval/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "naver_order_batch_execution_approval_readonly_api_mock_ready":
        result["status"] = "naver_order_batch_execution_approval_readonly_api_local_route_mock_ready"
        result["business_message"] = (
            "Naver order batch execution approval readonly route mock gate passed. "
            "It is review-only and does not approve execution, write orders, or call platform write APIs."
        )
        result["next_action"] = (
            "Implement the local readonly route separately. Order batch execution still needs a later approved phase."
        )
    return result


def evaluate_naver_order_batch_execution_approval_readonly_api_local(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for order batch execution approval; never writes rows."""

    result = evaluate_naver_order_batch_execution_approval_readonly_api_local_route_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "Naver-Order-Batch-3C",
        "naver_order_batch_execution_approval_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/naver/orders/execution-approval/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_order_sync_open": False,
        "platform_order_writes_enabled": False,
        "platform_writes_enabled": False,
        "shipment_write_enabled": False,
        "cancel_write_enabled": False,
        "return_write_enabled": False,
        "exchange_write_enabled": False,
    })
    if result.get("status") == "naver_order_batch_execution_approval_readonly_api_local_route_mock_ready":
        result["status"] = "naver_order_batch_execution_approval_readonly_api_ready"
        result["business_message"] = (
            "Naver order batch execution approval is available for local readonly review. "
            "This does not open formal order batch sync or approve any write."
        )
        result["next_action"] = (
            "Use the route as operator evidence only. A separate approved execution phase is required for any order write."
        )
    return result


def evaluate_naver_product_batch_execution_approval_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock approval gate for a later Naver product batch execution phase; never writes."""

    required_execution_flags = [
        "product_batch_candidates_fresh",
        "product_field_whitelist_verified",
        "price_stock_status_mapping_reviewed",
        "duplicate_protection_ready",
        "audit_chain_ready",
        "post_write_readback_required",
        "rollback_plan_ready",
        "sensitive_scan_passed",
        "platform_product_write_actions_excluded",
        "formal_sync_remains_closed",
    ]
    result = {
        "phase": "Naver-Product-Batch-2D",
        "naver_product_batch_execution_approval_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "required_execution_flags": required_execution_flags,
        "missing_execution_flags": [],
        "product_batch_execution_approval_ready": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_product_sync_open": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != "verify_all_temp_db":
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(execution_context, dict):
        result["skip_reason"] = "execution_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found({
        "readonly_evidence": readonly_evidence,
        "backup_evidence": backup_evidence,
        "execution_context": execution_context,
    }):
        result["skip_reason"] = "naver_product_batch_execution_sensitive_field_blocked"
        return result

    missing_flags = [
        flag for flag in required_execution_flags
        if execution_context.get(flag) is not True
    ]
    result["missing_execution_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "product_batch_execution_context_incomplete"
        return result
    if execution_context.get("execution_approved") is True:
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if execution_context.get("formal_sync_open") is True or execution_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    production_gate = _evaluate_formal_batch_sync_production_gate(
        sync_kind="naver_product_batch",
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        audit_plan_ready=True,
        rollback_plan_ready=True,
        duplicate_protection_ready=True,
        failure_isolation_ready=True,
        multi_store_isolation_ready=True,
        verification_scope=verification_scope,
        write_requested=True,
    )
    result["production_gate"] = production_gate
    result.update({
        "store_ids": production_gate.get("store_ids") or [],
        "candidate_count": production_gate.get("candidate_count"),
        "batch_size": production_gate.get("batch_size"),
        "permission_verified": bool(production_gate.get("permission_verified")),
        "approval_role_verified": bool(production_gate.get("approval_role_verified")),
        "backup_evidence_verified": bool(production_gate.get("backup_evidence_verified")),
        "readonly_evidence_verified": bool(production_gate.get("readonly_evidence_verified")),
    })
    if production_gate.get("status") != "formal_batch_gate_ready_for_later_execution":
        result["skip_reason"] = production_gate.get("skip_reason") or "formal_batch_gate_not_ready"
        return result

    result.update({
        "status": "naver_product_batch_execution_approval_mock_ready",
        "product_batch_execution_approval_ready": True,
        "business_message": (
            "Naver product batch execution approval mock gate passed. It only means future execution review materials are ready; no products are written and no platform write API is called."
        ),
        "next_action": (
            "Open a separate execution phase before any real product batch write, and re-check backup, audit, readback, rollback, and sensitive-scan evidence."
        ),
    })
    return result


def evaluate_naver_product_batch_execution_approval_readonly_api_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for a future readonly API around product batch execution approval."""

    result = evaluate_naver_product_batch_execution_approval_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "execution_button_excluded",
        "write_endpoint_excluded",
        "product_write_endpoint_excluded",
        "sensitive_fields_hidden_from_main_page",
        "audit_row_write_excluded",
        "route_requires_separate_implementation",
        "formal_sync_remains_closed",
    ]
    result.update({
        "phase": "Naver-Product-Batch-2I",
        "naver_product_batch_execution_approval_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/batch/naver/products/execution-approval/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_product_sync_open": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") != "naver_product_batch_execution_approval_mock_ready":
        return result
    if verification_scope != "verify_all_temp_db":
        result["status"] = "blocked"
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _formal_batch_sync_sensitive_marker_found(readonly_api_context):
        result["status"] = "blocked"
        result["skip_reason"] = "naver_product_batch_execution_readonly_api_sensitive_field_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("execution_approved") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "execution_approval_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("products_written") is True or readonly_api_context.get("operation_audit_rows_written") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "write_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "naver_product_batch_execution_approval_readonly_api_mock_ready",
        "product_batch_execution_approval_ready": True,
        "business_message": (
            "Naver product batch execution approval readonly API mock gate passed. "
            "It plans review-only display; no product write, audit row, or platform write is performed."
        ),
        "next_action": (
            "Plan a local readonly route separately. Product batch execution still requires a later explicit approval phase."
        ),
    })
    return result


def evaluate_naver_product_batch_execution_approval_readonly_api_local_route_mock_gate(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
    verification_scope: str | None,
) -> dict:
    """Mock gate for exposing product batch execution approval as a local readonly route."""

    result = evaluate_naver_product_batch_execution_approval_readonly_api_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        readonly_api_context=readonly_api_context,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "Naver-Product-Batch-2K",
        "naver_product_batch_execution_approval_readonly_api_local_route_mock_gate": True,
        "local_route_mock_gate": True,
        "route_path_planned": "/api/v1/batch/naver/products/execution-approval/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_product_sync_open": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "naver_product_batch_execution_approval_readonly_api_mock_ready":
        result["status"] = "naver_product_batch_execution_approval_readonly_api_local_route_mock_ready"
        result["business_message"] = (
            "Naver product batch execution approval readonly route mock gate passed. "
            "It is review-only and does not approve execution, write products, or call platform write APIs."
        )
        result["next_action"] = (
            "Implement the local readonly route separately. Product batch execution still needs a later approved phase."
        )
    return result


def evaluate_naver_product_batch_execution_approval_readonly_api_local(
    *,
    actor_context: dict | None,
    store_ids: list[int] | tuple[int, ...] | set[int] | None,
    candidate_count: int,
    batch_size: int,
    readonly_evidence: dict | None,
    backup_evidence: dict | None,
    manual_approval: bool,
    execution_context: dict | None,
    readonly_api_context: dict | None,
) -> dict:
    """Public local readonly helper for product batch execution approval; never writes rows."""

    result = evaluate_naver_product_batch_execution_approval_readonly_api_local_route_mock_gate(
        actor_context=actor_context,
        store_ids=store_ids,
        candidate_count=candidate_count,
        batch_size=batch_size,
        readonly_evidence=readonly_evidence,
        backup_evidence=backup_evidence,
        manual_approval=manual_approval,
        execution_context=execution_context,
        readonly_api_context=readonly_api_context,
        verification_scope="verify_all_temp_db",
    )
    result.update({
        "phase": "Naver-Product-Batch-2L",
        "naver_product_batch_execution_approval_readonly_api_local": True,
        "backend_route_implemented": True,
        "public_endpoint_enabled": True,
        "route_path": "/api/v1/batch/naver/products/execution-approval/readonly-check",
        "http_method": "POST",
        "execution_approved": False,
        "real_api_called": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "timeline_events_written": False,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "formal_product_sync_open": False,
        "platform_product_writes_enabled": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") == "naver_product_batch_execution_approval_readonly_api_local_route_mock_ready":
        result["status"] = "naver_product_batch_execution_approval_readonly_api_ready"
        result["business_message"] = (
            "Naver product batch execution approval is available for local readonly review. "
            "This does not open formal product batch sync or approve any write."
        )
        result["next_action"] = (
            "Use the route as operator evidence only. A separate approved execution phase is required for any product write."
        )
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
        "operation_audit_rows_planned": True,
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
            "business_message": "批量同步只读证据已整理。本次不会调用平台、不会同步、不会写入商品或订单。",
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

        privacy_gate = _validate_naver_order_detail_preview_for_local_write(
            refresh_preview,
            require_external_product_order_id=write_enabled,
        )
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

    privacy_gate = _validate_naver_order_detail_preview_for_local_write(
        refresh_preview,
        require_external_product_order_id=False,
    )
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
    safe_local_sync_result = dict(local_sync_result or _default_naver_order_local_sync_result(False))
    safe_local_sync_result["sample_ids"] = [
        value if _is_hash_identifier(value) else _mask_external_identifier(value)
        for value in (safe_local_sync_result.get("sample_ids") or [])
        if value
    ]
    candidate_results = [
        item for item in (safe_local_sync_result.get("candidate_results") or [])
        if isinstance(item, dict)
    ]
    safe_local_sync_result["privacy_gate"] = {
        "passed": bool(candidate_results) and all(item.get("privacy_gate_passed") is True for item in candidate_results),
        "reasons": sorted({
            reason
            for item in candidate_results
            for reason in (item.get("privacy_gate_reasons") or [])
            if isinstance(reason, str)
        }),
    }
    safe_local_sync_result["privacy_fields_redacted"] = True
    safe_keyword_flags = dict(
        field_observation.get("safe_keyword_flags")
        or api_credential_readiness_service._empty_naver_safe_keyword_flags()
    )
    business_error_hint = field_observation.get("business_error_hint") or api_credential_readiness_service._naver_business_error_hint(error_code)
    semantic_notice = (
        "Readonly official API read with local ERP order write only. No Naver platform data was modified."
        if safe_local_sync_result.get("orders_written")
        else "Readonly micro preview only. No local order rows were written."
    )
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
        "local_sync_result": safe_local_sync_result,
        "sample_ids": sample_ids,
        "field_observation": field_observation,
        "detail_preview": field_observation.get("detail_preview"),
        "complete_field_preview": field_observation.get("complete_field_preview")
        or _default_naver_order_complete_field_preview(False),
        "business_message": _build_naver_order_preview_business_message(preview_status),
        "business_status_summary": _build_naver_order_preview_business_status_summary(preview_status),
        "semantic_notice": semantic_notice,
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


def _clean_joined_text(*values: str | None, max_length: int = 300) -> str | None:
    parts = [str(value).strip() for value in values if value is not None and str(value).strip()]
    if not parts:
        return None
    return _bounded_text(re.sub(r"\s+", " ", " ".join(parts)), max_length)


def _extract_scalar_from_named_object(payload: object, object_keys: tuple[str, ...], keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for object_key in object_keys:
            value = payload.get(object_key)
            if isinstance(value, (dict, list)):
                found = _extract_scalar_by_keys(value, keys)
                if found:
                    return found
        for value in payload.values():
            found = _extract_scalar_from_named_object(value, object_keys, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_scalar_from_named_object(item, object_keys, keys)
            if found:
                return found
    return None


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
    receiver_object_keys = ("receiver", "receiverInfo", "recipient", "recipientInfo", "shippingAddress")
    receiver_name = _bounded_text(
        _extract_scalar_from_named_object(item, receiver_object_keys, ("name", "receiverName", "recipientName"))
        or _extract_scalar_by_keys(item, ("receiverName", "recipientName")),
        120,
    )
    receiver_phone = _bounded_text(
        _extract_scalar_from_named_object(item, receiver_object_keys, (
            "safeNumber",
            "mobile",
            "phone",
            "phoneNumber",
            "tel",
            "receiverPhone",
            "receiverSafeNumber",
            "receiverNumber",
        ))
        or _extract_scalar_by_keys(item, ("receiverPhone", "receiverSafeNumber", "receiverNumber", "recipientPhone")),
        40,
    )
    receiver_address = _clean_joined_text(
        _extract_scalar_from_named_object(item, receiver_object_keys, ("addr1", "address1", "baseAddress", "receiverAddress1")),
        _extract_scalar_from_named_object(item, receiver_object_keys, ("addr2", "address2", "detailAddress", "receiverAddress2")),
        max_length=300,
    ) or _bounded_text(_extract_scalar_by_keys(item, ("receiverAddress", "recipientAddress", "shippingAddress")), 300)
    zip_code = _bounded_text(
        _extract_scalar_from_named_object(item, receiver_object_keys, ("postCode", "zipCode", "zipcode", "postalCode"))
        or _extract_scalar_by_keys(item, ("postCode", "zipCode", "zipcode", "postalCode")),
        30,
    )
    delivery_company = _bounded_text(
        _extract_scalar_by_keys(item, (
            "deliveryCompanyName",
            "deliveryCompany",
            "courierCompany",
            "courier",
            "carrier",
        )),
        120,
    )
    delivery_company_code = _bounded_text(
        _extract_scalar_by_keys(item, ("deliveryCompanyCode", "courierCode", "carrierCode")),
        80,
    )
    tracking_number = _bounded_text(
        _extract_scalar_by_keys(item, ("invoiceNumber", "invoiceNo", "trackingNumber", "waybillNumber")),
        120,
    )
    shipment_status = _extract_scalar_by_keys(item, ("shipmentStatus", "deliveryStatus", "orderStatus", "status"))
    delivery_summary = _delivery_status_summary(shipment_status, shipment_status)

    return {
        "external_order_id": external_order_id,
        "buyer_name": _extract_scalar_by_keys(item, ("buyerName", "ordererName", "receiverName")),
        "buyer_masked_phone": _mask_phone(_extract_scalar_by_keys(item, ("buyerPhone", "ordererPhone", "receiverPhone", "ordererSafeNumber", "receiverSafeNumber"))),
        "receiver_name": receiver_name,
        "receiver_phone": receiver_phone,
        "receiver_address": receiver_address,
        "zip_code": zip_code,
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
        "raw_data": {
            "mapping_version": "coupang_order_local_summary_v2",
            "platform_write": False,
            "shipment_box_id": _bounded_text(_extract_scalar_by_keys(item, ("shipmentBoxId", "shipment_box_id")), 120),
            "delivery_company": delivery_company,
            "delivery_company_code": delivery_company_code,
            "tracking_number": tracking_number,
            "shipment_status": _bounded_text(shipment_status, 60),
            "delivery_status": delivery_summary.get("raw"),
            "delivery_status_label_zh": delivery_summary.get("label_zh"),
            "raw_response_saved": False,
        },
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
