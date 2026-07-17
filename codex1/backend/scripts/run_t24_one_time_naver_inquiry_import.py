from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
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
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.customer_inquiry import CustomerInquiry
from app.models.pxg_naver_readonly import PxgNaverReadonlyCustomerInquiry
from app.models.sync_log import SyncLog
from app.services import customer_inquiry_service, naver_readonly_inquiry_service
from app.services.encryption import decrypt_value
from app.services.naver_inquiry_identity import naver_inquiry_external_id_hash
from run_t24_controlled_naver_inquiry_probe import (
    CAPABILITY_KEY,
    ProbeBlocked,
    _assert_no_active_lease_or_cooldown,
    _assert_runtime_closed,
    _resolve_store_and_credential,
)


APPROVAL_VALUE = "owner-approved-one-time-30-day-import"
IMPORT_SYNC_TYPE = "t24_one_time_inquiry_import"
LEGACY_SENSITIVE_RAW_KEYS = frozenset({
    "answercomment",
    "answercontent",
    "answer_content",
    "content",
    "customername",
    "customer_name",
    "inquirycontent",
    "inquiry_content",
    "message",
    "title",
})


def _require_process_approval(store_id: int) -> None:
    if os.environ.get("T24_ONE_TIME_INQUIRY_IMPORT_APPROVAL") != APPROVAL_VALUE:
        raise ProbeBlocked("t24_import_owner_approval_missing")
    try:
        approved_store_id = int(os.environ.get("T24_ONE_TIME_INQUIRY_IMPORT_STORE_ID", "0"))
    except ValueError as exc:
        raise ProbeBlocked("t24_import_approved_store_invalid") from exc
    if approved_store_id != store_id:
        raise ProbeBlocked("t24_import_approved_store_mismatch")


def _assert_capability_evidence(db: Session, *, store_id: int, credential_id: int) -> None:
    evidence = db.scalar(
        select(ApiCapabilityTestResult)
        .join(ApiCapabilityCheck, ApiCapabilityCheck.id == ApiCapabilityTestResult.capability_id)
        .where(
            ApiCapabilityTestResult.store_id == store_id,
            ApiCapabilityTestResult.credential_id == credential_id,
            ApiCapabilityCheck.platform == "naver",
            ApiCapabilityCheck.capability_key == CAPABILITY_KEY,
            ApiCapabilityTestResult.test_mode == "real_readonly",
            ApiCapabilityTestResult.test_status == "tested_success",
            ApiCapabilityTestResult.http_status == 200,
            ApiCapabilityTestResult.permission_result == "order_seller_confirmed",
        )
        .order_by(ApiCapabilityTestResult.id.desc())
    )
    if evidence is None:
        raise ProbeBlocked("t24_import_capability_evidence_missing")


def _assert_not_already_started(db: Session, *, store_id: int) -> None:
    existing = db.scalar(
        select(SyncLog.id).where(
            SyncLog.store_id == store_id,
            SyncLog.platform == "naver",
            SyncLog.sync_type == IMPORT_SYNC_TYPE,
            SyncLog.status.in_(("started", "success")),
        ).limit(1)
    )
    if existing is not None:
        raise ProbeBlocked("t24_import_already_started")


def _start_attempt(db: Session, *, store_id: int, now: datetime) -> int:
    row = SyncLog(
        store_id=store_id,
        platform="naver",
        sync_type=IMPORT_SYNC_TYPE,
        status="started",
        started_at=now,
        message="Owner-approved one-time 30-day Naver inquiry import started",
        raw_summary={
            "resource": "customer_inquiries",
            "window_days": 30,
            "raw_response_saved": False,
            "platform_write": False,
            "automatic_sync_enabled": False,
        },
    )
    db.add(row)
    db.commit()
    return row.id


