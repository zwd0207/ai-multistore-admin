from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy.engine import URL, make_url


DEFAULT_OSS_ENDPOINT = "https://oss-ap-northeast-2.aliyuncs.com"
DEFAULT_ROLE_NAME = "aiglxt-prod-backup-role"
DEFAULT_ECS_METADATA_BASE = "http://100.100.100.200/latest/meta-data/ram/security-credentials"
DEFAULT_PREFIX = "postgresql/"
DEFAULT_LOCAL_ROOT = "/var/lib/ai-multistore/backups"
DEFAULT_LOCK_PATH = "/run/ai-multistore/postgres-backup.lock"
AGE_RECIPIENT_PATTERN = re.compile(r"^age1[0-9a-z]{20,}$")
SAFE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9/_-]+$")


class BackupConfigurationError(RuntimeError):
    """Raised when a backup cannot safely start."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BackupConfigurationError(f"{name}_missing")
    return value


def _validate_configuration() -> dict[str, str]:
    database_url = _env_required("DATABASE_URL")
    try:
        parsed = make_url(database_url)
    except Exception as exc:
        raise BackupConfigurationError("database_url_invalid") from exc
    if parsed.get_backend_name() != "postgresql":
        raise BackupConfigurationError("postgresql_database_required")
    bucket = _env_required("BACKUP_OSS_BUCKET")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", bucket):
        raise BackupConfigurationError("oss_bucket_invalid")
    endpoint = os.environ.get("BACKUP_OSS_ENDPOINT", DEFAULT_OSS_ENDPOINT).strip().rstrip("/")
    if not endpoint.startswith("https://"):
        raise BackupConfigurationError("oss_endpoint_must_use_https")
    prefix = os.environ.get("BACKUP_OSS_PREFIX", DEFAULT_PREFIX).strip().strip("/") + "/"
    if not SAFE_KEY_PATTERN.fullmatch(prefix):
        raise BackupConfigurationError("oss_prefix_invalid")
    role_name = os.environ.get("BACKUP_OSS_ROLE_NAME", DEFAULT_ROLE_NAME).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", role_name):
        raise BackupConfigurationError("ram_role_name_invalid")
    recipient = _env_required("BACKUP_AGE_RECIPIENT")
    if not AGE_RECIPIENT_PATTERN.fullmatch(recipient):
        raise BackupConfigurationError("age_recipient_invalid")
    return {
        "database_url": database_url,
        "bucket": bucket,
        "endpoint": endpoint,
        "prefix": prefix,
        "role_name": role_name,
        "recipient": recipient,
        "local_root": os.environ.get("BACKUP_LOCAL_ROOT", DEFAULT_LOCAL_ROOT).strip() or DEFAULT_LOCAL_ROOT,
        "lock_path": os.environ.get("BACKUP_LOCK_PATH", DEFAULT_LOCK_PATH).strip() or DEFAULT_LOCK_PATH,
        "pg_dump_bin": os.environ.get("PG_DUMP_BIN", "/usr/bin/pg_dump").strip(),
        "age_bin": os.environ.get("AGE_BIN", "/usr/bin/age").strip(),
    }


def _database_connection_args(database_url: str, pgpass_path: Path) -> tuple[list[str], dict[str, str]]:
    parsed: URL = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise BackupConfigurationError("postgresql_database_required")
    host = parsed.host or "127.0.0.1"
    port = str(parsed.port or 5432)
    database = parsed.database or ""
    username = parsed.username or ""
    password = parsed.password or ""
    if not database or not username or not password:
        raise BackupConfigurationError("database_connection_fields_missing")
    def pgpass_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", "\\:")

    pgpass_path.write_text(
        f"{pgpass_escape(host)}:{pgpass_escape(port)}:{pgpass_escape(database)}:"
        f"{pgpass_escape(username)}:{pgpass_escape(password)}\n",
        encoding="utf-8",
    )
    pgpass_path.chmod(0o600)
    args = ["--host", host, "--port", port, "--username", username, "--dbname", database]
    return args, {"PGPASSFILE": str(pgpass_path)}


def _subprocess_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    blocked = {
        "DATABASE_URL",
        "DATABASE_PASSWORD",
        "BACKUP_AGE_RECIPIENT",
        "BACKUP_OSS_BUCKET",
        "BACKUP_OSS_ROLE_NAME",
    }
    environment = {key: value for key, value in os.environ.items() if key not in blocked}
    environment.update(extra or {})
    return environment


def _object_key(prefix: str, created_at: datetime, kind: str, suffix: str) -> str:
    if kind not in {"hourly", "daily", "monthly"}:
        raise ValueError("unsupported_backup_kind")
    stamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    if kind == "daily":
        stamp = created_at.strftime("%Y-%m-%d")
    elif kind == "monthly":
        stamp = created_at.strftime("%Y-%m")
    key = f"{prefix}{kind}/{stamp}/postgres-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{suffix}"
    if not SAFE_KEY_PATTERN.fullmatch(key):
        raise BackupConfigurationError("generated_object_key_invalid")
    return key


def _retention_cutoff(kind: str, now: datetime) -> datetime:
    if kind == "hourly":
        return now - timedelta(hours=48)
    if kind == "daily":
        return now - timedelta(days=30)
    if kind == "monthly":
        current_month = now.year * 12 + now.month - 1
        cutoff_month = current_month - 11
        return datetime(cutoff_month // 12, cutoff_month % 12 + 1, 1, tzinfo=timezone.utc)
    raise ValueError("unsupported_backup_kind")


def _safe_manifest(*, backup_id: str, created_at: datetime, object_key: str, manifest_key: str, size: int, sha256: str) -> dict[str, Any]:
    return {
        "manifest_version": "postgres-backup-v1",
        "backup_id": backup_id,
        "created_at": created_at.isoformat(),
        "database_engine": "postgresql",
        "pg_dump_format": "custom",
        "object_key": object_key,
        "manifest_key": manifest_key,
        "encrypted_size_bytes": size,
        "encrypted_sha256": sha256,
        "encryption": "age_recipient_plus_oss_server_side_encryption",
        "retention_classes": {"hourly": 48, "daily": 30, "monthly": 12},
        "rpo_target_hours": 1,
        "rto_target_hours": 2,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    }


def _import_oss2():
    try:
        import oss2
        from oss2.credentials import EcsRamRoleCredentialsProvider
    except ImportError as exc:  # pragma: no cover - exercised on an unprovisioned host
        raise BackupConfigurationError("oss2_dependency_missing") from exc
    return oss2, EcsRamRoleCredentialsProvider


def _make_bucket(config: dict[str, str]):
    oss2, provider_type = _import_oss2()
    metadata_url = f"{DEFAULT_ECS_METADATA_BASE}/{config['role_name']}"
    provider = provider_type(metadata_url)
    auth = oss2.ProviderAuth(provider)
    return oss2.Bucket(auth, config["endpoint"], config["bucket"])


def _upload(bucket: Any, path: Path, key: str) -> None:
    result = bucket.put_object_from_file(
        key,
        str(path),
        headers={
            "x-oss-object-acl": "private",
            "x-oss-server-side-encryption": "AES256",
            "Content-Type": "application/octet-stream",
        },
    )
    if getattr(result, "status", 0) not in {200, 201}:
        raise RuntimeError("oss_upload_failed")


def _assert_private_bucket(bucket: Any) -> None:
    result = bucket.get_bucket_acl()
    if str(getattr(result, "acl", "")).lower() != "private":
        raise BackupConfigurationError("oss_bucket_must_be_private")


def _verify_remote_object(bucket: Any, path: Path, key: str, readback_path: Path) -> None:
    head = bucket.head_object(key)
    remote_size = int(getattr(head, "content_length", -1))
    if remote_size != path.stat().st_size:
        raise RuntimeError("oss_remote_size_mismatch")
    bucket.get_object_to_file(key, str(readback_path))
    if _sha256_file(readback_path) != _sha256_file(path):
        raise RuntimeError("oss_remote_sha256_mismatch")


def _copy_if_needed(bucket: Any, bucket_name: str, source_key: str, destination_key: str) -> None:
    if source_key == destination_key:
        return
    result = bucket.copy_object(
        bucket_name,
        source_key,
        destination_key,
        headers={"x-oss-object-acl": "private", "x-oss-server-side-encryption": "AES256"},
    )
    if getattr(result, "status", 0) not in {200, 201}:
        raise RuntimeError("oss_copy_failed")


def _delete_expired(bucket: Any, prefix: str, now: datetime) -> dict[str, int]:
    deleted = {"hourly": 0, "daily": 0, "monthly": 0}
    for kind in deleted:
        kind_prefix = f"{prefix}{kind}/"
        cutoff = _retention_cutoff(kind, now)
        for item in bucket.list_objects(prefix=kind_prefix, max_keys=1000).object_list:
            modified = getattr(item, "last_modified", 0)
            if not modified or datetime.fromtimestamp(modified, timezone.utc) >= cutoff:
                continue
            bucket.delete_object(item.key)
            deleted[kind] += 1
    return deleted


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # pragma: no cover - production is Linux
            pass
        except BlockingIOError as exc:
            raise BackupConfigurationError("backup_already_running") from exc
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        handle.close()


def run_backup(*, now: datetime | None = None, dry_run: bool = False, bucket: Any | None = None) -> dict[str, Any]:
    config = _validate_configuration()
    current = now or _utc_now()
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    backup_id = f"postgres-{current.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    local_root = Path(config["local_root"]).resolve()
    if dry_run:
        return {
            "status": "backup_ready",
            "backup_id": backup_id,
            "bucket": config["bucket"],
            "endpoint": config["endpoint"],
            "platform_write": False,
            "dry_run": True,
        }
    if not Path(config["pg_dump_bin"]).exists():
        raise BackupConfigurationError("pg_dump_missing")
    if not Path(config["age_bin"]).exists():
        raise BackupConfigurationError("age_missing")
    local_root.mkdir(parents=True, exist_ok=True)
    local_root.chmod(0o700)
    with _exclusive_lock(Path(config["lock_path"])):
        bucket = bucket or _make_bucket(config)
        _assert_private_bucket(bucket)
        with tempfile.TemporaryDirectory(prefix="postgres-backup-", dir=local_root) as temp_dir:
            temp_root = Path(temp_dir)
            pg_dump_path = temp_root / f"{backup_id}.dump"
            encrypted_path = temp_root / f"{backup_id}.dump.age"
            pgpass_path = temp_root / ".pgpass"
            dump_args, pg_env = _database_connection_args(config["database_url"], pgpass_path)
            subprocess.run(
                [config["pg_dump_bin"], "--format=custom", "--no-owner", "--no-privileges", "--file", str(pg_dump_path), *dump_args],
                check=True,
                env=_subprocess_environment(pg_env),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                [config["age_bin"], "--encrypt", "--recipient", config["recipient"], "--output", str(encrypted_path), str(pg_dump_path)],
                check=True,
                env=_subprocess_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            pg_dump_path.unlink(missing_ok=True)
            encrypted_sha256 = _sha256_file(encrypted_path)
            hourly_key = _object_key(config["prefix"], current, "hourly", backup_id)
            daily_key = _object_key(config["prefix"], current, "daily", backup_id) if current.hour == 0 else None
            monthly_key = _object_key(config["prefix"], current, "monthly", backup_id) if current.hour == 0 and current.day == 1 else None
            manifest_key = hourly_key + ".manifest.json"
            manifest = _safe_manifest(
                backup_id=backup_id,
                created_at=current,
                object_key=hourly_key,
                manifest_key=manifest_key,
                size=encrypted_path.stat().st_size,
                sha256=encrypted_sha256,
            )
            manifest_path = temp_root / f"{backup_id}.manifest.json"
            readback_path = temp_root / f"{backup_id}.readback.age"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            _upload(bucket, encrypted_path, hourly_key)
            _upload(bucket, manifest_path, manifest_key)
            _verify_remote_object(bucket, encrypted_path, hourly_key, readback_path)
            if daily_key:
                _copy_if_needed(bucket, config["bucket"], hourly_key, daily_key)
                _copy_if_needed(bucket, config["bucket"], manifest_key, daily_key + ".manifest.json")
            if monthly_key:
                _copy_if_needed(bucket, config["bucket"], hourly_key, monthly_key)
                _copy_if_needed(bucket, config["bucket"], manifest_key, monthly_key + ".manifest.json")
            deleted = _delete_expired(bucket, config["prefix"], current)
    return {
        "status": "backup_uploaded",
        "backup_id": backup_id,
        "object_key": hourly_key,
        "manifest_key": manifest_key,
        "encrypted_size_bytes": encrypted_path.stat().st_size if encrypted_path.exists() else manifest["encrypted_size_bytes"],
        "encrypted_sha256": encrypted_sha256,
        "deleted_counts": deleted,
        "platform_write": False,
        "raw_response_saved": False,
        "secrets_saved": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an encrypted PostgreSQL backup and store it in private OSS.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run_backup(dry_run=args.dry_run), ensure_ascii=False, sort_keys=True))
    except BackupConfigurationError as exc:
        raise SystemExit(json.dumps({"status": "backup_blocked", "reason_code": str(exc)}, ensure_ascii=False)) from None
    except subprocess.CalledProcessError as exc:
        raise SystemExit(json.dumps({"status": "backup_blocked", "reason_code": "backup_command_failed", "command": Path(exc.cmd[0]).name}, ensure_ascii=False)) from None
    except Exception as exc:
        raise SystemExit(json.dumps({"status": "backup_blocked", "reason_code": exc.__class__.__name__}, ensure_ascii=False)) from None


if __name__ == "__main__":
    main()
