from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.api_credential import ApiCredential
from app.models.auth import ErpRole, ErpStoreMembership
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate, StoreOnboardingRead
from app.services import api_credential_readiness_service, order_service, product_service
from app.services.encryption import decrypt_value, encrypt_value


NAVER_PLATFORM = "naver"
INITIAL_SYNC_DAYS = 30
HISTORY_MAX_DAYS = 31
MAX_READ_PAGES = 100
ONBOARDING_PRODUCT_SYNC = "naver_onboarding_products"
ONBOARDING_ORDER_SYNC = "naver_onboarding_orders"
HISTORICAL_ORDER_SYNC = "naver_historical_orders"


@dataclass(frozen=True)
class NaverReadContext:
    store_id: int
    credential_id: int
    client_id: str
    client_secret: str
    channel_no: str | None


@dataclass(frozen=True)
class NaverValidation:
    token_authenticated: bool
    seller_identity_verified: bool
    channel_verified: bool
    ip_ready: bool
    permission_ready: bool
    selected_channel_no: str | None

    @property
    def ready(self) -> bool:
        return all((self.token_authenticated, self.seller_identity_verified, self.channel_verified, self.ip_ready, self.permission_ready))

    def sanitized(self) -> dict:
        return {
            "platform": NAVER_PLATFORM,
            "token_authenticated": self.token_authenticated,
            "seller_identity_verified": self.seller_identity_verified,
            "channel_verified": self.channel_verified,
            "ip_ready": self.ip_ready,
            "permission_ready": self.permission_ready,
            "channel_configured": bool(self.selected_channel_no),
        }


@dataclass(frozen=True)
class NaverReadPage:
    items: list[dict]
    next_cursor: str | None = None


