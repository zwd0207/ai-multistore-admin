from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.timezone import get_business_timezone, get_utc_now
from app.database import SessionLocal
from app.models.api_credential import ApiCredential
from app.models.auth import ErpRole, ErpStoreMembership
from app.models.store import Store
from app.models.store_onboarding import StoreOnboarding
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_log import SyncLog
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate, StoreOnboardingCredentialUpdate, StoreOnboardingRead
from app.services import api_credential_readiness_service, order_service, product_service, sync_service
from app.services.encryption import decrypt_value, encrypt_value


NAVER_PLATFORM = "naver"
INITIAL_SYNC_DAYS = 30
HISTORY_MAX_DAYS = 31
MAX_READ_PAGES = 100
PRODUCT_PAGE_SIZE = 5
ORDER_DETAIL_BATCH_SIZE = sync_service.NAVER_ORDER_MANUAL_BATCH_MAX_COUNT
WORKER_CLAIM_TTL = timedelta(minutes=15)
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
    api_base: str
    grant_type_used: str = "SELF"
    seller_account_id: str | None = None


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
    """Approved Naver read-only adapter composed from the existing sync helpers."""

    def __init__(
        self,
        *,
        token_request: Callable[[dict], tuple[str, int]] | None = None,
        product_search: Callable[..., dict] | None = None,
        order_feed: Callable[..., dict] | None = None,
        order_detail: Callable[..., dict] | None = None,
        validation: Callable[..., NaverValidation] | None = None,
    ) -> None:
        self._token_request = token_request or api_credential_readiness_service._request_naver_token_from_context
        self._product_search = product_search or sync_service._request_naver_product_search
        self._order_feed = order_feed or sync_service._request_naver_order_last_changed_feed
        self._order_detail = order_detail or sync_service._request_naver_order_detail_query
        self._validation = validation
        self._tokens: dict[int, str] = {}

    def validate(self, *, client_id: str, client_secret: str, channel_no: str | None) -> NaverValidation:
        if self._validation is not None:
            return self._validation(client_id=client_id, client_secret=client_secret, channel_no=channel_no)
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
        state = _decode_cursor(cursor, expected_kind="products", default={"page": 1})
        page_number = int(state.get("page") or 1)
        result = self._product_search(
            api_base=context.api_base,
            headers=self._headers(context),
            page=page_number,
            size=PRODUCT_PAGE_SIZE,
        )
        _raise_for_read_result(result, scope="product")
        payload = result.get("payload")
        candidates, _skip_reasons = sync_service._extract_naver_product_sync_candidates(payload)
        has_more = sync_service._naver_product_preview_has_more(payload)
        next_cursor = _encode_cursor("products", {"page": page_number + 1}) if has_more else None
        return NaverReadPage(items=candidates, next_cursor=next_cursor)

    def read_orders(self, context: NaverReadContext, *, start_at: datetime, end_at: datetime, cursor: str | None) -> NaverReadPage:
        start_kst = _as_aware_utc(start_at).astimezone(get_business_timezone())
        end_kst = _as_aware_utc(end_at).astimezone(get_business_timezone())
        state = _decode_cursor(cursor, expected_kind="orders", default={"slice": 0, "after": None})
        slice_index = int(state.get("slice") or 0)
        slice_start = start_kst + timedelta(days=slice_index)
        if slice_start >= end_kst:
            return NaverReadPage(items=[])
        slice_end = min(slice_start + timedelta(days=1), end_kst)
        after = _parse_cursor_datetime(state.get("after")) or slice_start
        if after < slice_start or after >= slice_end:
            after = slice_start
        feed = self._order_feed(
            api_base=context.api_base,
            headers=self._headers(context),
            start_kst=after,
            end_kst=slice_end,
            size=ORDER_DETAIL_BATCH_SIZE,
            attempt="onboarding_daily_read",
            include_last_changed_to=True,
            datetime_format_shape="offset_milliseconds",
        )
        _raise_for_read_result(feed, scope="order")
        feed_payload = feed.get("payload")
        product_order_ids = sync_service._extract_naver_product_order_ids(feed_payload)
        details: list[dict] = []
        for offset in range(0, len(product_order_ids), ORDER_DETAIL_BATCH_SIZE):
            batch = product_order_ids[offset:offset + ORDER_DETAIL_BATCH_SIZE]
            detail_result = self._order_detail(
                api_base=context.api_base,
                headers=self._headers(context),
                product_order_ids=batch,
            )
            _raise_for_read_result(detail_result, scope="order")
            records = sync_service._extract_naver_order_detail_records(detail_result.get("payload"), batch)
            details.extend(sync_service._build_naver_order_internal_detail(item, store_id=context.store_id) for item in records)

        if sync_service._naver_order_feed_has_more(feed_payload):
            latest = _latest_order_change_at(feed_payload)
            if latest is None or latest <= after.astimezone(latest.tzinfo) or latest >= slice_end.astimezone(latest.tzinfo):
                raise NaverReadFailure("order_feed_cursor_not_advanced", retryable=True)
            next_cursor = _encode_cursor("orders", {"slice": slice_index, "after": (latest + timedelta(milliseconds=1)).isoformat()})
        else:
            next_slice = slice_index + 1
            next_cursor = _encode_cursor("orders", {"slice": next_slice, "after": None}) if start_kst + timedelta(days=next_slice) < end_kst else None
        return NaverReadPage(items=details, next_cursor=next_cursor)

    def _headers(self, context: NaverReadContext) -> dict[str, str]:
        token = self._tokens.get(context.credential_id)
        if token is None:
            try:
                token, _ = self._token_request({
                    "client_id": context.client_id,
                    "secret_key": context.client_secret,
                    "api_base": context.api_base,
                    "grant_type_used": context.grant_type_used,
                    "seller_account_id": context.seller_account_id,
                })
            except api_credential_readiness_service.NaverReadonlyAuthError as exc:
                raise NaverReadFailure(exc.error_code) from exc
            except httpx.TimeoutException as exc:
                raise NaverReadFailure("network_timeout", retryable=True) from exc
            except httpx.HTTPError as exc:
                raise NaverReadFailure("network_error", retryable=True) from exc
            self._tokens[context.credential_id] = token
        return {"Authorization": f"Bearer {token}"}


