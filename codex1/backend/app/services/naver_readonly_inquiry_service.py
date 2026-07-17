"""Controlled Naver inquiry-only import and encrypted detail access.

The historical PXG table name is intentionally retained.  This service is store
generic and never invokes the legacy generic ``CustomerInquiry`` writer.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_business_date, get_utc_now
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyCleanupStatus, PxgNaverReadonlyCustomerInquiry
from app.models.store import Store
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services import api_credential_readiness_service, sync_service
from app.services.encryption import decrypt_value, encrypt_value
from app.services.naver_inquiry_identity import naver_inquiry_external_id_hash


INQUIRY_CONTENT_MAX_LENGTH = 4000
INQUIRY_ANSWER_CONTENT_MAX_LENGTH = 4000
INQUIRY_TITLE_MAX_LENGTH = 300
INQUIRY_CUSTOMER_NAME_MAX_LENGTH = 120
INQUIRY_RETENTION_DAYS = 30
INQUIRY_PAGE_SIZE = 200
INQUIRY_MAX_PAGES = 1000
INQUIRY_PAGE_DELAY_SECONDS = 1.0
INQUIRY_SYNC_TYPE = "naver_automatic_inquiries"
INQUIRY_LEASE_DURATION = timedelta(minutes=15)
INQUIRY_MANUAL_LEASE_NOTE = "t24_manual_inquiry_lease"
_SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.:-]+")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)


def _safe_label(value: object, fallback: str) -> str:
    normalized = _SAFE_LABEL.sub("_", str(value or "").strip())[:120].strip("_.:-")
    return normalized or fallback


def _is_answered(item: dict, *, answered_at: datetime | None, answer_content: str) -> bool:
    raw_value = item.get("answered")
    if isinstance(raw_value, bool):
        platform_answered = raw_value
    else:
        platform_answered = str(raw_value or "").strip().lower() in {"1", "true", "yes", "answered"}
    return bool(platform_answered or answered_at is not None or answer_content)


def assert_naver_inquiry_real_read_allowed(*, store_id: int, settings: Settings) -> None:
    if not settings.naver_readonly_inquiry_real_read_enabled:
        raise ApiError(
            "Naver inquiry readonly access is not approved",
            "naver_inquiry_real_read_disabled",
            403,
        )
    if settings.naver_readonly_inquiry_approved_store_id != store_id:
        raise ApiError(
            "Naver inquiry readonly access is not approved for this store",
            "naver_inquiry_store_not_approved",
            403,
        )


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
    answer_content = str(item.get("answerContent") or item.get("answer_content") or "")[
        :INQUIRY_ANSWER_CONTENT_MAX_LENGTH
    ]
    customer_name = str(item.get("customerName") or item.get("customer_name") or "")[
        :INQUIRY_CUSTOMER_NAME_MAX_LENGTH
    ]
    title = str(item.get("title") or "")[:INQUIRY_TITLE_MAX_LENGTH]
    inquiry_hash = naver_inquiry_external_id_hash(external_id)
    if inquiry_hash is None:
        return "skipped"
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
    answer_payload_hash = _hash(answer_content) if answer_content else None
    customer_name_hash = _hash(customer_name) if customer_name else None
    answered = _is_answered(item, answered_at=answered_at, answer_content=answer_content)
    source_updated_at = answered_at or received_at or observed_at
    related_order = _related_order(db, store_id, item)
    values = {
        "related_order_id": related_order.id if related_order else None,
        "inquiry_type": _safe_label(item.get("category") or item.get("inquiryType"), "platform_message"),
        "status": "answered" if answered else "open",
        "customer_display_masked": sync_service._mask_person_name(customer_name) if customer_name else None,
        "encrypted_customer_name": encrypt_value(customer_name) if customer_name else None,
        "customer_name_hash": customer_name_hash,
        "customer_name_length": len(customer_name),
        "subject_category": _safe_label(item.get("category") or item.get("inquiryType"), "platform_message"),
        "content_available": bool(content),
        "encrypted_content": encrypt_value(content) if content else None,
        "encrypted_title": encrypt_value(title) if title else None,
        "content_hash": payload_hash,
        "content_length": len(content),
        "encrypted_answer_content": encrypt_value(answer_content) if answer_content else None,
        "answer_content_hash": answer_payload_hash,
        "answer_content_length": len(answer_content),
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
    if payload_hash is None and record.content_hash is not None:
        values["content_available"] = record.content_available
        values["encrypted_content"] = record.encrypted_content
        values["content_hash"] = record.content_hash
        values["content_length"] = record.content_length
    if answer_payload_hash is None and record.answer_content_hash is not None:
        values["encrypted_answer_content"] = record.encrypted_answer_content
        values["answer_content_hash"] = record.answer_content_hash
        values["answer_content_length"] = record.answer_content_length
    if customer_name_hash is None and record.customer_name_hash is not None:
        values["encrypted_customer_name"] = record.encrypted_customer_name
        values["customer_name_hash"] = record.customer_name_hash
        values["customer_name_length"] = record.customer_name_length
    if not title and record.encrypted_title is not None:
        values["encrypted_title"] = record.encrypted_title
    if incoming_source_updated_at < existing_source_updated_at:
        return "skipped"
    if incoming_source_updated_at == existing_source_updated_at:
        question_conflict = bool(
            record.content_hash is not None
            and payload_hash is not None
            and record.content_hash != payload_hash
        )
        answer_conflict = bool(
            record.answer_content_hash is not None
            and answer_payload_hash is not None
            and record.answer_content_hash != answer_payload_hash
        )
        customer_name_conflict = bool(
            record.customer_name_hash is not None
            and customer_name_hash is not None
            and record.customer_name_hash != customer_name_hash
        )
        if question_conflict or answer_conflict or customer_name_conflict:
            raise ApiError(
                "same-timestamp inquiry content conflict is blocked",
                "readonly_inquiry_source_conflict",
                409,
            )
        gains_question = bool(
            record.encrypted_content is None
            and record.content_hash is None
            and payload_hash is not None
        )
        gains_answer = bool(
            record.encrypted_answer_content is None
            and record.answer_content_hash is None
            and answer_payload_hash is not None
        )
        gains_customer_name = bool(
            record.encrypted_customer_name is None
            and record.customer_name_hash is None
            and customer_name_hash is not None
        )
        if gains_question or gains_answer or gains_customer_name:
            # Old metadata-only rows may gain encrypted content exactly once at
            # their original source version. Later hash changes still conflict.
            for key, value in values.items():
                setattr(record, key, value)
            return "updated"
        # An identical source version is only observed again. Do not rotate
        # ciphertext or alter the immutable first-collection deadline.
        record.source_observed_at = observed_at
        record.is_stale = False
        return "skipped"
    # The immutable collection deadline is deliberately never refreshed.
    for key, value in values.items():
        setattr(record, key, value)
    return "updated"


def _recent_naver_inquiry_date_range(*, business_date: date | None = None) -> tuple[date, date]:
    end_date = business_date or get_business_date()
    return end_date - timedelta(days=29), end_date


def _active_lease(checkpoint: SyncCheckpoint, now: datetime) -> bool:
    return bool(
        checkpoint.lease_token
        and checkpoint.lease_expires_at
        and _utc(checkpoint.lease_expires_at) > _utc(now)
    )


def _acquire_inquiry_lease(
    db: Session,
    *,
    store_id: int,
    actor_id: str | None,
    settings: Settings,
    now: datetime,
) -> dict[str, Any]:
    checkpoint = db.scalar(select(SyncCheckpoint).where(
        SyncCheckpoint.store_id == store_id,
        SyncCheckpoint.platform == "naver",
        SyncCheckpoint.sync_type == INQUIRY_SYNC_TYPE,
    ))
    if checkpoint is None and settings.automatic_read_sync_enabled:
        from app.services import automatic_read_sync_service

        if store_id in automatic_read_sync_service._eligible_store_ids(db):
            checkpoint = automatic_read_sync_service._checkpoint(
                db,
                store_id=store_id,
                resource="customer_inquiries",
                now=_utc(now),
            )
            db.commit()

    token = secrets.token_urlsafe(24)
    if checkpoint is None:
        checkpoint = SyncCheckpoint(
            store_id=store_id,
            platform="naver",
            sync_type=INQUIRY_SYNC_TYPE,
            automatic_read_enabled=False,
            status="idle",
            lease_token=token,
            lease_expires_at=_utc(now) + INQUIRY_LEASE_DURATION,
            last_attempt_at=_utc(now),
            notes=INQUIRY_MANUAL_LEASE_NOTE,
        )
        db.add(checkpoint)
        try:
            db.commit()
            return {"checkpoint_id": checkpoint.id, "token": token, "owned": True, "ephemeral": True}
        except IntegrityError:
            db.rollback()
            checkpoint = db.scalar(select(SyncCheckpoint).where(
                SyncCheckpoint.store_id == store_id,
                SyncCheckpoint.platform == "naver",
                SyncCheckpoint.sync_type == INQUIRY_SYNC_TYPE,
            ))
            if checkpoint is None:
                raise ApiError(
                    "Naver inquiry refresh lease could not be established",
                    "naver_inquiry_lease_unavailable",
                    409,
                )

    if actor_id == "automatic-read" and checkpoint.status == "running" and _active_lease(checkpoint, now):
        return {
            "checkpoint_id": checkpoint.id,
            "token": checkpoint.lease_token,
            "owned": False,
            "ephemeral": False,
        }

    claimed = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == checkpoint.id,
        or_(SyncCheckpoint.lease_expires_at.is_(None), SyncCheckpoint.lease_expires_at <= _utc(now)),
    ).values(
        lease_token=token,
        lease_expires_at=_utc(now) + INQUIRY_LEASE_DURATION,
        last_attempt_at=_utc(now),
    ).execution_options(synchronize_session=False)).rowcount
    db.commit()
    if claimed != 1:
        raise ApiError(
            "Naver inquiry refresh is already running for this store",
            "naver_inquiry_sync_in_progress",
            409,
        )
    return {
        "checkpoint_id": checkpoint.id,
        "token": token,
        "owned": True,
        "ephemeral": checkpoint.notes == INQUIRY_MANUAL_LEASE_NOTE,
    }


def _release_inquiry_lease(db: Session, lease: dict[str, Any] | None) -> None:
    if not lease or not lease.get("owned"):
        return
    db.rollback()
    checkpoint = db.scalar(select(SyncCheckpoint).where(
        SyncCheckpoint.id == int(lease["checkpoint_id"]),
        SyncCheckpoint.lease_token == str(lease["token"]),
    ))
    if checkpoint is None:
        return
    if lease.get("ephemeral") and checkpoint.notes == INQUIRY_MANUAL_LEASE_NOTE and not checkpoint.automatic_read_enabled:
        db.delete(checkpoint)
    else:
        checkpoint.lease_token = None
        checkpoint.lease_expires_at = None
    db.commit()


def _renew_inquiry_lease(
    db: Session,
    *,
    lease: dict[str, Any],
    now: datetime | None = None,
) -> None:
    current = _utc(now or get_utc_now())
    renewed = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == int(lease["checkpoint_id"]),
        SyncCheckpoint.lease_token == str(lease["token"]),
        SyncCheckpoint.lease_expires_at.is_not(None),
        SyncCheckpoint.lease_expires_at > current,
    ).values(
        lease_expires_at=current + INQUIRY_LEASE_DURATION,
    ).execution_options(synchronize_session=False)).rowcount
    db.commit()
    if renewed != 1:
        raise ApiError(
            "Naver inquiry refresh lease was lost",
            "naver_inquiry_lease_lost",
            409,
        )


def _safe_request_error_detail(result: dict[str, Any]) -> dict[str, Any]:
    safe_error = result.get("safe_error") if isinstance(result.get("safe_error"), dict) else {}
    detail: dict[str, Any] = {"platform_http_status": result.get("http_status")}
    platform_error_code = _safe_label(safe_error.get("platform_error_code"), "")
    if platform_error_code:
        detail["platform_error_code"] = platform_error_code
    fields = [
        _safe_label(value, "")
        for value in (safe_error.get("platform_error_fields") or [])[:10]
    ]
    if fields:
        detail["platform_error_fields"] = [value for value in fields if value]
    trace_id = _safe_label(safe_error.get("trace_id"), "")
    if trace_id:
        detail["trace_id"] = trace_id
    rate_limit = safe_error.get("rate_limit")
    if isinstance(rate_limit, dict):
        detail["rate_limit"] = {
            _safe_label(name, ""): str(value)[:120]
            for name, value in list(rate_limit.items())[:20]
            if _safe_label(name, "")
        }
    retry_after = safe_error.get("retry_after_seconds")
    if isinstance(retry_after, int) and 0 <= retry_after <= 3600:
        detail["retry_after_seconds"] = retry_after
    return detail


def _raise_request_failure(result: dict[str, Any]) -> None:
    error_code = str(result.get("error_code") or "naver_customer_inquiry_request_failed")[:80]
    platform_status = result.get("http_status")
    status_code = 503 if result.get("retryable") else 502
    raise ApiError(
        "Naver inquiry readonly request failed",
        error_code,
        status_code,
        detail=_safe_request_error_detail(result) | {"platform_http_status": platform_status},
    )


def _pagination_error(error_code: str) -> ApiError:
    return ApiError(
        "Naver inquiry pagination response is inconsistent",
        error_code,
        502,
    )


def _validate_inquiry_page(
    payload: object,
    *,
    requested_page: int,
    requested_size: int,
    expected_total_pages: int | None,
    expected_total_elements: int | None,
    response_number_base: int | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _pagination_error("naver_inquiry_pagination_invalid")
    required = {
        "totalPages", "totalElements", "first", "last", "number", "size",
        "numberOfElements", "content", "empty",
    }
    if not required.issubset(payload):
        raise _pagination_error("naver_inquiry_pagination_metadata_missing")
    total_pages = payload["totalPages"]
    total_elements = payload["totalElements"]
    number = payload["number"]
    response_size = payload["size"]
    number_of_elements = payload["numberOfElements"]
    content = payload["content"]
    if any(type(value) is not int for value in (total_pages, total_elements, number, response_size, number_of_elements)):
        raise _pagination_error("naver_inquiry_pagination_metadata_invalid")
    if type(payload["first"]) is not bool or type(payload["last"]) is not bool or type(payload["empty"]) is not bool:
        raise _pagination_error("naver_inquiry_pagination_metadata_invalid")
    if not isinstance(content, list) or any(not isinstance(item, dict) for item in content):
        raise _pagination_error("naver_inquiry_pagination_content_invalid")
    if total_pages < 0 or total_elements < 0 or number_of_elements < 0:
        raise _pagination_error("naver_inquiry_pagination_metadata_invalid")
    if total_pages > INQUIRY_MAX_PAGES:
        raise _pagination_error("naver_inquiry_page_limit_reached")
    if response_size != requested_size or number_of_elements != len(content) or len(content) > requested_size:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if payload["empty"] != (len(content) == 0) or payload["first"] != (requested_page == 1):
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    expected_last = total_pages == 0 or requested_page >= total_pages
    if payload["last"] != expected_last:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if total_pages == 0 and (total_elements != 0 or content):
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if total_pages > 0 and total_elements == 0:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    calculated_total_pages = (total_elements + requested_size - 1) // requested_size
    if total_pages != calculated_total_pages:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if not payload["last"] and not content:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if expected_total_pages is not None and total_pages != expected_total_pages:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if expected_total_elements is not None and total_elements != expected_total_elements:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    if response_number_base is None:
        if requested_page != 1 or number not in {0, 1}:
            raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
        response_number_base = number
    expected_number = requested_page - 1 if response_number_base == 0 else requested_page
    if number != expected_number:
        raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
    return {
        "items": content,
        "total_pages": total_pages,
        "total_elements": total_elements,
        "last": payload["last"],
        "response_number_base": response_number_base,
    }


def _page_signature(items: list[dict[str, Any]]) -> str:
    encoded = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _fetch_naver_inquiry_pages(
    *,
    api_base: str,
    token: str,
    start_date: date,
    end_date: date,
    sleep_fn: Callable[[float], None] | None = None,
    before_request: Callable[[], None] | None = None,
) -> dict[str, Any]:
    sleep_fn = sleep_fn or time.sleep
    items: list[dict[str, Any]] = []
    seen_pages: set[str] = set()
    total_pages: int | None = None
    total_elements: int | None = None
    response_number_base: int | None = None
    for page in range(1, INQUIRY_MAX_PAGES + 1):
        if page > 1:
            sleep_fn(INQUIRY_PAGE_DELAY_SECONDS)
        if before_request is not None:
            before_request()
        result = sync_service._request_naver_customer_inquiries(
            api_base=api_base,
            headers={"Authorization": f"Bearer {token}"},
            start_date=start_date,
            end_date=end_date,
            answered=None,
            page=page,
            size=INQUIRY_PAGE_SIZE,
        )
        if not result.get("success"):
            _raise_request_failure(result)
        page_data = _validate_inquiry_page(
            result.get("payload"),
            requested_page=page,
            requested_size=INQUIRY_PAGE_SIZE,
            expected_total_pages=total_pages,
            expected_total_elements=total_elements,
            response_number_base=response_number_base,
        )
        total_pages = page_data["total_pages"]
        total_elements = page_data["total_elements"]
        response_number_base = page_data["response_number_base"]
        signature = _page_signature(page_data["items"])
        if signature in seen_pages:
            raise _pagination_error("naver_inquiry_duplicate_page")
        seen_pages.add(signature)
        items.extend(page_data["items"])
        if len(items) > total_elements:
            raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
        if page_data["last"]:
            if len(items) != total_elements:
                raise _pagination_error("naver_inquiry_pagination_metadata_conflict")
            return {"items": items, "pages_read": page, "total_elements": total_elements}
    raise _pagination_error("naver_inquiry_page_limit_reached")


def _record_refresh_failure(db: Session, *, store_id: int, exc: Exception) -> None:
    detail = exc.detail if isinstance(exc, ApiError) and isinstance(exc.detail, dict) else {}
    safe_summary: dict[str, Any] = {
        "resource": "customer_inquiries",
        "error_code": str(getattr(exc, "error_code", "naver_inquiry_refresh_failed"))[:80],
        "platform_write": False,
        "raw_response_saved": False,
    }
    for key in (
        "platform_http_status", "platform_error_code", "platform_error_fields",
        "trace_id", "rate_limit", "retry_after_seconds",
    ):
        if key in detail:
            safe_summary[key] = detail[key]
    try:
        db.add(SyncLog(
            store_id=store_id,
            platform="naver",
            sync_type="naver_readonly_inquiry_refresh",
            status="failed",
            message="Naver readonly inquiry refresh failed",
            error_detail=safe_summary["error_code"],
            raw_summary=safe_summary,
        ))
        db.commit()
    except Exception:
        db.rollback()


def refresh_naver_readonly_inquiries(
    db: Session, *, store_id: int, actor_id: str | None, settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    # This approval check deliberately precedes every mutable or secret-bearing
    # operation, including lease/checkpoint creation and credential lookup.
    assert_naver_inquiry_real_read_allowed(store_id=store_id, settings=settings)
    _store(db, store_id)
    now = get_utc_now()
    lease: dict[str, Any] | None = None
    try:
        lease = _acquire_inquiry_lease(
            db,
            store_id=store_id,
            actor_id=actor_id,
            settings=settings,
            now=now,
        )
        initialize_naver_inquiry_store(db, store_id=store_id, settings=settings)
        credential = sync_service._ensure_naver_product_preview_credential(
            db,
            store_id=store_id,
            credential_id=None,
        )
        context = sync_service._build_naver_token_context_from_credential(credential)
        _renew_inquiry_lease(db, lease=lease)
        token, _ = api_credential_readiness_service._request_naver_token_from_context(context)
        start_date, end_date = _recent_naver_inquiry_date_range()
        fetched = _fetch_naver_inquiry_pages(
            api_base=context["api_base"],
            token=token,
            start_date=start_date,
            end_date=end_date,
            before_request=lambda: _renew_inquiry_lease(db, lease=lease),
        )
        _renew_inquiry_lease(db, lease=lease)
        counts = {"created": 0, "updated": 0, "skipped": 0}
        for item in fetched["items"]:
            outcome = _upsert_item(db, store_id=store_id, item=item, observed_at=now)
            counts[outcome] += 1
        from app.services.pxg_naver_readonly_persistence_service import _audit_local_ingestion

        _audit_local_ingestion(
            db,
            store_id=store_id,
            actor_id=actor_id,
            source_mode="naver_inquiry_only",
            observed_at=now,
            counts={
                "products": {},
                "orders": {},
                "logistics": {},
                "customer_inquiries": {
                    "created": counts["created"],
                    "updated": counts["updated"],
                },
            },
        )
        db.add(SyncLog(
            store_id=store_id,
            platform="naver",
            sync_type="naver_readonly_inquiry_refresh",
            status="success",
            message="Naver readonly inquiry refresh completed",
            raw_summary={
                "resource": "customer_inquiries",
                "created": counts["created"],
                "updated": counts["updated"],
                "skipped": counts["skipped"],
                "pages_read": fetched["pages_read"],
                "total_elements": fetched["total_elements"],
                "raw_response_saved": False,
                "platform_write": False,
            },
        ))
        db.commit()
        return {
            "status": "success",
            "store_id": store_id,
            "platform": "naver",
            "resource": "customer_inquiries",
            "created_count": counts["created"],
            "updated_count": counts["updated"],
            "skipped_count": counts["skipped"],
            "pages_read": fetched["pages_read"],
            "raw_response_saved": False,
            "platform_write": False,
            "reply_count": 0,
        }
    except Exception as exc:
        db.rollback()
        _record_refresh_failure(db, store_id=store_id, exc=exc)
        raise
    finally:
        _release_inquiry_lease(db, lease)


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
        title = decrypt_value(record.encrypted_title) if record.encrypted_title else None
        customer_name = (
            decrypt_value(record.encrypted_customer_name)
            if record.encrypted_customer_name
            else None
        )
        customer_content = decrypt_value(record.encrypted_content) if record.encrypted_content else ""
        answer_content = (
            decrypt_value(record.encrypted_answer_content)
            if record.encrypted_answer_content
            else ""
        )
        conversation = []
        if customer_content:
            conversation.append({
                "actor": "customer",
                "content": customer_content,
                "sent_at": record.received_at,
            })
        if answer_content:
            conversation.append({
                "actor": "store",
                "content": answer_content,
                "sent_at": record.answered_at,
            })
        return {
            "id": record.id,
            "store_id": store_id,
            "platform": "naver",
            "title": title,
            "customer_name": customer_name,
            "content": customer_content,
            "content_length": record.content_length,
            "classification": "answered" if record.status == "answered" else "unanswered",
            "received_at": record.received_at,
            "answered_at": record.answered_at,
            "conversation": conversation,
            "reply_enabled": False,
        }
    except Exception as exc:
        raise ApiError("readonly inquiry content cannot be decrypted", "readonly_inquiry_content_invalid", 500) from exc
