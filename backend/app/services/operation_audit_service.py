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
INTEGRATION_MOCK_SCOPE = VERIFICATION_SCOPE
SELECTED_OPERATION_MOCK_SCOPE = VERIFICATION_SCOPE
SELECTED_OPERATION_LOCAL_MOCK_SCOPE = VERIFICATION_SCOPE
BACKUP_AUDIT_MOCK_SCOPE = VERIFICATION_SCOPE
BACKUP_AUDIT_RUNTIME_MOCK_SCOPE = VERIFICATION_SCOPE

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
    "approval_planned": "\u5199\u5165\u5ba1\u6279\u5df2\u8ba1\u5212",
    "audit_logs_readonly_mock_success": "\u5ba1\u8ba1\u65e5\u5fd7\u53ea\u8bfb\u9a8c\u8bc1",
    "audit_logs_readonly_mock_blocked": "\u5ba1\u8ba1\u65e5\u5fd7\u963b\u65ad\u8bb0\u5f55",
    "audit_writer_local_approved": "\u672c\u5730\u5ba1\u8ba1\u5199\u5165\u9a8c\u8bc1",
    "audit_writer_local_blocked_evidence": "\u672c\u5730\u5ba1\u8ba1\u963b\u65ad\u8bc1\u636e",
    "approval_verified": "\u4eba\u5de5\u6279\u51c6\u5df2\u9a8c\u8bc1",
    "backup_created": "\u5907\u4efd\u5df2\u521b\u5efa",
    "backup_hash_verified": "\u5907\u4efd\u54c8\u5e0c\u5df2\u9a8c\u8bc1",
    "backup_integrity_verified": "\u5907\u4efd\u5b8c\u6574\u6027\u5df2\u9a8c\u8bc1",
    "backup_manifest_verified": "\u5907\u4efd\u6e05\u5355\u5df2\u9a8c\u8bc1",
    "backup_planned": "\u5907\u4efd\u5df2\u8ba1\u5212",
    "database_backup_created": "\u6570\u636e\u5e93\u5907\u4efd",
    "local_write_attempted": "\u672c\u5730\u5199\u5165\u5df2\u5c1d\u8bd5",
    "local_write_blocked": "\u672c\u5730\u5199\u5165\u5df2\u963b\u65ad",
    "local_write_failed": "\u672c\u5730\u5199\u5165\u5931\u8d25",
    "local_write_succeeded": "\u672c\u5730\u5199\u5165\u6210\u529f",
    "order_refresh_batch_write_succeeded": "\u8ba2\u5355\u5237\u65b0\u5199\u5165",
    "product_batch_local_sync_succeeded": "\u5546\u54c1\u672c\u5730\u540c\u6b65",
    "post_write_verification_failed": "\u5199\u5165\u540e\u6821\u9a8c\u5931\u8d25",
    "post_write_verification_succeeded": "\u5199\u5165\u540e\u6821\u9a8c\u6210\u529f",
    "pre_write_backup_verified": "\u5199\u5165\u524d\u5907\u4efd\u5df2\u9a8c\u8bc1",
    "restore_dry_run_planned": "\u6062\u590d\u6f14\u7ec3\u5df2\u8ba1\u5212",
    "restore_integrity_verified": "\u6062\u590d\u5b8c\u6574\u6027\u5df2\u9a8c\u8bc1",
    "restore_source_verified": "\u6062\u590d\u6e90\u5df2\u9a8c\u8bc1",
    "restore_temp_copy_verified": "\u4e34\u65f6\u6062\u590d\u526f\u672c\u5df2\u9a8c\u8bc1",
    "schema_migration_planned": "\u7ed3\u6784\u8fc1\u79fb\u5df2\u8ba1\u5212",
    "schema_migration_backup_verified": "\u7ed3\u6784\u8fc1\u79fb\u524d\u5907\u4efd\u5df2\u9a8c\u8bc1",
    "schema_migration_succeeded": "\u7ed3\u6784\u8fc1\u79fb\u6210\u529f",
    "schema_migration_verified": "\u7ed3\u6784\u8fc1\u79fb\u540e\u6821\u9a8c\u6210\u529f",
    "selected_operation_finished": "\u9009\u5b9a\u64cd\u4f5c\u5df2\u5b8c\u6210",
    "selected_operation_started": "\u9009\u5b9a\u64cd\u4f5c\u5df2\u5f00\u59cb",
    "post_write_verification_finished": "\u5199\u5165\u540e\u6821\u9a8c\u5df2\u5b8c\u6210",
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
    "product_batch_local_sync_audit_linked": "\u5546\u54c1\u540c\u6b65\u5ba1\u8ba1\u5df2\u5173\u8054",
    "selected_operation_local_mock_gate": "\u9009\u5b9a\u64cd\u4f5c\u5ba1\u8ba1\u9a8c\u8bc1",
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
            "counts_summary": counts_summary if not counts_removed else None,
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


