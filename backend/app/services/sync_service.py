import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import date
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
from app.schemas.credential import DecryptedCredential
from app.services import credential_service, customer_inquiry_service, order_service, product_service, sync_log_service
from app.services.store_service import ensure_store_exists, normalize_platform


CLIENTS = {
    "naver": NaverClient,
    "coupang": CoupangClient,
}
COUPANG_ORDER_PREVIEW_SYNC_TYPE = "orders_coupang_real_preview"
COUPANG_ORDER_SOURCE_TYPE = "real_coupang"
COUPANG_ORDER_PREVIEW_MAX_DAYS = 3
COUPANG_ORDER_PREVIEW_MAX_PAGES = 3
COUPANG_ORDER_PREVIEW_PAGE_SIZE = 50


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
        unique_order_ids: list[str] = []
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
            page_ids = _extract_order_ids_from_preview_payload(payload)
            for order_id in page_ids:
                if order_id in seen_ids:
                    continue
                seen_ids.add(order_id)
                unique_order_ids.append(order_id)
            page_count += 1
            next_token = _extract_next_token(payload)
            if not next_token:
                break

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