def _read_failure_from_response(response: httpx.Response, *, scope: str) -> NaverReadFailure:
    if response.status_code == 429 or response.status_code >= 500:
        return NaverReadFailure("naver_read_retryable", retryable=True)
    if response.status_code == 403:
        code, flags = api_credential_readiness_service._classify_naver_forbidden_response(response, stage=scope, scope=scope)
        if flags.get("ip_keyword"):
            code = "ip_not_allowed"
        return NaverReadFailure(code)
    return NaverReadFailure("auth_failed" if response.status_code == 401 else "naver_read_failed")


def _raise_for_read_result(result: dict, *, scope: str) -> None:
    if result.get("success"):
        return
    code = str(result.get("error_code") or f"{scope}_read_failed")
    status = result.get("http_status")
    raise NaverReadFailure(code, retryable=status == 429 or isinstance(status, int) and status >= 500)


def _encode_cursor(kind: str, state: dict) -> str:
    return json.dumps({"kind": kind, **state}, sort_keys=True, separators=(",", ":"))


def _decode_cursor(cursor: str | None, *, expected_kind: str, default: dict) -> dict:
    if not cursor:
        return dict(default)
    try:
        state = json.loads(cursor)
    except (TypeError, ValueError) as exc:
        raise NaverReadFailure("checkpoint_cursor_invalid") from exc
    if not isinstance(state, dict) or state.get("kind") != expected_kind:
        raise NaverReadFailure("checkpoint_cursor_invalid")
    return state


def _sanitized_cursor(cursor: str | None) -> dict | None:
    if not cursor:
        return None
    try:
        state = json.loads(cursor)
    except ValueError:
        return {"status": "invalid"}
    if not isinstance(state, dict):
        return {"status": "invalid"}
    return {key: value for key, value in state.items() if key in {"kind", "page", "slice", "after"}}


