"""Durable, store-isolated scheduling for approved Naver readonly resources."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.timezone import get_utc_now
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.services.encryption import decrypt_value
from app.services import api_credential_readiness_service, naver_readonly_inquiry_service, order_service, product_service, store_onboarding_service
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local


NAVER = "naver"
RESOURCE_CONFIG = {
    "orders": {"sync_type": "naver_automatic_orders", "interval": timedelta(minutes=10), "freshness": timedelta(minutes=25), "lease": timedelta(minutes=15)},
    "customer_inquiries": {"sync_type": "naver_automatic_inquiries", "interval": timedelta(minutes=10), "freshness": timedelta(minutes=25), "lease": timedelta(minutes=15)},
    "products": {"sync_type": "naver_automatic_products", "interval": timedelta(hours=2), "freshness": timedelta(hours=4), "lease": timedelta(minutes=30)},
    "logistics": {"sync_type": "naver_automatic_logistics", "interval": None, "freshness": timedelta(minutes=75), "lease": None},
}
ORDER_OVERLAP = timedelta(minutes=15)
MAX_PAGES_PER_RUN = 20
LEGACY_APPROVED_READONLY_SYNC_TYPES = (
    "manual_batch_sync",
    "naver_real_order_sync",
    "naver_customer_inquiry_real_sync",
    "naver_readonly_inquiry_refresh",
)
RECOVERABLE_RESOURCES = ("orders", "customer_inquiries", "products")
MANUAL_REVIEW_ERROR_MARKERS = ("cursor", "page", "cleanup", "retention", "conflict", "invalid", "unknown")
RECOVERABLE_ERROR_MARKERS = ("credential", "auth", "ip_not_allowed", "permission", "forbidden")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)


def _stagger(store_id: int, resource: str, interval: timedelta) -> timedelta:
    seconds = max(1, int(interval.total_seconds()))
    digest = hashlib.sha256(f"{store_id}:{resource}".encode("ascii")).digest()
    ratio = (int.from_bytes(digest[:8], "big") / (2**64 - 1)) * 0.2 - 0.1
    return timedelta(seconds=round(seconds * ratio))


def _checkpoint(db: Session, *, store_id: int, resource: str, now: datetime) -> SyncCheckpoint:
    config = RESOURCE_CONFIG[resource]
    checkpoint = db.scalar(select(SyncCheckpoint).where(
        SyncCheckpoint.store_id == store_id,
        SyncCheckpoint.platform == NAVER,
        SyncCheckpoint.sync_type == config["sync_type"],
    ))
    if checkpoint is None:
        interval = config["interval"]
        checkpoint = SyncCheckpoint(
            store_id=store_id,
            platform=NAVER,
            sync_type=config["sync_type"],
            automatic_read_enabled=resource != "logistics",
            status="blocked" if resource == "logistics" else "idle",
            next_run_at=None if resource == "logistics" else now + _stagger(store_id, resource, interval),
            notes="not_supported" if resource == "logistics" else None,
        )
        db.add(checkpoint)
        db.flush()
    return checkpoint


def _eligible_store_ids(db: Session) -> list[int]:
    onboarded_store_ids = db.scalars(select(StoreOnboarding.store_id).join(Store, Store.id == StoreOnboarding.store_id).where(
        StoreOnboarding.status.in_(("partially_synced", "active_incremental")),
        Store.status == "active",
        Store.platform == NAVER,
        StoreOnboarding.store_id.is_not(None),
    )).all()
    legacy_store_ids = db.scalars(_legacy_compatible_store_ids_query()).all()
    return sorted(set(onboarded_store_ids).union(legacy_store_ids))


def _legacy_compatible_store_ids_query():
    return select(Store.id).join(ApiCredential, and_(
        ApiCredential.store_id == Store.id,
        ApiCredential.platform == NAVER,
        ApiCredential.status == "active",
        ApiCredential.auth_status.in_(("configured", "test_passed")),
    )).where(
        Store.status == "active",
        Store.platform == NAVER,
        ~select(StoreOnboarding.id).where(StoreOnboarding.store_id == Store.id).exists(),
        select(SyncLog.id).where(
            SyncLog.store_id == Store.id,
            SyncLog.platform == NAVER,
            SyncLog.sync_type.in_(LEGACY_APPROVED_READONLY_SYNC_TYPES),
            SyncLog.status == "success",
            SyncLog.raw_summary["status"].as_string() == "success",
            SyncLog.raw_summary["platform_write"].as_boolean().is_(False),
        ).exists(),
    )


def _legacy_configured_credential_is_approved(db: Session, credential: ApiCredential) -> bool:
    if credential.auth_status != "configured":
        return False
    return db.scalar(_legacy_compatible_store_ids_query().where(
        Store.id == credential.store_id,
        ApiCredential.id == credential.id,
    )) is not None


def ensure_automatic_read_schedule(db: Session, *, store_id: int, now: datetime | None = None) -> None:
    current = _utc(now or get_utc_now())
    for resource in RESOURCE_CONFIG:
        _checkpoint(db, store_id=store_id, resource=resource, now=current)
    db.commit()


def ensure_onboarded_store_schedules(db: Session, *, now: datetime | None = None) -> int:
    current = _utc(now or get_utc_now())
    store_ids = _eligible_store_ids(db)
    for store_id in store_ids:
        for resource in RESOURCE_CONFIG:
            _checkpoint(db, store_id=store_id, resource=resource, now=current)
    db.commit()
    return len(store_ids)


def _claim(db: Session, *, checkpoint_id: int, now: datetime) -> str | None:
    token = secrets.token_urlsafe(24)
    claimed = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == checkpoint_id,
        SyncCheckpoint.automatic_read_enabled.is_(True),
        SyncCheckpoint.status != "blocked",
        or_(SyncCheckpoint.next_run_at.is_(None), SyncCheckpoint.next_run_at <= now),
        or_(SyncCheckpoint.lease_expires_at.is_(None), SyncCheckpoint.lease_expires_at <= now),
    ).values(
        status="running", lease_token=token, lease_expires_at=now + _resource_lease(checkpoint_id, db),
        last_attempt_at=now, last_error_code=None,
    ).execution_options(synchronize_session=False)).rowcount
    db.commit()
    return token if claimed == 1 else None


def _resource_lease(checkpoint_id: int, db: Session) -> timedelta:
    checkpoint = db.get(SyncCheckpoint, checkpoint_id)
    if checkpoint is None:
        return timedelta(minutes=15)
    return RESOURCE_CONFIG.get(_resource_for_checkpoint(checkpoint), {}).get("lease") or timedelta(minutes=15)


def _context(db: Session, store_id: int) -> store_onboarding_service.NaverReadContext:
    credential = db.scalar(select(ApiCredential).where(
        ApiCredential.store_id == store_id, ApiCredential.platform == NAVER,
        ApiCredential.status == "active", ApiCredential.auth_status == "test_passed",
    ).order_by(ApiCredential.id.desc()))
    if credential is None:
        configured_credential = db.scalar(select(ApiCredential).where(
            ApiCredential.store_id == store_id, ApiCredential.platform == NAVER,
            ApiCredential.status == "active", ApiCredential.auth_status == "configured",
        ).order_by(ApiCredential.id.desc()))
        if configured_credential is not None and _legacy_configured_credential_is_approved(db, configured_credential):
            credential = configured_credential
    if credential is None or not credential.client_id:
        raise store_onboarding_service.NaverReadFailure("credential_unavailable")
    secret = decrypt_value(credential.encrypted_secret_key)
    if not secret:
        raise store_onboarding_service.NaverReadFailure("credential_unavailable")
    extra = credential.extra_config if isinstance(credential.extra_config, dict) else {}
    return store_onboarding_service.NaverReadContext(
        store_id, credential.id, credential.client_id, secret, extra.get("channel_no"),
        str(extra.get("api_base") or "https://api.commerce.naver.com/external").rstrip("/"),
        str(extra.get("grant_type") or "SELF"), extra.get("seller_account_id"),
    )


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, store_onboarding_service.NaverReadFailure):
        return exc.code[:80]
    return str(getattr(exc, "error_code", "automatic_read_failed"))[:80]


def _resource_for_checkpoint(checkpoint: SyncCheckpoint) -> str:
    for resource, config in RESOURCE_CONFIG.items():
        if checkpoint.sync_type == config["sync_type"]:
            return resource
    raise ValueError("unsupported automatic checkpoint")


def _sync_t13_resource(
    db: Session, *, checkpoint: SyncCheckpoint, resource: str,
    reader: store_onboarding_service.NaverReadAdapter, now: datetime,
) -> dict[str, int]:
    context = _context(db, checkpoint.store_id)
    if checkpoint.cursor_value:
        start_at = _utc(checkpoint.window_start_at or now - ORDER_OVERLAP)
        end_at = _utc(checkpoint.window_end_at or now)
    else:
        start_at = _utc((checkpoint.last_synced_at or now) - (ORDER_OVERLAP if resource == "orders" else timedelta(0)))
        end_at = now
        checkpoint.window_start_at, checkpoint.window_end_at = start_at, end_at
        db.commit()
    cursor = checkpoint.cursor_value
    created = updated = pages = 0
    while True:
        if pages >= MAX_PAGES_PER_RUN:
            raise store_onboarding_service.NaverReadFailure("read_page_limit_reached", retryable=True)
        page = reader.read_orders(context, start_at=start_at, end_at=end_at, cursor=cursor) if resource == "orders" else reader.read_products(context, start_at=start_at, end_at=end_at, cursor=cursor)
        if not isinstance(page, store_onboarding_service.NaverReadPage):
            raise store_onboarding_service.NaverReadFailure("invalid_read_adapter_page")
        items = store_onboarding_service._canonical_orders(page.items, "automatic_incremental") if resource == "orders" else store_onboarding_service._canonical_products(page.items, "automatic_incremental")
        outcome = order_service.upsert_orders(db, checkpoint.store_id, NAVER, items) if resource == "orders" else product_service.upsert_products(db, checkpoint.store_id, NAVER, items)
        # The writer commits before this cursor transition is persisted.
        created += outcome["created"]
        updated += outcome["updated"]
        pages += 1
        cursor = page.next_cursor
        checkpoint.cursor_value = cursor
        db.commit()
        if not cursor:
            break
    return {"created": created, "updated": updated, "pages": pages}


def _finish_success(db: Session, *, checkpoint: SyncCheckpoint, token: str, now: datetime, result: dict[str, int]) -> bool:
    if checkpoint.lease_token != token:
        return False
    resource = _resource_for_checkpoint(checkpoint)
    interval = RESOURCE_CONFIG[resource]["interval"]
    checkpoint.status = "success"
    checkpoint.last_synced_at = now
    checkpoint.fresh_until = now + RESOURCE_CONFIG[resource]["freshness"]
    checkpoint.next_run_at = now + interval + _stagger(checkpoint.store_id, resource, interval)
    checkpoint.retry_count = 0
    checkpoint.last_error_code = None
    checkpoint.lease_token = None
    checkpoint.lease_expires_at = None
    db.add(SyncLog(store_id=checkpoint.store_id, platform=NAVER, sync_type=checkpoint.sync_type, status="success", finished_at=now,
                   message="automatic readonly sync completed", raw_summary={**result, "raw_response_saved": False, "platform_write": False}))
    db.commit()
    return True


def _finish_failure(db: Session, *, checkpoint: SyncCheckpoint, token: str, now: datetime, exc: Exception) -> bool:
    if checkpoint.lease_token != token:
        return False
    checkpoint.last_error_code = _safe_error_code(exc)
    if _retryable_error(checkpoint.last_error_code):
        checkpoint.retry_count += 1
        checkpoint.status = "retry_wait"
        checkpoint.next_run_at = now + timedelta(minutes=min(60, 2 ** min(checkpoint.retry_count - 1, 6)))
    else:
        checkpoint.status = "blocked"
        checkpoint.automatic_read_enabled = False
        checkpoint.next_run_at = None
    checkpoint.lease_token = None
    checkpoint.lease_expires_at = None
    db.add(SyncLog(store_id=checkpoint.store_id, platform=NAVER, sync_type=checkpoint.sync_type, status="failed", finished_at=now,
                   message="automatic readonly sync failed", error_detail=checkpoint.last_error_code,
                   raw_summary={"error_code": checkpoint.last_error_code, "raw_response_saved": False, "platform_write": False}))
    db.commit()
    return True


def _retryable_error(code: str) -> bool:
    normalized = code.lower()
    return normalized in {"naver_read_retryable", "network_timeout", "network_error", "readonly_request_failed"} or any(
        marker in normalized for marker in ("timeout", "rate_limit", "http_429", "http_5", "retryable")
    )


def _safe_failure_reason(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.lower()
    if normalized == "not_supported":
        return "not_supported"
    if _retryable_error(normalized):
        return "temporary_platform_or_network_failure"
    if any(marker in normalized for marker in ("auth", "credential", "permission", "forbidden")):
        return "authentication_or_permission_required"
    if "cursor" in normalized:
        return "cursor_requires_manual_review"
    if "cleanup" in normalized or "retention" in normalized:
        return "privacy_cleanup_gate_blocked"
    if "conflict" in normalized:
        return "source_conflict_requires_manual_review"
    return "manual_review_required"


def _recovery_eligible_error(code: str | None) -> bool:
    if not code:
        return False
    normalized = code.lower()
    if any(marker in normalized for marker in MANUAL_REVIEW_ERROR_MARKERS):
        return False
    return any(marker in normalized for marker in RECOVERABLE_ERROR_MARKERS)


def _attention_fields(*, resource: str, status: str, enabled: bool, stale: bool, last_error_code: str | None, store_id: int) -> dict[str, Any]:
    if resource == "logistics":
        return {"attention_state": "none", "operator_message": "not_supported", "admin_action": None, "recovery_eligible": False, "action_path": None}
    if status == "blocked":
        eligible = _recovery_eligible_error(last_error_code)
        return {
            "attention_state": "admin_action",
            "operator_message": "administrator_recovery_required" if eligible else "manual_review_required",
            "admin_action": "recover_automatic_read" if eligible else "manual_review",
            "recovery_eligible": eligible,
            "action_path": f"/api/v1/stores/{store_id}/automatic-read/recover" if eligible else None,
        }
    if status == "retry_wait" or (enabled and stale):
        return {"attention_state": "automatic_retry", "operator_message": "automatic_retry_scheduled", "admin_action": None, "recovery_eligible": False, "action_path": None}
    return {"attention_state": "none", "operator_message": "automatic_read_on_schedule", "admin_action": None, "recovery_eligible": False, "action_path": None}


def recover_automatic_read(db: Session, *, store_id: int, actor_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Verify one store-bound readonly capability, then reopen eligible blocked checkpoints."""
    current = _utc(now or get_utc_now())
    settings = get_settings()
    store = db.get(Store, store_id)
    if store is None:
        raise ValueError("automatic_read_store_not_found")
    if store.status != "active":
        raise ValueError("automatic_read_store_inactive")
    if store.platform.lower() != NAVER:
        raise ValueError("automatic_read_platform_not_supported")
    if not settings.automatic_read_sync_enabled:
        raise ValueError("automatic_read_runtime_disabled")
    rows = db.scalars(select(SyncCheckpoint).where(
        SyncCheckpoint.store_id == store_id,
        SyncCheckpoint.platform == NAVER,
        SyncCheckpoint.sync_type.in_([RESOURCE_CONFIG[resource]["sync_type"] for resource in RECOVERABLE_RESOURCES]),
    )).all()
    if any(row.lease_token and row.lease_expires_at and _utc(row.lease_expires_at) > current for row in rows):
        raise ValueError("automatic_read_live_lease")
    eligible = [row for row in rows if row.status == "blocked" and _recovery_eligible_error(row.last_error_code)]
    if not eligible:
        raise ValueError("automatic_read_no_eligible_checkpoint")
    smoke = api_credential_readiness_service.run_api_credential_smoke_test(
        db=db, platform=NAVER, mode="readonly", store_id=store_id, capability_scope="seller_channels",
        persist_channel_no=False, persist_capability_results=False,
    )
    smoke_result = (smoke.get("results") or [{}])[0]
    if smoke_result.get("error_code") or smoke_result.get("seller_or_account_test") != "success":
        raise ValueError("automatic_read_recovery_verification_failed")
    restored_resources = []
    for checkpoint in eligible:
        checkpoint.status = "idle"
        checkpoint.automatic_read_enabled = True
        checkpoint.next_run_at = current
        checkpoint.retry_count = 0
        checkpoint.last_error_code = None
        checkpoint.lease_token = None
        checkpoint.lease_expires_at = None
        restored_resources.append(_resource_for_checkpoint(checkpoint))
    audit = write_operation_audit_log_local(
        db,
        {
            "created_at": current, "updated_at": current, "store_id": store_id, "platform": NAVER,
            "environment": settings.app_env, "actor_type": "human", "actor_id": actor_id,
            "action": "automatic_read_recovery", "operation_phase": "T16",
            "correlation_id": f"t16_recovery_{store_id}_{int(current.timestamp())}", "status": "success",
            "reason_code": "credential_verification_passed", "target_type": "sync_gate", "target_id": store_id,
            "changed_field_names": ["automatic_read_enabled", "last_error_code", "next_run_at", "retry_count", "status"],
            "counts_summary": {"restored_checkpoint_count": len(restored_resources)},
            "safety_flags": {"platform_write": False, "raw_response_saved": False, "smoke_persisted": False},
            "sensitive_scan_passed": True, "raw_response_saved": False, "secrets_saved": False,
            "privacy_fields_redacted": True,
        },
        write_enabled=True, manual_approval=True, local_write_scope=LOCAL_WRITER_SCOPE,
    )
    if not audit.get("audit_rows_written"):
        db.rollback()
        raise RuntimeError("automatic_read_recovery_audit_failed")
    return {"status": "automatic_read_recovery_restored", "store_id": store_id,
            "restored_resources": sorted(restored_resources), "restored_checkpoint_count": len(restored_resources),
            "platform_write": False, "sync_started": False, "smoke_persisted": False}


