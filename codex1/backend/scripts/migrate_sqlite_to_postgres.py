from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Engine, JSON, Numeric, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: E402,F401
from app.database import Base  # noqa: E402


CONFIRMATION = "EMPTY_TARGET_AND_BACKUP_VERIFIED"
ADVISORY_LOCK_KEY = 2_102_023
REQUIRED_TARGET_REVISION = "7e2a9c4f1b36"
SKIPPED_SOURCE_TABLES = {"erp_sessions"}
TENANT_SCOPED_TABLES = {"erp_users", "stores", "store_onboardings"}


@dataclass(frozen=True)
class SourceTable:
    name: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote_sqlite_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _source_snapshot(path: Path) -> tuple[dict[str, SourceTable], str]:
    source_hash = _sha256_file(path)
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError("source SQLite integrity check failed")
        table_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        snapshot: dict[str, SourceTable] = {}
        for table_name in table_names:
            quoted = _quote_sqlite_identifier(table_name)
            columns = tuple(str(row[1]) for row in connection.execute(f"PRAGMA table_info({quoted})").fetchall())
            rows = tuple(dict(row) for row in connection.execute(f"SELECT * FROM {quoted}").fetchall())
            snapshot[table_name] = SourceTable(table_name, columns, rows)
        return snapshot, source_hash
    finally:
        connection.close()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _convert_value(value: Any, column) -> Any:
    if value is None:
        return None
    column_type = column.type
    if isinstance(column_type, Boolean):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
        return bool(value)
    if isinstance(column_type, DateTime):
        return _parse_datetime(value)
    if isinstance(column_type, Date) and not isinstance(column_type, DateTime):
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    if isinstance(column_type, JSON):
        return json.loads(value) if isinstance(value, str) else value
    if isinstance(column_type, Numeric):
        return value if isinstance(value, Decimal) else Decimal(str(value))
    return value


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return "0" if normalized == 0 else format(normalized, "f")
    if isinstance(value, bytes):
        return {"sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
    return value


def _rows_digest(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = {column: _canonical_value(row.get(column)) for column in columns}
        digest.update(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _required_missing_columns(table, source_columns: set[str], transformed_columns: set[str]) -> list[str]:
    missing: list[str] = []
    for column in table.columns:
        if column.name in source_columns or column.name in transformed_columns:
            continue
        if column.nullable or column.default is not None or column.server_default is not None:
            continue
        if column.primary_key and getattr(column, "autoincrement", False) in {True, "auto"}:
            continue
        missing.append(column.name)
    return missing


def _prepare_rows(
    snapshot: dict[str, SourceTable],
    *,
    tenant_id: int,
    platform_admin_user_id: int | None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, tuple[str, ...]], dict[str, int]]:
    model_tables = {table.name: table for table in Base.metadata.sorted_tables}
    unexpected_tables = sorted(set(snapshot) - set(model_tables))
    if unexpected_tables:
        raise RuntimeError(f"source contains unsupported tables: {unexpected_tables}")
    if snapshot.get("tenants") and snapshot["tenants"].rows:
        raise RuntimeError("source already contains tenants; legacy single-tenant migration is required")
    users = snapshot.get("erp_users")
    source_users = users.rows if users is not None else ()
    if source_users and platform_admin_user_id is None:
        raise RuntimeError("source users exist; --platform-admin-user-id is required")
    if platform_admin_user_id is not None and not any(
        int(row["id"]) == platform_admin_user_id for row in source_users
    ):
        raise RuntimeError("platform administrator user id is not present in source erp_users")

    prepared: dict[str, list[dict[str, Any]]] = {}
    copied_columns: dict[str, tuple[str, ...]] = {}
    skipped_counts: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        source = snapshot.get(table.name)
        if source is None or table.name == "tenants":
            continue
        if table.name in SKIPPED_SOURCE_TABLES:
            skipped_counts[table.name] = len(source.rows)
            continue
        source_columns = set(source.columns)
        target_columns = {column.name for column in table.columns}
        unexpected_columns = sorted(source_columns - target_columns)
        if unexpected_columns:
            raise RuntimeError(f"{table.name} contains unsupported columns: {unexpected_columns}")
        transformed_columns = {"tenant_id"} if table.name in TENANT_SCOPED_TABLES else set()
        if table.name == "erp_users":
            transformed_columns.add("platform_role")
        missing_required = _required_missing_columns(table, source_columns, transformed_columns)
        if source.rows and missing_required:
            raise RuntimeError(f"{table.name} is missing required target columns: {missing_required}")

        columns = tuple(
            column.name
            for column in table.columns
            if column.name in source_columns or column.name in transformed_columns
        )
        table_rows: list[dict[str, Any]] = []
        for source_row in source.rows:
            row: dict[str, Any] = {}
            for column_name in columns:
                column = table.c[column_name]
                if column_name == "tenant_id" and table.name in TENANT_SCOPED_TABLES:
                    value = tenant_id
                elif column_name == "platform_role" and table.name == "erp_users":
                    value = "platform_admin" if int(source_row["id"]) == platform_admin_user_id else "tenant_owner"
                else:
                    value = source_row.get(column_name)
                row[column_name] = _convert_value(value, column)
            table_rows.append(row)
        primary_keys = tuple(column.name for column in table.primary_key.columns)
        if primary_keys:
            table_rows.sort(key=lambda row: tuple(row.get(key) for key in primary_keys))
        prepared[table.name] = table_rows
        copied_columns[table.name] = columns
    return prepared, copied_columns, skipped_counts


def _validate_target_schema(connection: Connection) -> str:
    table_names = set(inspect(connection).get_table_names())
    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    missing = sorted(expected_tables - table_names)
    if missing:
        raise RuntimeError(f"target is missing Alembic tables: {missing}")
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if not revision:
        raise RuntimeError("target Alembic revision is missing")
    if str(revision) != REQUIRED_TARGET_REVISION:
        raise RuntimeError(
            f"target Alembic revision must be {REQUIRED_TARGET_REVISION}; observed {revision}"
        )
    return str(revision)


def _validate_empty_target(connection: Connection) -> None:
    non_empty = []
    for table in Base.metadata.sorted_tables:
        count = int(connection.execute(select(func.count()).select_from(table)).scalar_one())
        if count:
            non_empty.append(f"{table.name}:{count}")
    if non_empty:
        raise RuntimeError(f"target application tables are not empty: {non_empty}")


def _reset_postgres_sequence(connection: Connection, table) -> None:
    if len(table.primary_key.columns) != 1:
        return
    primary_key = next(iter(table.primary_key.columns))
    if primary_key.name != "id":
        return
    maximum = connection.execute(select(func.max(primary_key))).scalar_one_or_none()
    if maximum is None:
        return
    quoted_table = connection.dialect.identifier_preparer.quote(table.name)
    quoted_column = connection.dialect.identifier_preparer.quote(primary_key.name)
    connection.execute(text(
        f"SELECT setval(pg_get_serial_sequence('{table.name}', '{primary_key.name}'), "
        f"(SELECT MAX({quoted_column}) FROM {quoted_table}), true)"
    ))


def _target_rows(connection: Connection, table, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    selected_columns = [table.c[name] for name in columns]
    statement = select(*selected_columns)
    primary_keys = [column for column in table.primary_key.columns if column.name in columns]
    if primary_keys:
        statement = statement.order_by(*primary_keys)
    return [dict(row) for row in connection.execute(statement).mappings().all()]


def migrate(
    *,
    source_path: Path,
    target_engine: Engine,
    tenant_name: str,
    platform_admin_user_id: int | None,
    execute: bool,
    confirmation: str | None,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    if execute and confirmation != CONFIRMATION:
        raise RuntimeError(f"execution requires --confirm {CONFIRMATION}")
    snapshot, source_hash_before = _source_snapshot(source_path)
    if execute and expected_source_sha256 != source_hash_before:
        raise RuntimeError("execution requires the exact reviewed source SHA-256")
    if not tenant_name.strip():
        raise RuntimeError("tenant name is required")
    tenant_id = 1
    prepared, copied_columns, skipped_counts = _prepare_rows(
        snapshot,
        tenant_id=tenant_id,
        platform_admin_user_id=platform_admin_user_id,
    )
    source_counts = {name: len(table.rows) for name, table in snapshot.items()}
    expected_digests = {
        name: _rows_digest(rows, copied_columns[name])
        for name, rows in prepared.items()
    }

    with target_engine.connect() as connection:
        revision = _validate_target_schema(connection)
        _validate_empty_target(connection)
    report: dict[str, Any] = {
        "status": "migration_ready" if not execute else "migration_pending",
        "mode": "dry_run" if not execute else "execute",
        "source_sha256": source_hash_before,
        "target_revision": revision,
        "source_counts": source_counts,
        "skipped_counts": skipped_counts,
        "tenant_id": tenant_id,
        "platform_admin_user_id": platform_admin_user_id,
        "platform_admin_bootstrap_required": platform_admin_user_id is None,
        "copied_counts": {name: len(rows) for name, rows in prepared.items()},
    }
    if not execute:
        if _sha256_file(source_path) != source_hash_before:
            raise RuntimeError("source SQLite changed during dry-run inspection")
        return report

    now = datetime.now(timezone.utc)
    tenant_key = "initial-" + source_hash_before[:24]
    with target_engine.begin() as connection:
        connection.execute(text("SET LOCAL statement_timeout = '5min'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
        _validate_empty_target(connection)
        tenant_table = Base.metadata.tables["tenants"]
        connection.execute(tenant_table.insert(), {
            "id": tenant_id,
            "tenant_key": tenant_key,
            "name": tenant_name.strip(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })
        for table in Base.metadata.sorted_tables:
            rows = prepared.get(table.name, [])
            if not rows:
                continue
            for offset in range(0, len(rows), 500):
                connection.execute(table.insert(), rows[offset:offset + 500])
        for table in Base.metadata.sorted_tables:
            _reset_postgres_sequence(connection, table)

        target_digests = {}
        for table_name, expected_digest in expected_digests.items():
            table = Base.metadata.tables[table_name]
            target_rows = _target_rows(connection, table, copied_columns[table_name])
            target_digest = _rows_digest(target_rows, copied_columns[table_name])
            target_digests[table_name] = target_digest
            if target_digest != expected_digest:
                raise RuntimeError(f"post-copy digest mismatch for {table_name}")
        tenant_count = int(connection.execute(select(func.count()).select_from(tenant_table)).scalar_one())
        if tenant_count != 1:
            raise RuntimeError("target tenant seed count mismatch")
        if _sha256_file(source_path) != source_hash_before:
            raise RuntimeError("source SQLite changed during migration")

    report.update({
        "status": "migration_completed",
        "table_digests": target_digests,
        "source_unchanged": True,
        "sessions_migrated": False,
    })
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate a legacy production SQLite database to empty PostgreSQL.")
    parser.add_argument("--source-sqlite", required=True, type=Path)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--platform-admin-user-id", type=int)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--source-sha256")
    parser.add_argument("--report-json", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    source_path = args.source_sqlite.resolve()
    if not source_path.is_file():
        raise SystemExit("source SQLite file does not exist")
    target_url = os.environ.get("TARGET_DATABASE_URL", "").strip()
    if not target_url.startswith(("postgresql+psycopg://", "postgresql://")):
        raise SystemExit("TARGET_DATABASE_URL must be a PostgreSQL URL")
    engine = create_engine(target_url, pool_pre_ping=True, future=True)
    try:
        report = migrate(
            source_path=source_path,
            target_engine=engine,
            tenant_name=args.tenant_name,
            platform_admin_user_id=args.platform_admin_user_id,
            execute=args.execute,
            confirmation=args.confirm,
            expected_source_sha256=args.source_sha256,
        )
    finally:
        engine.dispose()
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
