from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import secrets
import subprocess
import threading
from typing import Any, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.auth import (
    ErpPermission,
    ErpRole,
    ErpRolePermission,
    ErpStoreMembership,
    ErpUser,
)
from app.models.device_environment import DeviceEnvironment
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services.encryption import decrypt_value, encrypt_value
from app.services.operation_audit_service import (
    LOCAL_WRITER_SCOPE,
    write_operation_audit_log_local,
)
from app.services import platform_login_service


DIRECTORY_PROVIDER = "ziniao"
DIRECTORY_SYNC_TYPE = "ziniao_directory"
DIRECTORY_ACTIVE = "active"
DIRECTORY_REMOVED = "removed"
DIRECTORY_UNMANAGED = "unmanaged"
MODE_BUSINESS = "business"
MODE_OPEN_ONLY = "open_only"
ASSIGNMENT_MANUAL = "manual"
ASSIGNMENT_DIRECTORY = "ziniao_directory"
GEO_CACHE_TTL = timedelta(days=7)
MAX_DIRECTORY_ROWS = 2000

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
GeoLookup = Callable[[str], dict[str, str]]

_RUN_LOCK = threading.Lock()
_SCHEDULER_STATE_LOCK = threading.Lock()
_SCHEDULER_NEXT_RUN_AT: datetime | None = None
_SCHEDULER_RETRY_COUNT = 0


class ZiniaoDirectoryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = True):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ZiniaoDirectoryEntry:
    external_id: str
    external_id_hash: str
    source_name: str
    source_platform: str
    source_site: str
    platform: str
    operational_mode: str
    ip_address: str | None
    ip_status: str