def _finish_attempt(
    db: Session,
    *,
    attempt_id: int,
    status: str,
    now: datetime,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    row = db.get(SyncLog, attempt_id)
    if row is None:
        raise ProbeBlocked("t24_import_attempt_missing")
    row.status = status
    row.finished_at = now
    row.message = (
        "Owner-approved one-time 30-day Naver inquiry import completed"
        if status == "success"
        else "Owner-approved one-time 30-day Naver inquiry import failed"
    )
    row.error_detail = error_code[:120] if error_code else None
    row.raw_summary = {
        "resource": "customer_inquiries",
        "window_days": 30,
        "created": int((result or {}).get("created_count") or 0),
        "updated": int((result or {}).get("updated_count") or 0),
        "skipped": int((result or {}).get("skipped_count") or 0),
        "pages_read": int((result or {}).get("pages_read") or 0),
        "legacy_plaintext_sanitized": int(
            (result or {}).get("legacy_plaintext_sanitized_count") or 0
        ),
        "error_code": error_code[:120] if error_code else None,
        "raw_response_saved": False,
        "platform_write": False,
        "automatic_sync_enabled": False,
    }
    db.commit()


def _classification_counts(db: Session, *, store_id: int) -> dict[str, int]:
    total = db.scalar(select(func.count()).select_from(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
    )) or 0
    answered = db.scalar(select(func.count()).select_from(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
        PxgNaverReadonlyCustomerInquiry.status == "answered",
    )) or 0
    return {"all": int(total), "answered": int(answered), "unanswered": int(total - answered)}


def _scrub_legacy_raw_data(raw_data: object) -> dict[str, Any]:
    source = raw_data if isinstance(raw_data, dict) else {}

    def scrub(value: object) -> object:
        if isinstance(value, dict):
            return {
                str(key): scrub(item)
                for key, item in value.items()
                if str(key).replace("-", "_").strip().lower() not in LEGACY_SENSITIVE_RAW_KEYS
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    scrubbed = scrub(source)
    if not isinstance(scrubbed, dict):
        scrubbed = {}
    scrubbed.update({
        "source_type": customer_inquiry_service.NAVER_LEGACY_SYNC_SOURCE,
        "superseded_by_readonly": True,
        "raw_response_saved": False,
        "platform_write": False,
    })
    return scrubbed


def _sanitize_superseded_legacy_inquiries(db: Session, *, store_id: int) -> int:
    readonly_rows = db.scalars(select(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
    )).all()
    readonly_by_hash = {row.external_inquiry_id_hash: row for row in readonly_rows}
    legacy_rows = db.scalars(select(CustomerInquiry).where(
        CustomerInquiry.store_id == store_id,
        CustomerInquiry.platform == "naver",
    )).all()
    sanitized = 0
    for legacy in legacy_rows:
        raw_data = legacy.raw_data if isinstance(legacy.raw_data, dict) else {}
        if raw_data.get("source_type") != customer_inquiry_service.NAVER_LEGACY_SYNC_SOURCE:
            continue
        inquiry_hash = naver_inquiry_external_id_hash(legacy.external_inquiry_id)
        readonly = readonly_by_hash.get(inquiry_hash or "")
        if readonly is None:
            continue
        customer_content = decrypt_value(readonly.encrypted_content) if readonly.encrypted_content else ""
        customer_name = (
            decrypt_value(readonly.encrypted_customer_name)
            if readonly.encrypted_customer_name
            else ""
        )
        title = decrypt_value(readonly.encrypted_title) if readonly.encrypted_title else ""
        store_answer = (
            decrypt_value(readonly.encrypted_answer_content)
            if readonly.encrypted_answer_content
            else ""
        )
        legacy_answer = str(
            raw_data.get("answer_content")
            or raw_data.get("answerContent")
            or raw_data.get("answerComment")
            or ""
        )
        if legacy.content and customer_content != legacy.content:
            raise ProbeBlocked("t24_import_legacy_question_conflict")
        if legacy.customer_name and customer_name != legacy.customer_name:
            raise ProbeBlocked("t24_import_legacy_customer_name_conflict")
        if legacy.title and not title:
            raise ProbeBlocked("t24_import_legacy_title_not_preserved")
        if legacy_answer and not (store_answer == legacy_answer or store_answer.startswith(legacy_answer)):
            raise ProbeBlocked("t24_import_legacy_answer_conflict")
        legacy.customer_name = None
        legacy.title = "Migrated to encrypted readonly inquiry"
        legacy.content = ""
        legacy.raw_data = _scrub_legacy_raw_data(raw_data)
        sanitized += 1
    db.flush()
    return sanitized


def run_import(
    db: Session,
    *,
    store_id: int,
    expected_store_name_sha256: str,
    settings: Settings | None = None,
    now: datetime | None = None,
    refresh_runner: Callable[..., dict[str, Any]] | None = None,
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
    _assert_capability_evidence(db, store_id=store_id, credential_id=credential.id)
    _assert_no_active_lease_or_cooldown(db, store_id=store_id, now=current)
    _assert_not_already_started(db, store_id=store_id)
    attempt_id = _start_attempt(db, store_id=store_id, now=current)
    approved_settings = settings.model_copy(update={
        "automatic_read_sync_enabled": False,
        "naver_readonly_inquiry_real_read_enabled": True,
        "naver_readonly_inquiry_approved_store_id": store_id,
    })
    actor_id = hashlib.sha256(b"owner-approved-t24-one-time-inquiry-import").hexdigest()
    runner = refresh_runner or naver_readonly_inquiry_service.refresh_naver_readonly_inquiries
    try:
        result = runner(
            db,
            store_id=store.id,
            actor_id=actor_id,
            settings=approved_settings,
        )
        result = {
            **result,
            "legacy_plaintext_sanitized_count": _sanitize_superseded_legacy_inquiries(
                db,
                store_id=store.id,
            ),
        }
        _finish_attempt(
            db,
            attempt_id=attempt_id,
            status="success",
            now=get_utc_now(),
            result=result,
        )
    except Exception as exc:
        db.rollback()
        error_code = str(getattr(exc, "error_code", "t24_one_time_inquiry_import_failed"))[:120]
        _finish_attempt(
            db,
            attempt_id=attempt_id,
            status="failed",
            now=get_utc_now(),
            error_code=error_code,
        )
        raise
    return {
        "status": "success",
        "store_id": store.id,
        "platform": "naver",
        "window_days": 30,
        "created_count": int(result.get("created_count") or 0),
        "updated_count": int(result.get("updated_count") or 0),
        "skipped_count": int(result.get("skipped_count") or 0),
        "pages_read": int(result.get("pages_read") or 0),
        "classification_counts": _classification_counts(db, store_id=store.id),
        "legacy_plaintext_sanitized_count": int(result.get("legacy_plaintext_sanitized_count") or 0),
        "raw_response_saved": False,
        "platform_write": False,
        "automatic_sync_enabled": False,
        "reply_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one owner-approved 30-day Naver inquiry import")
    parser.add_argument("--store-id", type=int, required=True)
    parser.add_argument("--expected-store-name-sha256", required=True)
    args = parser.parse_args()

    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            result = run_import(
                db,
                store_id=args.store_id,
                expected_store_name_sha256=args.expected_store_name_sha256,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except ProbeBlocked as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": exc.error_code,
            "platform_write": False,
            "automatic_sync_enabled": False,
        }, sort_keys=True))
        raise SystemExit(3) from None
    except ApiError as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": str(exc.error_code)[:120],
            "platform_write": False,
            "automatic_sync_enabled": False,
        }, sort_keys=True))
        raise SystemExit(4) from None
    except Exception:
        print(json.dumps({
            "status": "failed",
            "error_code": "t24_one_time_inquiry_import_failed",
            "platform_write": False,
            "automatic_sync_enabled": False,
        }, sort_keys=True))
        raise SystemExit(5) from None


if __name__ == "__main__":
    main()
