from __future__ import annotations

from datetime import date, datetime, time
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.operation_audit_log import OperationAuditLog


VERIFICATION_SCOPE = "verify_all_temp_db"
LOCAL_WRITER_SCOPE = "local_runtime_approved"
READONLY_MOCK_SCOPE = VERIFICATION_SCOPE
READONLY_LOCAL_SCOPE = "local_readonly_route"

DEFAULT_AUDIT_READ_LIMIT = 20
MAX_AUDIT_READ_LIMIT = 50
MAX_AUDIT_READ_WINDOW_DAYS = 90

REQUIRED_AUDIT_FIELDS = {
    "created_at",
    "updated_at",
    "actor_type",
    "action",
    "correlation_id",
    "status",
}

ALLOWED_SENSITIVE_LOOKING_KEYS = {
    "addresssaved",
    "address_saved",
    "privacyfieldsredacted",
    "privacy_fields_redacted",
    "rawresponsesaved",
    "raw_response_saved",
    "secretssaved",
    "secrets_saved",
}

SENSITIVE_VALUE_MARKERS = {
    "authorization:",
    "bearer ",
    "bcrypt",
    "client_secret",
    "client-secret",
    "full address",
    "must-not-leak",
    "must not leak",
    "raw_response",
    "raw response",
    "raw-request",
    "signature",
}

SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
)

ALLOWED_AUDIT_READ_FILTERS = {
    "store_id",
    "platform",
    "status",
    "target_type",
    "action",
    "actor_type",
    "date_from",
    "date_to",
    "correlation_id",
    "limit",
    "offset",
    "include_advanced",
}

ALLOWED_AUDIT_STATUSES = {"planned", "success", "failed", "blocked", "skipped", "rolled_back"}
ALLOWED_AUDIT_ACTOR_TYPES = {"human", "system", "automation", "test"}
ALLOWED_AUDIT_PLATFORMS = {"naver", "coupang", "local", "all"}
ALLOWED_AUDIT_TARGET_TYPES = {
    "audit_log",
    "backup",
    "credential",
    "order",
    "product",
    "restore",
    "schema",
    "settings",
    "store",
    "sync_gate",
}

SAFE_ENUM_PATTERN = re.compile(r"^[a-z0-9_:-]{1,120}$")

STATUS_LABELS_ZH = {
    "planned": "\u5df2\u8ba1\u5212",
    "success": "\u5df2\u5b8c\u6210",
    "failed": "\u5931\u8d25",
    "blocked": "\u5df2\u963b\u65ad",
    "skipped": "\u5df2\u8df3\u8fc7",
    "rolled_back": "\u5df2\u56de\u6eda",
}

ACTOR_TYPE_LABELS_ZH = {
    "human": "\u4eba\u5de5\u64cd\u4f5c",
    "system": "\u7cfb\u7edf\u64cd\u4f5c",
    "automation": "\u81ea\u52a8\u5316\u4efb\u52a1",
    "test": "\u9a8c\u8bc1\u6d4b\u8bd5",
}

ACTION_LABELS_ZH = {
    "audit_logs_readonly_mock_success": "\u5ba1\u8ba1\u65e5\u5fd7\u53ea\u8bfb\u9a8c\u8bc1",
    "audit_logs_readonly_mock_blocked": "\u5ba1\u8ba1\u65e5\u5fd7\u963b\u65ad\u8bb0\u5f55",
    "audit_writer_local_approved": "\u672c\u5730\u5ba1\u8ba1\u5199\u5165\u9a8c\u8bc1",
    "audit_writer_local_blocked_evidence": "\u672c\u5730\u5ba1\u8ba1\u963b\u65ad\u8bc1\u636e",
    "database_backup_created": "\u6570\u636e\u5e93\u5907\u4efd",
    "order_refresh_batch_write_succeeded": "\u8ba2\u5355\u5237\u65b0\u5199\u5165",
}