class NaverReadFailure(Exception):
    def __init__(self, code: str, *, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class NaverReadAdapter(Protocol):
    def validate(self, *, client_id: str, client_secret: str, channel_no: str | None) -> NaverValidation: ...
    def read_products(self, context: NaverReadContext, *, start_at: datetime, end_at: datetime, cursor: str | None) -> NaverReadPage: ...
    def read_orders(self, context: NaverReadContext, *, start_at: datetime, end_at: datetime, cursor: str | None) -> NaverReadPage: ...


class DefaultNaverReadAdapter:
    """Uses only approved token and seller/channel read calls; dataset adapters remain closed."""

    def validate(self, *, client_id: str, client_secret: str, channel_no: str | None) -> NaverValidation:
        context = {
            "client_id": client_id,
            "secret_key": client_secret,
            "api_base": api_credential_readiness_service.NAVER_DEFAULT_API_BASE,
            "grant_type_used": "SELF",
            "seller_account_id": None,
        }
        try:
            token, _ = api_credential_readiness_service._request_naver_token_from_context(context)
            headers = {"Authorization": f"Bearer {token}"}
            base = context["api_base"]
            with httpx.Client(timeout=10.0) as client:
                account_response = client.get(f"{base}/v1/seller/account", headers=headers)
                if account_response.status_code >= 400:
                    raise _read_failure_from_response(account_response, scope="seller")
                channel_response = client.get(f"{base}/v1/seller/channels", headers=headers)
                if channel_response.status_code >= 400:
                    raise _read_failure_from_response(channel_response, scope="channel")
            channels = api_credential_readiness_service._extract_channel_no_values(channel_response.json())
            selected_channel = channel_no.strip() if channel_no else (channels[0] if len(channels) == 1 else None)
            if selected_channel and selected_channel not in channels:
                raise NaverReadFailure("channel_identity_mismatch")
            if not selected_channel:
                raise NaverReadFailure("channel_identity_unresolved")
            return NaverValidation(True, True, True, True, True, selected_channel)
        except api_credential_readiness_service.NaverReadonlyAuthError as exc:
            raise NaverReadFailure(exc.error_code) from exc
        except httpx.TimeoutException as exc:
            raise NaverReadFailure("network_timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise NaverReadFailure("network_error", retryable=True) from exc

    def read_products(self, context: NaverReadContext, *, start_at: datetime, end_at: datetime, cursor: str | None) -> NaverReadPage:
        raise NaverReadFailure("product_read_adapter_not_approved")

    def read_orders(self, context: NaverReadContext, *, start_at: datetime, end_at: datetime, cursor: str | None) -> NaverReadPage:
        raise NaverReadFailure("order_read_adapter_not_approved")


def _read_failure_from_response(response: httpx.Response, *, scope: str) -> NaverReadFailure:
    if response.status_code == 429 or response.status_code >= 500:
        return NaverReadFailure("naver_read_retryable", retryable=True)
    if response.status_code == 403:
        code, flags = api_credential_readiness_service._classify_naver_forbidden_response(response, stage=scope, scope=scope)
        if flags.get("ip_keyword"):
            code = "ip_not_allowed"
        return NaverReadFailure(code)
    return NaverReadFailure("auth_failed" if response.status_code == 401 else "naver_read_failed")


def get_naver_read_adapter() -> NaverReadAdapter:
    return DefaultNaverReadAdapter()


def serialize_onboarding(onboarding: StoreOnboarding) -> dict:
    return StoreOnboardingRead.model_validate(onboarding, from_attributes=True).model_dump(mode="json")


def submit_onboarding(
    db: Session,
    *,
    payload: StoreOnboardingCreate,
    creator_user_id: int,
    reader: NaverReadAdapter | None = None,
    now: datetime | None = None,
) -> dict:
    existing = db.scalar(select(StoreOnboarding).where(StoreOnboarding.idempotency_key == payload.idempotency_key))
    if existing is not None:
        if existing.creator_user_id != creator_user_id:
            raise ApiError("idempotency key is owned by another operator", "onboarding_idempotency_conflict", 409)
        return serialize_onboarding(existing)
    onboarding = StoreOnboarding(
        idempotency_key=payload.idempotency_key,
        requested_store_name=payload.store_name,
        creator_user_id=creator_user_id,
        encrypted_client_id=encrypt_value(payload.client_id),
        encrypted_client_secret=encrypt_value(payload.client_secret),
        requested_channel_no=payload.channel_no,
        status="validating",
        progress_summary=_empty_progress(),
    )
    db.add(onboarding)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError("onboarding idempotency conflict", "onboarding_idempotency_conflict", 409) from exc
    return resume_onboarding(db, onboarding_id=onboarding.id, reader=reader, now=now)


def resume_onboarding(
    db: Session,
    *,
    onboarding_id: int,
    reader: NaverReadAdapter | None = None,
    now: datetime | None = None,
) -> dict:
    onboarding = _get_onboarding(db, onboarding_id)
    if onboarding.status in {"active_incremental", "partially_synced", "cancelled"}:
        return serialize_onboarding(onboarding)
    reader = reader or get_naver_read_adapter()
    now = now or get_utc_now()

    if onboarding.store_id is None:
        client_id = decrypt_value(onboarding.encrypted_client_id)
        client_secret = decrypt_value(onboarding.encrypted_client_secret)
        if not client_id or not client_secret:
            _set_failure(db, onboarding, "credential_retry_material_missing", retryable=False, now=now)
            return serialize_onboarding(onboarding)
        onboarding.status = "validating"
        db.commit()
        try:
            validation = reader.validate(client_id=client_id, client_secret=client_secret, channel_no=onboarding.requested_channel_no)
        except NaverReadFailure as exc:
            _set_failure(db, onboarding, exc.code, retryable=exc.retryable, now=now)
            return serialize_onboarding(onboarding)
        if not validation.ready:
            _set_failure(db, onboarding, "naver_validation_not_ready", retryable=False, now=now)
            return serialize_onboarding(onboarding)
        onboarding.validation_summary = validation.sanitized()
        provisioned = _provision_validated_store(
            db,
            onboarding=onboarding,
            client_id=client_id,
            client_secret=client_secret,
            selected_channel_no=validation.selected_channel_no,
            now=now,
        )
        if not provisioned:
            return serialize_onboarding(_get_onboarding(db, onboarding.id))

    return _run_initial_backfill(db, onboarding=onboarding, reader=reader, now=now)


def run_historical_order_backfill(
    db: Session,
    *,
    onboarding_id: int,
    payload: HistoricalBackfillCreate,
    reader: NaverReadAdapter | None = None,
) -> dict:
    onboarding = _get_onboarding(db, onboarding_id)
    if onboarding.store_id is None or onboarding.credential_id is None:
        raise ApiError("onboarding has not provisioned a store", "onboarding_not_provisioned", 409)
    if onboarding.status == "cancelled":
        raise ApiError("onboarding is cancelled", "onboarding_cancelled", 409)
    start_at, end_at = _normalize_window(payload.start_at, payload.end_at, max_days=HISTORY_MAX_DAYS)
    reader = reader or get_naver_read_adapter()
    result = _sync_dataset(
        db,
        onboarding=onboarding,
        reader=reader,
        dataset="orders",
        sync_type=HISTORICAL_ORDER_SYNC,
        start_at=start_at,
        end_at=end_at,
        scope="historical",
    )
    progress = dict(onboarding.progress_summary or _empty_progress())
    progress["historical_orders"] = result
    onboarding.progress_summary = progress
    db.commit()
    return {
        "onboarding": serialize_onboarding(onboarding),
        "backfill": result,
        "platform_write": False,
        "local_only": True,
        "unsynced_history_retrieved": False,
    }


def _run_initial_backfill(db: Session, *, onboarding: StoreOnboarding, reader: NaverReadAdapter, now: datetime) -> dict:
    if onboarding.snapshot_end_at is None or onboarding.initial_window_start_at is None:
        onboarding.snapshot_end_at = now
        onboarding.initial_window_start_at = now - timedelta(days=INITIAL_SYNC_DAYS)
    onboarding.status = "backfilling"
    db.commit()
    results: dict[str, dict] = {}
    for dataset, sync_type in (("products", ONBOARDING_PRODUCT_SYNC), ("orders", ONBOARDING_ORDER_SYNC)):
        results[dataset] = _sync_dataset(
            db,
            onboarding=onboarding,
            reader=reader,
            dataset=dataset,
            sync_type=sync_type,
            start_at=onboarding.initial_window_start_at,
            end_at=onboarding.snapshot_end_at,
            scope="initial_30_day",
        )
        if results[dataset]["status"] != "success":
            _set_failure(
                db,
                onboarding,
                results[dataset]["error_code"] or "mandatory_dataset_sync_failed",
                retryable=bool(results[dataset].get("retryable")),
                now=now,
                progress={**_empty_progress(), **results, "customer_inquiries": _optional_not_approved(), "logistics": _optional_not_approved()},
            )
            return serialize_onboarding(onboarding)

    # Inquiry and logistics adapters are intentionally not called until their
    # contracts are approved, so the durable state must not claim full activation.
    onboarding.status = "partially_synced"
    onboarding.last_error_code = None
    onboarding.next_retry_at = None
    onboarding.progress_summary = {
        **_empty_progress(),
        **results,
        "customer_inquiries": _optional_not_approved(),
        "logistics": _optional_not_approved(),
    }
    db.commit()
    return serialize_onboarding(onboarding)


def _sync_dataset(
    db: Session,
    *,
    onboarding: StoreOnboarding,
    reader: NaverReadAdapter,
    dataset: str,
    sync_type: str,
    start_at: datetime,
    end_at: datetime,
    scope: str,
) -> dict:
    assert onboarding.store_id is not None and onboarding.credential_id is not None
    context = _read_context(db, onboarding)
    checkpoint = _checkpoint(db, store_id=onboarding.store_id, sync_type=sync_type)
    checkpoint.window_start_at = start_at
    checkpoint.window_end_at = end_at
    cursor = checkpoint.cursor_value
    sync_log = SyncLog(
        store_id=onboarding.store_id,
        platform=NAVER_PLATFORM,
        sync_type=sync_type,
        status="running",
        message=f"{scope} {dataset} local sync",
        raw_summary={"scope": scope, "dataset": dataset, "raw_response_saved": False, "platform_write": False},
    )
    db.add(sync_log)
    db.commit()
    created = updated = pages = 0
    try:
        while True:
            if pages >= MAX_READ_PAGES:
                raise NaverReadFailure("read_page_limit_reached", retryable=True)
            page = (
                reader.read_products(context, start_at=start_at, end_at=end_at, cursor=cursor)
                if dataset == "products"
                else reader.read_orders(context, start_at=start_at, end_at=end_at, cursor=cursor)
            )
            if not isinstance(page, NaverReadPage):
                raise NaverReadFailure("invalid_read_adapter_page")
            items = _canonical_products(page.items, scope) if dataset == "products" else _canonical_orders(page.items, scope)
            outcome = product_service.upsert_products(db, onboarding.store_id, NAVER_PLATFORM, items) if dataset == "products" else order_service.upsert_orders(db, onboarding.store_id, NAVER_PLATFORM, items)
            created += outcome["created"]
            updated += outcome["updated"]
            pages += 1
            cursor = page.next_cursor
            checkpoint.cursor_value = cursor
            checkpoint.last_synced_at = get_utc_now()
            db.commit()
            if not cursor:
                break
        sync_log.status = "success"
        sync_log.finished_at = get_utc_now()
        sync_log.raw_summary = {"scope": scope, "dataset": dataset, "created": created, "updated": updated, "pages": pages, "raw_response_saved": False, "platform_write": False}
        db.commit()
        return {"status": "success", "created": created, "updated": updated, "pages": pages, "window_start_at": start_at.isoformat(), "window_end_at": end_at.isoformat(), "error_code": None, "retryable": False}
    except NaverReadFailure as exc:
        sync_log.status = "failed"
        sync_log.finished_at = get_utc_now()
        sync_log.message = "sanitized Naver read failure"
        sync_log.error_detail = exc.code
        sync_log.raw_summary = {"scope": scope, "dataset": dataset, "raw_response_saved": False, "platform_write": False, "error_code": exc.code}
        db.commit()
        return {"status": "failed", "created": created, "updated": updated, "pages": pages, "window_start_at": start_at.isoformat(), "window_end_at": end_at.isoformat(), "error_code": exc.code, "retryable": exc.retryable}


def _provision_validated_store(db: Session, *, onboarding: StoreOnboarding, client_id: str, client_secret: str, selected_channel_no: str | None, now: datetime) -> bool:
    owner_role = db.scalar(select(ErpRole).where(ErpRole.role_key == "owner", ErpRole.status == "active"))
    if owner_role is None:
        _set_failure(db, onboarding, "creator_role_unavailable", retryable=False, now=now)
        return False
    onboarding.status = "provisioning"
    store = Store(name=onboarding.requested_store_name, platform=NAVER_PLATFORM)
    credential = ApiCredential(
        store=store,
        platform=NAVER_PLATFORM,
        credential_name=f"Naver onboarding {onboarding.requested_store_name}",
        encrypted_access_key=encrypt_value(client_id),
        encrypted_secret_key=encrypt_value(client_secret),
        auth_status="test_passed",
        status="active",
        extra_config={"api_base": api_credential_readiness_service.NAVER_DEFAULT_API_BASE, "channel_no": selected_channel_no, "onboarded": True, "encrypted_client_id": True},
    )
    membership = ErpStoreMembership(user_id=onboarding.creator_user_id, store=store, role=owner_role, scope_type="assigned", membership_status="active", assigned_by_user_id=onboarding.creator_user_id)
    db.add_all((store, credential, membership))
    try:
        db.flush()
        onboarding.store_id = store.id
        onboarding.credential_id = credential.id
        onboarding.encrypted_client_id = None
        onboarding.encrypted_client_secret = None
        onboarding.status = "backfilling"
        onboarding.snapshot_end_at = now
        onboarding.initial_window_start_at = now - timedelta(days=INITIAL_SYNC_DAYS)
        db.commit()
        return True
    except IntegrityError as exc:
        db.rollback()
        onboarding = _get_onboarding(db, onboarding.id)
        _set_failure(db, onboarding, "store_provisioning_conflict", retryable=False, now=now)
        return False


def _read_context(db: Session, onboarding: StoreOnboarding) -> NaverReadContext:
    credential = db.get(ApiCredential, onboarding.credential_id)
    if credential is None:
        raise ApiError("onboarding credential is unavailable", "onboarding_credential_missing", 409)
    extra = credential.extra_config if isinstance(credential.extra_config, dict) else {}
    client_id = decrypt_value(credential.encrypted_access_key) if extra.get("encrypted_client_id") else credential.client_id
    if not client_id:
        raise ApiError("onboarding credential is unavailable", "onboarding_credential_missing", 409)
    secret = decrypt_value(credential.encrypted_secret_key)
    if not secret:
        raise ApiError("onboarding credential cannot be decrypted", "onboarding_credential_decrypt_failed", 409)
    return NaverReadContext(onboarding.store_id or 0, credential.id, client_id, secret, extra.get("channel_no"))


def _checkpoint(db: Session, *, store_id: int, sync_type: str) -> SyncCheckpoint:
    checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.store_id == store_id, SyncCheckpoint.platform == NAVER_PLATFORM, SyncCheckpoint.sync_type == sync_type))
    if checkpoint is None:
        checkpoint = SyncCheckpoint(store_id=store_id, platform=NAVER_PLATFORM, sync_type=sync_type)
        db.add(checkpoint)
        db.flush()
    return checkpoint


