from __future__ import annotations

from datetime import date, datetime, time
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.operation_audit_log import OperationAuditLog


VERIFICATION_SCOPE = "verify_all_temp_db"
LOCAL_WRITER_SCOPE = "local_runtime_approved"

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