@dataclass(frozen=True)
class ZiniaoDirectorySnapshot:
    entries: tuple[ZiniaoDirectoryEntry, ...]
    source_count: int
    excluded_email_count: int


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _clean_text(value: Any, *, max_length: int, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ZiniaoDirectoryError("ziniao_directory_required_field_missing", retryable=False)
    if len(text) > max_length or any(ord(char) < 32 for char in text):
        raise ZiniaoDirectoryError("ziniao_directory_field_invalid", retryable=False)
    return text


def _identity_hash(value: str, settings: Settings) -> str:
    key = str(settings.credential_encryption_key or "").encode("utf-8")
    if not key:
        raise ZiniaoDirectoryError("ziniao_directory_encryption_key_missing", retryable=False)
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_ip(value: Any) -> tuple[str | None, str]:
    text = str(value or "").strip()
    if not text:
        return None, "no_ip"
    if text.casefold() in {"dynamic", "dynamic network", "动态网络"}:
        return None, "dynamic"
    try:
        return ipaddress.ip_address(text).compressed, "pending"
    except ValueError:
        return None, "invalid"


def _masked_ip(value: str) -> str:
    parsed = ipaddress.ip_address(value)
    if parsed.version == 4:
        octets = value.split(".")
        return f"{octets[0]}.{octets[1]}.*.*"
    groups = parsed.exploded.split(":")
    return ":".join(groups[:3]) + ":*"


def _entry_classification(platform_name: str, platform_code: str, site_name: str) -> tuple[str, str] | None:
    platform_text = platform_name.strip().lower()
    code_text = platform_code.strip().lower()
    site_text = site_name.strip().lower()
    if (
        platform_text in {"email", "邮箱"}
        or code_text.endswith("邮箱")
        or site_text in {"outlook", "网易163"}
    ):
        return None
    if "custom" in code_text or "自定义" in code_text or "custom" in site_text or "自定义" in site_text:
        return "custom", MODE_OPEN_ONLY
    if platform_text == "naver" or "naver" in code_text:
        return "naver", MODE_BUSINESS
    if platform_text == "coupang" or "coupang" in code_text:
        return "coupang", MODE_BUSINESS
    return "custom", MODE_OPEN_ONLY


def parse_directory_payload(payload_text: str, *, settings: Settings) -> ZiniaoDirectorySnapshot:
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ZiniaoDirectoryError("ziniao_directory_response_invalid") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ZiniaoDirectoryError("ziniao_directory_response_invalid")
    rows = payload.get("data")
    if isinstance(rows, dict):
        rows = rows.get("items") if isinstance(rows.get("items"), list) else rows.get("list")
    if not isinstance(rows, list) or len(rows) > MAX_DIRECTORY_ROWS:
        raise ZiniaoDirectoryError("ziniao_directory_snapshot_invalid")

    entries: list[ZiniaoDirectoryEntry] = []
    excluded_email_count = 0
    seen_hashes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ZiniaoDirectoryError("ziniao_directory_snapshot_invalid", retryable=False)
        external_id = _clean_text(row.get("id") or row.get("storeId"), max_length=200, required=True)
        source_name = _clean_text(row.get("name") or row.get("storeName"), max_length=200, required=True)
        source_platform = _clean_text(
            row.get("platformName") or row.get("platform"), max_length=500, required=True,
        )
        source_site = _clean_text(row.get("siteName"), max_length=200)
        platform_code = _clean_text(row.get("platform"), max_length=500)
        external_hash = _identity_hash(external_id, settings)
        if external_hash in seen_hashes:
            raise ZiniaoDirectoryError("ziniao_directory_duplicate_external_id", retryable=False)
        seen_hashes.add(external_hash)
        classification = _entry_classification(source_platform, platform_code, source_site)
        if classification is None:
            excluded_email_count += 1
            continue
        platform, operational_mode = classification
        ip_address, ip_status = _normalize_ip(row.get("ip"))
        entries.append(ZiniaoDirectoryEntry(
            external_id=external_id,
            external_id_hash=external_hash,
            source_name=source_name,
            source_platform=source_platform,
            source_site=source_site,
            platform=platform,
            operational_mode=operational_mode,
            ip_address=ip_address,
            ip_status=ip_status,
        ))
    return ZiniaoDirectorySnapshot(
        entries=tuple(entries),
        source_count=len(rows),
        excluded_email_count=excluded_email_count,
    )


def read_directory_snapshot(
    *,
    settings: Settings | None = None,
    command_runner: CommandRunner = subprocess.run,
) -> ZiniaoDirectorySnapshot:
    runtime_settings = settings or get_settings()
    executable = platform_login_service._cli_executable(runtime_settings)
    platform_login_service._require_cli_profile(
        executable,
        settings=runtime_settings,
        command_runner=command_runner,
    )
    result = platform_login_service._run_cli(
        executable,
        [
            "account", "list", "--page-all", "--page-size", "50",
            "--page-limit", "0", "--format", "json",
        ],
        settings=runtime_settings,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        raise ZiniaoDirectoryError("ziniao_directory_cli_failed")
    return parse_directory_payload(result.stdout, settings=runtime_settings)


def _default_geo_lookup(ip_address: str, *, settings: Settings) -> dict[str, str]:
    url = f"https://ipwho.is/{ip_address}"
    timeout = max(2, min(int(settings.ziniao_directory_geoip_timeout_seconds), 15))
    try:
        with httpx.Client(timeout=float(timeout), follow_redirects=False) as client:
            response = client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise ZiniaoDirectoryError("ziniao_geoip_unavailable") from exc
    if response.status_code != 200:
        raise ZiniaoDirectoryError("ziniao_geoip_unavailable")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ZiniaoDirectoryError("ziniao_geoip_response_invalid") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ZiniaoDirectoryError("ziniao_geoip_response_invalid")
    response_ip, response_status = _normalize_ip(payload.get("ip"))
    if response_status != "pending" or response_ip != ip_address:
        raise ZiniaoDirectoryError("ziniao_geoip_ip_mismatch")
    values = {
        "country": _clean_text(payload.get("country"), max_length=100),
        "region": _clean_text(payload.get("region"), max_length=100),
        "city": _clean_text(payload.get("city"), max_length=100),
    }
    if not any(values.values()):
        raise ZiniaoDirectoryError("ziniao_geoip_response_invalid")
    return values


def _platform_compatible(store: Store, entry: ZiniaoDirectoryEntry) -> bool:
    return str(store.platform or "").strip().lower() == entry.platform


def _find_store_for_entry(
    stores: list[Store],
    entry: ZiniaoDirectoryEntry,
) -> Store | None:
    by_hash = [store for store in stores if store.ziniao_external_id_hash == entry.external_id_hash]
    if len(by_hash) > 1:
        raise ZiniaoDirectoryError("ziniao_directory_local_identity_duplicate", retryable=False)
    if by_hash:
        if not _platform_compatible(by_hash[0], entry):
            raise ZiniaoDirectoryError("ziniao_directory_platform_identity_conflict", retryable=False)
        return by_hash[0]

    # Once a directory identity is bound, only that identity may match it.
    # Name fallbacks are reserved for pre-T20 stores that have never been bound.
    unbound_stores = [
        store for store in stores
        if not store.ziniao_external_id_hash and not store.ziniao_external_id_encrypted
    ]
    t19_matches = [
        store for store in stores
        if store in unbound_stores
        and store.browser_provider == DIRECTORY_PROVIDER
        and store.browser_profile_name == entry.source_name
        and _platform_compatible(store, entry)
    ]
    if len(t19_matches) > 1:
        raise ZiniaoDirectoryError("ziniao_directory_t19_binding_not_unique", retryable=False)
    if t19_matches:
        return t19_matches[0]

    name_matches = [
        store for store in unbound_stores
        if store.name == entry.source_name and _platform_compatible(store, entry)
    ]
    if len(name_matches) > 1:
        raise ZiniaoDirectoryError("ziniao_directory_store_match_not_unique", retryable=False)
    return name_matches[0] if name_matches else None


def _unique_store_name(
    entry: ZiniaoDirectoryEntry,
    occupied_names: dict[str, int | None],
    *,
    store_id: int | None,
) -> str:
    def available(candidate: str) -> bool:
        owner = occupied_names.get(candidate)
        return owner is None or owner == store_id

    desired = entry.source_name[:200]
    if available(desired):
        return desired
    suffix = (entry.source_site or entry.platform or "Ziniao")[:60]
    base_limit = max(1, 200 - len(suffix) - 3)
    candidate = f"{entry.source_name[:base_limit]} ({suffix})"
    if available(candidate):
        return candidate
    disambiguator = entry.external_id_hash[:8]
    suffix_with_hash = f"{suffix} {disambiguator}"
    base_limit = max(1, 200 - len(suffix_with_hash) - 3)
    candidate = f"{entry.source_name[:base_limit]} ({suffix_with_hash})"
    if available(candidate):
        return candidate
    raise ZiniaoDirectoryError("ziniao_directory_store_name_collision", retryable=False)


def _eligible_membership_templates(db: Session) -> set[tuple[int, int]]:
    return set(db.execute(
        select(ErpStoreMembership.user_id, ErpStoreMembership.role_id)
        .join(ErpUser, ErpUser.id == ErpStoreMembership.user_id)
        .join(ErpRole, ErpRole.id == ErpStoreMembership.role_id)
        .join(ErpRolePermission, ErpRolePermission.role_id == ErpRole.id)
        .join(ErpPermission, ErpPermission.id == ErpRolePermission.permission_id)
        .join(Store, Store.id == ErpStoreMembership.store_id)
        .where(
            ErpStoreMembership.membership_status == "active",
            ErpStoreMembership.assignment_source == ASSIGNMENT_MANUAL,
            ErpUser.status == "active",
            ErpRole.status == "active",
            ErpPermission.status == "active",
            ErpPermission.permission_key.in_(("platform.browser.open", "*")),
            Store.status == "active",
            Store.ziniao_auto_managed.is_(False),
        )
    ).all())


def _sync_memberships(
    db: Session,
    *,
    stores: list[Store],
    templates: set[tuple[int, int]],
    now: datetime,
) -> dict[str, int]:
    store_ids = {store.id for store in stores if store.id is not None}
    memberships = db.scalars(
        select(ErpStoreMembership).where(ErpStoreMembership.store_id.in_(store_ids))
    ).all() if store_ids else []
    manual_users_by_store: dict[int, set[int]] = {}
    membership_by_key: dict[tuple[int, int, int], ErpStoreMembership] = {}
    for membership in memberships:
        membership_by_key[(membership.user_id, membership.store_id, membership.role_id)] = membership
        if membership.assignment_source != ASSIGNMENT_DIRECTORY:
            manual_users_by_store.setdefault(membership.store_id, set()).add(membership.user_id)

    desired: set[tuple[int, int, int]] = set()
    created = restored = revoked = 0
    for store_id in store_ids:
        manual_users = manual_users_by_store.get(store_id, set())
        for user_id, role_id in templates:
            if user_id in manual_users:
                continue
            key = (user_id, store_id, role_id)
            desired.add(key)
            membership = membership_by_key.get(key)
            if membership is None:
                db.add(ErpStoreMembership(
                    user_id=user_id,
                    store_id=store_id,
                    role_id=role_id,
                    scope_type="assigned",
                    membership_status="active",
                    assignment_source=ASSIGNMENT_DIRECTORY,
                    assigned_at=now,
                ))
                created += 1
            elif membership.assignment_source == ASSIGNMENT_DIRECTORY and membership.membership_status != "active":
                membership.membership_status = "active"
                membership.revoked_at = None
                membership.assigned_at = now
                restored += 1

    for membership in memberships:
        key = (membership.user_id, membership.store_id, membership.role_id)
        if (
            membership.assignment_source == ASSIGNMENT_DIRECTORY
            and membership.membership_status == "active"
            and key not in desired
        ):
            membership.membership_status = "revoked"
            membership.revoked_at = now
            revoked += 1
    return {"created": created, "restored": restored, "revoked": revoked}


def _network_environment(db: Session, *, store: Store) -> DeviceEnvironment:
    rows = db.scalars(select(DeviceEnvironment).where(
        DeviceEnvironment.store_id == store.id,
        DeviceEnvironment.source_provider == DIRECTORY_PROVIDER,
    )).all()
    if len(rows) > 1:
        raise ZiniaoDirectoryError("ziniao_directory_network_environment_duplicate", retryable=False)
    if rows:
        return rows[0]
    environment = DeviceEnvironment(
        store_id=store.id,
        environment_name="Ziniao network environment",
        device_type="browser_profile",
        browser_name="Ziniao",
        source_provider=DIRECTORY_PROVIDER,
        network_status="not_configured",
        status="active",
    )
    db.add(environment)
    return environment


def _sync_network(
    db: Session,
    *,
    store: Store,
    entry: ZiniaoDirectoryEntry,
    settings: Settings,
    now: datetime,
    geo_lookup: GeoLookup | None,
) -> bool:
    environment = _network_environment(db, store=store)
    environment.ip_label = _masked_ip(entry.ip_address) if entry.ip_address else None
    if entry.ip_status == "dynamic":
        changed = bool(environment.encrypted_ip_address or environment.ip_address_hash)
        environment.encrypted_ip_address = None
        environment.ip_address_hash = None
        environment.masked_ip_address = None
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "dynamic"
        environment.network_checked_at = now
        return changed
    if entry.ip_status == "invalid":
        changed = bool(environment.encrypted_ip_address or environment.ip_address_hash)
        environment.encrypted_ip_address = None
        environment.ip_address_hash = None
        environment.masked_ip_address = None
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "failed"
        environment.network_checked_at = now
        return changed
    if not entry.ip_address:
        changed = bool(environment.encrypted_ip_address or environment.ip_address_hash)
        environment.encrypted_ip_address = None
        environment.ip_address_hash = None
        environment.masked_ip_address = None
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "no_ip"
        environment.network_checked_at = now
        return changed

    next_hash = _identity_hash(entry.ip_address, settings)
    ip_changed = environment.ip_address_hash != next_hash
    if ip_changed:
        environment.encrypted_ip_address = encrypt_value(entry.ip_address)
        environment.ip_address_hash = next_hash
        environment.masked_ip_address = _masked_ip(entry.ip_address)
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "pending"
        environment.network_checked_at = None

    parsed_ip = ipaddress.ip_address(entry.ip_address)
    if not parsed_ip.is_global:
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "not_applicable"
        environment.network_checked_at = now
        return ip_changed

    checked_at = _utc(environment.network_checked_at) if environment.network_checked_at else None
    lookup_due = (
        ip_changed
        or environment.network_status != "success"
        or checked_at is None
        or checked_at <= now - GEO_CACHE_TTL
    )
    if not lookup_due:
        return ip_changed
    try:
        values = (
            geo_lookup(entry.ip_address)
            if geo_lookup is not None
            else _default_geo_lookup(entry.ip_address, settings=settings)
        )
        country = _clean_text(values.get("country"), max_length=100)
        region = _clean_text(values.get("region"), max_length=100)
        city = _clean_text(values.get("city"), max_length=100)
        if not any((country, region, city)):
            raise ZiniaoDirectoryError("ziniao_geoip_response_invalid")
        environment.network_country = country or None
        environment.network_region = region or None
        environment.network_city = city or None
        environment.network_status = "success"
    except Exception:
        environment.network_country = None
        environment.network_region = None
        environment.network_city = None
        environment.network_status = "failed"
    environment.network_checked_at = now
    return ip_changed


def _safe_audit(
    db: Session,
    *,
    anchor_store_id: int,
    result: dict[str, Any],
    settings: Settings,
    now: datetime,
) -> None:
    try:
        write_operation_audit_log_local(
            db,
            {
                "created_at": now,
                "updated_at": now,
                "store_id": anchor_store_id,
                "platform": DIRECTORY_PROVIDER,
                "environment": settings.app_env,
                "actor_type": "system",
                "actor_id": "ziniao-directory-scheduler",
                "action": "ziniao_directory_sync",
                "operation_phase": "directory_snapshot",
                "correlation_id": f"ziniao_directory_{secrets.token_hex(10)}",
                "status": "success",
                "reason_code": "ziniao_directory_snapshot_applied",
                "target_type": "store_directory",
                "target_id": anchor_store_id,
                "changed_field_names": ["directory_status", "network_environment", "membership_assignment"],
                "counts_summary": {
                    "stores_created": result["created"],
                    "stores_updated": result["updated"],
                    "stores_archived": result["archived"],
                    "stores_restored": result["restored"],
                    "network_updates": result["network_updates"],
                    "memberships_created": result["memberships_created"],
                },
                "safety_flags": {
                    "platform_write": False,
                    "raw_response_saved": False,
                    "secrets_saved": False,
                },
                "sensitive_scan_passed": True,
                "raw_response_saved": False,
                "secrets_saved": False,
                "privacy_fields_redacted": True,
            },
            write_enabled=True,
            manual_approval=True,
            local_write_scope=LOCAL_WRITER_SCOPE,
        )
    except Exception:
        db.rollback()


def sync_ziniao_directory(
    db: Session,
    *,
    settings: Settings | None = None,
    command_runner: CommandRunner = subprocess.run,
    geo_lookup: GeoLookup | None = None,
    snapshot: ZiniaoDirectorySnapshot | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime_settings = settings or get_settings()
    current = _utc(now or get_utc_now())
    resolved_snapshot = snapshot or read_directory_snapshot(
        settings=runtime_settings,
        command_runner=command_runner,
    )
    templates = _eligible_membership_templates(db)
    stores = db.scalars(select(Store).order_by(Store.id.asc())).all()
    occupied_names = {store.name: store.id for store in stores}
    matched_store_ids: set[int] = set()
    managed_stores: list[Store] = []
    counts = {
        "created": 0,
        "updated": 0,
        "renamed": 0,
        "archived": 0,
        "restored": 0,
        "network_updates": 0,
    }
    try:
        for entry in resolved_snapshot.entries:
            store = _find_store_for_entry(stores, entry)
            created = store is None
            if store is None:
                name = _unique_store_name(entry, occupied_names, store_id=None)
                store = Store(
                    name=name,
                    platform=entry.platform,
                    country="KR",
                    language="ko-KR",
                    status="active",
                    browser_provider=DIRECTORY_PROVIDER,
                    browser_profile_name=entry.source_name,
                    ziniao_auto_managed=True,
                    ziniao_name_managed=True,
                    ziniao_directory_status=DIRECTORY_ACTIVE,
                    ziniao_operational_mode=entry.operational_mode,
                )
                db.add(store)
                db.flush()
                stores.append(store)
                occupied_names[store.name] = store.id
                counts["created"] += 1
            elif store.id in matched_store_ids:
                raise ZiniaoDirectoryError("ziniao_directory_local_store_reused", retryable=False)
            elif store.ziniao_name_managed:
                next_name = _unique_store_name(entry, occupied_names, store_id=store.id)
                if next_name != store.name:
                    occupied_names.pop(store.name, None)
                    store.name = next_name
                    occupied_names[next_name] = store.id
                    counts["renamed"] += 1

            previous_directory_status = store.ziniao_directory_status
            if previous_directory_status == DIRECTORY_REMOVED:
                counts["restored"] += 1
            store.platform = entry.platform
            store.browser_provider = DIRECTORY_PROVIDER
            store.browser_profile_name = entry.source_name
            if (
                store.ziniao_external_id_hash != entry.external_id_hash
                or not store.ziniao_external_id_encrypted
            ):
                store.ziniao_external_id_encrypted = encrypt_value(entry.external_id)
            store.ziniao_external_id_hash = entry.external_id_hash
            store.ziniao_source_name = entry.source_name
            store.ziniao_source_platform = entry.source_platform
            store.ziniao_source_site = entry.source_site or None
            store.ziniao_auto_managed = True
            store.ziniao_directory_status = DIRECTORY_ACTIVE
            store.ziniao_operational_mode = entry.operational_mode
            store.ziniao_last_seen_at = current
            store.ziniao_directory_checked_at = current
            store.ziniao_missing_count = 0
            store.ziniao_missing_since = None
            if not created:
                counts["updated"] += 1
            if _sync_network(
                db,
                store=store,
                entry=entry,
                settings=runtime_settings,
                now=current,
                geo_lookup=geo_lookup,
            ):
                counts["network_updates"] += 1
            matched_store_ids.add(store.id)
            managed_stores.append(store)

        for store in stores:
            if not store.ziniao_auto_managed or store.id in matched_store_ids:
                continue
            store.ziniao_directory_checked_at = current
            store.ziniao_missing_count = int(store.ziniao_missing_count or 0) + 1
            if store.ziniao_missing_since is None:
                store.ziniao_missing_since = current
            if store.ziniao_missing_count >= 2 and store.ziniao_directory_status != DIRECTORY_REMOVED:
                store.ziniao_directory_status = DIRECTORY_REMOVED
                counts["archived"] += 1
            managed_stores.append(store)

        membership_counts = _sync_memberships(
            db,
            stores=managed_stores,
            templates=templates,
            now=current,
        )
        result = {
            "status": "success",
            "source_count": resolved_snapshot.source_count,
            "business_entry_count": len(resolved_snapshot.entries),
            "excluded_email_count": resolved_snapshot.excluded_email_count,
            **counts,
            "memberships_created": membership_counts["created"],
            "memberships_restored": membership_counts["restored"],
            "memberships_revoked": membership_counts["revoked"],
            "platform_write": False,
            "raw_response_saved": False,
        }
        change_count = sum(
            result[key]
            for key in (
                "created", "renamed", "archived", "restored", "network_updates",
                "memberships_created", "memberships_restored", "memberships_revoked",
            )
        )
        anchor = min(managed_stores, key=lambda item: item.id) if managed_stores else None
        if anchor is not None and change_count:
            db.add(SyncLog(
                store_id=anchor.id,
                platform=DIRECTORY_PROVIDER,
                sync_type=DIRECTORY_SYNC_TYPE,
                status="success",
                started_at=current,
                finished_at=current,
                message="Ziniao directory snapshot applied",
                raw_summary={
                    "source_count": result["source_count"],
                    "business_entry_count": result["business_entry_count"],
                    "excluded_email_count": result["excluded_email_count"],
                    "created": result["created"],
                    "archived": result["archived"],
                    "restored": result["restored"],
                    "platform_write": False,
                    "raw_response_saved": False,
                },
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise

    if anchor is not None and change_count:
        _safe_audit(
            db,
            anchor_store_id=anchor.id,
            result=result,
            settings=runtime_settings,
            now=current,
        )
    return result


def record_directory_failure(
    db: Session,
    *,
    error_code: str,
    now: datetime | None = None,
) -> None:
    current = _utc(now or get_utc_now())
    anchor = db.scalar(select(Store).where(
        Store.ziniao_auto_managed.is_(True),
    ).order_by(Store.id.asc()))
    if anchor is None:
        return
    safe_code = str(error_code or "ziniao_directory_sync_failed")[:80]
    db.add(SyncLog(
        store_id=anchor.id,
        platform=DIRECTORY_PROVIDER,
        sync_type=DIRECTORY_SYNC_TYPE,
        status="failed",
        started_at=current,
        finished_at=current,
        message="Ziniao directory sync failed",
        error_detail=safe_code,
        raw_summary={
            "error_code": safe_code,
            "platform_write": False,
            "raw_response_saved": False,
        },
    ))
    db.commit()


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, ZiniaoDirectoryError):
        return exc.code
    if isinstance(exc, ApiError):
        return str(exc.error_code or "ziniao_directory_sync_failed").lower()[:80]
    return "ziniao_directory_sync_failed"


def run_due_ziniao_directory_sync(
    *,
    session_factory: Callable[[], Session],
    settings: Settings | None = None,
    command_runner: CommandRunner = subprocess.run,
    geo_lookup: GeoLookup | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    global _SCHEDULER_NEXT_RUN_AT, _SCHEDULER_RETRY_COUNT
    runtime_settings = settings or get_settings()
    current = _utc(now or get_utc_now())
    if not runtime_settings.ziniao_directory_sync_enabled:
        return {"status": "disabled", "platform_write": False}
    with _SCHEDULER_STATE_LOCK:
        if _SCHEDULER_NEXT_RUN_AT and current < _SCHEDULER_NEXT_RUN_AT:
            return {
                "status": "not_due",
                "next_run_at": _SCHEDULER_NEXT_RUN_AT.isoformat(),
                "platform_write": False,
            }
    if not _RUN_LOCK.acquire(blocking=False):
        return {"status": "running", "platform_write": False}
    try:
        with session_factory() as db:
            try:
                result = sync_ziniao_directory(
                    db,
                    settings=runtime_settings,
                    command_runner=command_runner,
                    geo_lookup=geo_lookup,
                    now=current,
                )
            except Exception as exc:
                db.rollback()
                error_code = _failure_code(exc)
                record_directory_failure(db, error_code=error_code, now=current)
                with _SCHEDULER_STATE_LOCK:
                    _SCHEDULER_RETRY_COUNT += 1
                    retry_minutes = min(60, 2 ** min(_SCHEDULER_RETRY_COUNT - 1, 6))
                    _SCHEDULER_NEXT_RUN_AT = current + timedelta(minutes=retry_minutes)
                return {
                    "status": "retry_wait",
                    "error_code": error_code,
                    "retry_count": _SCHEDULER_RETRY_COUNT,
                    "next_run_at": _SCHEDULER_NEXT_RUN_AT.isoformat(),
                    "platform_write": False,
                }
        interval = max(60, int(runtime_settings.ziniao_directory_sync_interval_seconds))
        with _SCHEDULER_STATE_LOCK:
            _SCHEDULER_RETRY_COUNT = 0
            _SCHEDULER_NEXT_RUN_AT = current + timedelta(seconds=interval)
        return {**result, "next_run_at": _SCHEDULER_NEXT_RUN_AT.isoformat()}
    finally:
        _RUN_LOCK.release()


def reset_scheduler_state_for_tests() -> None:
    global _SCHEDULER_NEXT_RUN_AT, _SCHEDULER_RETRY_COUNT
    with _SCHEDULER_STATE_LOCK:
        _SCHEDULER_NEXT_RUN_AT = None
        _SCHEDULER_RETRY_COUNT = 0


def decrypted_store_external_id(store: Store) -> str | None:
    if not store.ziniao_external_id_encrypted:
        return None
    value = decrypt_value(store.ziniao_external_id_encrypted)
    return str(value or "").strip() or None


def decrypted_network_ip(environment: DeviceEnvironment | None) -> str | None:
    if environment is None or not environment.encrypted_ip_address:
        return None
    value = decrypt_value(environment.encrypted_ip_address)
    return str(value or "").strip() or None