TARGET_TYPE_LABELS_ZH = {
    "audit_log": "\u5ba1\u8ba1\u8bb0\u5f55",
    "backup": "\u6570\u636e\u5e93\u5907\u4efd",
    "credential": "\u5e73\u53f0\u8fde\u63a5\u8d44\u6599",
    "order": "\u8ba2\u5355",
    "product": "\u5546\u54c1",
    "restore": "\u6570\u636e\u6062\u590d",
    "schema": "\u6570\u636e\u7ed3\u6784",
    "settings": "\u7cfb\u7edf\u8bbe\u7f6e",
    "store": "\u5e97\u94fa",
    "sync_gate": "\u540c\u6b65\u95e8\u7981",
}

REASON_LABELS_ZH = {
    "readonly_mock_gate": "\u53ea\u8bfb\u9a8c\u8bc1\u901a\u8fc7",
    "sensitive_scan_failed": "\u654f\u611f\u5b57\u6bb5\u626b\u63cf\u672a\u901a\u8fc7",
    "local_writer_verified": "\u672c\u5730\u5199\u5165\u95e8\u7981\u5df2\u9a8c\u8bc1",
    "manual_operation_blocked": "\u4eba\u5de5\u64cd\u4f5c\u5df2\u963b\u65ad",
}


def _base_result(*, phase: str = "ERP-Audit-1G", runtime_writer_enabled: bool = False) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": "audit_write_not_requested",
        "audit_rows_written": False,
        "rows_written": 0,
        "runtime_writer_enabled": runtime_writer_enabled,
        "real_api_called": False,
        "real_schema_changed": False,
        "sync_log_written": False,
        "products_written": False,
        "orders_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
    }


def _base_read_result(*, phase: str = "ERP-Audit-1J", public_endpoint_enabled: bool = False) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": "audit_read_not_enabled",
        "public_endpoint_enabled": public_endpoint_enabled,
        "audit_rows_written": False,
        "rows_written": 0,
        "real_api_called": False,
        "real_schema_changed": False,
        "sync_log_written": False,
        "products_written": False,
        "orders_written": False,
        "capability_tested_success_written": False,
        "safety_boundary_label_zh": "\u672a\u8fd4\u56de\u654f\u611f\u539f\u6587",
        "formal_sync_open": False,
    }


def _normalize_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _sensitive_key_name(key: str) -> str | None:
    normalized = _normalize_key(key)
    if normalized in {_normalize_key(item) for item in ALLOWED_SENSITIVE_LOOKING_KEYS}:
        return None
    if normalized.endswith("hash"):
        return None

    exact_forbidden = {
        "accesstoken",
        "authorization",
        "bcrypt",
        "buyerfullname",
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
        "receiverfullname",
        "receivername",
        "receiverphone",
        "refreshtoken",
        "requestheaders",
        "responseheaders",
        "signature",
        "token",
        "zipcode",
    }
    if normalized in exact_forbidden:
        return normalized
    if any(part in normalized for part in ["token", "authorization", "headers", "signature", "bcrypt", "clientsecret"]):
        return normalized
    if any(part in normalized for part in ["rawresponse", "rawrequest", "rawdata"]):
        return normalized
    if ("orderid" in normalized or "productorderid" in normalized) and not normalized.endswith("hash"):
        return normalized
    if any(part in normalized for part in ["buyer", "receiver", "phone", "address", "zipcode"]):
        return normalized
    return None


def _sensitive_fields(payload: Any) -> list[str]:
    forbidden: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_name = str(key)
                forbidden_key = _sensitive_key_name(key_name)
                if forbidden_key:
                    forbidden.add(forbidden_key)
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
            if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
                forbidden.add("sensitive_value")

    walk(payload)
    return sorted(forbidden)


