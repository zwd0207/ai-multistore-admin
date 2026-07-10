from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from scripts.create_local_backup import (
        DEFAULT_BACKUP_ROOT,
        DEFAULT_SOURCE_DB,
        REQUIRED_MANIFEST_FIELDS,
        _sensitive_fields,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from create_local_backup import (  # type: ignore
        DEFAULT_BACKUP_ROOT,
        DEFAULT_SOURCE_DB,
        REQUIRED_MANIFEST_FIELDS,
        _sensitive_fields,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved


def _collect_counts_and_integrity(db_path: Path, expected_tables: list[str]) -> tuple[str, dict[str, int]]:
    conn = sqlite3.connect(db_path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        missing = sorted(set(expected_tables) - table_names)
        if missing:
            raise ValueError(f"missing expected tables: {', '.join(missing)}")
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in expected_tables
        }
    finally:
        conn.close()
    return integrity, counts


def _base_result() -> dict[str, Any]:
    return {
        "phase": "ERP-Backup-1H",
        "status": "restore_dry_run_not_verified",
        "manifest_valid": False,
        "backup_verified": False,
        "temporary_restore_verified": False,
        "temporary_restore_deleted": False,
        "real_restore_executed": False,
        "production_db_touched": False,
        "backup_deleted": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }


def restore_backup_dry_run(
    *,
    manifest_path: Path,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    restore_root: Path | None = None,
    restore_path: Path | None = None,
    cleanup_restore_copy: bool = True,
    allow_custom_roots: bool = False,
) -> dict[str, Any]:
    result = _base_result()
    approved_backup_root = backup_root.resolve()
    if approved_backup_root != DEFAULT_BACKUP_ROOT.resolve() and not allow_custom_roots:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "backup_root_not_approved"})
        return result

    try:
        manifest_path = _resolve_inside(manifest_path, approved_backup_root)
    except ValueError:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "manifest_outside_approved_root"})
        return result
    if not manifest_path.exists():
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "manifest_missing"})
        return result

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "manifest_invalid_json"})
        return result

    missing_fields = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing_fields:
        result.update({
            "status": "restore_dry_run_blocked",
            "skip_reason": "missing_manifest_fields",
            "missing_manifest_fields": missing_fields,
        })
        return result
    if _sensitive_fields(manifest):
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "manifest_sensitive_field_blocked"})
        return result
    if manifest.get("raw_response_saved") is not False or manifest.get("secrets_saved") is not False:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "unsafe_manifest_saved_flags"})
        return result
    if manifest.get("privacy_fields_redacted") is not True or manifest.get("sensitive_scan_passed") is not True:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "manifest_safety_flags_failed"})
        return result
    result["manifest_valid"] = True

    backup_path = Path(str(manifest["backup_path"]))
    try:
        backup_path = _resolve_inside(backup_path, approved_backup_root)
    except ValueError:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "backup_outside_approved_root"})
        return result
    if not backup_path.exists():
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "backup_missing"})
        return result
    if backup_path.stat().st_size != int(manifest["backup_size_bytes"]):
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "backup_size_mismatch"})
        return result
    backup_sha256 = _sha256_file(backup_path)
    if backup_sha256 != manifest["backup_sha256"]:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "backup_sha256_mismatch"})
        return result
    result["backup_verified"] = True

    restore_temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if restore_path is None:
        if restore_root is None:
            restore_temp_dir = tempfile.TemporaryDirectory(prefix="erp-backup-1h-", ignore_cleanup_errors=True)
            restore_root = Path(restore_temp_dir.name)
        else:
            restore_root = restore_root.resolve()
            if restore_root == DEFAULT_SOURCE_DB.parent.resolve() and not allow_custom_roots:
                result.update({"status": "restore_dry_run_blocked", "skip_reason": "restore_root_not_approved"})
                return result
            restore_root.mkdir(parents=True, exist_ok=True)
        restore_path = restore_root / f"{backup_path.name}.restore-dry-run-copy.db"

    production_db_path = DEFAULT_SOURCE_DB.resolve()
    restore_path = restore_path.resolve()
    if restore_path == production_db_path:
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "restore_target_is_production_db"})
        return result
    if restore_path == backup_path.resolve():
        result.update({"status": "restore_dry_run_blocked", "skip_reason": "restore_target_is_backup_source"})
        return result

    source_before = None
    if production_db_path.exists():
        source_before = {
            "size": production_db_path.stat().st_size,
            "sha256": _sha256_file(production_db_path),
        }
    try:
        restore_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, restore_path)
        restored_sha256 = _sha256_file(restore_path)
        if restored_sha256 != backup_sha256:
            result.update({"status": "restore_dry_run_blocked", "skip_reason": "restored_copy_sha256_mismatch"})
            return result
        expected_counts = manifest["baseline_counts"]
        expected_tables = [
            table
            for table in expected_counts
            if table != "tested_success_store8"
        ]
        integrity, observed_counts = _collect_counts_and_integrity(restore_path, expected_tables)
        if integrity != "ok":
            result.update({"status": "restore_dry_run_blocked", "skip_reason": "sqlite_integrity_check_failed"})
            return result
        if observed_counts != {table: expected_counts[table] for table in expected_tables}:
            result.update({
                "status": "restore_dry_run_blocked",
                "skip_reason": "restore_count_mismatch",
                "observed_counts": observed_counts,
                "expected_counts": expected_counts,
            })
            return result
        result.update({
            "status": "restore_dry_run_verified",
            "temporary_restore_verified": True,
            "backup_path": backup_path.as_posix(),
            "manifest_path": manifest_path.as_posix(),
            "backup_sha256": backup_sha256,
            "restore_copy_sha256": restored_sha256,
            "sqlite_integrity_check": integrity,
            "observed_counts": observed_counts,
            "baseline_counts": expected_counts,
        })
    except Exception as exc:
        result.update({
            "status": "restore_dry_run_blocked",
            "skip_reason": "restore_dry_run_error",
            "error_class": exc.__class__.__name__,
        })
        return result
    finally:
        if cleanup_restore_copy:
            for attempt in range(5):
                try:
                    restore_path.unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.2)
            result["temporary_restore_deleted"] = not restore_path.exists()
        if restore_temp_dir is not None:
            restore_temp_dir.cleanup()

    if source_before is not None and production_db_path.exists():
        result["production_db_unchanged"] = source_before == {
            "size": production_db_path.stat().st_size,
            "sha256": _sha256_file(production_db_path),
        }
    else:
        result["production_db_unchanged"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a backup by restoring it to a temporary dry-run copy.")
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--restore-root", default=None)
    parser.add_argument("--keep-restore-copy", action="store_true")
    args = parser.parse_args()

    result = restore_backup_dry_run(
        manifest_path=Path(args.manifest_path),
        backup_root=Path(args.backup_root),
        restore_root=Path(args.restore_root) if args.restore_root else None,
        cleanup_restore_copy=not args.keep_restore_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["status"] != "restore_dry_run_verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