def run_automatic_checkpoint(
    db: Session, *, checkpoint_id: int, now: datetime | None = None,
    reader: store_onboarding_service.NaverReadAdapter | None = None,
    inquiry_runner: Callable[..., dict[str, Any]] | None = None,
) -> str:
    current = _utc(now or get_utc_now())
    token = _claim(db, checkpoint_id=checkpoint_id, now=current)
    if token is None:
        return "not_due"
    checkpoint = db.get(SyncCheckpoint, checkpoint_id)
    assert checkpoint is not None
    resource = _resource_for_checkpoint(checkpoint)
    try:
        if resource == "customer_inquiries":
            result = (inquiry_runner or naver_readonly_inquiry_service.refresh_naver_readonly_inquiries)(
                db, store_id=checkpoint.store_id, actor_id="automatic-read", settings=get_settings(),
            )
            summary = {"created": int(result.get("created_count", 0)), "updated": int(result.get("updated_count", 0)), "pages": int(result.get("pages_read", 0))}
        else:
            summary = _sync_t13_resource(db, checkpoint=checkpoint, resource=resource, reader=reader or store_onboarding_service.get_naver_read_adapter(), now=current)
        return "success" if _finish_success(db, checkpoint=checkpoint, token=token, now=current, result=summary) else "not_due"
    except Exception as exc:
        db.rollback()
        checkpoint = db.get(SyncCheckpoint, checkpoint_id)
        assert checkpoint is not None
        return "failed" if _finish_failure(db, checkpoint=checkpoint, token=token, now=current, exc=exc) else "not_due"