LOCAL_WRITE_INTEGRATION_TYPES = {
    "naver_order_local_write",
    "naver_order_local_refresh",
    "controlled_naver_order_local_refresh",
}
APPROVED_INTEGRATION_OPERATION_TYPES = LOCAL_WRITE_INTEGRATION_TYPES | {
    "database_backup",
    "restore_dry_run",
    "schema_migration",
}
LOCAL_WRITE_REQUIRED_ACTIONS = {
    "approval_planned",
    "pre_write_backup_verified",
    "local_write_attempted",
}
LOCAL_WRITE_TERMINAL_ACTIONS = {
    "local_write_succeeded",
    "local_write_blocked",
    "local_write_failed",
}
LOCAL_WRITE_VERIFICATION_ACTIONS = {
    "post_write_verification_succeeded",
    "post_write_verification_failed",
}
BACKUP_REQUIRED_ACTIONS = {
    "backup_planned",
    "backup_created",
    "backup_hash_verified",
    "backup_integrity_verified",
    "backup_manifest_verified",
}
RESTORE_DRY_RUN_REQUIRED_ACTIONS = {
    "restore_dry_run_planned",
    "restore_source_verified",
    "restore_temp_copy_verified",
    "restore_integrity_verified",
}
SCHEMA_MIGRATION_REQUIRED_ACTIONS = {
    "schema_migration_planned",
    "schema_migration_backup_verified",
    "schema_migration_succeeded",
    "schema_migration_verified",
}


def _validate_integration_chain(
    audit_rows: list[dict[str, Any]],
    *,
    operation_type: str,
) -> tuple[str | None, dict[str, Any]]:
    if operation_type not in APPROVED_INTEGRATION_OPERATION_TYPES:
        return "unsupported_operation_type", {
            "operation_type": operation_type,
            "approved_operation_types": sorted(APPROVED_INTEGRATION_OPERATION_TYPES),
        }
    if not audit_rows:
        return "missing_audit_chain_rows", {}
    if len(audit_rows) > 12:
        return "too_many_audit_chain_rows", {"max_rows": 12}

    correlation_ids = {
        str(row.get("correlation_id") or "").strip()
        for row in audit_rows
    }
    if "" in correlation_ids:
        return "missing_correlation_id", {}
    if len(correlation_ids) != 1:
        return "mixed_correlation_id", {"correlation_id_count": len(correlation_ids)}

    seen_request_ids: set[str] = set()
    for index, row in enumerate(audit_rows):
        skip_reason, extra = _validate_audit_row(row)
        if skip_reason:
            return skip_reason, {"invalid_row_index": index, **extra}

        request_id = str(row.get("request_id") or "").strip()
        if request_id:
            if request_id in seen_request_ids:
                return "duplicate_request_id", {"duplicate_request_id_index": index}
            seen_request_ids.add(request_id)

        if row.get("status") == "blocked":
            safety_flags = row.get("safety_flags") or {}
            if not isinstance(safety_flags, dict) or safety_flags.get("blocked_payload_written") is not False:
                return "blocked_payload_must_not_be_written", {"invalid_row_index": index}

    actions = {str(row.get("action") or "").strip() for row in audit_rows}
    if operation_type in LOCAL_WRITE_INTEGRATION_TYPES:
        missing = sorted(LOCAL_WRITE_REQUIRED_ACTIONS - actions)
        has_terminal = bool(actions & LOCAL_WRITE_TERMINAL_ACTIONS)
        has_verification = bool(actions & LOCAL_WRITE_VERIFICATION_ACTIONS)
        if missing or not has_terminal or not has_verification:
            return "incomplete_audit_chain", {
                "missing_required_actions": missing,
                "terminal_action_observed": has_terminal,
                "post_write_verification_observed": has_verification,
            }
    elif operation_type == "database_backup":
        missing = sorted(BACKUP_REQUIRED_ACTIONS - actions)
        if missing:
            return "incomplete_audit_chain", {"missing_required_actions": missing}
    elif operation_type == "restore_dry_run":
        missing = sorted(RESTORE_DRY_RUN_REQUIRED_ACTIONS - actions)
        if missing:
            return "incomplete_audit_chain", {"missing_required_actions": missing}
    elif operation_type == "schema_migration":
        missing = sorted(SCHEMA_MIGRATION_REQUIRED_ACTIONS - actions)
        if missing:
            return "incomplete_audit_chain", {"missing_required_actions": missing}

    return None, {"correlation_id": next(iter(correlation_ids)), "chain_actions": [row["action"] for row in audit_rows]}


