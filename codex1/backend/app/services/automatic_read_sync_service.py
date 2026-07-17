"""Durable, store-isolated scheduling for approved Naver readonly resources."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.models.order import Order
from app.models.pxg_naver_readonly import PxgNaverReadonlyLogisticsRecord
from app.services.encryption import decrypt_value
from app.services import api_credential_readiness_service, naver_readonly_inquiry_service, order_service, product_service, pxg_naver_readonly_persistence_service, store_onboarding_service
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local


NAVER = "naver"
RESOURCE_CONFIG = {
    "orders": {"sync_type": "naver_automatic_orders", "interval": timedelta(minutes=10), "freshness": timedelta(minutes=25), "lease": timedelta(minutes=15)},
    "customer_inquiries": {"sync_type": "naver_automatic_inquiries", "interval": timedelta(minutes=10), "freshness": timedelta(minutes=25), "lease": timedelta(minutes=15)},
    "products": {"sync_type": "naver_automatic_products", "interval": timedelta(hours=2), "freshness": timedelta(hours=4), "lease": timedelta(minutes=30)},
    "logistics": {"sync_type": "naver_automatic_logistics", "interval": timedelta(minutes=30), "freshness": timedelta(minutes=75), "lease": timedelta(minutes=20)},
}
PREPARED_ACTIVATION_RESOURCE_ORDER = ("orders", "customer_inquiries", "logistics", "products")
ORDER_OVERLAP = timedelta(minutes=15)
MAX_PAGES_PER_RUN = 20
MAX_RETRY_DELAY_SECONDS = 60 * 60
PREPARED_ACTIVATION_START_GRACE = timedelta(minutes=1)
INQUIRY_GATE_ERROR_CODES = frozenset({
    "naver_inquiry_real_read_disabled",
    "naver_inquiry_store_not_approved",
})
LEGACY_APPROVED_READONLY_SYNC_TYPES = (
    "manual_batch_sync",
    "naver_real_order_sync",
    "naver_customer_inquiry_real_sync",
    "naver_readonly_inquiry_refresh",
)
RECOVERABLE_RESOURCES = ("orders", "customer_inquiries", "products", "logistics")
RECOVERABLE_ERROR_CODES = frozenset({
    "credential_unavailable",
    "credential_not_ready",
    "credential_invalid",
    "credential_decrypt_failed",
    "auth_failed",
    "token_auth_failed",
    "permission_forbidden",
    "product_api_not_allowed",
    "order_api_not_allowed",
    "ip_not_allowed",
})


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
            automatic_read_enabled=True,
            status="idle",
            next_run_at=now + _stagger(store_id, resource, interval),
        )
        db.add(checkpoint)
        db.flush()
    elif resource == "logistics" and (
        checkpoint.status == "blocked"
        and checkpoint.automatic_read_enabled is False
        and checkpoint.notes == "not_supported"
    ):
        # Only the exact R1 placeholder is upgraded. Other operator-blocked
        # checkpoints remain fail-closed and require the normal recovery path.
        checkpoint.status = "idle"
        checkpoint.automatic_read_enabled = True
        checkpoint.notes = None
        checkpoint.next_run_at = now if checkpoint.next_run_at is None else checkpoint.next_run_at
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
        ApiCredential.auth_status == "test_passed",
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


def _inquiry_gate_error(settings: Settings, store_id: int) -> str | None:
    if not settings.naver_readonly_inquiry_real_read_enabled:
        return "naver_inquiry_real_read_disabled"
    if store_id not in settings.naver_readonly_inquiry_approved_store_id_set:
        return "naver_inquiry_store_not_approved"
    return None


def _apply_inquiry_real_read_gate(db: Session, *, settings: Settings, now: datetime) -> None:
    checkpoints = db.scalars(select(SyncCheckpoint).where(
        SyncCheckpoint.platform == NAVER,
        SyncCheckpoint.sync_type == RESOURCE_CONFIG["customer_inquiries"]["sync_type"],
    )).all()
    for checkpoint in checkpoints:
        gate_error = _inquiry_gate_error(settings, checkpoint.store_id)
        if gate_error is not None:
            checkpoint.status = "blocked"
            checkpoint.automatic_read_enabled = False
            checkpoint.next_run_at = None
            checkpoint.last_error_code = gate_error
            checkpoint.lease_token = None
            checkpoint.lease_expires_at = None
        elif checkpoint.last_error_code in INQUIRY_GATE_ERROR_CODES:
            checkpoint.status = "idle"
            checkpoint.automatic_read_enabled = True
            checkpoint.next_run_at = now
            checkpoint.last_error_code = None
            checkpoint.retry_count = 0
    db.commit()


def _apply_prepared_activation_gate(db: Session, *, now: datetime) -> int:
    current = _utc(now)
    store_ids = sorted(set(db.scalars(select(SyncLog.store_id).where(
        SyncLog.platform == NAVER,
        SyncLog.sync_type == naver_readonly_inquiry_service.DUAL_STORE_PREPARATION_SYNC_TYPE,
    )).all()))
    blocked_count = 0
    sync_types = [RESOURCE_CONFIG[resource]["sync_type"] for resource in PREPARED_ACTIVATION_RESOURCE_ORDER]
    for store_id in store_ids:
        rows = db.scalars(select(SyncCheckpoint).where(
            SyncCheckpoint.store_id == store_id,
            SyncCheckpoint.platform == NAVER,
            SyncCheckpoint.sync_type.in_(sync_types),
        )).all()
        if any(row.last_attempt_at is not None for row in rows):
            continue
        failure_code = None
        try:
            marker = naver_readonly_inquiry_service._prepared_marker_summary(
                db,
                store_id=store_id,
                lock=False,
            )
            if marker is None:
                continue
            activation_at = _utc(datetime.fromisoformat(
                str(marker["activation_at"]).replace("Z", "+00:00")
            ))
            offset_seconds = int(marker["first_run_offset_seconds"])
        except ApiError:
            activation_at = None
            offset_seconds = 0
            failure_code = "automatic_read_preparation_evidence_invalid"
        if len(rows) != len(PREPARED_ACTIVATION_RESOURCE_ORDER):
            failure_code = "automatic_read_preparation_checkpoint_incomplete"
        elif activation_at is not None:
            by_resource = {_resource_for_checkpoint(row): row for row in rows}
            for index, resource in enumerate(PREPARED_ACTIVATION_RESOURCE_ORDER):
                row = by_resource.get(resource)
                expected = activation_at + timedelta(seconds=offset_seconds) + timedelta(minutes=index)
                if row is None or row.next_run_at is None or _utc(row.next_run_at) != expected:
                    failure_code = "automatic_read_activation_schedule_changed"
                    break
            first_run_at = activation_at + timedelta(seconds=offset_seconds)
            if failure_code is None and current > first_run_at + PREPARED_ACTIVATION_START_GRACE:
                failure_code = "automatic_read_activation_window_missed"
        if failure_code is None:
            continue
        for row in rows:
            row.status = "blocked"
            row.automatic_read_enabled = False
            row.next_run_at = None
            row.last_error_code = failure_code
            row.lease_token = None
            row.lease_expires_at = None
            blocked_count += 1
    db.commit()
    return blocked_count


def ensure_automatic_read_schedule(
    db: Session,
    *,
    store_id: int,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> None:
    current = _utc(now or get_utc_now())
    for resource in RESOURCE_CONFIG:
        _checkpoint(db, store_id=store_id, resource=resource, now=current)
    db.commit()
    _apply_inquiry_real_read_gate(db, settings=settings or get_settings(), now=current)


def ensure_onboarded_store_schedules(
    db: Session,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> int:
    current = _utc(now or get_utc_now())
    store_ids = _eligible_store_ids(db)
    for store_id in store_ids:
        for resource in RESOURCE_CONFIG:
            _checkpoint(db, store_id=store_id, resource=resource, now=current)
    db.commit()
    _apply_inquiry_real_read_gate(db, settings=settings or get_settings(), now=current)
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
    credentials = db.scalars(select(ApiCredential).where(
        ApiCredential.store_id == store_id,
        ApiCredential.platform == NAVER,
        ApiCredential.status == "active",
    ).order_by(ApiCredential.id.asc()).with_for_update()).all()
    if len(credentials) != 1:
        raise store_onboarding_service.NaverReadFailure("credential_ambiguous")
    credential = credentials[0]
    if credential.auth_status != "test_passed" or not credential.client_id:
        raise store_onboarding_service.NaverReadFailure("credential_unavailable")
    prepared_credential_id = naver_readonly_inquiry_service._prepared_credential_id(
        db,
        store_id=store_id,
    )
    if prepared_credential_id is not None and prepared_credential_id != credential.id:
        raise store_onboarding_service.NaverReadFailure("credential_changed_since_activation")
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


def _bounded_retry_after_seconds(exc: Exception) -> int | None:
    detail = exc.detail if isinstance(exc, ApiError) and isinstance(exc.detail, dict) else {}
    value = detail.get("retry_after_seconds")
    if type(value) is not int or value < 0:
        return None
    return min(value, MAX_RETRY_DELAY_SECONDS)


def _resource_for_checkpoint(checkpoint: SyncCheckpoint) -> str:
    for resource, config in RESOURCE_CONFIG.items():
        if checkpoint.sync_type == config["sync_type"]:
            return resource
    raise ValueError("unsupported automatic checkpoint")


def _renew_page_lease(
    db: Session,
    *,
    checkpoint_id: int,
    token: str,
    resource: str,
    now: datetime,
) -> None:
    renewed = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == checkpoint_id,
        SyncCheckpoint.automatic_read_enabled.is_(True),
        SyncCheckpoint.status == "running",
        SyncCheckpoint.lease_token == token,
        SyncCheckpoint.lease_expires_at.is_not(None),
        SyncCheckpoint.lease_expires_at > now,
    ).values(
        lease_expires_at=now + RESOURCE_CONFIG[resource]["lease"],
    ).execution_options(synchronize_session=False)).rowcount
    db.commit()
    if renewed != 1:
        raise store_onboarding_service.NaverReadFailure("automatic_read_lease_lost")


def _fence_page_commit(
    db: Session,
    *,
    checkpoint_id: int,
    token: str,
    resource: str,
    credential_id: int,
    now: datetime,
) -> None:
    fenced = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == checkpoint_id,
        SyncCheckpoint.automatic_read_enabled.is_(True),
        SyncCheckpoint.status == "running",
        SyncCheckpoint.lease_token == token,
        SyncCheckpoint.lease_expires_at.is_not(None),
        SyncCheckpoint.lease_expires_at > now,
    ).values(
        lease_expires_at=now + RESOURCE_CONFIG[resource]["lease"],
    ).execution_options(synchronize_session=False)).rowcount
    if fenced != 1:
        raise store_onboarding_service.NaverReadFailure("automatic_read_commit_fence_lost")
    checkpoint = db.get(SyncCheckpoint, checkpoint_id)
    if checkpoint is None:
        raise store_onboarding_service.NaverReadFailure("automatic_read_commit_fence_lost")
    current_context = _context(db, checkpoint.store_id)
    if current_context.credential_id != credential_id:
        raise store_onboarding_service.NaverReadFailure("credential_changed_during_automatic_read")
    db.commit()


def _sync_t13_resource(
    db: Session, *, checkpoint: SyncCheckpoint, resource: str,
    reader: store_onboarding_service.NaverReadAdapter, now: datetime,
    token: str, clock: Callable[[], datetime],
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
        page_now = _utc(clock())
        _renew_page_lease(
            db,
            checkpoint_id=checkpoint.id,
            token=token,
            resource=resource,
            now=page_now,
        )
        page = reader.read_orders(context, start_at=start_at, end_at=end_at, cursor=cursor) if resource == "orders" else reader.read_products(context, start_at=start_at, end_at=end_at, cursor=cursor)
        if not isinstance(page, store_onboarding_service.NaverReadPage):
            raise store_onboarding_service.NaverReadFailure("invalid_read_adapter_page")
        items = store_onboarding_service._canonical_orders(page.items, "automatic_incremental") if resource == "orders" else store_onboarding_service._canonical_products(page.items, "automatic_incremental")
        outcome = order_service.upsert_orders(db, checkpoint.store_id, NAVER, items, commit=False) if resource == "orders" else product_service.upsert_products(db, checkpoint.store_id, NAVER, items, commit=False)
        created += outcome["created"]
        updated += outcome["updated"]
        pages += 1
        cursor = page.next_cursor
        checkpoint.cursor_value = cursor
        _fence_page_commit(
            db,
            checkpoint_id=checkpoint.id,
            token=token,
            resource=resource,
            credential_id=context.credential_id,
            now=_utc(clock()),
        )
        if not cursor:
            break
    return {"created": created, "updated": updated, "pages": pages}


def _sync_t17_logistics(
    db: Session, *, checkpoint: SyncCheckpoint,
    reader: store_onboarding_service.NaverReadAdapter, now: datetime,
    token: str, clock: Callable[[], datetime],
) -> dict[str, int]:
    """Read existing order-detail snapshots and persist only local logistics data."""
    from app.services import pxg_naver_readonly_persistence_service

    context = _context(db, checkpoint.store_id)
    cursor = _decode_logistics_cursor(checkpoint.cursor_value)
    last_order_id = cursor["last_order_id"]
    checkpoint.window_start_at, checkpoint.window_end_at = _utc(now - timedelta(days=30)), now
    pages = saved = not_available = skipped = 0
    while True:
        if pages >= MAX_PAGES_PER_RUN:
            raise store_onboarding_service.NaverReadFailure("read_page_limit_reached", retryable=True)
        _renew_page_lease(
            db,
            checkpoint_id=checkpoint.id,
            token=token,
            resource="logistics",
            now=_utc(clock()),
        )
        batch = _t17_logistics_candidates(
            db, store_id=checkpoint.store_id, now=now, after_order_id=last_order_id,
        )[:store_onboarding_service.ORDER_DETAIL_BATCH_SIZE]
        if not batch:
            checkpoint.cursor_value = None
            break
        product_order_ids = [str(order.external_product_order_id) for order in batch]
        details = reader.read_logistics(context, product_order_ids=product_order_ids)
        if not isinstance(details, list):
            raise store_onboarding_service.NaverReadFailure("invalid_logistics_detail_page")
        received_ids = {str(item.get("external_product_order_id") or "").strip() for item in details if isinstance(item, dict)}
        if received_ids != set(product_order_ids):
            raise ApiError("Naver logistics detail response is incomplete", "naver_logistics_detail_response_incomplete", 409)
        outcome = pxg_naver_readonly_persistence_service.persist_naver_order_detail_logistics_page(
            db, store_id=checkpoint.store_id, details=details, now=now, scope="automatic",
        )
        saved += outcome["saved"]
        not_available += outcome["not_available"]
        skipped += outcome["skipped"]
        pages += 1
        last_order_id = batch[-1].id
        checkpoint.cursor_value = _encode_logistics_cursor(last_order_id)
        _fence_page_commit(
            db,
            checkpoint_id=checkpoint.id,
            token=token,
            resource="logistics",
            credential_id=context.credential_id,
            now=_utc(clock()),
        )
    return {"created": saved, "updated": 0, "pages": pages, "not_available": not_available, "skipped": skipped}


def _encode_logistics_cursor(last_order_id: int) -> str:
    return f"logistics-local-id:{last_order_id}"


def _decode_logistics_cursor(value: str | None) -> dict[str, int]:
    if not value:
        return {"last_order_id": 0}
    prefix, separator, order_id = value.partition(":")
    if prefix != "logistics-local-id" or not separator or not order_id.isdigit():
        raise store_onboarding_service.NaverReadFailure("logistics_checkpoint_cursor_invalid")
    return {"last_order_id": int(order_id)}


def _t17_logistics_candidates(db: Session, *, store_id: int, now: datetime, after_order_id: int = 0) -> list[Order]:
    cutoff = _utc(now) - timedelta(days=30)
    conditions = (
        Order.store_id == store_id,
        Order.platform == NAVER,
        Order.ordered_at >= cutoff,
        Order.source_type.notin_(order_service.TEST_ORDER_SOURCE_TYPES),
        Order.source_type != order_service.HISTORICAL_BACKFILL_SOURCE_TYPE,
        Order.external_product_order_id.is_not(None),
        Order.external_product_order_id != "",
    )
    all_rows = db.scalars(select(Order).where(*conditions)).all()
    by_product_order_id: dict[str, list[Order]] = {}
    for row in all_rows:
        key = str(row.external_product_order_id or "").strip()
        if key:
            by_product_order_id.setdefault(key, []).append(row)
    candidates: list[Order] = []
    stop_statuses = pxg_naver_readonly_persistence_service.NAVER_LOGISTICS_STOP_STATUSES
    terminal_statuses = pxg_naver_readonly_persistence_service.NAVER_DELIVERY_TERMINAL_STATUSES
    rows = db.scalars(select(Order).where(*conditions, Order.id > after_order_id).order_by(Order.id.asc())).all()
    for order in rows:
        product_rows = by_product_order_id[str(order.external_product_order_id).strip()]
        if len(product_rows) != 1:
            raise ApiError("Naver logistics product-order ID is duplicated", "naver_logistics_duplicate_product_order_id", 409)
        if str(order.order_status or "").upper() in stop_statuses:
            continue
        record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
            PxgNaverReadonlyLogisticsRecord.order_id == order.id,
            PxgNaverReadonlyLogisticsRecord.store_id == store_id,
            PxgNaverReadonlyLogisticsRecord.platform == NAVER,
        ))
        if record is not None and str(record.shipment_status or "").upper() in terminal_statuses:
            continue
        if order.id > after_order_id:
            candidates.append(order)
    return candidates


def _finish_success(db: Session, *, checkpoint: SyncCheckpoint, token: str, now: datetime, result: dict[str, int]) -> bool:
    resource = _resource_for_checkpoint(checkpoint)
    interval = RESOURCE_CONFIG[resource]["interval"]
    _context(db, checkpoint.store_id)
    finished = db.execute(update(SyncCheckpoint).where(
        SyncCheckpoint.id == checkpoint.id,
        SyncCheckpoint.automatic_read_enabled.is_(True),
        SyncCheckpoint.status == "running",
        SyncCheckpoint.lease_token == token,
    ).values(
        status="success",
        last_synced_at=now,
        fresh_until=now + RESOURCE_CONFIG[resource]["freshness"],
        next_run_at=now + interval + _stagger(checkpoint.store_id, resource, interval),
        retry_count=0,
        last_error_code=None,
        lease_token=None,
        lease_expires_at=None,
    ).execution_options(synchronize_session=False)).rowcount
    if finished != 1:
        db.rollback()
        return False
    db.add(SyncLog(store_id=checkpoint.store_id, platform=NAVER, sync_type=checkpoint.sync_type, status="success", finished_at=now,
                   message="automatic readonly sync completed", raw_summary={**result, "raw_response_saved": False, "platform_write": False}))
    db.commit()
    return True


def _finish_failure(db: Session, *, checkpoint: SyncCheckpoint, token: str, now: datetime, exc: Exception) -> bool:
    if checkpoint.lease_token != token:
        return False
    checkpoint.last_error_code = _safe_error_code(exc)
    if bool(getattr(exc, "retryable", False)) or _retryable_error(checkpoint.last_error_code):
        checkpoint.retry_count += 1
        checkpoint.status = "retry_wait"
        exponential_seconds = min(
            MAX_RETRY_DELAY_SECONDS,
            60 * (2 ** min(checkpoint.retry_count - 1, 6)),
        )
        retry_after_seconds = _bounded_retry_after_seconds(exc) or 0
        checkpoint.next_run_at = now + timedelta(
            seconds=max(exponential_seconds, retry_after_seconds),
        )
    else:
        checkpoint.status = "blocked"
        checkpoint.automatic_read_enabled = False
        checkpoint.next_run_at = None
    checkpoint.lease_token = None
    checkpoint.lease_expires_at = None
    safe_summary = {
        "error_code": checkpoint.last_error_code,
        "raw_response_saved": False,
        "platform_write": False,
    }
    retry_after_seconds = _bounded_retry_after_seconds(exc)
    if retry_after_seconds is not None:
        safe_summary["retry_after_seconds"] = retry_after_seconds
    db.add(SyncLog(store_id=checkpoint.store_id, platform=NAVER, sync_type=checkpoint.sync_type, status="failed", finished_at=now,
                   message="automatic readonly sync failed", error_detail=checkpoint.last_error_code,
                   raw_summary=safe_summary))
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
    return code.strip().lower() in RECOVERABLE_ERROR_CODES


def _attention_fields(*, resource: str, status: str, enabled: bool, stale: bool, last_error_code: str | None, store_id: int) -> dict[str, Any]:
    if status == "blocked":
        eligible = _recovery_eligible_error(last_error_code)
        return {
            "attention_state": "admin_action",
            "operator_message": "自动读取已暂停，请管理员检查店铺连接。" if eligible else "自动读取已暂停，需要管理员处理。",
            "admin_action": "verify_and_recover" if eligible else "manual_review",
            "recovery_eligible": eligible,
            "action_path": f"/stores?storeId={store_id}&focus=connection",
        }
    if status == "retry_wait" or (enabled and stale):
        return {"attention_state": "automatic_retry", "operator_message": "数据更新暂时延迟，系统会自动重试，无需操作。", "admin_action": None, "recovery_eligible": False, "action_path": None}
    return {"attention_state": "none", "operator_message": "", "admin_action": None, "recovery_eligible": False, "action_path": None}


def _write_recovery_audit(
    db: Session, *, store_id: int, actor_id: str, now: datetime, settings: Settings,
    status: str, reason_code: str, restored_count: int = 0,
) -> bool:
    audit = write_operation_audit_log_local(
        db,
        {
            "created_at": now, "updated_at": now, "store_id": store_id, "platform": NAVER,
            "environment": settings.app_env, "actor_type": "human", "actor_id": actor_id,
            "action": "automatic_read_recovery", "operation_phase": "T16",
            "correlation_id": f"t16_recovery_{store_id}_{int(now.timestamp())}", "status": status,
            "reason_code": reason_code, "target_type": "sync_gate", "target_id": store_id,
            "changed_field_names": ["automatic_read_enabled", "last_error_code", "next_run_at", "retry_count", "status"] if restored_count else [],
            "counts_summary": {"restored_checkpoint_count": restored_count},
            "safety_flags": {"platform_write": False, "raw_response_saved": False, "smoke_persisted": False},
            "sensitive_scan_passed": True, "raw_response_saved": False, "secrets_saved": False,
            "privacy_fields_redacted": True,
        },
        write_enabled=True, manual_approval=True, local_write_scope=LOCAL_WRITER_SCOPE,
    )
    return bool(audit.get("audit_rows_written"))


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
        _write_recovery_audit(db, store_id=store_id, actor_id=actor_id, now=current, settings=settings, status="blocked", reason_code="no_eligible_checkpoint")
        raise ValueError("automatic_read_no_eligible_checkpoint")
    smoke = api_credential_readiness_service.run_api_credential_smoke_test(
        db=db, platform=NAVER, mode="readonly", store_id=store_id, capability_scope="seller_channels",
        persist_channel_no=False, persist_capability_results=False,
    )
    smoke_result = (smoke.get("results") or [{}])[0]
    if smoke_result.get("error_code") or smoke_result.get("seller_or_account_test") != "success":
        _write_recovery_audit(db, store_id=store_id, actor_id=actor_id, now=current, settings=settings, status="failed", reason_code="verification_failed")
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
    if not _write_recovery_audit(
        db, store_id=store_id, actor_id=actor_id, now=current, settings=settings,
        status="success", reason_code="credential_verification_passed", restored_count=len(restored_resources),
    ):
        db.rollback()
        raise RuntimeError("automatic_read_recovery_audit_failed")
    return {"status": "recovered", "store_id": store_id,
            "restored_resources": sorted(restored_resources), "restored_checkpoint_count": len(restored_resources),
            "verification_status": "passed", "automatic_read_status": automatic_read_status(db, store_id=store_id, now=current),
            "safety_flags": {"platform_write": False, "sync_started": False, "smoke_persisted": False}}


def run_automatic_checkpoint(
    db: Session, *, checkpoint_id: int, now: datetime | None = None,
    reader: store_onboarding_service.NaverReadAdapter | None = None,
    inquiry_runner: Callable[..., dict[str, Any]] | None = None,
) -> str:
    fixed_now = _utc(now) if now is not None else None
    current = fixed_now or _utc(get_utc_now())
    _apply_prepared_activation_gate(db, now=current)
    pending_checkpoint = db.get(SyncCheckpoint, checkpoint_id)
    if (
        pending_checkpoint is not None
        and pending_checkpoint.sync_type == RESOURCE_CONFIG["customer_inquiries"]["sync_type"]
        and _inquiry_gate_error(get_settings(), pending_checkpoint.store_id) is not None
    ):
        _apply_inquiry_real_read_gate(db, settings=get_settings(), now=current)
        return "not_due"
    token = _claim(db, checkpoint_id=checkpoint_id, now=current)
    if token is None:
        return "not_due"
    checkpoint = db.get(SyncCheckpoint, checkpoint_id)
    assert checkpoint is not None
    resource = _resource_for_checkpoint(checkpoint)
    clock = (lambda: current) if fixed_now is not None else get_utc_now
    try:
        if resource == "customer_inquiries":
            result = (inquiry_runner or naver_readonly_inquiry_service.refresh_naver_readonly_inquiries)(
                db, store_id=checkpoint.store_id, actor_id="automatic-read", settings=get_settings(),
            )
            summary = {"created": int(result.get("created_count", 0)), "updated": int(result.get("updated_count", 0)), "pages": int(result.get("pages_read", 0))}
        elif resource == "logistics":
            summary = _sync_t17_logistics(
                db,
                checkpoint=checkpoint,
                reader=reader or store_onboarding_service.get_naver_read_adapter(),
                now=current,
                token=token,
                clock=clock,
            )
        else:
            summary = _sync_t13_resource(
                db,
                checkpoint=checkpoint,
                resource=resource,
                reader=reader or store_onboarding_service.get_naver_read_adapter(),
                now=current,
                token=token,
                clock=clock,
            )
        return "success" if _finish_success(db, checkpoint=checkpoint, token=token, now=current, result=summary) else "not_due"
    except Exception as exc:
        db.rollback()
        checkpoint = db.get(SyncCheckpoint, checkpoint_id)
        assert checkpoint is not None
        failure_time = fixed_now or _utc(get_utc_now())
        return "failed" if _finish_failure(db, checkpoint=checkpoint, token=token, now=failure_time, exc=exc) else "not_due"


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
        ensure_onboarded_store_schedules(db, now=current, settings=settings)
        _apply_prepared_activation_gate(db, now=current)
        due_ids = db.scalars(select(SyncCheckpoint.id).where(
            SyncCheckpoint.platform == NAVER, SyncCheckpoint.automatic_read_enabled.is_(True),
            SyncCheckpoint.status != "blocked", or_(SyncCheckpoint.next_run_at.is_(None), SyncCheckpoint.next_run_at <= current),
        )).all()
    counts = {"scheduled": len(due_ids), "success": 0, "failed": 0}
    for checkpoint_id in due_ids:
        with session_factory() as db:
            result = run_automatic_checkpoint(
                db,
                checkpoint_id=checkpoint_id,
                now=current if now is not None else None,
                reader=reader,
                inquiry_runner=inquiry_runner,
            )
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
        if row is None:
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