def run_due_automatic_read_syncs(
    *, session_factory: Callable[[], Session], now: datetime | None = None,
    reader: store_onboarding_service.NaverReadAdapter | None = None,
    inquiry_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    settings = get_settings()
    if not settings.automatic_read_sync_enabled:
        return {"scheduled": 0, "success": 0, "failed": 0}
    current = _utc(now or get_utc_now())
    with session_factory() as db:
        ensure_onboarded_store_schedules(db, now=current)
        due_ids = db.scalars(select(SyncCheckpoint.id).where(
            SyncCheckpoint.platform == NAVER, SyncCheckpoint.automatic_read_enabled.is_(True),
            SyncCheckpoint.status != "blocked", or_(SyncCheckpoint.next_run_at.is_(None), SyncCheckpoint.next_run_at <= current),
        )).all()
    counts = {"scheduled": len(due_ids), "success": 0, "failed": 0}
    for checkpoint_id in due_ids:
        with session_factory() as db:
            result = run_automatic_checkpoint(db, checkpoint_id=checkpoint_id, now=current, reader=reader, inquiry_runner=inquiry_runner)
            if result in counts:
                counts[result] += 1
    return counts


def automatic_read_status(db: Session, *, store_id: int, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    rows = db.scalars(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store_id, SyncCheckpoint.platform == NAVER)).all()
    by_type = {row.sync_type: row for row in rows}
    result: dict[str, dict[str, Any]] = {}
    current = _utc(now or get_utc_now())
    for resource, config in RESOURCE_CONFIG.items():
        row = by_type.get(config["sync_type"])
        if resource == "logistics":
            result[resource] = _status_item(resource, store_id, "blocked", False, None, None, None, 0, "not_supported", None, current)
        elif row is None:
            result[resource] = _status_item(resource, store_id, "disabled", False, None, None, None, 0, None, None, current)
        else:
            result[resource] = _status_item(resource, store_id, row.status, row.automatic_read_enabled, row.last_synced_at, row.next_run_at, row.fresh_until, row.retry_count, row.last_error_code, row.last_attempt_at, current)
    return result


def _status_item(resource: str, store_id: int, status: str, enabled: bool, last_success_at: datetime | None, next_run_at: datetime | None, data_fresh_until: datetime | None, retry_count: int, last_error_code: str | None, last_attempt_at: datetime | None, now: datetime) -> dict[str, Any]:
    stale = bool(data_fresh_until and _utc(data_fresh_until) < now)
    due = bool(next_run_at and _utc(next_run_at) <= now)
    display_status = "blocked" if status == "blocked" else ("stale" if stale else ("due" if due and status not in {"running", "retry_wait"} else status))
    return {"status": display_status, "automatic_read_enabled": enabled, "last_success_at": last_success_at,
            "next_run_at": next_run_at, "data_fresh_until": data_fresh_until, "retry_count": retry_count,
            "last_error_code": last_error_code, "safe_failure_reason": _safe_failure_reason(last_error_code),
            "is_stale": stale, "last_attempt_at": last_attempt_at,
            **_attention_fields(resource=resource, status=status, enabled=enabled, stale=stale, last_error_code=last_error_code, store_id=store_id)}