def _as_aware_utc(value: datetime) -> datetime:
    from datetime import timezone

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _parse_cursor_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise NaverReadFailure("checkpoint_cursor_invalid") from exc
    return _as_aware_utc(parsed).astimezone(get_business_timezone())


def _latest_order_change_at(payload: object) -> datetime | None:
    values: list[datetime] = []

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key, value in item.items():
                if key in {"lastChangedAt", "lastChangedDate", "lastChangeDate"}:
                    parsed = sync_service._extract_datetime_by_keys({key: value}, (key,))
                    if parsed is not None:
                        values.append(parsed)
                else:
                    walk(value)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(payload)
    return max(values) if values else None


def get_naver_read_adapter() -> NaverReadAdapter:
    return DefaultNaverReadAdapter()


def serialize_onboarding(onboarding: StoreOnboarding) -> dict:
    return StoreOnboardingRead.model_validate(onboarding, from_attributes=True).model_dump(mode="json")


def submit_onboarding(
    db: Session,
    *,
    payload: StoreOnboardingCreate,
    creator_user_id: int,
    now: datetime | None = None,
) -> dict:
    existing = db.scalar(select(StoreOnboarding).where(StoreOnboarding.idempotency_key == payload.idempotency_key))
    if existing is not None:
        if existing.creator_user_id != creator_user_id:
            raise ApiError("idempotency key is owned by another operator", "onboarding_idempotency_conflict", 409)
        return serialize_onboarding(existing)
    frozen_end = now or get_utc_now()
    onboarding = StoreOnboarding(
        idempotency_key=payload.idempotency_key,
        requested_store_name=payload.store_name,
        creator_user_id=creator_user_id,
        encrypted_client_id=encrypt_value(payload.client_id),
        encrypted_client_secret=encrypt_value(payload.client_secret),
        requested_channel_no=payload.channel_no,
        status="validating",
        progress_summary=_empty_progress(),
        snapshot_end_at=frozen_end,
        initial_window_start_at=frozen_end - timedelta(days=INITIAL_SYNC_DAYS),
    )
    db.add(onboarding)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError("onboarding idempotency conflict", "onboarding_idempotency_conflict", 409) from exc
    db.refresh(onboarding)
    return serialize_onboarding(onboarding)


def request_onboarding_resume(db: Session, *, onboarding_id: int) -> dict:
    onboarding = _get_onboarding(db, onboarding_id)
    if onboarding.status == "cancelled":
        raise ApiError("onboarding is cancelled", "onboarding_cancelled", 409)
    if onboarding.status in {"partially_synced", "active_incremental"}:
        return serialize_onboarding(onboarding)
    if onboarding.status != "validating":
        onboarding.status = "validating" if onboarding.store_id is None else "backfilling"
    onboarding.next_retry_at = None
    db.commit()
    db.refresh(onboarding)
    return serialize_onboarding(onboarding)