def _valid_sha256(value: str | None) -> bool:
    if value is None:
        return True
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _missing_required_fields(audit_row: dict[str, Any]) -> list[str]:
    return sorted(
        field
        for field in REQUIRED_AUDIT_FIELDS
        if not str(audit_row.get(field, "")).strip()
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _abbreviate(value: str | None, *, keep: int = 12) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) <= keep:
        return text
    return f"{text[:keep]}..."


def _safe_json(value: Any) -> tuple[Any, bool]:
    if value is None:
        return None, False
    if _sensitive_fields(value):
        return None, True
    return value, False


def _label(mapping: dict[str, str], value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return mapping.get(value, fallback)


def _platform_label(platform: str | None) -> str:
    if platform == "naver":
        return "Naver"
    if platform == "coupang":
        return "Coupang"
    return "\u672c\u5730\u7cfb\u7edf"


def _changed_fields_label(changed_fields: Any) -> list[str]:
    if not isinstance(changed_fields, list):
        return []
    labels = {
        "order_status": "\u8ba2\u5355\u72b6\u6001",
        "delivery_status": "\u914d\u9001\u72b6\u6001",
        "claim_status": "\u552e\u540e\u72b6\u6001",
        "last_synced_at": "\u6700\u8fd1\u540c\u6b65\u65f6\u95f4",
        "counts_summary": "\u6570\u91cf\u6458\u8981",
        "safety_flags": "\u5b89\u5168\u6807\u8bb0",
        "action": "\u64cd\u4f5c\u7c7b\u578b",
        "status": "\u5904\u7406\u7ed3\u679c",
    }
    return [labels.get(str(field), str(field)) for field in changed_fields if str(field).strip()]


def _counts_summary_label(counts_summary: Any) -> str:
    if not isinstance(counts_summary, dict):
        return "\u6709\u5b89\u5168\u5ba1\u8ba1\u8bb0\u5f55"
    if counts_summary.get("audit_rows_written"):
        return f"\u8bb0\u5f55 {counts_summary['audit_rows_written']} \u6761\u5ba1\u8ba1\u8bc1\u636e"
    if counts_summary.get("orders_written"):
        return f"\u5199\u5165 {counts_summary['orders_written']} \u6761\u8ba2\u5355"
    if counts_summary.get("orders_updated"):
        return f"\u66f4\u65b0 {counts_summary['orders_updated']} \u6761\u8ba2\u5355"
    if counts_summary.get("blocked_count"):
        return f"\u963b\u65ad {counts_summary['blocked_count']} \u6b21\u64cd\u4f5c"
    return "\u6709\u5b89\u5168\u5ba1\u8ba1\u8bb0\u5f55"


def _safe_summary_field_names(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    labels = {
        "audit_rows_written": "\u5ba1\u8ba1\u8bb0\u5f55\u6570",
        "blocked_count": "\u963b\u65ad\u6b21\u6570",
        "orders_updated": "\u8ba2\u5355\u66f4\u65b0\u6570",
        "orders_written": "\u8ba2\u5355\u5199\u5165\u6570",
        "products_written": "\u5546\u54c1\u5199\u5165\u6570",
        "rows_written": "\u5199\u5165\u884c\u6570",
        "sync_logs_written": "\u540c\u6b65\u8bb0\u5f55\u5199\u5165\u6570",
    }
    return [labels.get(str(key), str(key)) for key in value.keys() if SAFE_ENUM_PATTERN.match(str(key))]


def _backup_evidence_label(row: OperationAuditLog) -> str:
    if row.backup_sha256 or row.backup_path:
        return "\u5df2\u8bb0\u5f55\u5907\u4efd\u8bc1\u636e"
    if row.restore_source_sha256 or row.restore_source_path:
        return "\u5df2\u8bb0\u5f55\u6062\u590d\u8bc1\u636e"
    return "\u672a\u8bb0\u5f55\u5907\u4efd\u8bc1\u636e"


def _safety_label(row: OperationAuditLog, *, sanitized_summary_removed: bool) -> str:
    if row.raw_response_saved or row.secrets_saved or not row.privacy_fields_redacted:
        return "\u9700\u4eba\u5de5\u590d\u6838\u5b89\u5168\u8fb9\u754c"
    if sanitized_summary_removed:
        return "\u5df2\u9690\u85cf\u4e0d\u5b89\u5168\u6458\u8981"
    return "\u672a\u4fdd\u5b58\u654f\u611f\u539f\u6587"


def _next_action_label(row: OperationAuditLog) -> str:
    if row.status == "blocked":
        return "\u9700\u8981\u590d\u6838\u963b\u65ad\u539f\u56e0"
    if row.status == "failed":
        return "\u9700\u8981\u68c0\u67e5\u5931\u8d25\u539f\u56e0"
    if row.status == "planned":
        return "\u7b49\u5f85\u4eba\u5de5\u6279\u51c6\u6216\u4e0b\u4e00\u6b65\u9a8c\u8bc1"
    return "\u65e0\u9700\u5904\u7406"


def _safe_public_text(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    if _sensitive_fields({"value": value}):
        return fallback
    return value


def _serialize_audit_log_item(row: OperationAuditLog, *, include_advanced: bool = False) -> dict[str, Any]:
    counts_summary, counts_removed = _safe_json(row.counts_summary)
    safety_flags, safety_removed = _safe_json(row.safety_flags)
    before_summary, before_removed = _safe_json(row.before_summary)
    after_summary, after_removed = _safe_json(row.after_summary)
    changed_field_names, changed_removed = _safe_json(row.changed_field_names)
    sanitized_summary_removed = any([
        counts_removed,
        safety_removed,
        before_removed,
        after_removed,
        changed_removed,
    ])

    item: dict[str, Any] = {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "store_id": row.store_id,
        "store_label": f"\u5e97\u94fa {row.store_id}" if row.store_id else "\u7cfb\u7edf\u64cd\u4f5c",
        "platform": row.platform,
        "platform_label": _platform_label(row.platform),
        "actor_label": _safe_public_text(row.actor_label, "\u7cfb\u7edf"),
        "actor_type_label": _label(ACTOR_TYPE_LABELS_ZH, row.actor_type, "\u5176\u4ed6\u64cd\u4f5c"),
        "action_label_zh": _label(ACTION_LABELS_ZH, row.action, "\u672c\u5730\u8fd0\u8425\u64cd\u4f5c"),
        "target_label": _safe_public_text(row.target_label, _label(TARGET_TYPE_LABELS_ZH, row.target_type, "\u4e1a\u52a1\u5bf9\u8c61")),
        "status_label_zh": _label(STATUS_LABELS_ZH, row.status, "\u672a\u77e5\u7ed3\u679c"),
        "reason_label_zh": REASON_LABELS_ZH.get(row.reason_code) if row.reason_code else None,
        "changed_fields_label_zh": _changed_fields_label(changed_field_names),
        "counts_summary_label_zh": _counts_summary_label(counts_summary),
        "backup_evidence_label_zh": _backup_evidence_label(row),
        "safety_label_zh": _safety_label(row, sanitized_summary_removed=sanitized_summary_removed),
        "next_action_label_zh": _next_action_label(row),
        "sanitized_summary_removed": sanitized_summary_removed,
    }

    if include_advanced:
        item["advanced_details"] = {
            "action": row.action,
            "status": row.status,
            "reason_code": row.reason_code,
            "operation_phase": row.operation_phase,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_hash_abbrev": _abbreviate(row.target_hash),
            "correlation_id_abbrev": _abbreviate(row.correlation_id),
            "request_id_abbrev": _abbreviate(row.request_id),
            "changed_field_names": changed_field_names if not changed_removed else None,
            "safe_summary_fields": _safe_summary_field_names(counts_summary) if not counts_removed else [],
            "safety_summary_label_zh": _safety_label(row, sanitized_summary_removed=sanitized_summary_removed),
            "backup_path_label": row.backup_path,
            "backup_sha256_abbrev": _abbreviate(row.backup_sha256),
            "restore_source_sha256_abbrev": _abbreviate(row.restore_source_sha256),
            "sanitized_summary_removed": sanitized_summary_removed,
        }
    return item


def _validate_read_filters(filters: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    unknown = sorted(set(filters) - ALLOWED_AUDIT_READ_FILTERS)
    if unknown:
        return None, {"skip_reason": "unsupported_filter", "unsupported_filters": unknown}

    cleaned = dict(filters)
    limit = cleaned.get("limit", DEFAULT_AUDIT_READ_LIMIT)
    offset = cleaned.get("offset", 0)
    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        return None, {"skip_reason": "invalid_pagination"}
    if limit < 1 or offset < 0:
        return None, {"skip_reason": "invalid_pagination"}
    cleaned["limit_was_capped"] = limit > MAX_AUDIT_READ_LIMIT
    cleaned["limit"] = min(limit, MAX_AUDIT_READ_LIMIT)
    cleaned["offset"] = offset

    if cleaned.get("store_id") is not None:
        try:
            store_id = int(cleaned["store_id"])
        except (TypeError, ValueError):
            return None, {"skip_reason": "invalid_store_id"}
        if store_id < 1:
            return None, {"skip_reason": "invalid_store_id"}
        cleaned["store_id"] = store_id

    enum_checks = {
        "platform": ALLOWED_AUDIT_PLATFORMS,
        "status": ALLOWED_AUDIT_STATUSES,
        "target_type": ALLOWED_AUDIT_TARGET_TYPES,
        "actor_type": ALLOWED_AUDIT_ACTOR_TYPES,
    }
    for field, allowed in enum_checks.items():
        value = cleaned.get(field)
        if value is not None and value not in allowed:
            return None, {"skip_reason": f"invalid_{field}"}

    for field in ["action", "correlation_id"]:
        value = cleaned.get(field)
        if value is not None and not SAFE_ENUM_PATTERN.match(str(value)):
            return None, {"skip_reason": f"unsafe_{field}"}

    for field in ["date_from", "date_to"]:
        if cleaned.get(field) is not None:
            parsed = _coerce_datetime(cleaned[field])
            if parsed is None:
                return None, {"skip_reason": f"invalid_{field}"}
            cleaned[field] = parsed
    if cleaned.get("date_from") and cleaned.get("date_to"):
        if cleaned["date_from"] > cleaned["date_to"]:
            return None, {"skip_reason": "invalid_date_range"}
        if (cleaned["date_to"] - cleaned["date_from"]).days > MAX_AUDIT_READ_WINDOW_DAYS:
            return None, {"skip_reason": "date_window_too_large"}

    cleaned["include_advanced"] = bool(cleaned.get("include_advanced", False))
    return cleaned, {}


def _apply_read_filters(query: Any, filters: dict[str, Any]) -> Any:
    if filters.get("store_id") is not None:
        query = query.filter(OperationAuditLog.store_id == filters["store_id"])
    if filters.get("platform") and filters["platform"] != "all":
        query = query.filter(OperationAuditLog.platform == filters["platform"])
    if filters.get("status"):
        query = query.filter(OperationAuditLog.status == filters["status"])
    if filters.get("target_type"):
        query = query.filter(OperationAuditLog.target_type == filters["target_type"])
    if filters.get("action"):
        query = query.filter(OperationAuditLog.action == filters["action"])
    if filters.get("actor_type"):
        query = query.filter(OperationAuditLog.actor_type == filters["actor_type"])
    if filters.get("correlation_id"):
        query = query.filter(OperationAuditLog.correlation_id == filters["correlation_id"])
    if filters.get("date_from"):
        query = query.filter(OperationAuditLog.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(OperationAuditLog.created_at <= filters["date_to"])
    return query


def _list_operation_audit_logs_readonly(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
    phase: str,
    public_endpoint_enabled: bool,
    gate_label: str,
) -> dict[str, Any]:
    result = _base_read_result(phase=phase, public_endpoint_enabled=public_endpoint_enabled)
    cleaned_filters, filter_error = _validate_read_filters(filters or {})
    if cleaned_filters is None:
        result.update({
            "status": "audit_read_blocked",
            **filter_error,
        })
        return result

    query = _apply_read_filters(db.query(OperationAuditLog), cleaned_filters)
    total = query.count()
    rows = (
        query
        .order_by(OperationAuditLog.created_at.desc(), OperationAuditLog.id.desc())
        .offset(cleaned_filters["offset"])
        .limit(cleaned_filters["limit"])
        .all()
    )
    include_advanced = cleaned_filters["include_advanced"]
    items = [_serialize_audit_log_item(row, include_advanced=include_advanced) for row in rows]
    if items:
        business_message = "\u5df2\u663e\u793a\u5b89\u5168\u5ba1\u8ba1\u8bb0\u5f55\u3002"
        read_status = "audit_read_success"
    else:
        business_message = "\u5f53\u524d\u8fd8\u6ca1\u6709\u64cd\u4f5c\u5ba1\u8ba1\u8bb0\u5f55\u3002\u540e\u7eed\u53d7\u63a7\u5199\u5165\u3001\u5907\u4efd\u3001\u6062\u590d\u7b49\u64cd\u4f5c\u63a5\u5165\u540e\u4f1a\u663e\u793a\u5728\u8fd9\u91cc\u3002"
        read_status = "audit_read_empty"

    result.update({
        "status": read_status,
        "items": items,
        "total": total,
        "limit": cleaned_filters["limit"],
        "offset": cleaned_filters["offset"],
        "limit_was_capped": cleaned_filters["limit_was_capped"],
        "include_advanced": include_advanced,
        "business_message": business_message,
        gate_label: True,
        "public_endpoint_enabled": public_endpoint_enabled,
    })
    return result


def _summarize_operation_audit_logs_readonly(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
    phase: str,
    public_endpoint_enabled: bool,
    gate_label: str,
) -> dict[str, Any]:
    result = _base_read_result(phase=phase, public_endpoint_enabled=public_endpoint_enabled)
    cleaned_filters, filter_error = _validate_read_filters(filters or {})
    if cleaned_filters is None:
        result.update({
            "status": "audit_read_blocked",
            **filter_error,
        })
        return result

    query = _apply_read_filters(db.query(OperationAuditLog), cleaned_filters)
    rows = query.all()
    total = len(rows)
    status_counts: dict[str, int] = {}
    backup_evidence_count = 0
    restore_evidence_count = 0
    needs_attention_count = 0
    latest_created_at: str | None = None
    for row in rows:
        status_label = _label(STATUS_LABELS_ZH, row.status, "\u672a\u77e5\u7ed3\u679c")
        status_counts[status_label] = status_counts.get(status_label, 0) + 1
        if row.status in {"failed", "blocked"}:
            needs_attention_count += 1
        if row.backup_path or row.backup_sha256:
            backup_evidence_count += 1
        if row.restore_source_path or row.restore_source_sha256:
            restore_evidence_count += 1
        if row.created_at:
            created_text = row.created_at.isoformat()
            if latest_created_at is None or created_text > latest_created_at:
                latest_created_at = created_text

    if total == 0:
        runtime_status = "empty"
        business_message = "\u5f53\u524d\u8fd8\u6ca1\u6709\u64cd\u4f5c\u5ba1\u8ba1\u8bb0\u5f55\u3002"
    elif needs_attention_count:
        runtime_status = "needs_attention"
        business_message = "\u6709\u9700\u8981\u590d\u6838\u7684\u5ba1\u8ba1\u8bb0\u5f55\u3002"
    else:
        runtime_status = "available"
        business_message = "\u5ba1\u8ba1\u8bb0\u5f55\u53ef\u8bfb\u3002"

    result.update({
        "status": "audit_summary_success",
        "audit_runtime_status": runtime_status,
        "total": total,
        "status_counts_label_zh": status_counts,
        "backup_evidence_count": backup_evidence_count,
        "restore_evidence_count": restore_evidence_count,
        "needs_attention_count": needs_attention_count,
        "latest_audit_time": latest_created_at,
        "business_message": business_message,
        gate_label: True,
        "public_endpoint_enabled": public_endpoint_enabled,
    })
    return result


def list_operation_audit_logs_readonly_mock_gate(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for the future read-only audit API.

    1J verifies response shape only. It intentionally does not create a public
    route, does not enable frontend readers, and never writes rows.
    """

    if verification_scope != READONLY_MOCK_SCOPE:
        result = _base_read_result()
        result.update({
            "status": "audit_read_blocked",
            "skip_reason": "readonly_mock_scope_required",
        })
        return result
    return _list_operation_audit_logs_readonly(
        db,
        filters=filters,
        phase="ERP-Audit-1J",
        public_endpoint_enabled=False,
        gate_label="readonly_mock_gate",
    )


def summarize_operation_audit_logs_readonly_mock_gate(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for a future audit summary card."""

    if verification_scope != READONLY_MOCK_SCOPE:
        result = _base_read_result()
        result.update({
            "status": "audit_read_blocked",
            "skip_reason": "readonly_mock_scope_required",
        })
        return result
    return _summarize_operation_audit_logs_readonly(
        db,
        filters=filters,
        phase="ERP-Audit-1J",
        public_endpoint_enabled=False,
        gate_label="readonly_mock_gate",
    )


def list_operation_audit_logs_readonly_local(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Local read-only route helper for 1L.

    This reads sanitized audit metadata only. It does not write audit rows,
    business rows, or platform data.
    """

    return _list_operation_audit_logs_readonly(
        db,
        filters=filters,
        phase="ERP-Audit-1L",
        public_endpoint_enabled=True,
        gate_label="readonly_local_route",
    )


def summarize_operation_audit_logs_readonly_local(
    db: Session,
    *,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Local read-only summary route helper for 1L."""

    return _summarize_operation_audit_logs_readonly(
        db,
        filters=filters,
        phase="ERP-Audit-1L",
        public_endpoint_enabled=True,
        gate_label="readonly_local_route",
    )


def _validate_audit_row(audit_row: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    missing_required = _missing_required_fields(audit_row)
    if missing_required:
        return "missing_required_fields", {"missing_required_fields": missing_required}

    invalid_datetime_fields = [
        field
        for field in ["created_at", "updated_at"]
        if _coerce_datetime(audit_row.get(field)) is None
    ]
    if invalid_datetime_fields:
        return "invalid_datetime", {"invalid_datetime_fields": invalid_datetime_fields}

    invalid_sha_fields = [
        field
        for field in ["backup_sha256", "restore_source_sha256"]
        if not _valid_sha256(audit_row.get(field))
    ]
    if invalid_sha_fields:
        return "invalid_sha256", {"invalid_sha256_fields": invalid_sha_fields}

    if audit_row.get("raw_response_saved") is not False or audit_row.get("secrets_saved") is not False:
        return "unsafe_saved_flags", {}
    if audit_row.get("privacy_fields_redacted") is not True:
        return "privacy_fields_not_redacted", {}
    if audit_row.get("status") != "blocked" and audit_row.get("sensitive_scan_passed") is not True:
        return "sensitive_scan_not_passed", {}

    forbidden_fields = _sensitive_fields(audit_row)
    if forbidden_fields:
        return "audit_sensitive_field_blocked", {"forbidden_field_names": forbidden_fields}

    return None, {}


def _insert_audit_row(db: Session, audit_row: dict[str, Any]) -> OperationAuditLog:
    row = OperationAuditLog(
        created_at=_coerce_datetime(audit_row["created_at"]),
        updated_at=_coerce_datetime(audit_row["updated_at"]),
        store_id=audit_row.get("store_id"),
        platform=audit_row.get("platform"),
        environment=audit_row.get("environment", "local"),
        actor_type=audit_row["actor_type"],
        actor_id=audit_row.get("actor_id"),
        actor_label=audit_row.get("actor_label"),
        actor_role=audit_row.get("actor_role"),
        action=audit_row["action"],
        operation_phase=audit_row.get("operation_phase"),
        correlation_id=audit_row["correlation_id"],
        request_id=audit_row.get("request_id"),
        status=audit_row["status"],
        reason_code=audit_row.get("reason_code"),
        target_type=audit_row.get("target_type"),
        target_id=audit_row.get("target_id"),
        target_hash=audit_row.get("target_hash"),
        target_label=audit_row.get("target_label"),
        changed_field_names=audit_row.get("changed_field_names"),
        before_summary=audit_row.get("before_summary"),
        after_summary=audit_row.get("after_summary"),
        counts_summary=audit_row.get("counts_summary"),
        safety_flags=audit_row.get("safety_flags"),
        backup_path=audit_row.get("backup_path"),
        backup_sha256=audit_row.get("backup_sha256"),
        restore_source_path=audit_row.get("restore_source_path"),
        restore_source_sha256=audit_row.get("restore_source_sha256"),
        sensitive_scan_passed=audit_row.get("sensitive_scan_passed", False),
        raw_response_saved=audit_row.get("raw_response_saved", False),
        secrets_saved=audit_row.get("secrets_saved", False),
        privacy_fields_redacted=audit_row.get("privacy_fields_redacted", True),
        notes=audit_row.get("notes"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def write_operation_audit_log_mock_gate(
    db: Session,
    audit_row: dict[str, Any],
    *,
    write_enabled: bool,
    manual_approval: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for verification only.

    The function intentionally blocks unless the caller passes the private
    verify_all scope. Public routes and runtime writers are not enabled by this
    phase.
    """

    result = _base_result()
    if not write_enabled:
        return result
    if verification_scope != VERIFICATION_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "runtime_writer_not_enabled",
        })
        return result
    if not manual_approval:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, extra = _validate_audit_row(audit_row)
    if skip_reason:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": skip_reason,
            **extra,
        })
        return result

    row = _insert_audit_row(db, audit_row)
    result.update({
        "status": "audit_row_written",
        "audit_rows_written": True,
        "rows_written": 1,
        "audit_log_id": row.id,
    })
    return result


def write_operation_audit_log_local(
    db: Session,
    audit_row: dict[str, Any],
    *,
    write_enabled: bool,
    manual_approval: bool,
    local_write_scope: str | None = None,
) -> dict[str, Any]:
    """Controlled local writer for explicitly approved internal operations.

    1H adds the service entry point but does not wire it to public routes or
    broad business flows. Callers must pass the private local scope and manual
    approval, and the payload must pass the same safety gates as the mock gate.
    """

    result = _base_result(phase="ERP-Audit-1H")
    if not write_enabled:
        return result
    if local_write_scope != LOCAL_WRITER_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "local_writer_scope_required",
        })
        return result
    if not manual_approval:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, extra = _validate_audit_row(audit_row)
    if skip_reason:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": skip_reason,
            **extra,
        })
        return result

    row = _insert_audit_row(db, audit_row)
    result.update({
        "status": "audit_row_written",
        "audit_rows_written": True,
        "rows_written": 1,
        "audit_log_id": row.id,
        "runtime_writer_enabled": True,
        "local_write_scope": "approved_internal_only",
    })
    return result
