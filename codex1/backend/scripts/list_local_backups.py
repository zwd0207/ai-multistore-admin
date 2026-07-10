from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.create_local_backup import DEFAULT_BACKUP_ROOT, REQUIRED_MANIFEST_FIELDS, _sensitive_fields
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from create_local_backup import DEFAULT_BACKUP_ROOT, REQUIRED_MANIFEST_FIELDS, _sensitive_fields  # type: ignore


def _resolve_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _abbrev(value: object, keep: int = 12) -> str | None:
    if not value:
        return None
    text = str(value)
    return text if len(text) <= keep else f"{text[:keep]}..."


def _safe_manifest_summary(manifest: dict[str, Any], manifest_path: Path, backup_root: Path) -> dict[str, Any]:
    missing_fields = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    sensitive_fields = _sensitive_fields(manifest)
    backup_path = Path(str(manifest.get("backup_path", "")))
    backup_exists = False
    backup_inside_root = False
    backup_size_matches = False
    if str(backup_path):
        try:
            resolved_backup = _resolve_inside(backup_path, backup_root)
            backup_inside_root = True
            backup_exists = resolved_backup.exists()
            if backup_exists:
                backup_size_matches = resolved_backup.stat().st_size == int(manifest.get("backup_size_bytes", -1))
        except (ValueError, OSError, TypeError):
            backup_inside_root = False
    return {
        "backup_id": str(manifest.get("backup_id") or manifest_path.stem)[:120],
        "phase": str(manifest.get("phase") or "")[:80],
        "operation_type": str(manifest.get("operation_type") or "")[:120],
        "created_at": manifest.get("created_at"),
        "created_at_sort": (_parse_datetime(manifest.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)).isoformat(),
        "created_by_actor_type": str(manifest.get("created_by_actor_type") or "")[:40],
        "created_by_actor_label": str(manifest.get("created_by_actor_label") or "")[:80],
        "backup_path": str(manifest.get("backup_path") or ""),
        "manifest_path": manifest_path.as_posix(),
        "backup_sha256_abbrev": _abbrev(manifest.get("backup_sha256")),
        "backup_size_bytes": int(manifest.get("backup_size_bytes") or 0),
        "sqlite_integrity_check": manifest.get("sqlite_integrity_check"),
        "retention_class": manifest.get("retention_class"),
        "retention_until": manifest.get("retention_until"),
        "protected_from_auto_delete": bool(manifest.get("protected_from_auto_delete")),
        "restore_drill_status": manifest.get("restore_drill_status"),
        "baseline_counts": {
            key: int(value)
            for key, value in (manifest.get("baseline_counts") or {}).items()
            if isinstance(value, int)
        },
        "manifest_valid": not missing_fields and not sensitive_fields,
        "missing_manifest_fields": missing_fields,
        "sensitive_scan_passed": not sensitive_fields
        and manifest.get("sensitive_scan_passed") is True
        and manifest.get("raw_response_saved") is False
        and manifest.get("secrets_saved") is False
        and manifest.get("privacy_fields_redacted") is True,
        "backup_exists": backup_exists,
        "backup_inside_root": backup_inside_root,
        "backup_size_matches": backup_size_matches,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }


def list_local_backups(
    *,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    limit: int = 20,
    allow_custom_root: bool = False,
) -> dict[str, Any]:
    result = {
        "phase": "ERP-Backup-1I",
        "status": "backup_report_not_available",
        "backup_root": backup_root.resolve().as_posix(),
        "backup_count": 0,
        "manifest_count": 0,
        "items": [],
        "backup_deleted": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }
    backup_root = backup_root.resolve()
    if backup_root != DEFAULT_BACKUP_ROOT.resolve() and not allow_custom_root:
        result.update({"status": "backup_report_blocked", "skip_reason": "backup_root_not_approved"})
        return result
    if not backup_root.exists():
        result.update({"status": "backup_report_empty", "skip_reason": "backup_root_missing"})
        return result
    try:
        _resolve_inside(backup_root, backup_root)
    except ValueError:
        result.update({"status": "backup_report_blocked", "skip_reason": "backup_root_invalid"})
        return result

    backup_files = sorted(backup_root.glob("*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    manifest_files = sorted(backup_root.glob("*.manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    result["backup_count"] = len(backup_files)
    result["manifest_count"] = len(manifest_files)

    items: list[dict[str, Any]] = []
    for manifest_path in manifest_files[: max(0, min(limit, 100))]:
        try:
            manifest_path = _resolve_inside(manifest_path, backup_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            items.append(_safe_manifest_summary(manifest, manifest_path, backup_root))
        except Exception as exc:
            items.append({
                "backup_id": manifest_path.stem[:120],
                "manifest_path": manifest_path.as_posix(),
                "manifest_valid": False,
                "sensitive_scan_passed": False,
                "skip_reason": "manifest_read_failed",
                "error_class": exc.__class__.__name__,
                "raw_response_saved": False,
                "secrets_saved": False,
                "privacy_fields_redacted": True,
            })
    items.sort(key=lambda item: item.get("created_at_sort") or "", reverse=True)
    result.update({
        "status": "backup_report_ready",
        "items": items,
        "latest_backup": items[0] if items else None,
        "all_manifests_valid": all(item.get("manifest_valid") for item in items),
        "all_sensitive_scans_passed": all(item.get("sensitive_scan_passed") for item in items),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="List safe local backup manifests.")
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = list_local_backups(backup_root=Path(args.backup_root), limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["status"] not in {"backup_report_ready", "backup_report_empty"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
