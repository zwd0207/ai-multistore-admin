from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import get_utc_now
from app.models.shipping import (
    LogisticsInventoryItem,
    LogisticsInventoryMapping,
    ShippingExportBatch,
    ShippingExportBatchRow,
    ShippingTrackingImportBatch,
    ShippingTrackingImportRow,
)
from app.models.order import Order
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.store_service import ensure_store_exists


SHIPPING_WRITE_SCOPE = "shipping_mapping_stock_local"
SHIPPING_MAPPING_VERSION = "shipping_mapping_v1"
SHIPPING_EXPORT_MAPPING_VERSION = "shipping_export_mock_v1"
SHIPPING_EXPORT_LOCAL_MAPPING_VERSION = "shipping_export_v1"
SHIPPING_EXPORT_FILE_TYPE = "shipping_request"
SHIPPING_EXPORT_FILE_FORMAT = "xlsx"
SHIPPING_TRACKING_IMPORT_MAPPING_VERSION = "shipping_tracking_import_mock_v1"
SHIPPING_TRACKING_IMPORT_LOCAL_MAPPING_VERSION = "shipping_tracking_import_v1"
SHIPPING_TRACKING_UPLOAD_FILE_TYPE = "tracking_upload"
DEFAULT_SHIPPING_EXPORT_DIR = Path(__file__).resolve().parents[2] / "exports" / "shipping"
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


