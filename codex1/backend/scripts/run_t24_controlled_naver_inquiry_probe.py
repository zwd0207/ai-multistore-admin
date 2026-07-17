from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.api_capability import ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import PxgNaverReadonlyCustomerInquiry
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import api_credential_readiness_service, naver_readonly_inquiry_service, sync_service


APPROVAL_VALUE = "owner-approved-one-get"
CAPABILITY_KEY = "naver.customer_inquiry_read"
PROBE_PAGE_SIZE = 10
RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS = 3600


class ProbeBlocked(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _require_process_approval(store_id: int) -> None:
    if os.environ.get("T24_CONTROLLED_READ_APPROVAL") != APPROVAL_VALUE:
        raise ProbeBlocked("t24_owner_approval_missing")
    try:
        approved_store_id = int(os.environ.get("T24_CONTROLLED_READ_APPROVED_STORE_ID", "0"))
    except ValueError as exc:
        raise ProbeBlocked("t24_approved_store_invalid") from exc
    if approved_store_id != store_id:
        raise ProbeBlocked("t24_approved_store_mismatch")


def _assert_runtime_closed(settings: Settings) -> None:
    if settings.app_env != "production":
        raise ProbeBlocked("t24_production_runtime_required")
    if settings.real_api_test_enabled:
        raise ProbeBlocked("t24_parallel_real_test_enabled")
    if settings.automatic_read_sync_enabled:
        raise ProbeBlocked("t24_automatic_read_must_remain_disabled")
    if settings.naver_readonly_inquiry_real_read_enabled:
        raise ProbeBlocked("t24_persistent_inquiry_gate_must_remain_disabled")
    write_flags = (
        settings.real_api_write_enabled,
        settings.platform_product_write_enabled,
        settings.platform_inventory_write_enabled,
        settings.platform_order_write_enabled,
        settings.customer_platform_write_enabled,
        settings.shipping_platform_write_enabled,
        settings.pxg_naver_shipping_pilot_enabled,
        settings.ai_automatic_operations_enabled,
    )
    if any(write_flags):
        raise ProbeBlocked("t24_platform_write_gate_open")
    if not settings.credential_encryption_key:
        raise ProbeBlocked("t24_credential_encryption_key_missing")


def _resolve_store_and_credential(
    db: Session,
    *,
    store_id: int,
    expected_store_name_sha256: str,
) -> tuple[Store, ApiCredential]:
    store = db.get(Store, store_id)
    if store is None or store.status != "active" or str(store.platform).strip().lower() != "naver":
        raise ProbeBlocked("t24_store_ineligible")
    actual_name_hash = hashlib.sha256(store.name.encode("utf-8")).hexdigest()
    if actual_name_hash != expected_store_name_sha256.lower():
        raise ProbeBlocked("t24_store_name_mismatch")
    credentials = db.scalars(select(ApiCredential).where(
        ApiCredential.store_id == store_id,
        ApiCredential.platform == "naver",
        ApiCredential.status == "active",
    ).order_by(ApiCredential.id.asc())).all()
    if len(credentials) != 1:
        raise ProbeBlocked("t24_unique_active_credential_required")
    credential = credentials[0]
    if not credential.client_id or not credential.encrypted_secret_key:
        raise ProbeBlocked("t24_credential_not_ready")
    return store, credential


def _assert_no_active_lease_or_cooldown(
    db: Session,
    *,
    store_id: int,
    now: datetime,
) -> None:
    checkpoint = db.scalar(select(SyncCheckpoint).where(
        SyncCheckpoint.store_id == store_id,
        SyncCheckpoint.platform == "naver",
        SyncCheckpoint.sync_type == naver_readonly_inquiry_service.INQUIRY_SYNC_TYPE,
    ))
    if checkpoint is not None and checkpoint.lease_expires_at is not None:
        if _utc(checkpoint.lease_expires_at) > _utc(now):
            raise ProbeBlocked("t24_inquiry_lease_active")

    logs = db.scalars(select(SyncLog).where(
        SyncLog.store_id == store_id,
        SyncLog.platform == "naver",
    ).order_by(SyncLog.id.desc()).limit(100)).all()
    for log in logs:
        summary = log.raw_summary if isinstance(log.raw_summary, dict) else {}
        error_code = str(summary.get("error_code") or log.error_detail or "")
        if error_code != "naver_customer_inquiry_rate_limit":
            continue
        try:
            retry_after = int(summary.get("retry_after_seconds") or RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS)
        except (TypeError, ValueError):
            retry_after = RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS
        retry_after = max(60, min(retry_after, RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS))
        observed_at = _utc(log.finished_at or log.started_at)
        if _utc(now) < observed_at + timedelta(seconds=retry_after):
            raise ProbeBlocked("t24_rate_limit_cooldown_active")
        break


def _business_counts(db: Session, store_id: int) -> dict[str, int]:
    return {
        "orders": db.scalar(select(func.count()).select_from(Order).where(Order.store_id == store_id)) or 0,
        "products": db.scalar(select(func.count()).select_from(Product).where(Product.store_id == store_id)) or 0,
        "customer_inquiries": db.scalar(
            select(func.count()).select_from(CustomerInquiry).where(CustomerInquiry.store_id == store_id)
        ) or 0,
        "readonly_inquiries": db.scalar(
            select(func.count()).select_from(PxgNaverReadonlyCustomerInquiry).where(
                PxgNaverReadonlyCustomerInquiry.store_id == store_id,
            )
        ) or 0,
    }


def _single_get(
    credential: ApiCredential,
    *,
    context_builder: Callable[[ApiCredential], dict[str, Any]] | None = None,
    token_request: Callable[[dict[str, Any]], tuple[str, int]] | None = None,
    inquiry_request: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context_builder = context_builder or sync_service._build_naver_token_context_from_credential
    token_request = token_request or api_credential_readiness_service._request_naver_token_from_context
    inquiry_request = inquiry_request or sync_service._request_naver_customer_inquiries
    context = context_builder(credential)
    token, token_http_status = token_request(context)
    start_date, end_date = naver_readonly_inquiry_service._recent_naver_inquiry_date_range()
    request_result = inquiry_request(
        api_base=context["api_base"],
        headers={"Authorization": f"Bearer {token}"},
        start_date=start_date,
        end_date=end_date,
        answered=None,
        page=1,
        size=PROBE_PAGE_SIZE,
    )
    diagnostics = request_result.get("diagnostics") if isinstance(request_result.get("diagnostics"), dict) else {}
    base = {
        "business_get_count": 1,
        "token_exchange_count": 1,
        "token_http_status": token_http_status,
        "http_status": request_result.get("http_status"),
        "rate_limit": diagnostics.get("rate_limit") if isinstance(diagnostics.get("rate_limit"), dict) else {},
        "retry_after_seconds": diagnostics.get("retry_after_seconds"),
        "raw_response_saved": False,
        "platform_write": False,
    }
    if not request_result.get("success"):
        return {
            **base,
            "status": "blocked",
            "error_code": str(request_result.get("error_code") or "naver_inquiry_probe_failed")[:120],
            "retryable": bool(request_result.get("retryable")),
            "response_fields_observed": [],
            "item_count": 0,
            "total_elements": None,
            "total_pages": None,
        }

    payload = request_result.get("payload")
    try:
        page_data = naver_readonly_inquiry_service._validate_inquiry_page(
            payload,
            requested_page=1,
            requested_size=PROBE_PAGE_SIZE,
            expected_total_pages=None,
            expected_total_elements=None,
            response_number_base=None,
        )
    except ApiError as exc:
        return {
            **base,
            "status": "blocked",
            "error_code": str(exc.error_code)[:120],
            "retryable": False,
            "response_fields_observed": [],
            "item_count": 0,
            "total_elements": None,
            "total_pages": None,
        }
    allowed_fields = {
        "content", "totalPages", "totalElements", "number", "last", "size",
        "numberOfElements", "first", "empty",
    }
    observed_fields = sorted(key for key in payload.keys() if key in allowed_fields)
    return {
        **base,
        "status": "passed",
        "error_code": None,
        "retryable": False,
        "response_fields_observed": observed_fields,
        "item_count": len(page_data["items"]),
        "total_elements": page_data["total_elements"],
        "total_pages": page_data["total_pages"],
    }


def _persist_capability_evidence(
    db: Session,
    *,
    store_id: int,
    credential_id: int,
    probe: dict[str, Any],
) -> int:
    meta = api_credential_readiness_service.NAVER_CAPABILITY_MAP[CAPABILITY_KEY]
    passed = probe["status"] == "passed"
    http_status = probe.get("http_status")
    permission_result = "order_seller_confirmed" if passed else (
        "order_seller_not_confirmed" if http_status in {401, 403} else "order_seller_not_evaluated"
    )
    result = {
        "platform": "naver",
        "capability_key": CAPABILITY_KEY,
        "capability_name": meta["capability_name"],
        "api_category": meta["api_category"],
        "endpoint_path": meta["endpoint_path"],
        "method": meta["method"],
        "test_mode": "real_readonly",
        "test_status": "tested_success" if passed else (
            "permission_required" if http_status in {401, 403} else "tested_failed"
        ),
        "store_id": store_id,
        "credential_id": credential_id,
        "http_status": http_status,
        "error_code": probe.get("error_code"),
        "permission_result": permission_result,
        "rate_limit_summary": json.dumps(probe.get("rate_limit") or {}, sort_keys=True),
        "response_fields_observed": ",".join(probe.get("response_fields_observed") or []),
        "notes": "One owner-approved Naver inquiry GET; no pagination follow-up, raw response persistence, or platform write.",
    }
    persisted = api_credential_readiness_service._persist_real_readonly_capability_results(db, [result])
    result_id = persisted.get(CAPABILITY_KEY)
    if result_id is None:
        raise ProbeBlocked("t24_capability_evidence_not_persisted")
    return result_id


def run_probe(
    db: Session,
    *,
    store_id: int,
    expected_store_name_sha256: str,
    settings: Settings | None = None,
    now: datetime | None = None,
    single_get: Callable[[ApiCredential], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    current = now or get_utc_now()
    _require_process_approval(store_id)
    _assert_runtime_closed(settings)
    store, credential = _resolve_store_and_credential(
        db,
        store_id=store_id,
        expected_store_name_sha256=expected_store_name_sha256,
    )
    _assert_no_active_lease_or_cooldown(db, store_id=store_id, now=current)
    counts_before = _business_counts(db, store_id)
    probe = (single_get or _single_get)(credential)
    db.rollback()
    evidence_id = _persist_capability_evidence(
        db,
        store_id=store_id,
        credential_id=credential.id,
        probe=probe,
    )
    counts_after = _business_counts(db, store_id)
    if counts_before != counts_after:
        raise ProbeBlocked("t24_business_state_changed")
    return {
        "status": probe["status"],
        "store_id": store.id,
        "store_name": store.name,
        "platform": "naver",
        "credential_id": credential.id,
        "capability_result_id": evidence_id,
        "endpoint": "/v1/pay-user/inquiries",
        "method": "GET",
        "page": 1,
        "page_size": PROBE_PAGE_SIZE,
        "business_get_count": probe["business_get_count"],
        "token_exchange_count": probe["token_exchange_count"],
        "http_status": probe.get("http_status"),
        "error_code": probe.get("error_code"),
        "retryable": probe.get("retryable", False),
        "retry_after_seconds": probe.get("retry_after_seconds"),
        "item_count": probe.get("item_count", 0),
        "total_elements": probe.get("total_elements"),
        "total_pages": probe.get("total_pages"),
        "permission_result": "order_seller_confirmed" if probe["status"] == "passed" else "not_confirmed",
        "business_state_unchanged": True,
        "raw_response_saved": False,
        "platform_write": False,
        "follow_up_get_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one owner-approved T24 Naver inquiry GET")
    parser.add_argument("--store-id", type=int, required=True)
    parser.add_argument("--expected-store-name-sha256", required=True)
    args = parser.parse_args()

    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            result = run_probe(
                db,
                store_id=args.store_id,
                expected_store_name_sha256=args.expected_store_name_sha256,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if result["status"] != "passed":
            raise SystemExit(2)
    except ProbeBlocked as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": exc.error_code,
            "business_get_count": 0,
            "platform_write": False,
        }, sort_keys=True))
        raise SystemExit(3) from None
    except ApiError as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": str(exc.error_code)[:120],
            "business_get_count": 0,
            "platform_write": False,
        }, sort_keys=True))
        raise SystemExit(4) from None
    except Exception:
        print(json.dumps({
            "status": "failed",
            "error_code": "t24_controlled_probe_failed",
            "business_get_count": 0,
            "platform_write": False,
        }, sort_keys=True))
        raise SystemExit(5) from None


if __name__ == "__main__":
    main()
