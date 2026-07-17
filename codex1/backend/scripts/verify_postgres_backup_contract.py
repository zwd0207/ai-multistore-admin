from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.backup_postgres_to_oss import (  # noqa: E402
    BackupConfigurationError,
    DEFAULT_ECS_METADATA_BASE,
    _assert_private_bucket,
    _object_key,
    _retention_cutoff,
    _safe_manifest,
    _validate_configuration,
    run_backup,
)


class _Result:
    status = 200


class _Head:
    def __init__(self, size: int):
        self.content_length = size


class _Object:
    def __init__(self, key: str):
        self.key = key
        self.last_modified = 1_800_000_000


class _PrivateBucket:
    bucket_name = "aiglxt-prod-backup-123"

    def __init__(self):
        self.acl = "private"
        self.objects: dict[str, bytes] = {}

    def get_bucket_acl(self):
        return type("AclResult", (), {"acl": self.acl})()

    def put_object_from_file(self, key, path, headers=None):
        self.objects[key] = Path(path).read_bytes()
        return _Result()

    def head_object(self, key):
        return _Head(len(self.objects[key]))

    def get_object_to_file(self, key, path):
        Path(path).write_bytes(self.objects[key])
        return _Result()

    def copy_object(self, bucket_name, source_key, destination_key, headers=None):
        assert bucket_name == self.bucket_name
        self.objects[destination_key] = self.objects[source_key]
        return _Result()

    def list_objects(self, prefix="", max_keys=1000):
        return type("ListResult", (), {"object_list": [_Object(key) for key in self.objects if key.startswith(prefix)]})()

    def delete_object(self, key):
        self.objects.pop(key, None)
        return _Result()


class _AclAccessDenied(Exception):
    status = 403
    details = {"Code": "AccessDenied"}


class _BucketInfoFallback:
    def __init__(self, acl: str):
        self.acl = acl

    def get_bucket_acl(self):
        raise _AclAccessDenied()

    def get_bucket_info(self):
        acl = type("BucketInfoAcl", (), {"grant": self.acl})()
        return type("BucketInfo", (), {"acl": acl})()


def main() -> None:
    previous = dict(os.environ)
    try:
        for key in (
            "DATABASE_URL", "BACKUP_OSS_BUCKET", "BACKUP_OSS_ENDPOINT", "BACKUP_OSS_PREFIX",
            "BACKUP_OSS_ROLE_NAME", "BACKUP_AGE_RECIPIENT", "BACKUP_LOCAL_ROOT", "BACKUP_LOCK_PATH",
        ):
            os.environ.pop(key, None)
        os.environ["DATABASE_URL"] = "sqlite:///./must-not-be-used.db"
        try:
            _validate_configuration()
        except BackupConfigurationError as exc:
            assert str(exc) == "postgresql_database_required"
        else:
            raise AssertionError("SQLite backup source must be rejected")

        now = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
        prefix = "postgresql/"
        hourly = _object_key(prefix, now, "hourly", "postgres-demo")
        daily = _object_key(prefix, now, "daily", "postgres-demo")
        monthly = _object_key(prefix, now, "monthly", "postgres-demo")
        assert hourly.startswith("postgresql/hourly/20260717T000000Z/")
        assert daily.startswith("postgresql/daily/2026-07-17/")
        assert monthly.startswith("postgresql/monthly/2026-07/")
        assert _retention_cutoff("monthly", now) < _retention_cutoff("daily", now)
        assert _retention_cutoff("daily", now) < _retention_cutoff("hourly", now)
        assert _retention_cutoff("monthly", now) == datetime(2025, 8, 1, tzinfo=timezone.utc)

        manifest = _safe_manifest(
            backup_id="postgres-demo",
            created_at=now,
            object_key=hourly,
            manifest_key=hourly + ".manifest.json",
            size=123,
            sha256="a" * 64,
        )
        assert manifest["encryption"].startswith("age_")
        assert manifest["raw_response_saved"] is False
        assert manifest["secrets_saved"] is False
        assert "DATABASE_URL" not in str(manifest)
        assert "AccessKey" not in str(manifest)

        os.environ.update({
            "DATABASE_URL": "postgresql+psycopg://dbuser:dbpassword@127.0.0.1:5432/dbname",
            "BACKUP_OSS_BUCKET": "aiglxt-prod-backup-123",
            "BACKUP_AGE_RECIPIENT": "age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq",
            "BACKUP_LOCAL_ROOT": str(Path.cwd() / "temporary-backup-root"),
            "BACKUP_LOCK_PATH": str(Path.cwd() / "temporary-backup.lock"),
        })
        dry = run_backup(dry_run=True)
        assert dry["status"] == "backup_ready"
        assert dry["dry_run"] is True
        assert dry["platform_write"] is False
        assert DEFAULT_ECS_METADATA_BASE == "http://100.100.100.200/latest/meta-data/ram/security-credentials"
        _assert_private_bucket(_BucketInfoFallback("private"))
        try:
            _assert_private_bucket(_BucketInfoFallback("public-read"))
        except BackupConfigurationError as exc:
            assert str(exc) == "oss_bucket_must_be_private"
        else:
            raise AssertionError("public bucket info must be rejected")

        temp_root = Path(tempfile.mkdtemp(prefix="verify-postgres-backup-"))
        bucket = _PrivateBucket()
        original_run = subprocess.run
        python_bin = sys.executable

        def fake_run(command, **kwargs):
            assert "DATABASE_URL" not in kwargs["env"]
            assert "BACKUP_AGE_RECIPIENT" not in kwargs["env"]
            if "--file" in command:
                pgpass = Path(kwargs["env"]["PGPASSFILE"])
                assert pgpass.exists() and "dbpassword" in pgpass.read_text(encoding="utf-8")
                output_path = Path(command[command.index("--file") + 1])
                output_path.write_bytes(b"synthetic pg custom dump")
            elif "--output" in command:
                output_path = Path(command[command.index("--output") + 1])
                source_path = Path(command[-1])
                output_path.write_bytes(b"age-encrypted:" + source_path.read_bytes())
            return subprocess.CompletedProcess(command, 0, "", "")

        subprocess.run = fake_run
        monthly_now = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        os.environ.update({
            "PG_DUMP_BIN": python_bin,
            "AGE_BIN": python_bin,
            "BACKUP_LOCAL_ROOT": str(temp_root / "backups"),
            "BACKUP_LOCK_PATH": str(temp_root / "backup.lock"),
        })
        try:
            uploaded = run_backup(now=monthly_now, bucket=bucket)
        finally:
            subprocess.run = original_run
            shutil.rmtree(temp_root, ignore_errors=True)
        assert uploaded["status"] == "backup_uploaded"
        assert uploaded["encrypted_sha256"]
        assert any(key.endswith(".manifest.json") for key in bucket.objects)
        assert any("/daily/" in key for key in bucket.objects)
        assert any("/monthly/" in key for key in bucket.objects)
        print("verify_postgres_backup_contract: ok")
    finally:
        os.environ.clear()
        os.environ.update(previous)


if __name__ == "__main__":
    main()
