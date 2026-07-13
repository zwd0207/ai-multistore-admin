"""Controlled Naver inquiry-only import and encrypted detail access.

The historical PXG table name is intentionally retained.  This service is store
generic and never invokes the legacy generic ``CustomerInquiry`` writer.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyCustomerInquiry
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services import api_credential_readiness_service, sync_service
from app.services.encryption import decrypt_value, encrypt_value


INQUIRY_CONTENT_MAX_LENGTH = 4000
INQUIRY_TITLE_MAX_LENGTH = 300
INQUIRY_RETENTION_DAYS = 30
INQUIRY_PAGE_SIZE = 50
INQUIRY_MAX_PAGES = 10
_SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.:-]+")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)


def _safe_label(value: object, fallback: str) -> str:
    normalized = _SAFE_LABEL.sub("_", str(value or "").strip())[:120].strip("_.:-")
    return normalized or fallback


def _store(db: Session, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if store is None or str(store.platform).strip().lower() != "naver" or store.status != "active":
        raise ApiError("active Naver store is required", "readonly_inquiry_store_ineligible", 409)
    return store


def _cleanup_status(db: Session, store_id: int) -> PxgNaverReadonlyCleanupStatus:
    row = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
        PxgNaverReadonlyCleanupStatus.store_id == store_id,
        PxgNaverReadonlyCleanupStatus.platform == "naver",
    ))
    if row is None:
        row = PxgNaverReadonlyCleanupStatus(store_id=store_id, platform="naver", status="healthy")
        db.add(row)
        db.flush()
    return row


def run_naver_inquiry_retention_cleanup(
    db: Session, *, store_id: int, settings: Settings | None = None, now=None
) -> dict[str, Any]:
    """Delete expired encrypted inquiry content and leave a per-store health signal."""
    settings = settings or get_settings()
    _store(db, store_id)
    status = _cleanup_status(db, store_id)
    current = now or get_utc_now()
    status.last_run_at = current
    # This table is shared with the approved PXG lifecycle. Never let the
    # inquiry scheduler clear a pre-existing manual-review or failure stop.
    if status.status in {"manual_review_required", "failed"}:
        db.commit()
        raise ApiError("inquiry cleanup health is already blocking use", "readonly_retention_cleanup_failed", 409)
    if not settings.pxg_naver_local_read_retention_cleanup_enabled:
        status.status = "failed"
        status.last_failure_at = current
        status.last_failure_code = "readonly_retention_cleanup_disabled"
        db.commit()
        raise ApiError("inquiry retention cleanup is disabled", "readonly_retention_cleanup_disabled", 409)
    try:
        expired = db.scalars(select(PxgNaverReadonlyCustomerInquiry).where(
            PxgNaverReadonlyCustomerInquiry.store_id == store_id,
            PxgNaverReadonlyCustomerInquiry.platform == "naver",
            PxgNaverReadonlyCustomerInquiry.expires_at <= current,
        )).all()
        for record in expired:
            db.delete(record)
        status.status = "healthy"
        status.last_success_at = current
        status.last_failure_at = None
        status.last_failure_code = None
        db.commit()
        return {"status": "completed", "store_id": store_id, "deleted_count": len(expired)}
    except Exception:
        db.rollback()
        status = _cleanup_status(db, store_id)
        status.status = "failed"
        status.last_run_at = current
        status.last_failure_at = current
        status.last_failure_code = "readonly_inquiry_cleanup_failed"
        db.commit()
        raise


def assert_naver_inquiry_cleanup_healthy(db: Session, *, store_id: int, settings: Settings | None = None) -> None:
    # Reuse the full established gate: cleanup state, safety locks, expired
    # encrypted backups, and the 24-hour overdue deadline all apply equally.
    from app.services.pxg_naver_readonly_persistence_service import assert_pxg_naver_cleanup_healthy

    assert_pxg_naver_cleanup_healthy(db, store_id=store_id, settings=settings or get_settings())


def initialize_naver_inquiry_store(db: Session, *, store_id: int, settings: Settings | None = None) -> None:
    """Perform the first successful cleanup before an eligible store can receive content."""
    run_naver_inquiry_retention_cleanup(db, store_id=store_id, settings=settings)
    assert_naver_inquiry_cleanup_healthy(db, store_id=store_id, settings=settings)


def run_naver_inquiry_cleanup_scheduler(db: Session, *, settings: Settings | None = None) -> dict[str, int]:
    """Run isolated inquiry retention for every active Naver store.

    A per-store failure is retained in its health row and does not make another
    store appear healthy.
    """
    settings = settings or get_settings()
    completed = failed = 0
    for store_id in db.scalars(select(Store.id).where(Store.status == "active", Store.platform == "naver")).all():
        try:
            run_naver_inquiry_retention_cleanup(db, store_id=store_id, settings=settings)
            completed += 1
        except Exception:
            failed += 1
    return {"completed_store_count": completed, "failed_store_count": failed}


def _related_order(db: Session, store_id: int, item: dict) -> Order | None:
    order_id = str(item.get("orderId") or item.get("order_id") or "").strip()
    product_ids = sync_service._split_naver_product_order_ids(item.get("productOrderIdList") or item.get("product_order_id_list"))
    statement = select(Order).where(Order.store_id == store_id, Order.platform == "naver")
    for product_id in product_ids:
        product_order = db.scalar(statement.where(Order.external_product_order_id == product_id))
        if product_order is not None:
            return product_order
    return db.scalar(statement.where(Order.external_order_id == order_id)) if order_id else None


def _upsert_item(db: Session, *, store_id: int, item: dict, observed_at) -> str:
    external_id = str(item.get("inquiryNo") or item.get("inquiry_no") or "").strip()
    if not external_id:
        return "skipped"
    content = str(item.get("inquiryContent") or item.get("content") or "")[:INQUIRY_CONTENT_MAX_LENGTH]
    title = str(item.get("title") or "")[:INQUIRY_TITLE_MAX_LENGTH]
    inquiry_hash = _hash(f"customer-inquiry:{external_id}")
    record = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
        PxgNaverReadonlyCustomerInquiry.external_inquiry_id_hash == inquiry_hash,
    ))
    received_at = sync_service._parse_preview_iso_datetime(sync_service._extract_scalar_by_keys(
        item, ("inquiryRegistrationDateTime", "registeredAt", "createdAt")
    ))
    answered_at = sync_service._parse_preview_iso_datetime(sync_service._extract_scalar_by_keys(
        item, ("answerRegistrationDateTime", "answeredAt")
    ))
    payload_hash = _hash(content) if content else None
    source_updated_at = answered_at or received_at or observed_at
    related_order = _related_order(db, store_id, item)
    values = {
        "related_order_id": related_order.id if related_order else None,
        "inquiry_type": _safe_label(item.get("category") or item.get("inquiryType"), "platform_message"),
        "status": "answered" if bool(item.get("answered")) else "open",
        "customer_display_masked": sync_service._mask_person_name(item.get("customerName") or item.get("customer_name")) if (item.get("customerName") or item.get("customer_name")) else None,
        "subject_category": _safe_label(item.get("category") or item.get("inquiryType"), "platform_message"),
        "content_available": bool(content),
        "encrypted_content": encrypt_value(content) if content else None,
        "encrypted_title": encrypt_value(title) if title else None,
        "content_hash": payload_hash,
        "content_length": len(content),
        "received_at": received_at,
        "answered_at": answered_at,
        "source_updated_at": source_updated_at,
        "source_observed_at": observed_at,
        "is_stale": False,
    }
    if record is None:
        record = PxgNaverReadonlyCustomerInquiry(
            store_id=store_id, platform="naver", external_inquiry_id_hash=inquiry_hash,
            expires_at=observed_at + timedelta(days=INQUIRY_RETENTION_DAYS), **values,
        )
        db.add(record)
        return "created"
    # Every observation corrects legacy metadata retention immediately, even
    # when the source is older or unchanged. ``created_at`` is immutable.
    first_collection_at = _utc(record.created_at or record.source_observed_at)
    max_deadline = first_collection_at + timedelta(days=INQUIRY_RETENTION_DAYS)
    record.expires_at = min(_utc(record.expires_at), max_deadline)
    existing_source_updated_at = _utc(record.source_updated_at)
    incoming_source_updated_at = _utc(source_updated_at)
    if incoming_source_updated_at < existing_source_updated_at:
        return "skipped"
    if incoming_source_updated_at == existing_source_updated_at:
        if record.encrypted_content is None and record.content_hash is None and payload_hash is not None:
            # Old metadata-only rows may gain encrypted content exactly once at
            # their original source version. Later hash changes still conflict.
            for key, value in values.items():
                setattr(record, key, value)
            return "updated"
        if record.content_hash != payload_hash:
            raise ApiError(
                "same-timestamp inquiry content conflict is blocked",
                "readonly_inquiry_source_conflict",
                409,
            )
        # An identical source version is only observed again. Do not rotate
        # ciphertext or alter the immutable first-collection deadline.
        record.source_observed_at = observed_at
        record.is_stale = False
        return "skipped"
    # The immutable collection deadline is deliberately never refreshed.
    for key, value in values.items():
        setattr(record, key, value)
    return "updated"


def refresh_naver_readonly_inquiries(
    db: Session, *, store_id: int, actor_id: str | None, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    _store(db, store_id)
    initialize_naver_inquiry_store(db, store_id=store_id, settings=settings)
    credential = sync_service._ensure_naver_product_preview_credential(db, store_id=store_id, credential_id=None)
    context = sync_service._build_naver_token_context_from_credential(credential)
    token, _ = api_credential_readiness_service._request_naver_token_from_context(context)
    now = get_utc_now()
    items: list[dict] = []
    seen_pages: set[tuple[str, ...]] = set()
    pages_read = 0
    for page in range(1, INQUIRY_MAX_PAGES + 1):
        result = sync_service._request_naver_customer_inquiries(
            api_base=context["api_base"], headers={"Authorization": f"Bearer {token}"},
            start_date=(now - timedelta(days=30)).date(), end_date=now.date(), answered=None,
            page=page, size=INQUIRY_PAGE_SIZE,
        )
        if not result.get("success"):
            raise ApiError("Naver inquiry readonly request failed", str(result.get("error_code") or "readonly_request_failed"), 502)
        page_items = sync_service._extract_naver_customer_inquiry_items(result.get("payload"))[:INQUIRY_PAGE_SIZE]
        if not page_items:
            break
        page_keys = tuple(str(item.get("inquiryNo") or item.get("inquiry_no") or "") for item in page_items)
        if page_keys in seen_pages:
            break
        seen_pages.add(page_keys)
        items.extend(page_items)
        pages_read += 1
        if len(page_items) < INQUIRY_PAGE_SIZE:
            break
    counts = {"created": 0, "updated": 0, "skipped": 0}
    for item in items:
        outcome = _upsert_item(db, store_id=store_id, item=item, observed_at=now)
        counts[outcome] += 1
    from app.services.pxg_naver_readonly_persistence_service import _audit_local_ingestion
    _audit_local_ingestion(
        db, store_id=store_id, actor_id=actor_id, source_mode="naver_inquiry_only",
        observed_at=now,
        counts={
            "products": {}, "orders": {}, "logistics": {},
            "customer_inquiries": {"created": counts["created"], "updated": counts["updated"]},
        },
    )
    db.add(SyncLog(store_id=store_id, platform="naver", sync_type="naver_readonly_inquiry_refresh", status="success",
                   message="Naver readonly inquiry refresh completed",
                   raw_summary={"created": counts["created"], "updated": counts["updated"], "skipped": counts["skipped"], "pages_read": pages_read, "actor_id_hash": _hash(actor_id or "authorized")[:64], "raw_response_saved": False, "platform_write": False}))
    db.commit()
    return {"status": "success", "store_id": store_id, "platform": "naver", "resource": "customer_inquiries", "created_count": counts["created"], "updated_count": counts["updated"], "skipped_count": counts["skipped"], "pages_read": pages_read, "raw_response_saved": False, "platform_write": False, "reply_count": 0}


def inquiry_detail(db: Session, *, store_id: int, readonly_id: int, settings: Settings | None = None) -> dict[str, Any]:
    assert_naver_inquiry_cleanup_healthy(db, store_id=store_id, settings=settings)
    record = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.id == readonly_id,
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
    ))
    if record is None:
        raise ApiError("readonly inquiry is not found", "readonly_inquiry_not_found", 404)
    if _utc(record.expires_at) <= _utc(get_utc_now()) or record.is_stale:
        raise ApiError("readonly inquiry has expired", "readonly_inquiry_expired", 409)
    try:
        return {"id": record.id, "store_id": store_id, "platform": "naver", "title": decrypt_value(record.encrypted_title) if record.encrypted_title else None, "content": decrypt_value(record.encrypted_content) if record.encrypted_content else "", "content_length": record.content_length, "reply_enabled": False}
    except Exception as exc:
        raise ApiError("readonly inquiry content cannot be decrypted", "readonly_inquiry_content_invalid", 500) from exc