def write_operation_audit_integration_mock_gate(
    db: Session,
    audit_rows: list[dict[str, Any]],
    *,
    operation_type: str,
    write_enabled: bool,
    manual_approval: bool,
    verification_scope: str | None = None,
    read_only_operation: bool = False,
) -> dict[str, Any]:
    """Private integration mock gate for future audit writer wiring.

    1R verifies multi-row correlation chains only in the temporary verify_all
    database. It does not enable runtime wiring or write the real database.
    """

    result = _base_result(phase="ERP-Audit-1R")
    result.update({
        "integration_mock_gate": True,
        "operation_type": operation_type,
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    if read_only_operation:
        result.update({
            "status": "audit_integration_readonly_no_write",
            "skip_reason": "read_only_operation_not_audited_yet",
        })
        return result
    if not write_enabled:
        return result
    if verification_scope != INTEGRATION_MOCK_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "integration_mock_scope_required",
        })
        return result
    if not manual_approval:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, chain_extra = _validate_integration_chain(audit_rows, operation_type=operation_type)
    if skip_reason:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": skip_reason,
            **chain_extra,
        })
        return result

    inserted_ids: list[int] = []
    for row in audit_rows:
        inserted = _insert_audit_row(db, row)
        inserted_ids.append(inserted.id)

    result.update({
        "status": "audit_integration_chain_written",
        "audit_rows_written": True,
        "rows_written": len(inserted_ids),
        "audit_log_ids": inserted_ids,
        "correlation_id": chain_extra["correlation_id"],
        "chain_actions": chain_extra["chain_actions"],
        "runtime_writer_enabled": False,
    })
    return result


