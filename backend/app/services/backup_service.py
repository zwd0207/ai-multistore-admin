from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.create_local_backup import DEFAULT_BACKUP_ROOT
from scripts.list_local_backups import list_local_backups


BACKUP_REPORT_MOCK_SCOPE = "verify_all_temp_db"
DEFAULT_BACKUP_REPORT_LIMIT = 20
MAX_BACKUP_REPORT_LIMIT = 50
ALLOWED_BACKUP_REPORT_FILTERS = {"limit"}


FORBIDDEN_BACKUP_REPORT_MARKERS = (
    "authorization",
    "bearer ",
    "bcrypt",
    "client_secret",
    "client-secret",
    "headers",
    "raw response",
    "raw_response_body",
    "signature",
    "token",
    "productorderid",
    "buyername",
    "buyerphone",
    "receivername",
    "receiverphone",
    "zipcode",
)


def _base_backup_report_result(*, phase: str, public_endpoint_enabled: bool) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": "backup_report_not_available",
        "backup_report_readonly": True,
        "public_endpoint_enabled": public_endpoint_enabled,
        "backup_deleted": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "rows_written": 0,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }


def _validate_limit(limit: int | None) -> tuple[int | None, dict[str, Any]]:
    if limit is None:
        return DEFAULT_BACKUP_REPORT_LIMIT, {"limit_was_capped": False}
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        return None, {"skip_reason": "invalid_limit"}
    if normalized < 1:
        return None, {"skip_reason": "invalid_limit"}
    return min(normalized, MAX_BACKUP_REPORT_LIMIT), {"limit_was_capped": normalized > MAX_BACKUP_REPORT_LIMIT}


def _sensitive_scan_passed(payload: object) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, default=str).lower()
    return not any(marker in serialized for marker in FORBIDDEN_BACKUP_REPORT_MARKERS)


def _safe_backup_business_message(report: dict[str, Any]) -> str:
    if report.get("status") == "backup_report_empty":
        return "当前还没有可读取的本地备份记录。"
    if report.get("status") != "backup_report_ready":
        return "本地备份报告暂不可用，请检查备份目录或稍后重试。"
    if not report.get("items"):
        return "当前还没有可读取的本地备份记录。"
    if report.get("all_manifests_valid") and report.get("all_sensitive_scans_passed"):
        return "本地备份报告已读取，备份清单和安全检查通过。"
    return "本地备份报告已读取，但存在需要人工复核的备份清单。"


def _summarize_report_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    valid_count = sum(1 for item in items if item.get("manifest_valid") is True)
    sensitive_passed_count = sum(1 for item in items if item.get("sensitive_scan_passed") is True)
    existing_backup_count = sum(1 for item in items if item.get("backup_exists") is True)
    return {
        "reported_item_count": len(items),
        "valid_manifest_count": valid_count,
        "sensitive_scan_passed_count": sensitive_passed_count,
        "existing_backup_count": existing_backup_count,
        "needs_attention_count": len(items) - min(valid_count, sensitive_passed_count, existing_backup_count),
    }


def _build_backup_report(
    *,
    phase: str,
    public_endpoint_enabled: bool,
    limit: int | None = None,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    allow_custom_root: bool = False,
) -> dict[str, Any]:
    normalized_limit, limit_meta = _validate_limit(limit)
    result = _base_backup_report_result(phase=phase, public_endpoint_enabled=public_endpoint_enabled)
    result.update(limit_meta)
    if normalized_limit is None:
        result.update({"status": "backup_report_blocked"})
        return result

    report = list_local_backups(
        backup_root=backup_root,
        limit=normalized_limit,
        allow_custom_root=allow_custom_root,
    )
    result.update(report)
    result.update({
        "phase": phase,
        "backup_report_readonly": True,
        "public_endpoint_enabled": public_endpoint_enabled,
        "limit": normalized_limit,
        "limit_was_capped": limit_meta["limit_was_capped"],
        "rows_written": 0,
        "backup_deleted": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
        "business_message": _safe_backup_business_message(report),
    })
    items = result.get("items") if isinstance(result.get("items"), list) else []
    result["summary"] = _summarize_report_items(items)
    result["sensitive_scan_passed"] = _sensitive_scan_passed(result)
    if result["sensitive_scan_passed"] is not True:
        result.update({
            "status": "backup_report_blocked",
            "skip_reason": "backup_report_sensitive_field_blocked",
            "items": [],
            "latest_backup": None,
        })
    return result


def list_backup_report_readonly_mock_gate(
    *,
    limit: int | None = None,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    if verification_scope != BACKUP_REPORT_MOCK_SCOPE:
        result = _base_backup_report_result(phase="ERP-Backup-1K", public_endpoint_enabled=False)
        result.update({
            "status": "backup_report_blocked",
            "skip_reason": "backup_report_mock_scope_required",
        })
        return result
    return _build_backup_report(
        phase="ERP-Backup-1K",
        public_endpoint_enabled=False,
        limit=limit,
        backup_root=backup_root,
        allow_custom_root=True,
    )


def list_backup_report_readonly_local(*, limit: int | None = None) -> dict[str, Any]:
    return _build_backup_report(
        phase="ERP-Backup-1L",
        public_endpoint_enabled=True,
        limit=limit,
        backup_root=DEFAULT_BACKUP_ROOT,
        allow_custom_root=False,
    )


def summarize_backup_report_readonly_local(*, limit: int | None = None) -> dict[str, Any]:
    report = list_backup_report_readonly_local(limit=limit)
    summary = dict(report.get("summary") or {})
    summary.update({
        "phase": "ERP-Backup-1L",
        "status": "backup_summary_success" if report.get("status") in {"backup_report_ready", "backup_report_empty"} else "backup_summary_blocked",
        "backup_report_readonly": True,
        "public_endpoint_enabled": True,
        "backup_count": report.get("backup_count", 0),
        "manifest_count": report.get("manifest_count", 0),
        "all_manifests_valid": report.get("all_manifests_valid", False),
        "all_sensitive_scans_passed": report.get("all_sensitive_scans_passed", False),
        "latest_backup": report.get("latest_backup"),
        "business_message": report.get("business_message"),
        "backup_deleted": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "rows_written": 0,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
        "sensitive_scan_passed": report.get("sensitive_scan_passed") is True,
    })
    return summary
