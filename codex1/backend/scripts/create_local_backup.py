from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
CODEX1_ROOT = BACKEND_DIR.parent
CODEX2_ROOT = CODEX1_ROOT.parent
PROJECT_DIR = BACKEND_DIR.parent.parent.parent
DEFAULT_SOURCE_DB = BACKEND_DIR / "codex1.db"
DEFAULT_BACKUP_ROOT = PROJECT_DIR / "codex1-db-backups"

ALLOWED_RETENTION_CLASSES = {
    "pre_write",
    "pre_migration",
    "pre_restore",
    "scheduled_daily",
    "scheduled_weekly",
    "manual_checkpoint",
    "release_checkpoint",
    "incident_response",
}

RETENTION_DAYS_BY_CLASS = {
    "pre_write": 90,
    "pre_migration": 180,
    "pre_restore": 180,
    "manual_checkpoint": 90,
    "release_checkpoint": 180,
    "scheduled_daily": 14,
    "scheduled_weekly": 56,
}

REQUIRED_MANIFEST_FIELDS = {
    "manifest_version",
    "backup_id",
    "phase",
    "operation_type",
    "created_at",
    "created_by_actor_type",
    "created_by_actor_label",
    "source_db_path",
    "backup_path",
    "backup_sha256",
    "backup_size_bytes",
    "backup_method",
    "sqlite_integrity_check",
    "git_commit_codex1",
    "git_commit_codex2",
    "baseline_counts",
    "retention_class",
    "retention_reason",
    "retention_until",
    "legal_hold",
    "protected_from_auto_delete",
    "restore_drill_status",
    "sensitive_scan_passed",
    "raw_response_saved",
    "secrets_saved",
    "privacy_fields_redacted",
}

SAFE_SLUG_PATTERN = re.compile(r"[^a-z0-9_-]+")
SENSITIVE_MARKERS = {
    "authorization:",
    "bearer ",
    "bcrypt",
    "client_secret",
    "client-secret",
    "headers-must-not-leak",
    "raw_response",
    "raw response",
    "raw-request",
    "signature",
    "token-must-not-leak",
}
SENSITIVE_KEYS = {
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
    "rawrequest",
    "rawresponse",
    "receivername",
    "receiverphone",
    "refreshtoken",
    "signature",
    "token",
    "zipcode",
}


def _normalize_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _sensitive_fields(payload: Any) -> list[str]:
    forbidden: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                normalized = _normalize_key(str(key))
                if normalized in {"rawresponsesaved", "secretssaved", "privacyfieldsredacted"}:
                    walk(nested)
                    continue
                if normalized.endswith("hash"):
                    walk(nested)
                    continue
                if normalized in SENSITIVE_KEYS:
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
            if any(marker in lowered for marker in SENSITIVE_MARKERS):
                forbidden.add("sensitive_value")

    walk(payload)
    return sorted(forbidden)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _retention_until(created_at: datetime, retention_class: str) -> str | None:
    days = RETENTION_DAYS_BY_CLASS.get(retention_class)
    if days is None:
        return None
    return (created_at + timedelta(days=days)).isoformat()


def _safe_slug(value: str) -> str:
    slug = SAFE_SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return slug or "manual-backup"


def _resolve_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved


def _git_commit(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _collect_counts_and_metadata(db_path: Path) -> tuple[dict[str, int], dict[str, int | str]]:
    with closing(sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        tables = [
            "stores",
            "products",
            "orders",
            "sync_logs",
            "api_capability_test_results",
            "order_status_events",
            "operation_audit_logs",
        ]
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if table in table_names
            else 0
            for table in tables
        }
        if "api_capability_test_results" in table_names:
            counts["tested_success_store8"] = conn.execute(
                "SELECT COUNT(*) FROM api_capability_test_results WHERE store_id=8 AND test_status='tested_success'"
            ).fetchone()[0]
        else:
            counts["tested_success_store8"] = 0
    return counts, {
        "sqlite_integrity_check": integrity,
        "sqlite_page_count": page_count,
        "sqlite_page_size": page_size,
    }


def _sqlite_online_backup(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(destination_path)) as destination:
            source.backup(destination)


def create_local_backup(
    *,
    phase: str,
    operation_type: str,
    created_by_actor_type: str,
    created_by_actor_label: str,
    retention_class: str,
    retention_reason: str,
    source_db_path: Path = DEFAULT_SOURCE_DB,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    related_store_ids: list[int] | None = None,
    related_platforms: list[str] | None = None,
    related_safe_hashes: list[str] | None = None,
    operation_audit_correlation_id: str | None = None,
    git_commit_codex1: str = "unknown",
    git_commit_codex2: str = "unknown",
    allow_non_default_source: bool = False,
    allow_custom_backup_root: bool = False,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    result = {
        "phase": "ERP-Backup-1G",
        "status": "backup_not_created",
        "backup_created": False,
        "manifest_written": False,
        "real_restore_executed": False,
        "backup_deleted": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }
    inputs = {
        "phase": phase,
        "operation_type": operation_type,
        "created_by_actor_type": created_by_actor_type,
        "created_by_actor_label": created_by_actor_label,
        "retention_class": retention_class,
        "retention_reason": retention_reason,
        "related_store_ids": related_store_ids or [],
        "related_platforms": related_platforms or [],
        "related_safe_hashes": related_safe_hashes or [],
        "operation_audit_correlation_id": operation_audit_correlation_id,
    }
    if _sensitive_fields(inputs):
        result.update({"status": "backup_blocked", "skip_reason": "sensitive_input_blocked"})
        return result
    if retention_class not in ALLOWED_RETENTION_CLASSES:
        result.update({"status": "backup_blocked", "skip_reason": "invalid_retention_class"})
        return result

    source_path = source_db_path.resolve()
    intended_source = DEFAULT_SOURCE_DB.resolve()
    if source_path != intended_source and not allow_non_default_source:
        result.update({"status": "backup_blocked", "skip_reason": "source_db_path_mismatch"})
        return result
    if not source_path.exists():
        result.update({"status": "backup_blocked", "skip_reason": "source_db_missing"})
        return result

    backup_root = backup_root.resolve()
    if backup_root != DEFAULT_BACKUP_ROOT.resolve() and not allow_custom_backup_root:
        result.update({"status": "backup_blocked", "skip_reason": "backup_root_not_approved"})
        return result
    backup_root.mkdir(parents=True, exist_ok=True)
    created_at = created_at or datetime.now(timezone.utc)
    timestamp = created_at.strftime("%Y%m%d-%H%M%S")
    safe_phase = _safe_slug(phase)
    backup_path = backup_root / f"codex1.db.backup-{safe_phase}-{timestamp}.db"
    backup_path = _resolve_inside(backup_path, backup_root)
    tmp_backup_path = backup_path.with_suffix(backup_path.suffix + ".tmp")
    manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    tmp_manifest_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json.tmp")
    if backup_path.exists() or manifest_path.exists():
        result.update({"status": "backup_blocked", "skip_reason": "backup_or_manifest_already_exists"})
        return result

    source_size = source_path.stat().st_size
    source_sha256 = _sha256_file(source_path)
    final_backup_created = False
    final_manifest_created = False
    try:
        _sqlite_online_backup(source_path, tmp_backup_path)
        backup_counts, sqlite_meta = _collect_counts_and_metadata(tmp_backup_path)
        if sqlite_meta["sqlite_integrity_check"] != "ok":
            result.update({"status": "backup_blocked", "skip_reason": "sqlite_integrity_check_failed"})
            return result

        backup_sha256 = _sha256_file(tmp_backup_path)
        manifest = {
            "manifest_version": "backup-manifest-v1",
            "backup_id": f"backup-{safe_phase}-{timestamp}",
            "phase": phase,
            "operation_type": operation_type,
            "created_at": created_at.isoformat(),
            "created_by_actor_type": created_by_actor_type,
            "created_by_actor_label": created_by_actor_label,
            "source_db_path": source_path.as_posix(),
            "source_db_sha256_before_backup": source_sha256,
            "source_db_size_bytes_before_backup": source_size,
            "backup_path": backup_path.as_posix(),
            "backup_sha256": backup_sha256,
            "backup_size_bytes": tmp_backup_path.stat().st_size,
            "backup_method": "sqlite_online_backup",
            "sqlite_page_count": sqlite_meta["sqlite_page_count"],
            "sqlite_page_size": sqlite_meta["sqlite_page_size"],
            "sqlite_integrity_check": sqlite_meta["sqlite_integrity_check"],
            "git_commit_codex1": git_commit_codex1,
            "git_commit_codex2": git_commit_codex2,
            "baseline_counts": backup_counts,
            "related_store_ids": related_store_ids or [],
            "related_platforms": related_platforms or [],
            "related_safe_hashes": related_safe_hashes or [],
            "retention_class": retention_class,
            "retention_reason": retention_reason,
            "retention_until": _retention_until(created_at, retention_class),
            "legal_hold": False,
            "protected_from_auto_delete": retention_class in {
                "pre_write",
                "pre_migration",
                "pre_restore",
                "incident_response",
            } or bool(operation_audit_correlation_id),
            "restore_drill_status": "pending",
            "last_restore_drill_at": None,
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "operation_audit_correlation_id": operation_audit_correlation_id,
            "notes": "Manual local backup created by ERP-Backup-1G helper.",
        }
        missing = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
        if missing:
            result.update({"status": "backup_blocked", "skip_reason": "missing_manifest_fields"})
            return result
        if _sensitive_fields(manifest):
            result.update({"status": "backup_blocked", "skip_reason": "manifest_sensitive_field_blocked"})
            return result
        tmp_manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        loaded = json.loads(tmp_manifest_path.read_text(encoding="utf-8"))
        if loaded["backup_sha256"] != backup_sha256:
            result.update({"status": "backup_blocked", "skip_reason": "manifest_sha256_mismatch"})
            return result
        if loaded["backup_size_bytes"] != tmp_backup_path.stat().st_size:
            result.update({"status": "backup_blocked", "skip_reason": "manifest_size_mismatch"})
            return result

        tmp_backup_path.replace(backup_path)
        final_backup_created = True
        tmp_manifest_path.replace(manifest_path)
        final_manifest_created = True
    except Exception as exc:
        if final_backup_created and not final_manifest_created:
            backup_path.unlink(missing_ok=True)
        result.update({
            "status": "backup_blocked",
            "skip_reason": "backup_helper_error",
            "error_class": exc.__class__.__name__,
        })
        return result
    finally:
        tmp_backup_path.unlink(missing_ok=True)
        tmp_manifest_path.unlink(missing_ok=True)

    result.update({
        "status": "backup_created",
        "backup_created": True,
        "manifest_written": True,
        "backup_path": backup_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "backup_sha256": backup_sha256,
        "backup_size_bytes": backup_path.stat().st_size,
        "source_db_sha256_before_backup": source_sha256,
        "source_db_size_bytes_before_backup": source_size,
        "sqlite_integrity_check": sqlite_meta["sqlite_integrity_check"],
        "baseline_counts": backup_counts,
        "retention_class": retention_class,
        "protected_from_auto_delete": manifest["protected_from_auto_delete"],
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a safe local backup for backend/codex1.db.")
    parser.add_argument("--phase", required=True)
    parser.add_argument("--operation-type", required=True)
    parser.add_argument("--actor-label", default="local_operator")
    parser.add_argument("--actor-type", default="human")
    parser.add_argument("--retention-class", default="manual_checkpoint")
    parser.add_argument("--retention-reason", default="manual local backup")
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--operation-audit-correlation-id", default=None)
    args = parser.parse_args()

    result = create_local_backup(
        phase=args.phase,
        operation_type=args.operation_type,
        created_by_actor_type=args.actor_type,
        created_by_actor_label=args.actor_label,
        retention_class=args.retention_class,
        retention_reason=args.retention_reason,
        backup_root=Path(args.backup_root),
        operation_audit_correlation_id=args.operation_audit_correlation_id,
        git_commit_codex1=_git_commit(CODEX1_ROOT),
        git_commit_codex2=_git_commit(CODEX2_ROOT),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["status"] != "backup_created":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