def write_selected_operation_audit_runtime_wiring_mock_gate(
    db: Session,
    *,
    operation_type: str,
    store_id: int,
    platform: str,
    target_order_hash: str | None,
    manual_approval: bool,
    backup_verified: bool,
    fake_write_result: dict[str, Any] | None,
    fake_post_write_readback: dict[str, Any] | None,
    audit_write_enabled: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private 1U mock gate for a selected-operation audit call site.

    This models the future runtime wiring shape without connecting the writer
    to real order flows or writing the real database.
    """

    result = _base_result(phase="ERP-Audit-1U")
    result.update({
        "selected_operation_mock_gate": True,
        "operation_type": operation_type,
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    if not audit_write_enabled:
        return result
    if verification_scope != SELECTED_OPERATION_MOCK_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "selected_operation_mock_scope_required",
        })
        return result
    if operation_type != "controlled_naver_order_local_refresh":
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_selected_operation",
        })
        return result
    if store_id != 8:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_store_id",
        })
        return result
    if platform != "naver":
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_platform",
        })
        return result
    if not str(target_order_hash or "").strip():
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_target_order_hash",
        })
        return result
    if manual_approval is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result
    if backup_verified is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "pre_write_backup_required",
        })
        return result
    if not isinstance(fake_write_result, dict):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_fake_write_result",
        })
        return result
    if not isinstance(fake_post_write_readback, dict):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_fake_post_write_readback",
        })
        return result

    terminal_status = str(fake_write_result.get("status") or "").strip()
    if terminal_status not in {"succeeded", "blocked", "failed"}:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "invalid_fake_write_status",
        })
        return result
    verification_status = str(fake_post_write_readback.get("status") or "").strip()
    if verification_status not in {"succeeded", "failed"}:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "invalid_fake_verification_status",
        })
        return result

    forbidden_fields = _sensitive_fields({
        "target_order_hash": target_order_hash,
        "fake_write_result": fake_write_result,
        "fake_post_write_readback": fake_post_write_readback,
    })
    if forbidden_fields:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "audit_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    terminal_action = {
        "succeeded": "local_write_succeeded",
        "blocked": "local_write_blocked",
        "failed": "local_write_failed",
    }[terminal_status]
    verification_action = {
        "succeeded": "post_write_verification_succeeded",
        "failed": "post_write_verification_failed",
    }[verification_status]
    status_by_action = {
        "approval_planned": "planned",
        "pre_write_backup_verified": "success",
        "local_write_attempted": "success",
        terminal_action: "blocked" if terminal_status == "blocked" else ("failed" if terminal_status == "failed" else "success"),
        verification_action: "failed" if verification_status == "failed" else "success",
    }

    now = datetime.now()
    correlation_id = f"audit-corr-1u-{target_order_hash[:24]}"
    actions = [
        "approval_planned",
        "pre_write_backup_verified",
        "local_write_attempted",
        terminal_action,
        verification_action,
    ]
    audit_rows: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        action_status = status_by_action[action]
        safety_flags = {
            "selected_operation_mock_scope_only": True,
            "real_api_called": False,
            "runtime_writer_enabled": False,
            "real_database_written": False,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "formal_sync_open": False,
        }
        sensitive_scan_passed = True
        if action_status == "blocked":
            safety_flags["blocked_payload_written"] = False
            safety_flags["sensitive_scan_passed"] = False
            sensitive_scan_passed = False

        audit_rows.append({
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "platform": platform,
            "environment": "local",
            "actor_type": "human",
            "actor_id": "operator-safe-hash-1u",
            "actor_label": "Local operator",
            "actor_role": "owner",
            "action": action,
            "operation_phase": "ERP-Audit-1U",
            "correlation_id": correlation_id,
            "request_id": f"audit-request-1u-{index + 1:03d}",
            "status": action_status,
            "reason_code": "selected_operation_mock_gate",
            "target_type": "order",
            "target_id": None,
            "target_hash": target_order_hash,
            "target_label": "Controlled Naver order local refresh audit mock",
            "changed_field_names": ["order_status", "delivery_status", "last_synced_at"],
            "before_summary": {
                "operation_type": operation_type,
                "selected_operation": "controlled_naver_order_local_refresh",
                "formal_sync_open": False,
            },
            "after_summary": {
                "audit_chain_action": action,
                "fake_write_status": terminal_status,
                "fake_verification_status": verification_status,
            },
            "counts_summary": {
                "audit_rows_written": 1,
                "orders_written": int(fake_write_result.get("orders_written") or 0),
                "orders_updated": int(fake_write_result.get("orders_updated") or 0),
                "products_written": 0,
                "sync_logs_written": 0,
                "capability_results_written": 0,
                "order_status_events_written": 0,
            },
            "safety_flags": safety_flags,
            "backup_path": "C:/safe-backups/codex1.db.backup-erp-audit-1u",
            "backup_sha256": "3" * 64,
            "restore_source_path": "C:/safe-backups/codex1.db.backup-erp-audit-1u",
            "restore_source_sha256": "4" * 64,
            "sensitive_scan_passed": sensitive_scan_passed,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Selected operation audit wiring mock uses temporary verification database only.",
        })

    gate = write_operation_audit_integration_mock_gate(
        db,
        audit_rows,
        operation_type=operation_type,
        write_enabled=True,
        manual_approval=True,
        verification_scope=INTEGRATION_MOCK_SCOPE,
    )
    result.update(gate)
    result.update({
        "phase": "ERP-Audit-1U",
        "selected_operation_mock_gate": True,
        "runtime_writer_enabled": False,
        "real_database_written": False,
        "operation_type": operation_type,
    })
    return result


def write_selected_operation_audit_local_implementation_mock_gate(
    db: Session,
    *,
    operation_type: str,
    store_id: int,
    platform: str,
    target_order_hash: str | None,
    manual_approval: bool,
    backup_evidence: dict[str, Any] | None,
    local_operation_result: dict[str, Any] | None,
    post_write_verification: dict[str, Any] | None,
    audit_write_enabled: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private 2D mock gate for selected local operation audit evidence.

    The helper validates the production-shaped audit chain defined in
    ERP-Audit-2C, but writes only to the isolated verify_all database.
    """

    result = _base_result(phase="ERP-Audit-2D")
    result.update({
        "selected_operation_local_mock_gate": True,
        "operation_type": operation_type,
        "runtime_writer_enabled": False,
        "real_database_written": False,
        "temp_database_only": True,
    })
    if not audit_write_enabled:
        return result
    if verification_scope != SELECTED_OPERATION_LOCAL_MOCK_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "selected_operation_local_mock_scope_required",
        })
        return result
    if operation_type != "controlled_naver_order_local_refresh":
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_selected_operation",
        })
        return result
    if store_id != 8:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_store_id",
        })
        return result
    if platform != "naver":
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsupported_platform",
        })
        return result

    safe_target_hash = str(target_order_hash or "").strip()
    if not safe_target_hash:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_target_order_hash",
        })
        return result
    if not safe_target_hash.startswith("id-hash-") or not SAFE_ENUM_PATTERN.match(safe_target_hash):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "unsafe_target_order_hash",
        })
        return result
    if manual_approval is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result
    if not isinstance(backup_evidence, dict):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "backup_evidence_required",
        })
        return result

    backup_sha256 = str(backup_evidence.get("backup_sha256") or "").strip()
    if not _valid_sha256(backup_sha256):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "invalid_backup_sha256",
        })
        return result
    required_backup_flags = {
        "backup_created": True,
        "manifest_written": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }
    missing_backup_flags = sorted(
        key
        for key, expected in required_backup_flags.items()
        if backup_evidence.get(key) is not expected
    )
    if backup_evidence.get("sqlite_integrity_check") != "ok" or missing_backup_flags:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "backup_evidence_not_verified",
            "missing_or_invalid_backup_flags": missing_backup_flags,
        })
        return result

    if not isinstance(local_operation_result, dict):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_local_operation_result",
        })
        return result
    if local_operation_result.get("formal_sync_open") is not False:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "formal_sync_must_remain_closed",
        })
        return result
    if local_operation_result.get("platform_writes_enabled") is not False:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "platform_writes_must_remain_disabled",
        })
        return result

    operation_status = str(local_operation_result.get("status") or "").strip()
    if operation_status not in {"succeeded", "blocked", "failed"}:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "invalid_local_operation_status",
        })
        return result

    if not isinstance(post_write_verification, dict):
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "missing_post_write_verification",
        })
        return result
    verification_status = str(post_write_verification.get("status") or "").strip()
    if verification_status not in {"succeeded", "failed"}:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "invalid_post_write_verification_status",
        })
        return result
    if post_write_verification.get("raw_response_saved") is not False:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "post_write_raw_response_must_not_be_saved",
        })
        return result
    if post_write_verification.get("privacy_fields_redacted") is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "post_write_privacy_must_be_redacted",
        })
        return result

    forbidden_fields = _sensitive_fields({
        "target_order_hash": safe_target_hash,
        "backup_evidence": backup_evidence,
        "local_operation_result": local_operation_result,
        "post_write_verification": post_write_verification,
    })
    if forbidden_fields:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "audit_sensitive_field_blocked",
            "forbidden_field_names": forbidden_fields,
        })
        return result

    operation_row_status = {
        "succeeded": "success",
        "blocked": "blocked",
        "failed": "failed",
    }[operation_status]
    verification_row_status = "success" if verification_status == "succeeded" else "failed"
    actions: list[tuple[str, str]] = [
        ("approval_verified", "success"),
        ("pre_write_backup_verified", "success"),
        ("selected_operation_started", "success"),
        ("selected_operation_finished", operation_row_status),
        ("post_write_verification_finished", verification_row_status),
    ]

    now = datetime.now()
    correlation_id = f"audit-corr-2d-{safe_target_hash[:24]}"
    backup_path = str(backup_evidence.get("backup_path") or "C:/safe-backups/codex1.db.backup-erp-audit-2d")
    audit_rows: list[dict[str, Any]] = []
    for index, (action, action_status) in enumerate(actions):
        safety_flags = {
            "selected_operation_local_mock_scope_only": True,
            "real_api_called": False,
            "runtime_writer_enabled": False,
            "real_database_written": False,
            "temp_database_only": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "formal_sync_open": False,
            "platform_writes_enabled": False,
            "sensitive_scan_passed": action_status != "blocked",
        }
        sensitive_scan_passed = action_status != "blocked"
        if action_status == "blocked":
            safety_flags["blocked_payload_written"] = False

        audit_rows.append({
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "platform": platform,
            "environment": "local",
            "actor_type": "human",
            "actor_id": "operator-safe-hash-2d",
            "actor_label": "Local operator",
            "actor_role": "owner",
            "action": action,
            "operation_phase": "ERP-Audit-2D",
            "correlation_id": correlation_id,
            "request_id": f"audit-request-2d-{index + 1:03d}",
            "status": action_status,
            "reason_code": "selected_operation_local_mock_gate",
            "target_type": "order",
            "target_id": None,
            "target_hash": safe_target_hash,
            "target_label": "Controlled Naver order local refresh audit mock",
            "changed_field_names": ["order_status", "delivery_status", "last_synced_at"],
            "before_summary": {
                "operation_type": operation_type,
                "manual_approval": True,
                "backup_verified": True,
                "formal_sync_open": False,
            },
            "after_summary": {
                "audit_chain_action": action,
                "local_operation_status": operation_status,
                "post_write_verification_status": verification_status,
            },
            "counts_summary": {
                "audit_rows_written": 1,
                "orders_written": int(local_operation_result.get("orders_written") or 0),
                "orders_updated": int(local_operation_result.get("orders_updated") or 0),
                "products_written": 0,
                "sync_logs_written": 0,
                "capability_results_written": 0,
                "order_status_events_written": int(local_operation_result.get("order_status_events_written") or 0),
            },
            "safety_flags": safety_flags,
            "backup_path": backup_path,
            "backup_sha256": backup_sha256,
            "restore_source_path": backup_path,
            "restore_source_sha256": backup_sha256,
            "sensitive_scan_passed": sensitive_scan_passed,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Selected operation local implementation mock writes only to verify_all temporary database.",
        })

    inserted_ids: list[int] = []
    for row_index, audit_row in enumerate(audit_rows):
        skip_reason, extra = _validate_audit_row(audit_row)
        if skip_reason:
            result.update({
                "status": "audit_write_blocked",
                "skip_reason": skip_reason,
                "invalid_row_index": row_index,
                **extra,
            })
            return result
        inserted_ids.append(_insert_audit_row(db, audit_row).id)

    result.update({
        "status": "selected_operation_local_mock_chain_written",
        "audit_rows_written": True,
        "rows_written": len(inserted_ids),
        "audit_log_ids": inserted_ids,
        "correlation_id": correlation_id,
        "chain_actions": [action for action, _status in actions],
        "runtime_writer_enabled": False,
        "real_database_written": False,
        "temp_database_only": True,
        "real_api_called": False,
        "sync_log_written": False,
        "products_written": False,
        "orders_written": False,
        "capability_tested_success_written": False,
    })
    return result