def _canonical_products(items: list[dict], scope: str) -> list[dict]:
    now = get_utc_now()
    normalized = []
    for item in items:
        external_id = str(item.get("external_product_id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not external_id or not name:
            raise NaverReadFailure("invalid_product_read_record")
        normalized.append({
            "external_product_id": external_id,
            "name": name[:300], "sku": _text(item.get("sku"), 120), "brand": _text(item.get("brand"), 120), "category": _text(item.get("category"), 120),
            "status": _text(item.get("status"), 30) or "active", "price": item.get("price") or 0, "currency": _text(item.get("currency"), 10) or "KRW", "stock_quantity": int(item.get("stock_quantity") or 0),
            "source_type": "naver_onboarding_sync", "last_synced_at": now, "raw_data": {"sync_scope": scope, "raw_response_saved": False},
        })
    return normalized


def _canonical_orders(items: list[dict], scope: str) -> list[dict]:
    now = get_utc_now()
    normalized = []
    for item in items:
        external_order_id = str(item.get("external_order_id") or "").strip()
        product_name = str(item.get("product_name") or "").strip()
        ordered_at = item.get("ordered_at")
        if not external_order_id or not product_name or not isinstance(ordered_at, datetime):
            raise NaverReadFailure("invalid_order_read_record")
        normalized.append({
            "external_order_id": external_order_id, "external_product_order_id": _text(item.get("external_product_order_id"), 120),
            "buyer_name": _text(item.get("buyer_name"), 120), "buyer_phone": _text(item.get("buyer_phone"), 40), "buyer_masked_phone": _text(item.get("buyer_masked_phone"), 30),
            "receiver_name": _text(item.get("receiver_name"), 120), "receiver_phone": _text(item.get("receiver_phone"), 40), "receiver_address": _text(item.get("receiver_address"), 300), "zip_code": _text(item.get("zip_code"), 30),
            "product_name": product_name[:300], "quantity": int(item.get("quantity") or 1), "order_amount": item.get("order_amount") or 0, "currency": _text(item.get("currency"), 10) or "KRW",
            "order_status": _text(item.get("order_status"), 30) or "UNKNOWN", "paid_at": item.get("paid_at") if isinstance(item.get("paid_at"), datetime) else None, "ordered_at": ordered_at,
            "source_type": "naver_historical_backfill" if scope == "historical" else "naver_onboarding_sync", "last_synced_at": now,
            "raw_data": {"sync_scope": scope, "platform_product_id": _text(item.get("platform_product_id"), 120), "raw_response_saved": False},
        })
    return normalized


def _set_failure(db: Session, onboarding: StoreOnboarding, code: str, *, retryable: bool, now: datetime, progress: dict | None = None) -> None:
    onboarding.retry_count += 1
    onboarding.last_error_code = code
    onboarding.status = "retry_wait" if retryable else "blocked"
    onboarding.next_retry_at = now + timedelta(minutes=min(60, 2 ** min(onboarding.retry_count, 5))) if retryable else None
    if progress is not None:
        onboarding.progress_summary = progress
    db.commit()


def _get_onboarding(db: Session, onboarding_id: int) -> StoreOnboarding:
    onboarding = db.get(StoreOnboarding, onboarding_id)
    if onboarding is None:
        raise ApiError("store onboarding was not found", "store_onboarding_not_found", 404)
    return onboarding


def _normalize_window(start_at: datetime, end_at: datetime, *, max_days: int) -> tuple[datetime, datetime]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise ApiError("backfill dates must be timezone-aware and increasing", "invalid_backfill_window", 400)
    if end_at - start_at > timedelta(days=max_days):
        raise ApiError("backfill date window exceeds the bounded limit", "invalid_backfill_window", 400, {"max_days": max_days})
    return start_at, end_at


def _text(value: object, limit: int) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text[:limit] if text else None


def _empty_progress() -> dict:
    return {"products": {"status": "pending"}, "orders": {"status": "pending"}}


def _optional_not_approved() -> dict:
    return {"status": "not_approved", "adapter_called": False, "raw_response_saved": False}