def run_onboarding_work(
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
        except Exception:
            _set_failure(db, onboarding, "naver_validation_unexpected_failure", retryable=True, now=now)
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
    elif onboarding.status == "validating":
        context = _read_context(db, onboarding)
        try:
            validation = reader.validate(
                client_id=context.client_id,
                client_secret=context.client_secret,
                channel_no=context.channel_no,
            )
        except NaverReadFailure as exc:
            _set_failure(db, onboarding, exc.code, retryable=exc.retryable, now=now)
            return serialize_onboarding(onboarding)
        except Exception:
            _set_failure(db, onboarding, "naver_validation_unexpected_failure", retryable=True, now=now)
            return serialize_onboarding(onboarding)
        if not validation.ready:
            _set_failure(db, onboarding, "naver_validation_not_ready", retryable=False, now=now)
            return serialize_onboarding(onboarding)
        onboarding.validation_summary = validation.sanitized()
        credential = db.get(ApiCredential, onboarding.credential_id)
        if credential is not None:
            credential.auth_status = "test_passed"
        db.commit()

    return _run_initial_backfill(db, onboarding=onboarding, reader=reader, now=now)


def run_onboarding_worker(
    onboarding_id: int,
    *,
    reader: NaverReadAdapter | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> dict | None:
    claim_token = uuid.uuid4().hex
    now = get_utc_now()
    stale_before = now - WORKER_CLAIM_TTL
    with session_factory() as db:
        claimed = db.execute(
            update(StoreOnboarding)
            .where(
                StoreOnboarding.id == onboarding_id,
                or_(StoreOnboarding.worker_claim_token.is_(None), StoreOnboarding.worker_claimed_at < stale_before),
            )
            .values(worker_claim_token=claim_token, worker_claimed_at=now)
        )
        db.commit()
        if claimed.rowcount != 1:
            return None
        try:
            return run_onboarding_work(db, onboarding_id=onboarding_id, reader=reader, now=now)
        finally:
            db.execute(
                update(StoreOnboarding)
                .where(StoreOnboarding.id == onboarding_id, StoreOnboarding.worker_claim_token == claim_token)
                .values(worker_claim_token=None, worker_claimed_at=None)
            )
            db.commit()


def run_due_onboarding_workers(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    worker: Callable[..., dict | None] = run_onboarding_worker,
    now: datetime | None = None,
    limit: int = 10,
) -> dict[str, int]:
    """Resume durable work after restart and retry transient failures when due."""
    current = now or get_utc_now()
    stale_before = current - WORKER_CLAIM_TTL
    with session_factory() as db:
        ids = db.scalars(
            select(StoreOnboarding.id)
            .where(
                or_(
                    StoreOnboarding.status.in_(("validating", "provisioning", "backfilling")),
                    (StoreOnboarding.status == "retry_wait") & (StoreOnboarding.next_retry_at <= current),
                ),
                or_(
                    StoreOnboarding.worker_claim_token.is_(None),
                    StoreOnboarding.worker_claimed_at < stale_before,
                ),
            )
            .order_by(StoreOnboarding.updated_at.asc(), StoreOnboarding.id.asc())
            .limit(max(1, min(int(limit), 100)))
        ).all()
    completed = 0
    for onboarding_id in ids:
        if worker(onboarding_id, session_factory=session_factory) is not None:
            completed += 1
    return {"scheduled": len(ids), "completed": completed}


def list_store_onboardings(db: Session, *, store_id: int, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(StoreOnboarding)
        .join(
            ErpStoreMembership,
            ErpStoreMembership.store_id == StoreOnboarding.store_id,
        )
        .where(
            StoreOnboarding.store_id == store_id,
            ErpStoreMembership.user_id == user_id,
            ErpStoreMembership.membership_status == "active",
        )
        .order_by(StoreOnboarding.updated_at.desc(), StoreOnboarding.id.desc())
    ).all()
    return [serialize_onboarding(item) for item in rows]


def update_onboarding_credentials(
    db: Session,
    *,
    onboarding_id: int,
    payload: StoreOnboardingCredentialUpdate,
) -> dict:
    onboarding = _get_onboarding(db, onboarding_id)
    if onboarding.status == "cancelled":
        raise ApiError("onboarding is cancelled", "onboarding_cancelled", 409)
    if onboarding.worker_claim_token and onboarding.worker_claimed_at:
        claimed_at = _as_aware_utc(onboarding.worker_claimed_at)
        if claimed_at >= get_utc_now() - WORKER_CLAIM_TTL:
            raise ApiError("onboarding worker is active", "onboarding_worker_busy", 409)
    updates = payload.model_dump(exclude_unset=True)
    if onboarding.credential_id is None:
        if "client_id" in updates:
            onboarding.encrypted_client_id = encrypt_value(updates["client_id"])
        if "client_secret" in updates:
            onboarding.encrypted_client_secret = encrypt_value(updates["client_secret"])
        if "channel_no" in updates:
            onboarding.requested_channel_no = updates["channel_no"] or None
    else:
        credential = db.get(ApiCredential, onboarding.credential_id)
        if credential is None:
            raise ApiError("onboarding credential is unavailable", "onboarding_credential_missing", 409)
        if "client_id" in updates:
            credential.client_id = updates["client_id"]
        if "client_secret" in updates:
            credential.encrypted_secret_key = encrypt_value(updates["client_secret"])
        extra = dict(credential.extra_config or {})
        if "channel_no" in updates:
            if updates["channel_no"]:
                extra["channel_no"] = updates["channel_no"]
            else:
                extra.pop("channel_no", None)
        extra.pop("encrypted_client_id", None)
        credential.extra_config = extra
        credential.auth_status = "needs_test"
    onboarding.configuration_version += 1
    onboarding.last_error_code = None
    onboarding.next_retry_at = None
    onboarding.validation_summary = None
    onboarding.status = "validating"
    onboarding.worker_claim_token = None
    onboarding.worker_claimed_at = None
    db.commit()
    db.refresh(onboarding)
    return serialize_onboarding(onboarding)


def onboarding_access_allowed(db: Session, *, onboarding: StoreOnboarding, user_id: int) -> bool:
    if onboarding.creator_user_id == user_id:
        return True
    if onboarding.store_id is None:
        return False
    membership = db.scalar(
        select(ErpStoreMembership.id)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .where(
            ErpStoreMembership.user_id == user_id,
            ErpStoreMembership.store_id == onboarding.store_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
        )
        .limit(1)
    )
    return membership is not None


def require_onboarding_access(db: Session, *, onboarding: StoreOnboarding, user_id: int) -> None:
    if not onboarding_access_allowed(db, onboarding=onboarding, user_id=user_id):
        raise ApiError("store onboarding is outside assigned scope", "store_onboarding_scope_forbidden", 403)


def run_historical_order_backfill(
    db: Session,
    *,
    onboarding_id: int,
    payload: HistoricalBackfillCreate,
    reader: NaverReadAdapter | None = None,
    now: datetime | None = None,
) -> dict:
    onboarding = _get_onboarding(db, onboarding_id)
    if onboarding.store_id is None or onboarding.credential_id is None:
        raise ApiError("onboarding has not provisioned a store", "onboarding_not_provisioned", 409)
    if onboarding.status == "cancelled":
        raise ApiError("onboarding is cancelled", "onboarding_cancelled", 409)
    start_at, end_at = _normalize_historical_backfill_window(
        payload.start_at,
        payload.end_at,
        now=now,
    )
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
        "unsynced_history_retrieved": result.get("status") == "success" and int(result.get("remote_items") or 0) > 0,
    }


def _run_initial_backfill(db: Session, *, onboarding: StoreOnboarding, reader: NaverReadAdapter, now: datetime) -> dict:
    if onboarding.snapshot_end_at is None or onboarding.initial_window_start_at is None:
        onboarding.snapshot_end_at = now
        onboarding.initial_window_start_at = now - timedelta(days=INITIAL_SYNC_DAYS)
    onboarding.status = "backfilling"
    db.commit()
    results: dict[str, dict] = dict(onboarding.progress_summary or _empty_progress())
    for dataset, sync_type in (("products", ONBOARDING_PRODUCT_SYNC), ("orders", ONBOARDING_ORDER_SYNC)):
        if results.get(dataset, {}).get("status") == "success":
            continue
        previous = dict(results.get(dataset) or {})
        results[dataset] = {
            **previous,
            "status": "running",
            "created": int(previous.get("created") or 0),
            "updated": int(previous.get("updated") or 0),
            "pages": int(previous.get("pages") or 0),
            "remote_items": int(previous.get("remote_items") or 0),
        }
        onboarding.progress_summary = {
            **results,
            "customer_inquiries": _optional_not_approved(),
            "logistics": _optional_not_approved(),
        }
        db.commit()
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
                progress={**results, "customer_inquiries": _optional_not_approved(), "logistics": _optional_not_approved()},
            )
            return serialize_onboarding(onboarding)

    # Inquiry and logistics adapters are intentionally not called until their
    # contracts are approved, so the durable state must not claim full activation.
    onboarding.status = "partially_synced"
    onboarding.last_error_code = None
    onboarding.next_retry_at = None
    onboarding.progress_summary = {
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
    existing_progress = dict((onboarding.progress_summary or {}).get(dataset) or {})
    created = int(existing_progress.get("created") or 0)
    updated = int(existing_progress.get("updated") or 0)
    pages = int(existing_progress.get("pages") or 0)
    remote_items = int(existing_progress.get("remote_items") or 0)
    pages_this_run = 0
    try:
        while True:
            if pages_this_run >= MAX_READ_PAGES:
                raise NaverReadFailure("read_page_limit_reached", retryable=True)
            page = (
                reader.read_products(context, start_at=start_at, end_at=end_at, cursor=cursor)
                if dataset == "products"
                else reader.read_orders(context, start_at=start_at, end_at=end_at, cursor=cursor)
            )
            if not isinstance(page, NaverReadPage):
                raise NaverReadFailure("invalid_read_adapter_page")
            remote_items += len(page.items)
            items = _canonical_products(page.items, scope) if dataset == "products" else _canonical_orders(page.items, scope)
            outcome = product_service.upsert_products(db, onboarding.store_id, NAVER_PLATFORM, items) if dataset == "products" else order_service.upsert_orders(db, onboarding.store_id, NAVER_PLATFORM, items)
            created += outcome["created"]
            updated += outcome["updated"]
            pages += 1
            pages_this_run += 1
            cursor = page.next_cursor
            checkpoint.cursor_value = cursor
            checkpoint.last_synced_at = get_utc_now()
            progress = dict(onboarding.progress_summary or _empty_progress())
            progress[dataset] = {
                "status": "running" if cursor else "success",
                "created": created,
                "updated": updated,
                "pages": pages,
                "remote_items": remote_items,
                "cursor": _sanitized_cursor(cursor),
                "window_start_at": start_at.isoformat(),
                "window_end_at": end_at.isoformat(),
                "raw_response_saved": False,
                "platform_write": False,
            }
            onboarding.progress_summary = progress
            db.commit()
            if not cursor:
                break
        sync_log.status = "success"
        sync_log.finished_at = get_utc_now()
        sync_log.raw_summary = {"scope": scope, "dataset": dataset, "created": created, "updated": updated, "pages": pages, "raw_response_saved": False, "platform_write": False}
        db.commit()
        return {"status": "success", "created": created, "updated": updated, "pages": pages, "remote_items": remote_items, "window_start_at": start_at.isoformat(), "window_end_at": end_at.isoformat(), "error_code": None, "retryable": False, "raw_response_saved": False, "platform_write": False}
    except Exception as exc:
        db.rollback()
        failure = exc if isinstance(exc, NaverReadFailure) else NaverReadFailure(
            "readonly_adapter_unexpected_failure",
            retryable=True,
        )
        sync_log.status = "failed"
        sync_log.finished_at = get_utc_now()
        sync_log.message = "sanitized Naver read failure"
        sync_log.error_detail = failure.code
        sync_log.raw_summary = {"scope": scope, "dataset": dataset, "raw_response_saved": False, "platform_write": False, "error_code": failure.code}
        progress = dict(onboarding.progress_summary or _empty_progress())
        progress[dataset] = {
            "status": "failed",
            "created": created,
            "updated": updated,
            "pages": pages,
            "remote_items": remote_items,
            "cursor": _sanitized_cursor(cursor),
            "error_code": failure.code,
            "retryable": failure.retryable,
            "raw_response_saved": False,
            "platform_write": False,
        }
        onboarding.progress_summary = progress
        db.commit()
        return {"status": "failed", "created": created, "updated": updated, "pages": pages, "remote_items": remote_items, "window_start_at": start_at.isoformat(), "window_end_at": end_at.isoformat(), "error_code": failure.code, "retryable": failure.retryable, "raw_response_saved": False, "platform_write": False}


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
        client_id=client_id,
        encrypted_secret_key=encrypt_value(client_secret),
        auth_status="test_passed",
        status="active",
        extra_config={"api_base": api_credential_readiness_service.NAVER_DEFAULT_API_BASE, "channel_no": selected_channel_no, "onboarded": True},
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
    client_id = credential.client_id
    # Compatibility for rows created by the original T13 preview commit.
    if not client_id and extra.get("encrypted_client_id"):
        client_id = decrypt_value(credential.encrypted_access_key)
    if not client_id:
        raise ApiError("onboarding credential is unavailable", "onboarding_credential_missing", 409)
    secret = decrypt_value(credential.encrypted_secret_key)
    if not secret:
        raise ApiError("onboarding credential cannot be decrypted", "onboarding_credential_decrypt_failed", 409)
    grant_type = str(extra.get("grant_type") or "SELF").strip().upper()
    if grant_type not in {"SELF", "SELLER"}:
        grant_type = "SELF"
    return NaverReadContext(
        onboarding.store_id or 0,
        credential.id,
        client_id,
        secret,
        extra.get("channel_no"),
        str(extra.get("api_base") or api_credential_readiness_service.NAVER_DEFAULT_API_BASE).rstrip("/"),
        grant_type,
        extra.get("seller_account_id"),
    )


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
        external_product_order_id = _text(item.get("external_product_order_id"), 120)
        external_order_id = str(
            item.get("external_product_order_id_hash")
            or item.get("external_order_id")
            or ""
        ).strip()
        product_name = str(item.get("product_name") or "").strip()
        ordered_at = _parse_business_datetime(item.get("ordered_at"))
        if not external_order_id or not external_product_order_id or not product_name or ordered_at is None:
            raise NaverReadFailure("invalid_order_read_record")
        order_status = item.get("order_status")
        if isinstance(order_status, dict):
            order_status = order_status.get("raw")
        normalized.append({
            "external_order_id": external_order_id, "external_product_order_id": external_product_order_id,
            "buyer_name": _text(item.get("buyer_name_masked") or item.get("buyer_name"), 120), "buyer_phone": None, "buyer_masked_phone": _text(item.get("buyer_phone_masked"), 30),
            "receiver_name": _text(item.get("receiver_name"), 120), "receiver_phone": _text(item.get("receiver_phone"), 40), "receiver_address": _text(item.get("receiver_address"), 300), "zip_code": _text(item.get("zip_code"), 30),
            "product_name": product_name[:300], "quantity": int(item.get("quantity") or 1), "order_amount": item.get("order_amount") or 0, "currency": _text(item.get("currency"), 10) or "KRW",
            "order_status": _text(order_status, 30) or "UNKNOWN", "paid_at": _parse_business_datetime(item.get("paid_at")), "ordered_at": ordered_at,
            "source_type": order_service.HISTORICAL_BACKFILL_SOURCE_TYPE if scope == "historical" else "naver_onboarding_sync", "last_synced_at": now,
            "raw_data": {
                "sync_scope": scope,
                "source_type": order_service.HISTORICAL_BACKFILL_SOURCE_TYPE if scope == "historical" else "naver_onboarding_sync",
                "platform_product_id": _text(item.get("platform_product_id"), 120),
                "option_name": _text(item.get("option_name"), 160),
                "external_order_id_hash": _text(item.get("external_order_id_hash"), 120),
                "mapping_version": _text(item.get("mapping_version"), 80),
                "raw_response_saved": False,
                "platform_write": False,
            },
        })
    return normalized


def _parse_business_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_aware_utc(value)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_aware_utc(parsed)


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


def _normalize_historical_backfill_window(
    start_at: datetime,
    end_at: datetime,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    start_at, end_at = _normalize_window(start_at, end_at, max_days=HISTORY_MAX_DAYS)
    current_window_start = order_service.current_order_window_start(as_of=now)
    if end_at > current_window_start:
        raise ApiError(
            "historical backfill must end before the current order window",
            "historical_backfill_current_window_overlap",
            400,
        )
    return start_at, end_at


def _text(value: object, limit: int) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text[:limit] if text else None


def _empty_progress() -> dict:
    return {"products": {"status": "pending"}, "orders": {"status": "pending"}}


def _optional_not_approved() -> dict:
    return {"status": "not_approved", "adapter_called": False, "raw_response_saved": False}