def _validate_backup_creation_evidence(
    backup_evidence: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any], str | None]:
    if not isinstance(backup_evidence, dict):
        return "backup_evidence_missing", {}, None

    backup_sha256 = str(backup_evidence.get("backup_sha256") or "")
    if not _valid_sha256(backup_sha256):
        return "invalid_backup_sha256", {}, None
    if backup_evidence.get("sqlite_integrity_check") != "ok":
        return "backup_integrity_not_verified", {}, None
    required_flags = {
        "backup_created": True,
        "manifest_written": True,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }
    for key, expected in required_flags.items():
        if backup_evidence.get(key) is not expected:
            return "backup_evidence_safety_flags_failed", {"failed_flag": key}, None
    forbidden_fields = _sensitive_fields(backup_evidence)
    if forbidden_fields:
        return "audit_sensitive_field_blocked", {"forbidden_field_names": forbidden_fields}, None
    return None, {}, backup_sha256


def _build_backup_creation_audit_rows(
    backup_evidence: dict[str, Any],
    *,
    phase: str,
    reason_code: str,
    correlation_prefix: str,
    request_prefix: str,
    actor_id: str,
    safety_scope_key: str,
    runtime_writer_enabled: bool,
    real_database_written: bool,
    notes: str,
) -> list[dict[str, Any]]:
    backup_sha256 = str(backup_evidence["backup_sha256"])
    now = datetime.now()
    correlation_id = f"{correlation_prefix}-{backup_sha256[:16]}"
    actions = [
        "backup_planned",
        "backup_created",
        "backup_hash_verified",
        "backup_integrity_verified",
        "backup_manifest_verified",
    ]
    audit_rows: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        audit_rows.append({
            "created_at": now,
            "updated_at": now,
            "store_id": None,
            "platform": "local",
            "environment": "local",
            "actor_type": str(backup_evidence.get("created_by_actor_type") or "human")[:40],
            "actor_id": actor_id,
            "actor_label": str(backup_evidence.get("created_by_actor_label") or "Local operator")[:120],
            "actor_role": "owner",
            "action": action,
            "operation_phase": phase,
            "correlation_id": correlation_id,
            "request_id": f"{request_prefix}-{index + 1:03d}",
            "status": "success",
            "reason_code": reason_code,
            "target_type": "backup",
            "target_id": None,
            "target_hash": f"id-hash-{backup_sha256[:10]}",
            "target_label": "Local database backup evidence",
            "changed_field_names": ["backup_sha256", "sqlite_integrity_check", "manifest_written"],
            "before_summary": {
                "backup_audit": "not_recorded",
                "formal_sync_open": False,
            },
            "after_summary": {
                "audit_chain_action": action,
                "backup_verified": True,
                "manifest_verified": True,
            },
            "counts_summary": {
                "audit_rows_written": 1,
                "orders_written": 0,
                "products_written": 0,
                "sync_logs_written": 0,
                "capability_results_written": 0,
                "order_status_events_written": 0,
            },
            "safety_flags": {
                safety_scope_key: True,
                "real_api_called": False,
                "runtime_writer_enabled": runtime_writer_enabled,
                "real_database_written": real_database_written,
                "business_tables_written": False,
                "raw_response_saved": False,
                "secrets_saved": False,
                "privacy_fields_redacted": True,
                "formal_sync_open": False,
            },
            "backup_path": backup_evidence.get("backup_path"),
            "backup_sha256": backup_sha256,
            "restore_source_path": backup_evidence.get("backup_path"),
            "restore_source_sha256": backup_sha256,
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": notes,
        })
    return audit_rows


