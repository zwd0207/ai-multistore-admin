from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import get_utc_now
from app.models.shipping import LogisticsInventoryItem, LogisticsInventoryMapping
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.store_service import ensure_store_exists


SHIPPING_WRITE_SCOPE = "shipping_mapping_stock_local"
SHIPPING_MAPPING_VERSION = "shipping_mapping_v1"
ALLOWED_SHIPPING_PLATFORMS = {"naver", "coupang", "future_platform"}

SENSITIVE_KEY_MARKERS = {
    "accesstoken",
    "authorization",
    "bcrypt",
    "buyername",
    "buyerphone",
    "channelno",
    "clientsecret",
    "detailedaddress",
    "headers",
    "orderid",
    "productorderid",
    "rawdata",
    "rawrequest",
    "rawresponse",
    "receivername",
    "receiverphone",
    "refreshtoken",
    "requestheaders",
    "responseheaders",
    "signature",
    "token",
    "zipcode",
}

SENSITIVE_VALUE_MARKERS = (
    "authorization:",
    "bearer ",
    "bcrypt",
    "client_secret",
    "client-secret",
    "raw response",
    "raw_response",
    "signature",
    "token",
)

PHONE_PATTERN = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")
HASH_PATTERN = re.compile(r"^(id-hash-|sku-hash-|actor-hash-)?[a-zA-Z0-9_.:-]{8,160}$")


def _base_result(*, phase: str = "Shipping-2C") -> dict[str, Any]:
    return {
        "phase": phase,
        "status": "blocked",
        "skip_reason": None,
        "real_api_called": False,
        "platform_writes_enabled": False,
        "formal_order_sync_open": False,
        "formal_product_sync_open": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "shipping_mappings_written": False,
        "shipping_inventory_written": False,
        "operation_audit_rows_written": False,
        "real_database_written": False,
    }