def _validate_shipping_export_rows(export_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    if not export_rows:
        return None, {"skip_reason": "shipping_export_rows_required"}
    if len(export_rows) > 100:
        return None, {"skip_reason": "shipping_export_row_limit_exceeded"}

    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(export_rows):
        row = dict(item)
        product_name = _clean_text(row.get("product_name") or row.get("productName"), max_length=300)
        option_name = _clean_text(row.get("option_name") or row.get("optionName"), max_length=300)
        logistics_inventory_code = _clean_text(
            row.get("logistics_inventory_code") or row.get("logisticsInventoryCode"),
            max_length=120,
        )
        logistics_provider_name = _clean_text(
            row.get("logistics_provider_name") or row.get("logisticsProviderName"),
            max_length=160,
        ) or None
        order_reference = _clean_text(row.get("order_reference") or row.get("orderNo") or row.get("order_no"), max_length=120)
        if not product_name:
            return None, {"skip_reason": "export_product_name_required", "invalid_row_index": index}
        if not logistics_inventory_code:
            return None, {"skip_reason": "export_logistics_inventory_code_required", "invalid_row_index": index}
        try:
            quantity = max(1, int(row.get("quantity") or 0))
        except (TypeError, ValueError):
            return None, {"skip_reason": "export_quantity_invalid", "invalid_row_index": index}
        try:
            logistics_current_stock = max(
                0,
                int(row.get("logistics_current_stock") or row.get("logisticsCurrentStock") or 0),
            )
        except (TypeError, ValueError):
            return None, {"skip_reason": "export_logistics_stock_invalid", "invalid_row_index": index}

        platform_product_id_hash = _safe_optional_hash(row.get("platform_product_id_hash") or row.get("platformProductIdHash"))
        platform_option_id_hash = _safe_optional_hash(row.get("platform_option_id_hash") or row.get("platformOptionIdHash"))
        if (row.get("platform_product_id_hash") or row.get("platformProductIdHash")) and platform_product_id_hash is None:
            return None, {"skip_reason": "export_platform_product_id_hash_invalid", "invalid_row_index": index}
        if (row.get("platform_option_id_hash") or row.get("platformOptionIdHash")) and platform_option_id_hash is None:
            return None, {"skip_reason": "export_platform_option_id_hash_invalid", "invalid_row_index": index}

        normalized_rows.append({
            "row_index": index + 1,
            "order_reference": order_reference or f"local-order-row-{index + 1}",
            "product_name": product_name,
            "option_name": option_name,
            "quantity": quantity,
            "logistics_inventory_code": logistics_inventory_code,
            "logistics_provider_name": logistics_provider_name,
            "logistics_current_stock": logistics_current_stock,
            "platform_product_id_hash": platform_product_id_hash,
            "platform_option_id_hash": platform_option_id_hash,
            "internal_sku": _clean_text(row.get("internal_sku") or row.get("internalSku"), max_length=120) or None,
            "match_status": "matched",
        })
    return normalized_rows, {}


def _validate_tracking_import_rows(tracking_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    if not tracking_rows:
        return None, {"skip_reason": "tracking_import_rows_required"}
    if len(tracking_rows) > 200:
        return None, {"skip_reason": "tracking_import_row_limit_exceeded"}

    normalized_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    duplicate_count = 0
    for index, item in enumerate(tracking_rows):
        row = dict(item)
        order_reference = _clean_text(
            row.get("order_reference") or row.get("orderReference") or row.get("order_no") or row.get("orderNo"),
            max_length=160,
        )
        product_order_reference = _clean_text(
            row.get("product_order_reference")
            or row.get("productOrderReference")
            or row.get("product_order_no")
            or row.get("productOrderNo"),
            max_length=160,
        )
        logistics_inventory_code = _clean_text(
            row.get("logistics_inventory_code") or row.get("logisticsInventoryCode"),
            max_length=120,
        )
        carrier = _clean_text(row.get("carrier"), max_length=120)
        tracking_number = _clean_text(row.get("tracking_number") or row.get("trackingNumber"), max_length=120)
        shipped_at = _clean_text(row.get("shipped_at") or row.get("shippedAt"), max_length=80) or None
        operator_note = _clean_text(row.get("operator_note") or row.get("operatorNote"), max_length=300) or None

        if not order_reference and not product_order_reference:
            return None, {"skip_reason": "tracking_order_reference_required", "invalid_row_index": index}
        if not carrier:
            return None, {"skip_reason": "tracking_carrier_required", "invalid_row_index": index}
        if not tracking_number:
            return None, {"skip_reason": "tracking_number_required", "invalid_row_index": index}

        dedupe_key = (order_reference or product_order_reference, tracking_number)
        duplicate_in_payload = dedupe_key in seen_keys
        if duplicate_in_payload:
            duplicate_count += 1
        seen_keys.add(dedupe_key)

        normalized_rows.append({
            "row_index": index + 1,
            "order_reference": order_reference,
            "product_order_reference": product_order_reference,
            "logistics_inventory_code": logistics_inventory_code,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "shipped_at": shipped_at,
            "row_status": "duplicate_in_upload" if duplicate_in_payload else "ready_for_future_review",
            "operator_note": operator_note,
            "future_write_allowed": False,
        })

    return normalized_rows, {"duplicate_count": duplicate_count}


def evaluate_real_excel_generation_mock_gate(
    *,
    store_id: int,
    platform: str,
    export_rows: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
    file_type: str = SHIPPING_EXPORT_FILE_TYPE,
    file_format: str = SHIPPING_EXPORT_FILE_FORMAT,
    include_receiver_privacy: bool = False,
    export_record_schema_acknowledged: bool = False,
    audit_linkage_acknowledged: bool = False,
    tracking_import_contract_acknowledged: bool = False,
) -> dict[str, Any]:
    result = {
        **_base_result(phase="Shipping-2H"),
        "manual_approval": bool(manual_approval),
        "file_type": file_type,
        "file_format": file_format,
        "file_generated": False,
        "file_persisted": False,
        "export_record_written": False,
        "download_record_written": False,
        "tracking_number_import_open": False,
        "receiver_privacy_included": False,
        "export_record_schema_planned": bool(export_record_schema_acknowledged),
        "audit_linkage_planned": bool(audit_linkage_acknowledged),
        "tracking_import_contract_planned": bool(tracking_import_contract_acknowledged),
        "mapping_version": SHIPPING_EXPORT_MAPPING_VERSION,
    }

    forbidden_fields = _sensitive_fields({
        "export_rows": export_rows,
        "actor_context": actor_context or {},
    })
    if forbidden_fields:
        result.update({
            "skip_reason": "shipping_export_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    normalized_platform = _normalize_platform(platform)
    if normalized_platform is None:
        result["skip_reason"] = "platform_not_supported"
        return result
    if not isinstance(store_id, int) or store_id <= 0:
        result["skip_reason"] = "store_id_invalid"
        return result
    if file_type != SHIPPING_EXPORT_FILE_TYPE:
        result["skip_reason"] = "shipping_export_file_type_not_supported"
        return result
    if str(file_format).lower() != SHIPPING_EXPORT_FILE_FORMAT:
        result["skip_reason"] = "shipping_export_file_format_not_supported"
        return result
    if include_receiver_privacy:
        result["skip_reason"] = "receiver_privacy_separate_approval_required"
        return result
    if manual_approval is not True:
        result["skip_reason"] = "manual_approval_required"
        return result
    if export_record_schema_acknowledged is not True:
        result["skip_reason"] = "export_record_schema_plan_required"
        return result
    if audit_linkage_acknowledged is not True:
        result["skip_reason"] = "audit_linkage_plan_required"
        return result

    normalized_rows, error = _validate_shipping_export_rows(export_rows)
    if error:
        result.update(error)
        return result

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "store_id": store_id,
                "platform": normalized_platform,
                "rows": normalized_rows,
                "file_type": file_type,
                "file_format": SHIPPING_EXPORT_FILE_FORMAT,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    result.update({
        "status": "real_excel_generation_mock_ready",
        "skip_reason": None,
        "store_id": store_id,
        "platform": normalized_platform,
        "row_count": len(normalized_rows or []),
        "matched_row_count": len(normalized_rows or []),
        "unmatched_row_count": 0,
        "file_name_preview": f"{normalized_platform}-shipping-request-store-{store_id}-mock.xlsx",
        "file_hash_planned": f"sha256-planned-{fingerprint}",
        "export_rows_preview": normalized_rows,
        "business_message": (
            "真实 Excel 生成 mock 门禁已通过；当前只确认导出字段、导出记录和审计联动边界，"
            "不会创建文件、不会写导出记录，也不会调用平台或物流商接口。"
        ),
    })
    return result


def evaluate_tracking_number_import_mock_gate(
    *,
    store_id: int,
    platform: str,
    tracking_rows: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
    file_type: str = SHIPPING_TRACKING_UPLOAD_FILE_TYPE,
    file_format: str = SHIPPING_EXPORT_FILE_FORMAT,
    parser_contract_acknowledged: bool = False,
) -> dict[str, Any]:
    result = {
        **_base_result(phase="Shipping-4B"),
        "manual_approval": bool(manual_approval),
        "file_type": file_type,
        "file_format": file_format,
        "parser_contract_acknowledged": bool(parser_contract_acknowledged),
        "tracking_number_import_open": False,
        "tracking_numbers_written": False,
        "shipment_writeback_open": False,
        "shipment_writeback_called": False,
        "file_parsed": False,
        "import_record_written": False,
        "mapping_version": SHIPPING_TRACKING_IMPORT_MAPPING_VERSION,
    }

    forbidden_fields = _sensitive_fields({
        "tracking_rows": tracking_rows,
        "actor_context": actor_context or {},
    })
    if forbidden_fields:
        result.update({
            "skip_reason": "tracking_import_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    normalized_platform = _normalize_platform(platform)
    if normalized_platform is None:
        result["skip_reason"] = "platform_not_supported"
        return result
    if not isinstance(store_id, int) or store_id <= 0:
        result["skip_reason"] = "store_id_invalid"
        return result
    if file_type != SHIPPING_TRACKING_UPLOAD_FILE_TYPE:
        result["skip_reason"] = "tracking_file_type_not_supported"
        return result
    if str(file_format).lower() != SHIPPING_EXPORT_FILE_FORMAT:
        result["skip_reason"] = "tracking_file_format_not_supported"
        return result
    if manual_approval is not True:
        result["skip_reason"] = "manual_approval_required"
        return result
    if parser_contract_acknowledged is not True:
        result["skip_reason"] = "tracking_parser_contract_required"
        return result

    normalized_rows, error = _validate_tracking_import_rows(tracking_rows)
    if error and error.get("skip_reason"):
        result.update(error)
        return result

    duplicate_count = int((error or {}).get("duplicate_count") or 0)
    result.update({
        "status": "tracking_import_mock_parse_ready",
        "skip_reason": None,
        "store_id": store_id,
        "platform": normalized_platform,
        "file_parsed": True,
        "row_count": len(normalized_rows or []),
        "ready_row_count": len([row for row in normalized_rows or [] if row["row_status"] == "ready_for_future_review"]),
        "duplicate_row_count": duplicate_count,
        "tracking_rows_preview": normalized_rows,
        "business_message": (
            "物流单号导入 mock 解析门禁已通过。当前只验证字段、重复行和安全边界；"
            "不会写订单、不会保存导入记录，也不会回填 Naver 发货。"
        ),
    })
    return result


def _serialize_export_batch(row: ShippingExportBatch, *, rows: list[ShippingExportBatchRow] | None = None) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "store_id": row.store_id,
        "platform": row.platform,
        "file_type": row.file_type,
        "file_format": row.file_format,
        "file_name": row.file_name,
        "file_path": row.file_path,
        "file_sha256": row.file_sha256,
        "row_count": row.row_count,
        "matched_row_count": row.matched_row_count,
        "unmatched_row_count": row.unmatched_row_count,
        "audit_correlation_id": row.audit_correlation_id,
        "export_status": row.export_status,
        "include_receiver_privacy": row.include_receiver_privacy,
        "file_generated": row.file_generated,
        "file_persisted": row.file_persisted,
        "raw_response_saved": row.raw_response_saved,
        "secrets_saved": row.secrets_saved,
        "privacy_fields_redacted": row.privacy_fields_redacted,
        "mapping_version": row.mapping_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if rows is not None:
        payload["rows"] = [
            {
                "id": item.id,
                "export_batch_id": item.export_batch_id,
                "store_id": item.store_id,
                "platform": item.platform,
                "order_reference": item.order_reference,
                "product_name": item.product_name,
                "option_name": item.option_name,
                "quantity": item.quantity,
                "logistics_inventory_code": item.logistics_inventory_code,
                "logistics_provider_name": item.logistics_provider_name,
                "internal_sku": item.internal_sku,
                "platform_product_id_hash": item.platform_product_id_hash,
                "platform_option_id_hash": item.platform_option_id_hash,
                "row_status": item.row_status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows
        ]
    return payload


def list_shipping_export_history(
    db: Session,
    *,
    store_id: int,
    platform: str = "naver",
    limit: int = 20,
    offset: int = 0,
    include_rows: bool = False,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    normalized_platform = _normalize_platform(platform)
    result = {
        **_base_result(phase="Shipping-4D"),
        "readonly_route": True,
        "export_history_readonly": True,
        "tracking_number_import_open": False,
        "shipment_writeback_open": False,
        "import_record_written": False,
    }
    if normalized_platform is None:
        result.update({"status": "blocked", "skip_reason": "platform_not_supported"})
        return result

    bounded_limit = min(max(int(limit or 20), 1), 100)
    bounded_offset = max(int(offset or 0), 0)
    total = db.scalar(
        select(func.count(ShippingExportBatch.id)).where(
            ShippingExportBatch.store_id == store_id,
            ShippingExportBatch.platform == normalized_platform,
        )
    ) or 0
    batches = db.scalars(
        select(ShippingExportBatch)
        .where(
            ShippingExportBatch.store_id == store_id,
            ShippingExportBatch.platform == normalized_platform,
        )
        .order_by(ShippingExportBatch.created_at.desc(), ShippingExportBatch.id.desc())
        .offset(bounded_offset)
        .limit(bounded_limit)
    ).all()
    rows_by_batch: dict[int, list[ShippingExportBatchRow]] = {}
    if include_rows and batches:
        batch_ids = [item.id for item in batches]
        row_items = db.scalars(
            select(ShippingExportBatchRow)
            .where(ShippingExportBatchRow.export_batch_id.in_(batch_ids))
            .order_by(ShippingExportBatchRow.export_batch_id.desc(), ShippingExportBatchRow.id.asc())
        ).all()
        for item in row_items:
            rows_by_batch.setdefault(item.export_batch_id, []).append(item)

    items = [
        _serialize_export_batch(batch, rows=rows_by_batch.get(batch.id) if include_rows else None)
        for batch in batches
    ]
    result.update({
        "status": "shipping_export_history_ready",
        "skip_reason": None,
        "store_id": store_id,
        "platform": normalized_platform,
        "total": int(total),
        "limit": bounded_limit,
        "offset": bounded_offset,
        "include_rows": bool(include_rows),
        "items": items,
        "business_message": (
            "已读取本地发货 Excel 导出历史。"
            if items
            else "当前还没有本地发货 Excel 导出记录。"
        ),
        "real_database_written": False,
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


def evaluate_tracking_import_local_write_gate(
    *,
    store_id: int,
    platform: str,
    tracking_rows: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
    file_type: str = SHIPPING_TRACKING_UPLOAD_FILE_TYPE,
    file_format: str = SHIPPING_EXPORT_FILE_FORMAT,
    parser_contract_acknowledged: bool = False,
    source_file_name: str | None = None,
) -> dict[str, Any]:
    gate = evaluate_tracking_number_import_mock_gate(
        store_id=store_id,
        platform=platform,
        tracking_rows=tracking_rows,
        manual_approval=manual_approval,
        actor_context=actor_context,
        file_type=file_type,
        file_format=file_format,
        parser_contract_acknowledged=parser_contract_acknowledged,
    )
    result = {
        **gate,
        "phase": "Shipping-5C",
        "tracking_import_records_written": False,
        "tracking_import_batch_written": False,
        "tracking_import_rows_written": False,
        "operation_audit_rows_written": False,
        "source_file_name": _clean_text(source_file_name, max_length=255) or None,
    }
    forbidden_file_fields = _sensitive_fields({"source_file_name": source_file_name or ""})
    if forbidden_file_fields:
        result.update({
            "status": "blocked",
            "skip_reason": "tracking_import_sensitive_field_blocked",
            "forbidden_field_names": forbidden_file_fields,
            "source_file_name": None,
        })
        return result
    if gate.get("status") != "tracking_import_mock_parse_ready":
        return result

    result.update({
        "status": "tracking_import_local_write_gate_ready",
        "business_message": (
            "物流单号导入本地写入门禁已通过。下一步只会记录导入批次和行，"
            "不会更新订单状态，也不会回填 Naver。"
        ),
    })
    return result


def _audit_row_for_tracking_import(
    *,
    store_id: int,
    platform: str,
    actor_context: dict[str, Any] | None,
    import_batch_id: int,
    row_count: int,
    ready_row_count: int,
    duplicate_row_count: int,
    correlation_id: str,
) -> dict[str, Any]:
    now = get_utc_now()
    return {
        "created_at": now,
        "updated_at": now,
        "store_id": store_id,
        "platform": platform,
        "environment": "local",
        "actor_type": "human",
        "actor_id": _actor_hash(actor_context) or "actor-hash-shipping-tracking-import-local",
        "actor_label": "Local operator",
        "actor_role": str((actor_context or {}).get("role") or "admin")[:80],
        "action": "local_write_succeeded",
        "operation_phase": "Shipping-5D",
        "correlation_id": correlation_id,
        "request_id": f"shipping-5d-tracking-import-{import_batch_id}",
        "status": "success",
        "reason_code": "shipping_tracking_import_local_write",
        "target_type": "settings",
        "target_id": str(import_batch_id),
        "target_hash": f"id-hash-{hashlib.sha256(correlation_id.encode('utf-8')).hexdigest()[:16]}",
        "target_label": "Shipping tracking import record",
        "changed_field_names": ["shipping_tracking_import_batches", "shipping_tracking_import_rows"],
        "before_summary": {"manual_approval": True, "tracking_records_written": False},
        "after_summary": {
            "row_count": row_count,
            "ready_row_count": ready_row_count,
            "duplicate_row_count": duplicate_row_count,
        },
        "counts_summary": {
            "shipping_tracking_import_batches_written": 1,
            "shipping_tracking_import_rows_written": row_count,
            "orders_written": 0,
            "products_written": 0,
            "sync_logs_written": 0,
            "capability_results_written": 0,
        },
        "safety_flags": {
            "shipping_tracking_import_local_write": True,
            "real_api_called": False,
            "platform_writes_enabled": False,
            "shipment_writeback_called": False,
            "formal_sync_open": False,
            "orders_written": False,
            "orders_updated": False,
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
        "notes": "Approved local tracking import record write. No Naver shipment writeback or logistics-provider API was called.",
    }


def write_tracking_import_local(
    db: Session,
    *,
    store_id: int,
    platform: str,
    tracking_rows: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
    file_type: str = SHIPPING_TRACKING_UPLOAD_FILE_TYPE,
    file_format: str = SHIPPING_EXPORT_FILE_FORMAT,
    parser_contract_acknowledged: bool = False,
    source_file_name: str | None = None,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    gate = evaluate_tracking_import_local_write_gate(
        store_id=store_id,
        platform=platform,
        tracking_rows=tracking_rows,
        manual_approval=manual_approval,
        actor_context=actor_context,
        file_type=file_type,
        file_format=file_format,
        parser_contract_acknowledged=parser_contract_acknowledged,
        source_file_name=source_file_name,
    )
    result = {**gate, "phase": "Shipping-5D"}
    if gate.get("status") != "tracking_import_local_write_gate_ready":
        result.update({
            "tracking_import_records_written": False,
            "tracking_import_batch_written": False,
            "tracking_import_rows_written": False,
            "operation_audit_rows_written": False,
            "real_database_written": False,
        })
        return result

    normalized_platform = _normalize_platform(platform) or "naver"
    normalized_rows = list(gate.get("tracking_rows_preview") or [])
    now = get_utc_now()
    actor_hash = _actor_hash(actor_context)
    ready_row_count = len([row for row in normalized_rows if row["row_status"] == "ready_for_future_review"])
    duplicate_row_count = len([row for row in normalized_rows if row["row_status"] == "duplicate_in_upload"])
    blocked_row_count = len([row for row in normalized_rows if row["row_status"] == "blocked"])
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "store_id": store_id,
                "platform": normalized_platform,
                "rows": normalized_rows,
                "created_at": now.isoformat(),
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:12]
    correlation_id = f"shipping-5d-{fingerprint}"

    try:
        import_batch = ShippingTrackingImportBatch(
            store_id=store_id,
            platform=normalized_platform,
            file_type=SHIPPING_TRACKING_UPLOAD_FILE_TYPE,
            file_format=SHIPPING_EXPORT_FILE_FORMAT,
            source_file_name=_clean_text(source_file_name, max_length=255) or None,
            row_count=len(normalized_rows),
            ready_row_count=ready_row_count,
            duplicate_row_count=duplicate_row_count,
            blocked_row_count=blocked_row_count,
            actor_id_hash=actor_hash,
            audit_correlation_id=correlation_id,
            import_status="recorded",
            parser_contract_acknowledged=True,
            tracking_number_import_open=False,
            shipment_writeback_called=False,
            orders_updated=False,
            raw_response_saved=False,
            secrets_saved=False,
            privacy_fields_redacted=True,
            mapping_version=SHIPPING_TRACKING_IMPORT_LOCAL_MAPPING_VERSION,
            created_at=now,
            updated_at=now,
        )
        db.add(import_batch)
        db.flush()
        for row in normalized_rows:
            db.add(ShippingTrackingImportRow(
                import_batch_id=import_batch.id,
                store_id=store_id,
                platform=normalized_platform,
                order_reference=row["order_reference"],
                product_order_reference=row["product_order_reference"],
                logistics_inventory_code=row["logistics_inventory_code"] or None,
                carrier=row["carrier"],
                tracking_number=row["tracking_number"],
                shipped_at=row["shipped_at"],
                row_status=row["row_status"],
                operator_note=row["operator_note"],
                future_write_allowed=False,
                created_at=now,
            ))

        audit_result = write_operation_audit_log_local(
            db,
            _audit_row_for_tracking_import(
                store_id=store_id,
                platform=normalized_platform,
                actor_context=actor_context,
                import_batch_id=import_batch.id,
                row_count=len(normalized_rows),
                ready_row_count=ready_row_count,
                duplicate_row_count=duplicate_row_count,
                correlation_id=correlation_id,
            ),
            write_enabled=True,
            manual_approval=True,
            local_write_scope=LOCAL_WRITER_SCOPE,
        )
        if audit_result.get("status") != "audit_row_written":
            db.rollback()
            result.update({
                "status": "tracking_import_local_write_blocked",
                "skip_reason": audit_result.get("skip_reason") or "audit_write_failed",
                "tracking_import_records_written": False,
                "tracking_import_batch_written": False,
                "tracking_import_rows_written": False,
                "operation_audit_rows_written": False,
                "real_database_written": False,
            })
            return result
    except Exception:
        db.rollback()
        raise

    result.update({
        "status": "tracking_import_local_write_succeeded",
        "skip_reason": None,
        "business_message": "物流单号导入记录已保存到本地。当前不会更新订单，也不会回填 Naver 发货。",
        "import_batch_id": import_batch.id,
        "row_count": len(normalized_rows),
        "ready_row_count": ready_row_count,
        "duplicate_row_count": duplicate_row_count,
        "blocked_row_count": blocked_row_count,
        "audit_correlation_id": correlation_id,
        "operation_audit_log_id": audit_result.get("audit_log_id"),
        "tracking_import_records_written": True,
        "tracking_import_batch_written": True,
        "tracking_import_rows_written": True,
        "operation_audit_rows_written": True,
        "real_database_written": True,
        "real_api_called": False,
        "tracking_number_import_open": False,
        "tracking_numbers_written": False,
        "shipment_writeback_called": False,
        "shipment_writeback_open": False,
        "orders_written": False,
        "orders_updated": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_order_sync_open": False,
        "platform_writes_enabled": False,
        "tracking_rows_preview": normalized_rows,
    })
    return result


def _serialize_tracking_import_batch(
    row: ShippingTrackingImportBatch,
    *,
    rows: list[ShippingTrackingImportRow] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "store_id": row.store_id,
        "platform": row.platform,
        "file_type": row.file_type,
        "file_format": row.file_format,
        "source_file_name": row.source_file_name,
        "row_count": row.row_count,
        "ready_row_count": row.ready_row_count,
        "duplicate_row_count": row.duplicate_row_count,
        "blocked_row_count": row.blocked_row_count,
        "audit_correlation_id": row.audit_correlation_id,
        "import_status": row.import_status,
        "parser_contract_acknowledged": row.parser_contract_acknowledged,
        "tracking_number_import_open": row.tracking_number_import_open,
        "shipment_writeback_called": row.shipment_writeback_called,
        "orders_updated": row.orders_updated,
        "raw_response_saved": row.raw_response_saved,
        "secrets_saved": row.secrets_saved,
        "privacy_fields_redacted": row.privacy_fields_redacted,
        "mapping_version": row.mapping_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if rows is not None:
        payload["rows"] = [
            {
                "id": item.id,
                "import_batch_id": item.import_batch_id,
                "store_id": item.store_id,
                "platform": item.platform,
                "order_reference": item.order_reference,
                "product_order_reference": item.product_order_reference,
                "logistics_inventory_code": item.logistics_inventory_code,
                "carrier": item.carrier,
                "tracking_number": item.tracking_number,
                "shipped_at": item.shipped_at,
                "row_status": item.row_status,
                "operator_note": item.operator_note,
                "future_write_allowed": item.future_write_allowed,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows
        ]
    return payload


def list_shipping_tracking_import_history(
    db: Session,
    *,
    store_id: int,
    platform: str = "naver",
    limit: int = 20,
    offset: int = 0,
    include_rows: bool = False,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    normalized_platform = _normalize_platform(platform)
    result = {
        **_base_result(phase="Shipping-5E"),
        "readonly_route": True,
        "tracking_import_history_readonly": True,
        "tracking_number_import_open": False,
        "shipment_writeback_open": False,
        "shipment_writeback_called": False,
        "orders_updated": False,
    }
    if normalized_platform is None:
        result.update({"status": "blocked", "skip_reason": "platform_not_supported"})
        return result

    bounded_limit = min(max(int(limit or 20), 1), 100)
    bounded_offset = max(int(offset or 0), 0)
    total = db.scalar(
        select(func.count(ShippingTrackingImportBatch.id)).where(
            ShippingTrackingImportBatch.store_id == store_id,
            ShippingTrackingImportBatch.platform == normalized_platform,
        )
    ) or 0
    batches = db.scalars(
        select(ShippingTrackingImportBatch)
        .where(
            ShippingTrackingImportBatch.store_id == store_id,
            ShippingTrackingImportBatch.platform == normalized_platform,
        )
        .order_by(ShippingTrackingImportBatch.created_at.desc(), ShippingTrackingImportBatch.id.desc())
        .offset(bounded_offset)
        .limit(bounded_limit)
    ).all()
    rows_by_batch: dict[int, list[ShippingTrackingImportRow]] = {}
    if include_rows and batches:
        batch_ids = [item.id for item in batches]
        row_items = db.scalars(
            select(ShippingTrackingImportRow)
            .where(ShippingTrackingImportRow.import_batch_id.in_(batch_ids))
            .order_by(ShippingTrackingImportRow.import_batch_id.desc(), ShippingTrackingImportRow.id.asc())
        ).all()
        for item in row_items:
            rows_by_batch.setdefault(item.import_batch_id, []).append(item)

    items = [
        _serialize_tracking_import_batch(batch, rows=rows_by_batch.get(batch.id) if include_rows else None)
        for batch in batches
    ]
    result.update({
        "status": "tracking_import_history_ready",
        "skip_reason": None,
        "store_id": store_id,
        "platform": normalized_platform,
        "total": int(total),
        "limit": bounded_limit,
        "offset": bounded_offset,
        "include_rows": bool(include_rows),
        "items": items,
        "business_message": (
            "已读取本地物流单号导入记录。"
            if items
            else "当前还没有本地物流单号导入记录。"
        ),
        "real_database_written": False,
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


def _tracking_rows_from_import_batch(
    db: Session,
    *,
    store_id: int,
    platform: str,
    import_batch_id: int,
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ShippingTrackingImportRow)
        .where(
            ShippingTrackingImportRow.import_batch_id == import_batch_id,
            ShippingTrackingImportRow.store_id == store_id,
            ShippingTrackingImportRow.platform == platform,
        )
        .order_by(ShippingTrackingImportRow.id.asc())
    ).all()
    return [
        {
            "order_reference": item.order_reference,
            "product_order_reference": item.product_order_reference,
            "logistics_inventory_code": item.logistics_inventory_code,
            "carrier": item.carrier,
            "tracking_number": item.tracking_number,
            "shipped_at": item.shipped_at,
            "operator_note": item.operator_note,
        }
        for item in rows
    ]


def evaluate_tracking_order_match_readonly(
    db: Session,
    *,
    store_id: int,
    platform: str = "naver",
    import_batch_id: int | None = None,
    tracking_rows: list[dict[str, Any]] | None = None,
    matching_contract_acknowledged: bool = False,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    normalized_platform = _normalize_platform(platform)
    result = {
        **_base_result(phase="Shipping-6B"),
        "readonly_route": True,
        "matching_contract_acknowledged": bool(matching_contract_acknowledged),
        "tracking_order_match_readonly": True,
        "tracking_number_import_open": False,
        "shipment_writeback_open": False,
        "shipment_writeback_called": False,
        "orders_updated": False,
        "tracking_rows_written": False,
        "import_batch_id": import_batch_id,
        "match_rows": [],
        "total_tracking_rows": 0,
        "matched_order_count": 0,
        "unmatched_order_count": 0,
        "duplicate_tracking_row_count": 0,
    }
    if normalized_platform is None:
        result.update({"status": "blocked", "skip_reason": "platform_not_supported"})
        return result
    if matching_contract_acknowledged is not True:
        result.update({"status": "blocked", "skip_reason": "matching_contract_required"})
        return result

    source_rows = list(tracking_rows or [])
    if import_batch_id:
        source_rows = _tracking_rows_from_import_batch(
            db,
            store_id=store_id,
            platform=normalized_platform,
            import_batch_id=import_batch_id,
        )

    forbidden_fields = _sensitive_fields({
        "tracking_rows": source_rows,
        "actor_context": actor_context or {},
    })
    if forbidden_fields:
        result.update({
            "status": "blocked",
            "skip_reason": "tracking_order_match_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    if not source_rows:
        result.update({
            "status": "tracking_order_match_empty",
            "skip_reason": None,
            "store_id": store_id,
            "platform": normalized_platform,
            "business_message": "No local tracking import rows are available for order matching.",
        })
        return result

    normalized_rows, error = _validate_tracking_import_rows(source_rows)
    if error and error.get("skip_reason"):
        result.update(error)
        return result

    duplicate_count = int((error or {}).get("duplicate_count") or 0)
    orders = db.scalars(
        select(Order).where(
            Order.store_id == store_id,
            Order.platform == normalized_platform,
        )
    ).all()
    orders_by_external_reference = {
        str(order.external_order_id or "").strip(): order
        for order in orders
        if str(order.external_order_id or "").strip()
    }
    orders_by_local_reference = {
        f"local-order-{order.id}": order
        for order in orders
    }
    match_rows: list[dict[str, Any]] = []
    matched_count = 0
    for row in normalized_rows or []:
        order_reference = row["order_reference"]
        order = orders_by_external_reference.get(order_reference) or orders_by_local_reference.get(order_reference)
        if order:
            matched_count += 1
            match_status = "matched_existing_order"
            match_method = "order_reference"
            order_summary = {
                "local_order_id": order.id,
                "order_reference": order.external_order_id,
                "order_status": order.order_status,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "source_type": order.source_type,
            }
        else:
            match_status = "no_local_order_match"
            match_method = None
            order_summary = None
        match_rows.append({
            "row_index": row["row_index"],
            "order_reference": order_reference,
            "product_order_reference": row["product_order_reference"],
            "logistics_inventory_code": row["logistics_inventory_code"],
            "carrier": row["carrier"],
            "tracking_number": row["tracking_number"],
            "shipped_at": row["shipped_at"],
            "row_status": row["row_status"],
            "match_status": match_status,
            "match_method": match_method,
            "order_summary": order_summary,
            "future_write_allowed": False,
        })

    total_count = len(normalized_rows or [])
    result.update({
        "status": "tracking_order_match_readonly_ready",
        "skip_reason": None,
        "store_id": store_id,
        "platform": normalized_platform,
        "total_tracking_rows": total_count,
        "matched_order_count": matched_count,
        "unmatched_order_count": max(total_count - matched_count, 0),
        "duplicate_tracking_row_count": duplicate_count,
        "match_rows": match_rows,
        "business_message": (
            "Tracking rows have been compared with local orders. This is readonly evidence only; "
            "orders are not updated and Naver shipment writeback remains closed."
        ),
        "real_database_written": False,
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


def evaluate_shipment_writeback_approval_boundary(
    db: Session,
    *,
    store_id: int,
    platform: str = "naver",
    manual_approval: bool = False,
    matched_order_count: int = 0,
    total_tracking_rows: int = 0,
    matching_evidence_acknowledged: bool = False,
    backup_evidence_acknowledged: bool = False,
    audit_evidence_acknowledged: bool = False,
    naver_writeback_boundary_acknowledged: bool = False,
    operator_checklist_acknowledged: bool = False,
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    normalized_platform = _normalize_platform(platform)
    result = {
        **_base_result(phase="Shipping-6C"),
        "readonly_route": True,
        "shipment_writeback_boundary_review": True,
        "manual_approval": bool(manual_approval),
        "matched_order_count": max(int(matched_order_count or 0), 0),
        "total_tracking_rows": max(int(total_tracking_rows or 0), 0),
        "matching_evidence_acknowledged": bool(matching_evidence_acknowledged),
        "backup_evidence_acknowledged": bool(backup_evidence_acknowledged),
        "audit_evidence_acknowledged": bool(audit_evidence_acknowledged),
        "naver_writeback_boundary_acknowledged": bool(naver_writeback_boundary_acknowledged),
        "operator_checklist_acknowledged": bool(operator_checklist_acknowledged),
        "shipment_writeback_open": False,
        "shipment_writeback_called": False,
        "tracking_number_import_open": False,
        "orders_updated": False,
        "required_actions": [
            "manual_approval",
            "matched_order_evidence",
            "matching_evidence_acknowledged",
            "backup_evidence_acknowledged",
            "audit_evidence_acknowledged",
            "naver_writeback_boundary_acknowledged",
            "operator_checklist_acknowledged",
        ],
        "missing_actions": [],
    }
    if normalized_platform is None:
        result.update({"status": "blocked", "skip_reason": "platform_not_supported"})
        return result
    forbidden_fields = _sensitive_fields({"actor_context": actor_context or {}})
    if forbidden_fields:
        result.update({
            "status": "blocked",
            "skip_reason": "shipment_writeback_boundary_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    missing_actions = []
    if manual_approval is not True:
        missing_actions.append("manual_approval")
    if int(matched_order_count or 0) <= 0 or int(total_tracking_rows or 0) <= 0:
        missing_actions.append("matched_order_evidence")
    if matching_evidence_acknowledged is not True:
        missing_actions.append("matching_evidence_acknowledged")
    if backup_evidence_acknowledged is not True:
        missing_actions.append("backup_evidence_acknowledged")
    if audit_evidence_acknowledged is not True:
        missing_actions.append("audit_evidence_acknowledged")
    if naver_writeback_boundary_acknowledged is not True:
        missing_actions.append("naver_writeback_boundary_acknowledged")
    if operator_checklist_acknowledged is not True:
        missing_actions.append("operator_checklist_acknowledged")

    result.update({
        "store_id": store_id,
        "platform": normalized_platform,
        "missing_actions": missing_actions,
        "status": "shipment_writeback_boundary_ready" if not missing_actions else "blocked",
        "skip_reason": None if not missing_actions else missing_actions[0],
        "business_message": (
            "Shipment writeback boundary evidence is ready for a future separately approved phase. "
            "This route still does not call Naver."
            if not missing_actions
            else "Shipment writeback remains closed until every approval, backup, audit, and operator checklist item is ready."
        ),
        "real_database_written": False,
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


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(value: Any, row_index: int, column_index: int) -> str:
    reference = f"{_xlsx_column_name(column_index)}{row_index}"
    if isinstance(value, int):
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = escape(str(value or ""))
    return f'<c r="{reference}" t="inlineStr"><is><t>{text}</t></is></c>'


def _build_xlsx_bytes(rows: list[dict[str, Any]]) -> bytes:
    from io import BytesIO

    headers = [
        ("order_reference", "订单号"),
        ("product_name", "商品名称"),
        ("option_name", "选项名称"),
        ("quantity", "数量"),
        ("logistics_inventory_code", "物流库存编号"),
        ("logistics_provider_name", "物流商"),
        ("logistics_current_stock", "物流当前库存"),
        ("internal_sku", "内部 SKU"),
    ]
    sheet_rows = []
    header_cells = [_xlsx_cell(label, 1, column_index) for column_index, (_key, label) in enumerate(headers, start=1)]
    sheet_rows.append(f'<row r="1">{"".join(header_cells)}</row>')
    for row_index, row in enumerate(rows, start=2):
        cells = [
            _xlsx_cell(row.get(key), row_index, column_index)
            for column_index, (key, _label) in enumerate(headers, start=1)
        ]
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'{"".join(sheet_rows)}'
        '</sheetData>'
        '</worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Shipping Request" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _audit_row_for_export(
    *,
    store_id: int,
    platform: str,
    actor_context: dict[str, Any] | None,
    export_batch_id: int,
    file_sha256: str,
    file_name: str,
    row_count: int,
    correlation_id: str,
) -> dict[str, Any]:
    now = get_utc_now()
    return {
        "created_at": now,
        "updated_at": now,
        "store_id": store_id,
        "platform": platform,
        "environment": "local",
        "actor_type": "human",
        "actor_id": _actor_hash(actor_context) or "actor-hash-shipping-export-local",
        "actor_label": "Local operator",
        "actor_role": str((actor_context or {}).get("role") or "admin")[:80],
        "action": "local_write_succeeded",
        "operation_phase": "Shipping-3D",
        "correlation_id": correlation_id,
        "request_id": f"shipping-3d-export-{export_batch_id}",
        "status": "success",
        "reason_code": "shipping_excel_export_local_write",
        "target_type": "settings",
        "target_id": str(export_batch_id),
        "target_hash": f"id-hash-{file_sha256[:16]}",
        "target_label": "Shipping Excel export",
        "changed_field_names": ["shipping_export_batches", "shipping_export_batch_rows"],
        "before_summary": {"manual_approval": True, "file_generated": False},
        "after_summary": {
            "file_name": file_name,
            "file_sha256": file_sha256,
            "row_count": row_count,
        },
        "counts_summary": {
            "shipping_export_batches_written": 1,
            "shipping_export_batch_rows_written": row_count,
            "orders_written": 0,
            "products_written": 0,
            "sync_logs_written": 0,
            "capability_results_written": 0,
        },
        "safety_flags": {
            "shipping_excel_export_local_write": True,
            "real_api_called": False,
            "platform_writes_enabled": False,
            "formal_sync_open": False,
            "orders_written": False,
            "products_written": False,
            "sync_log_written": False,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "privacy_payload_included": False,
        },
        "sensitive_scan_passed": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "notes": "Approved local Shipping Excel export. No Naver or logistics-provider API was called.",
    }


def generate_shipping_excel_local(
    db: Session,
    *,
    store_id: int,
    platform: str,
    export_rows: list[dict[str, Any]],
    manual_approval: bool,
    actor_context: dict[str, Any] | None = None,
    include_receiver_privacy: bool = False,
    export_directory: Path | None = None,
) -> dict[str, Any]:
    ensure_store_exists(db, store_id)
    gate = evaluate_real_excel_generation_mock_gate(
        store_id=store_id,
        platform=platform,
        export_rows=export_rows,
        manual_approval=manual_approval,
        actor_context=actor_context,
        include_receiver_privacy=include_receiver_privacy,
        export_record_schema_acknowledged=True,
        audit_linkage_acknowledged=True,
        tracking_import_contract_acknowledged=True,
    )
    result = {**gate, "phase": "Shipping-3D"}
    if gate.get("status") != "real_excel_generation_mock_ready":
        result.update({
            "file_generated": False,
            "file_persisted": False,
            "export_record_written": False,
            "download_record_written": False,
            "operation_audit_rows_written": False,
            "real_database_written": False,
        })
        return result

    normalized_platform = _normalize_platform(platform) or "naver"
    normalized_rows = list(gate.get("export_rows_preview") or [])
    now = get_utc_now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"store_id": store_id, "platform": normalized_platform, "rows": normalized_rows, "timestamp": timestamp},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:12]
    file_name = f"{normalized_platform}-shipping-request-store-{store_id}-{timestamp}-{fingerprint}.xlsx"
    target_dir = export_directory or DEFAULT_SHIPPING_EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name

    xlsx_bytes = _build_xlsx_bytes(normalized_rows)
    file_path.write_bytes(xlsx_bytes)
    file_sha256 = _sha256_bytes(xlsx_bytes)
    correlation_id = f"shipping-3d-{fingerprint}"
    actor_hash = _actor_hash(actor_context)

    try:
        export_batch = ShippingExportBatch(
            store_id=store_id,
            platform=normalized_platform,
            file_type=SHIPPING_EXPORT_FILE_TYPE,
            file_format=SHIPPING_EXPORT_FILE_FORMAT,
            file_name=file_name,
            file_path=str(file_path),
            file_sha256=file_sha256,
            row_count=len(normalized_rows),
            matched_row_count=len(normalized_rows),
            unmatched_row_count=0,
            actor_id_hash=actor_hash,
            audit_correlation_id=correlation_id,
            export_status="generated",
            include_receiver_privacy=False,
            file_generated=True,
            file_persisted=True,
            raw_response_saved=False,
            secrets_saved=False,
            privacy_fields_redacted=True,
            mapping_version=SHIPPING_EXPORT_LOCAL_MAPPING_VERSION,
            created_at=now,
            updated_at=now,
        )
        db.add(export_batch)
        db.flush()
        for row in normalized_rows:
            db.add(ShippingExportBatchRow(
                export_batch_id=export_batch.id,
                store_id=store_id,
                platform=normalized_platform,
                order_reference=row["order_reference"],
                product_name=row["product_name"],
                option_name=row["option_name"],
                quantity=row["quantity"],
                logistics_inventory_code=row["logistics_inventory_code"],
                logistics_provider_name=row["logistics_provider_name"],
                internal_sku=row["internal_sku"],
                platform_product_id_hash=row["platform_product_id_hash"],
                platform_option_id_hash=row["platform_option_id_hash"],
                row_status="ready",
                created_at=now,
            ))

        audit_result = write_operation_audit_log_local(
            db,
            _audit_row_for_export(
                store_id=store_id,
                platform=normalized_platform,
                actor_context=actor_context,
                export_batch_id=export_batch.id,
                file_sha256=file_sha256,
                file_name=file_name,
                row_count=len(normalized_rows),
                correlation_id=correlation_id,
            ),
            write_enabled=True,
            manual_approval=True,
            local_write_scope=LOCAL_WRITER_SCOPE,
        )
        if audit_result.get("status") != "audit_row_written":
            db.rollback()
            file_path.unlink(missing_ok=True)
            result.update({
                "status": "shipping_excel_export_blocked",
                "skip_reason": audit_result.get("skip_reason") or "audit_write_failed",
                "file_generated": False,
                "file_persisted": False,
                "export_record_written": False,
                "operation_audit_rows_written": False,
                "real_database_written": False,
            })
            return result
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    result.update({
        "status": "shipping_excel_local_export_succeeded",
        "skip_reason": None,
        "business_message": "本地 Excel 文件已生成，并已写入导出记录和审计证据。未调用 Naver 或物流商接口。",
        "export_batch_id": export_batch.id,
        "export_batch_row_count": len(normalized_rows),
        "file_name": file_name,
        "file_path": str(file_path),
        "file_sha256": file_sha256,
        "file_size_bytes": len(xlsx_bytes),
        "row_count": len(normalized_rows),
        "matched_row_count": len(normalized_rows),
        "unmatched_row_count": 0,
        "file_generated": True,
        "file_persisted": True,
        "export_record_written": True,
        "download_record_written": False,
        "operation_audit_rows_written": True,
        "operation_audit_log_id": audit_result.get("audit_log_id"),
        "audit_correlation_id": correlation_id,
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
        "tracking_number_import_open": False,
        "export_rows_preview": normalized_rows,
    })
    return result


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