def write_backup_creation_audit_mock_gate(
    db: Session,
    *,
    backup_evidence: dict[str, Any] | None,
    audit_write_enabled: bool,
    manual_approval: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private 1X mock gate for future backup creation audit evidence."""

    result = _base_result(phase="ERP-Audit-1X")
    result.update({
        "backup_creation_audit_mock_gate": True,
        "operation_type": "database_backup",
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    if not audit_write_enabled:
        return result
    if verification_scope != BACKUP_AUDIT_MOCK_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "backup_audit_mock_scope_required",
        })
        return result
    if manual_approval is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, extra, _backup_sha256 = _validate_backup_creation_evidence(backup_evidence)
    if skip_reason:
        result.update({"status": "audit_write_blocked", "skip_reason": skip_reason, **extra})
        return result

    audit_rows = _build_backup_creation_audit_rows(
        backup_evidence or {},
        phase="ERP-Audit-1X",
        reason_code="backup_creation_audit_mock_gate",
        correlation_prefix="audit-corr-1x",
        request_prefix="audit-request-1x",
        actor_id="operator-safe-hash-1x",
        safety_scope_key="backup_audit_mock_scope_only",
        runtime_writer_enabled=False,
        real_database_written=False,
        notes="Backup creation audit mock writes only safe evidence in the temporary verification database.",
    )
    gate = write_operation_audit_integration_mock_gate(
        db,
        audit_rows,
        operation_type="database_backup",
        write_enabled=True,
        manual_approval=True,
        verification_scope=INTEGRATION_MOCK_SCOPE,
    )
    result.update(gate)
    result.update({
        "phase": "ERP-Audit-1X",
        "backup_creation_audit_mock_gate": True,
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    return result


def write_backup_creation_audit_runtime_wiring_mock_gate(
    db: Session,
    *,
    backup_evidence: dict[str, Any] | None,
    audit_write_enabled: bool,
    manual_approval: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private 1Z mock gate for backup-helper-to-audit runtime wiring."""

    result = _base_result(phase="ERP-Audit-1Z")
    result.update({
        "backup_creation_audit_runtime_wiring_mock_gate": True,
        "operation_type": "database_backup",
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    if not audit_write_enabled:
        return result
    if verification_scope != BACKUP_AUDIT_RUNTIME_MOCK_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "backup_audit_runtime_mock_scope_required",
        })
        return result
    if manual_approval is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, extra, _backup_sha256 = _validate_backup_creation_evidence(backup_evidence)
    if skip_reason:
        result.update({"status": "audit_write_blocked", "skip_reason": skip_reason, **extra})
        return result

    audit_rows = _build_backup_creation_audit_rows(
        backup_evidence or {},
        phase="ERP-Audit-1Z",
        reason_code="backup_creation_audit_runtime_wiring_mock_gate",
        correlation_prefix="audit-corr-1z",
        request_prefix="audit-request-1z",
        actor_id="operator-safe-hash-1z",
        safety_scope_key="backup_audit_runtime_mock_scope_only",
        runtime_writer_enabled=False,
        real_database_written=False,
        notes="Backup creation audit runtime wiring mock uses the temporary verification database only.",
    )
    gate = write_operation_audit_integration_mock_gate(
        db,
        audit_rows,
        operation_type="database_backup",
        write_enabled=True,
        manual_approval=True,
        verification_scope=INTEGRATION_MOCK_SCOPE,
    )
    result.update(gate)
    result.update({
        "phase": "ERP-Audit-1Z",
        "backup_creation_audit_runtime_wiring_mock_gate": True,
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    return result


def write_backup_creation_audit_local(
    db: Session,
    *,
    backup_evidence: dict[str, Any] | None,
    audit_write_enabled: bool,
    manual_approval: bool,
    local_write_scope: str | None = None,
) -> dict[str, Any]:
    """Controlled 2A local audit chain for an approved real local backup."""

    result = _base_result(phase="ERP-Audit-2A")
    result.update({
        "backup_creation_audit_local_implementation": True,
        "operation_type": "database_backup",
        "runtime_writer_enabled": False,
        "real_database_written": False,
    })
    if not audit_write_enabled:
        return result
    if local_write_scope != LOCAL_WRITER_SCOPE:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "local_writer_scope_required",
        })
        return result
    if manual_approval is not True:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    skip_reason, extra, _backup_sha256 = _validate_backup_creation_evidence(backup_evidence)
    if skip_reason:
        result.update({"status": "audit_write_blocked", "skip_reason": skip_reason, **extra})
        return result
    if not str((backup_evidence or {}).get("manifest_path") or "").strip():
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": "manifest_path_missing",
        })
        return result

    audit_rows = _build_backup_creation_audit_rows(
        backup_evidence or {},
        phase="ERP-Audit-2A",
        reason_code="backup_creation_audit_local_implementation",
        correlation_prefix="audit-corr-2a",
        request_prefix="audit-request-2a",
        actor_id="operator-safe-hash-2a",
        safety_scope_key="backup_audit_local_runtime",
        runtime_writer_enabled=True,
        real_database_written=True,
        notes="Approved local backup creation audit chain. Only operation_audit_logs rows are written.",
    )
    skip_reason, chain_extra = _validate_integration_chain(audit_rows, operation_type="database_backup")
    if skip_reason:
        result.update({
            "status": "audit_write_blocked",
            "skip_reason": skip_reason,
            **chain_extra,
        })
        return result

    inserted_ids: list[int] = []
    for row in audit_rows:
        inserted = _insert_audit_row(db, row)
        inserted_ids.append(inserted.id)

    result.update({
        "status": "backup_audit_chain_written",
        "audit_rows_written": True,
        "rows_written": len(inserted_ids),
        "audit_log_ids": inserted_ids,
        "correlation_id": chain_extra["correlation_id"],
        "chain_actions": chain_extra["chain_actions"],
        "runtime_writer_enabled": True,
        "real_database_written": True,
        "real_api_called": False,
        "sync_log_written": False,
        "products_written": False,
        "orders_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
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