def _normalize_platform(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_SHIPPING_PLATFORMS else None


def _normalize_key_part(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _clean_text(value: Any, *, max_length: int = 300) -> str:
    return str(value or "").strip()[:max_length]


def _normalize_sensitive_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _sensitive_fields(payload: Any) -> list[str]:
    forbidden: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_name = str(key)
                normalized = _normalize_sensitive_key(key_name)
                if normalized in {"rawresponsesaved", "secretssaved", "privacyfieldsredacted"}:
                    walk(nested)
                    continue
                if normalized.endswith("hash"):
                    walk(nested)
                    continue
                if normalized in SENSITIVE_KEY_MARKERS:
                    forbidden.add(normalized)
                    continue
                if any(part in normalized for part in ["token", "authorization", "headers", "signature", "bcrypt", "clientsecret"]):
                    forbidden.add(normalized)
                    continue
                if any(part in normalized for part in ["rawresponse", "rawrequest", "rawdata"]):
                    forbidden.add(normalized)
                    continue
                if ("orderid" in normalized or "productorderid" in normalized) and not normalized.endswith("hash"):
                    forbidden.add(normalized)
                    continue
                if any(part in normalized for part in ["buyer", "receiver", "phone", "address", "zipcode"]):
                    forbidden.add(normalized)
                    continue
                walk(nested)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                walk(item)
            return
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in SENSITIVE_VALUE_MARKERS):
                forbidden.add("sensitive_value")
            if PHONE_PATTERN.search(value):
                forbidden.add("sensitive_value")

    walk(payload)
    return sorted(forbidden)


def _safe_optional_hash(value: Any) -> str | None:
    text = _clean_text(value, max_length=160)
    if not text:
        return None
    return text if HASH_PATTERN.fullmatch(text) else None


def _actor_hash(actor_context: dict[str, Any] | None) -> str | None:
    if not isinstance(actor_context, dict):
        return None
    actor_id = actor_context.get("actor_id")
    if not actor_id:
        return None
    digest = hashlib.sha256(str(actor_id).encode("utf-8")).hexdigest()[:16]
    return f"actor-hash-{digest}"


def _stock_status(quantity: int, requested: str | None = None) -> str:
    requested_status = str(requested or "").strip().lower()
    if requested_status in {"available", "low_stock", "out_of_stock", "unknown"}:
        return requested_status
    if quantity <= 0:
        return "out_of_stock"
    if quantity <= 3:
        return "low_stock"
    return "available"


def _mapping_identity(row: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalize_key_part(row.get("match_product_name")),
        _normalize_key_part(row.get("match_option_name")),
    )


def _validate_payload(
    *,
    store_id: int,
    platform: str,
    mappings: list[dict[str, Any]],
    actor_context: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    if _sensitive_fields({"mappings": mappings, "actor_context": actor_context or {}}):
        return None, {
            "skip_reason": "shipping_sensitive_field_blocked",
            "forbidden_field_names": _sensitive_fields({"mappings": mappings, "actor_context": actor_context or {}}),
        }

    normalized_platform = _normalize_platform(platform)
    if normalized_platform is None:
        return None, {"skip_reason": "platform_not_supported"}
    if not isinstance(store_id, int) or store_id <= 0:
        return None, {"skip_reason": "store_id_invalid"}
    if not mappings:
        return None, {"skip_reason": "mapping_payload_empty"}

    normalized_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, item in enumerate(mappings):
        row = dict(item)
        product_name = _clean_text(row.get("match_product_name"))
        option_name = _clean_text(row.get("match_option_name"), max_length=300)
        inventory_code = _clean_text(row.get("logistics_inventory_code"), max_length=120)
        provider_name = _clean_text(row.get("logistics_provider_name"), max_length=160) or None
        if not product_name:
            return None, {"skip_reason": "match_product_name_required", "invalid_row_index": index}
        if not inventory_code:
            return None, {"skip_reason": "logistics_inventory_code_required", "invalid_row_index": index}

        platform_product_id_hash = _safe_optional_hash(row.get("platform_product_id_hash"))
        platform_option_id_hash = _safe_optional_hash(row.get("platform_option_id_hash"))
        if row.get("platform_product_id_hash") and platform_product_id_hash is None:
            return None, {"skip_reason": "platform_product_id_hash_invalid", "invalid_row_index": index}
        if row.get("platform_option_id_hash") and platform_option_id_hash is None:
            return None, {"skip_reason": "platform_option_id_hash_invalid", "invalid_row_index": index}

        try:
            current_stock_quantity = max(0, int(row.get("current_stock_quantity") or 0))
        except (TypeError, ValueError):
            return None, {"skip_reason": "current_stock_quantity_invalid", "invalid_row_index": index}
        try:
            match_priority = max(0, int(row.get("match_priority") or 100))
        except (TypeError, ValueError):
            return None, {"skip_reason": "match_priority_invalid", "invalid_row_index": index}

        identity = _mapping_identity({
            "match_product_name": product_name,
            "match_option_name": option_name,
        })
        if identity in seen_keys:
            return None, {"skip_reason": "duplicate_mapping_key_in_payload", "invalid_row_index": index}
        seen_keys.add(identity)

        normalized_rows.append({
            "store_id": store_id,
            "platform": normalized_platform,
            "match_product_name": product_name,
            "match_option_name": option_name,
            "normalized_product_name": identity[0],
            "normalized_option_name": identity[1],
            "platform_product_id_hash": platform_product_id_hash,
            "platform_option_id_hash": platform_option_id_hash,
            "internal_sku": _clean_text(row.get("internal_sku"), max_length=120) or None,
            "logistics_inventory_code": inventory_code,
            "logistics_provider_name": provider_name,
            "current_stock_quantity": current_stock_quantity,
            "stock_status": _stock_status(current_stock_quantity, row.get("stock_status")),
            "match_priority": match_priority,
            "note": _clean_text(row.get("note"), max_length=500) or None,
            "is_active": bool(row.get("is_active", True)),
        })

    return normalized_rows, {}


def _serialize_mapping(row: LogisticsInventoryMapping, item: LogisticsInventoryItem | None) -> dict[str, Any]:
    provider_name = row.logistics_provider_name or (item.logistics_provider_name if item else None)
    return {
        "id": row.id,
        "store_id": row.store_id,
        "platform": row.platform,
        "match_product_name": row.match_product_name,
        "match_option_name": row.match_option_name,
        "normalized_product_name": row.normalized_product_name,
        "normalized_option_name": row.normalized_option_name,
        "platform_product_id_hash": row.platform_product_id_hash,
        "platform_option_id_hash": row.platform_option_id_hash,
        "internal_sku": row.internal_sku,
        "logistics_inventory_code": row.logistics_inventory_code,
        "logistics_provider_name": provider_name,
        "match_priority": row.match_priority,
        "is_active": row.is_active,
        "mapping_version": row.mapping_version,
        "current_stock_quantity": int(item.current_stock_quantity if item else 0),
        "stock_status": item.stock_status if item else "unknown",
        "last_manual_checked_at": item.last_manual_checked_at.isoformat() if item and item.last_manual_checked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_logistics_inventory_mappings(
    db: Session,
    *,
    store_id: int,
    platform: str = "naver",
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    normalized_platform = _normalize_platform(platform)
    if normalized_platform is None:
        result = _base_result(phase="Shipping-2B")
        result.update({"status": "blocked", "skip_reason": "platform_not_supported"})
        return result

    mappings = db.scalars(
        select(LogisticsInventoryMapping)
        .where(
            LogisticsInventoryMapping.store_id == store_id,
            LogisticsInventoryMapping.platform == normalized_platform,
        )
        .order_by(LogisticsInventoryMapping.match_priority.asc(), LogisticsInventoryMapping.id.asc())
    ).all()
    inventory_items = db.scalars(
        select(LogisticsInventoryItem).where(
            LogisticsInventoryItem.store_id == store_id,
            LogisticsInventoryItem.platform == normalized_platform,
        )
    ).all()
    inventory_by_code = {item.logistics_inventory_code: item for item in inventory_items}
    items = [_serialize_mapping(mapping, inventory_by_code.get(mapping.logistics_inventory_code)) for mapping in mappings]
    return {
        **_base_result(phase="Shipping-2B"),
        "status": "ready",
        "business_message": (
            "已读取本地物流库存编号映射。"
            if items
            else "当前还没有本地物流库存编号映射，请先维护商品名称和选项名称对应的物流库存编号。"
        ),
        "store_id": store_id,
        "platform": normalized_platform,
        "items": items,
        "total": len(items),
        "inventory_item_count": len(inventory_items),
    }


def evaluate_mapping_and_stock_write_gate(
    db: Session,
    *,
    store_id: int,
    platform: str,
    mappings: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _base_result(phase="Shipping-2C")
    ensure_store_exists(db, store_id)
    normalized_rows, error = _validate_payload(
        store_id=store_id,
        platform=platform,
        mappings=mappings,
        actor_context=actor_context,
    )
    if error:
        result.update(error)
        return result
    if manual_approval is not True:
        result.update({"skip_reason": "manual_approval_required"})
        return result

    result.update({
        "status": "mapping_stock_write_gate_ready",
        "skip_reason": None,
        "manual_approval": True,
        "store_id": store_id,
        "platform": _normalize_platform(platform),
        "mapping_rows_ready": len(normalized_rows or []),
        "inventory_rows_ready": len({row["logistics_inventory_code"] for row in normalized_rows or []}),
        "business_message": "物流库存编号映射和库存维护已通过本地写入门禁，可进入受控本地写入。",
    })
    return result


def _audit_row_for_write(
    *,
    store_id: int,
    platform: str,
    actor_context: dict[str, Any] | None,
    counts: dict[str, int],
) -> dict[str, Any]:
    now = get_utc_now()
    fingerprint = hashlib.sha256(
        json.dumps({"store_id": store_id, "platform": platform, "counts": counts}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "created_at": now,
        "updated_at": now,
        "store_id": store_id,
        "platform": platform,
        "environment": "local",
        "actor_type": "human",
        "actor_id": _actor_hash(actor_context) or "actor-hash-shipping-local",
        "actor_label": "Local operator",
        "actor_role": str((actor_context or {}).get("role") or "admin")[:80],
        "action": "local_write_succeeded",
        "operation_phase": "Shipping-2D",
        "correlation_id": f"shipping-2d-{fingerprint}",
        "request_id": f"shipping-2d-write-{fingerprint}",
        "status": "success",
        "reason_code": "shipping_mapping_stock_local_write",
        "target_type": "settings",
        "target_id": None,
        "target_hash": f"id-hash-{fingerprint}",
        "target_label": "Logistics mapping and stock",
        "changed_field_names": ["logistics_inventory_mappings", "logistics_inventory_items"],
        "before_summary": {"manual_approval": True, "formal_sync_open": False},
        "after_summary": {
            "mapping_rows_changed": counts["mapping_rows_changed"],
            "inventory_rows_changed": counts["inventory_rows_changed"],
        },
        "counts_summary": {
            "shipping_mappings_written": counts["mapping_rows_changed"],
            "shipping_inventory_written": counts["inventory_rows_changed"],
            "orders_written": 0,
            "products_written": 0,
            "sync_logs_written": 0,
            "capability_results_written": 0,
        },
        "safety_flags": {
            "shipping_mapping_stock_local_write": True,
            "real_api_called": False,
            "platform_writes_enabled": False,
            "formal_sync_open": False,
            "orders_written": False,
            "products_written": False,
            "sync_log_written": False,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
        },
        "sensitive_scan_passed": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "notes": "Shipping assistant mapping and logistics stock local write. No platform API or order sync was executed.",
    }


def write_mapping_and_stock_local(
    db: Session,
    *,
    store_id: int,
    platform: str,
    mappings: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = evaluate_mapping_and_stock_write_gate(
        db,
        store_id=store_id,
        platform=platform,
        mappings=mappings,
        manual_approval=manual_approval,
        actor_context=actor_context,
    )
    result = {**gate, "phase": "Shipping-2D"}
    if gate.get("status") != "mapping_stock_write_gate_ready":
        result.update({
            "shipping_mappings_written": False,
            "shipping_inventory_written": False,
            "real_database_written": False,
        })
        return result

    normalized_rows, _error = _validate_payload(
        store_id=store_id,
        platform=platform,
        mappings=mappings,
        actor_context=actor_context,
    )
    assert normalized_rows is not None
    actor_hash = _actor_hash(actor_context)
    now = get_utc_now()
    created_mappings = 0
    updated_mappings = 0
    created_inventory_items = 0
    updated_inventory_items = 0
    changed_mapping_ids: list[int] = []

    for row in normalized_rows:
        inventory_item = db.scalar(
            select(LogisticsInventoryItem).where(
                LogisticsInventoryItem.store_id == store_id,
                LogisticsInventoryItem.platform == row["platform"],
                LogisticsInventoryItem.logistics_inventory_code == row["logistics_inventory_code"],
            )
        )
        if inventory_item is None:
            inventory_item = LogisticsInventoryItem(
                store_id=store_id,
                platform=row["platform"],
                logistics_inventory_code=row["logistics_inventory_code"],
                logistics_provider_name=row["logistics_provider_name"],
                current_stock_quantity=row["current_stock_quantity"],
                stock_status=row["stock_status"],
                last_manual_checked_at=now,
                last_manual_updated_by_actor_hash=actor_hash,
                note=row["note"],
                is_active=row["is_active"],
            )
            db.add(inventory_item)
            created_inventory_items += 1
        else:
            inventory_item.logistics_provider_name = row["logistics_provider_name"] or inventory_item.logistics_provider_name
            inventory_item.current_stock_quantity = row["current_stock_quantity"]
            inventory_item.stock_status = row["stock_status"]
            inventory_item.last_manual_checked_at = now
            inventory_item.last_manual_updated_by_actor_hash = actor_hash
            inventory_item.note = row["note"]
            inventory_item.is_active = row["is_active"]
            updated_inventory_items += 1

        mapping = db.scalar(
            select(LogisticsInventoryMapping).where(
                LogisticsInventoryMapping.store_id == store_id,
                LogisticsInventoryMapping.platform == row["platform"],
                LogisticsInventoryMapping.normalized_product_name == row["normalized_product_name"],
                LogisticsInventoryMapping.normalized_option_name == row["normalized_option_name"],
            )
        )
        if mapping is None:
            mapping = LogisticsInventoryMapping(
                store_id=store_id,
                platform=row["platform"],
                match_product_name=row["match_product_name"],
                match_option_name=row["match_option_name"],
                normalized_product_name=row["normalized_product_name"],
                normalized_option_name=row["normalized_option_name"],
                platform_product_id_hash=row["platform_product_id_hash"],
                platform_option_id_hash=row["platform_option_id_hash"],
                internal_sku=row["internal_sku"],
                logistics_inventory_code=row["logistics_inventory_code"],
                logistics_provider_name=row["logistics_provider_name"],
                match_priority=row["match_priority"],
                is_active=row["is_active"],
                mapping_version=SHIPPING_MAPPING_VERSION,
                created_by_actor_hash=actor_hash,
                updated_by_actor_hash=actor_hash,
            )
            db.add(mapping)
            db.flush()
            created_mappings += 1
        else:
            mapping.match_product_name = row["match_product_name"]
            mapping.match_option_name = row["match_option_name"]
            mapping.platform_product_id_hash = row["platform_product_id_hash"]
            mapping.platform_option_id_hash = row["platform_option_id_hash"]
            mapping.internal_sku = row["internal_sku"]
            mapping.logistics_inventory_code = row["logistics_inventory_code"]
            mapping.logistics_provider_name = row["logistics_provider_name"]
            mapping.match_priority = row["match_priority"]
            mapping.is_active = row["is_active"]
            mapping.mapping_version = SHIPPING_MAPPING_VERSION
            mapping.updated_by_actor_hash = actor_hash
            db.flush()
            updated_mappings += 1
        changed_mapping_ids.append(mapping.id)

    counts = {
        "mapping_rows_changed": created_mappings + updated_mappings,
        "inventory_rows_changed": created_inventory_items + updated_inventory_items,
    }
    audit_result = write_operation_audit_log_local(
        db,
        _audit_row_for_write(
            store_id=store_id,
            platform=_normalize_platform(platform) or "naver",
            actor_context=actor_context,
            counts=counts,
        ),
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )
    if audit_result.get("status") != "audit_row_written":
        db.rollback()
        result.update({
            "status": "mapping_stock_write_blocked",
            "skip_reason": audit_result.get("skip_reason") or "audit_write_failed",
            "shipping_mappings_written": False,
            "shipping_inventory_written": False,
            "operation_audit_rows_written": False,
            "real_database_written": False,
        })
        return result

    listing = list_logistics_inventory_mappings(db, store_id=store_id, platform=platform)
    result.update({
        "status": "mapping_stock_local_write_succeeded",
        "skip_reason": None,
        "business_message": "物流库存编号映射和物流库存已保存到本地。当前不会写订单、商品、同步日志，也不会调用 Naver 发货接口。",
        "created_mappings": created_mappings,
        "updated_mappings": updated_mappings,
        "created_inventory_items": created_inventory_items,
        "updated_inventory_items": updated_inventory_items,
        "mapping_ids": changed_mapping_ids,
        "items": listing["items"],
        "total": listing["total"],
        "shipping_mappings_written": counts["mapping_rows_changed"] > 0,
        "shipping_inventory_written": counts["inventory_rows_changed"] > 0,
        "operation_audit_rows_written": True,
        "operation_audit_log_id": audit_result.get("audit_log_id"),
        "real_database_written": True,
        "real_api_called": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result
