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
from app.services import naver_readonly_inquiry_service, order_service, product_service, store_onboarding_service


NAVER = "naver"
RESOURCE_CONFIG = {
    "orders": {"sync_type": "naver_automatic_orders", "interval": timedelta(minutes=10)},
    "customer_inquiries": {"sync_type": "naver_automatic_inquiries", "interval": timedelta(minutes=10)},
    "products": {"sync_type": "naver_automatic_products", "interval": timedelta(hours=2)},
    "logistics": {"sync_type": "naver_automatic_logistics", "interval": None},
}
LEASE_DURATION = timedelta(minutes=5)
ORDER_OVERLAP = timedelta(minutes=15)
MAX_PAGES_PER_RUN = 20


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)


def _stagger(store_id: int, resource: str, interval: timedelta) -> timedelta:
    seconds = max(1, int(interval.total_seconds()))
    digest = hashlib.sha256(f"{store_id}:{resource}".encode("ascii")).digest()
    return timedelta(seconds=int.from_bytes(digest[:4], "big") % min(60, seconds))


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
    return db.scalars(select(StoreOnboarding.store_id).join(Store, Store.id == StoreOnboarding.store_id).where(
        StoreOnboarding.status.in_(("partially_synced", "active_incremental")),
        Store.status == "active",
        Store.platform == NAVER,
        StoreOnboarding.store_id.is_not(None),
    )).all()


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
        status="running", lease_token=token, lease_expires_at=now + LEASE_DURATION,
        last_attempt_at=now, last_error_code=None,
    ).execution_options(synchronize_session=False)).rowcount
    db.commit()
    return token if claimed == 1 else None


def _context(db: Session, store_id: int) -> store_onboarding_service.NaverReadContext:
    credential = db.scalar(select(ApiCredential).where(
        ApiCredential.store_id == store_id, ApiCredential.platform == NAVER,
        ApiCredential.status == "active", ApiCredential.auth_status == "test_passed",
    ).order_by(ApiCredential.id.desc()))
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
    checkpoint.fresh_until = now + interval
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
    checkpoint.retry_count += 1
    checkpoint.status = "retry_wait"
    checkpoint.last_error_code = _safe_error_code(exc)
    checkpoint.next_run_at = now + timedelta(seconds=min(1800, 60 * (2 ** min(checkpoint.retry_count - 1, 5))))
    checkpoint.lease_token = None
    checkpoint.lease_expires_at = None
    db.add(SyncLog(store_id=checkpoint.store_id, platform=NAVER, sync_type=checkpoint.sync_type, status="failed", finished_at=now,
                   message="automatic readonly sync failed", error_detail=checkpoint.last_error_code,
                   raw_summary={"error_code": checkpoint.last_error_code, "raw_response_saved": False, "platform_write": False}))
    db.commit()
    return True


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


def automatic_read_status(db: Session, *, store_id: int) -> dict[str, dict[str, Any]]:
    rows = db.scalars(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store_id, SyncCheckpoint.platform == NAVER)).all()
    by_type = {row.sync_type: row for row in rows}
    result: dict[str, dict[str, Any]] = {}
    for resource, config in RESOURCE_CONFIG.items():
        row = by_type.get(config["sync_type"])
        if resource == "logistics":
            result[resource] = {"status": "blocked", "error_code": "not_supported", "automatic_read_enabled": False}
        elif row is None:
            result[resource] = {"status": "pending", "automatic_read_enabled": False}
        else:
            result[resource] = {"status": row.status, "automatic_read_enabled": row.automatic_read_enabled,
                                "next_run_at": row.next_run_at, "fresh_until": row.fresh_until,
                                "retry_count": row.retry_count, "last_error_code": row.last_error_code,
                                "last_attempt_at": row.last_attempt_at}
    return result
