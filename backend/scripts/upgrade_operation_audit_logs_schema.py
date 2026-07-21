import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine


OPERATION_AUDIT_LOG_TABLE = "operation_audit_logs"

OPERATION_AUDIT_LOG_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "store_id",
    "platform",
    "environment",
    "actor_type",
    "actor_id",
    "actor_label",
    "actor_role",
    "action",
    "operation_phase",
    "correlation_id",
    "request_id",
    "status",
    "reason_code",
    "target_type",
    "target_id",
    "target_hash",
    "target_label",
    "changed_field_names",
    "before_summary",
    "after_summary",
    "counts_summary",
    "safety_flags",
    "backup_path",
    "backup_sha256",
    "restore_source_path",
    "restore_source_sha256",
    "sensitive_scan_passed",
    "raw_response_saved",
    "secrets_saved",
    "privacy_fields_redacted",
    "notes",
}

OPERATION_AUDIT_LOG_NOT_NULL_COLUMNS = {
    "created_at",
    "updated_at",
    "environment",
    "actor_type",
    "action",
    "correlation_id",
    "status",
    "sensitive_scan_passed",
    "raw_response_saved",
    "secrets_saved",
    "privacy_fields_redacted",
}

OPERATION_AUDIT_LOG_INDEXES = {
    "ix_operation_audit_logs_created_at": ["created_at"],
    "ix_operation_audit_logs_store_created_at": ["store_id", "created_at"],
    "ix_operation_audit_logs_platform_created_at": ["platform", "created_at"],
    "ix_operation_audit_logs_actor_created_at": ["actor_type", "actor_id", "created_at"],
    "ix_operation_audit_logs_action_created_at": ["action", "created_at"],
    "ix_operation_audit_logs_status_reason": ["status", "reason_code"],
    "ix_operation_audit_logs_target": ["target_type", "target_id"],
    "ix_operation_audit_logs_target_hash": ["target_hash"],
    "ix_operation_audit_logs_correlation_id": ["correlation_id"],
    "ix_operation_audit_logs_request_id": ["request_id"],
}

FORBIDDEN_OPERATION_AUDIT_LOG_COLUMNS = {
    "access_token",
    "authorization",
    "buyer_name",
    "buyer_phone",
    "channel_no",
    "client_secret",
    "headers",
    "order_id",
    "product_order_id",
    "raw_data",
    "raw_request",
    "raw_response",
    "receiver_name",
    "receiver_phone",
    "refresh_token",
    "signature",
    "token",
    "zip_code",
}


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_operation_audit_logs_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def create_operation_audit_log_schema(connection: sqlite3.Connection) -> bool:
    existed = OPERATION_AUDIT_LOG_TABLE in get_existing_tables(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS operation_audit_logs (
            id INTEGER PRIMARY KEY,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            store_id INTEGER,
            platform VARCHAR(50),
            environment VARCHAR(30) NOT NULL DEFAULT 'local',
            actor_type VARCHAR(30) NOT NULL,
            actor_id VARCHAR(120),
            actor_label VARCHAR(160),
            actor_role VARCHAR(80),
            action VARCHAR(120) NOT NULL,
            operation_phase VARCHAR(120),
            correlation_id VARCHAR(80) NOT NULL,
            request_id VARCHAR(120),
            status VARCHAR(30) NOT NULL,
            reason_code VARCHAR(120),
            target_type VARCHAR(80),
            target_id INTEGER,
            target_hash VARCHAR(160),
            target_label VARCHAR(200),
            changed_field_names JSON,
            before_summary JSON,
            after_summary JSON,
            counts_summary JSON,
            safety_flags JSON,
            backup_path VARCHAR(500),
            backup_sha256 VARCHAR(64),
            restore_source_path VARCHAR(500),
            restore_source_sha256 VARCHAR(64),
            sensitive_scan_passed BOOLEAN NOT NULL DEFAULT 0,
            raw_response_saved BOOLEAN NOT NULL DEFAULT 0,
            secrets_saved BOOLEAN NOT NULL DEFAULT 0,
            privacy_fields_redacted BOOLEAN NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            CHECK (length(trim(actor_type)) > 0),
            CHECK (length(trim(action)) > 0),
            CHECK (length(trim(correlation_id)) > 0),
            CHECK (length(trim(status)) > 0),
            CHECK (raw_response_saved IN (0, 1)),
            CHECK (secrets_saved IN (0, 1)),
            CHECK (privacy_fields_redacted IN (0, 1)),
            CHECK (backup_sha256 IS NULL OR (length(backup_sha256) = 64 AND backup_sha256 NOT GLOB '*[^0-9a-f]*')),
            CHECK (restore_source_sha256 IS NULL OR (length(restore_source_sha256) = 64 AND restore_source_sha256 NOT GLOB '*[^0-9a-f]*'))
        )
    """)
    for index_name, index_columns in OPERATION_AUDIT_LOG_INDEXES.items():
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON operation_audit_logs ({', '.join(index_columns)})"
        )
    return not existed


def verify_operation_audit_log_schema(connection: sqlite3.Connection) -> None:
    table_info = connection.execute("PRAGMA table_info(operation_audit_logs)").fetchall()
    if not table_info:
        raise RuntimeError("operation_audit_logs table does not exist")

    columns = {row[1] for row in table_info}
    missing_columns = sorted(OPERATION_AUDIT_LOG_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError(f"Missing operation_audit_logs columns: {missing_columns}")

    forbidden_columns = sorted({column.lower() for column in columns} & FORBIDDEN_OPERATION_AUDIT_LOG_COLUMNS)
    if forbidden_columns:
        raise RuntimeError(f"Forbidden operation_audit_logs columns: {forbidden_columns}")

    not_null = {row[1]: bool(row[3]) for row in table_info}
    missing_not_null = sorted(
        column
        for column in OPERATION_AUDIT_LOG_NOT_NULL_COLUMNS
        if not not_null.get(column)
    )
    if missing_not_null:
        raise RuntimeError(f"Missing operation_audit_logs NOT NULL columns: {missing_not_null}")

    default_values = {row[1]: row[4] for row in table_info}
    expected_defaults = {
        "environment": {"'local'", "local"},
        "sensitive_scan_passed": {"0", "'0'"},
        "raw_response_saved": {"0", "'0'"},
        "secrets_saved": {"0", "'0'"},
        "privacy_fields_redacted": {"1", "'1'"},
    }
    for column, expected_values in expected_defaults.items():
        observed = str(default_values.get(column))
        if observed not in expected_values:
            raise RuntimeError(
                f"Unexpected operation_audit_logs default for {column}: {observed}; "
                f"expected one of {sorted(expected_values)}"
            )

    index_rows = connection.execute("PRAGMA index_list(operation_audit_logs)").fetchall()
    index_names = {row[1] for row in index_rows}
    unique_index_names = {row[1] for row in index_rows if row[2]}
    if unique_index_names:
        raise RuntimeError(f"Unexpected unique operation_audit_logs indexes: {sorted(unique_index_names)}")

    missing_indexes = sorted(set(OPERATION_AUDIT_LOG_INDEXES) - index_names)
    if missing_indexes:
        raise RuntimeError(f"Missing operation_audit_logs indexes: {missing_indexes}")

    for index_name, expected_columns in OPERATION_AUDIT_LOG_INDEXES.items():
        rows = connection.execute(f"PRAGMA index_info({index_name})").fetchall()
        observed_columns = [row[2] for row in rows]
        if observed_columns != expected_columns:
            raise RuntimeError(
                f"Unexpected {index_name} columns: {observed_columns}; expected {expected_columns}"
            )


def upgrade(*, run_create_all: bool = True) -> dict[str, list[str]]:
    import app.models  # noqa: F401

    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        if run_create_all:
            Base.metadata.create_all(bind=engine)
        return {"tables": [], "indexes": []}

    database_path = resolve_sqlite_path(settings.database_url)
    with sqlite3.connect(database_path) as pre_connection:
        existed_before = OPERATION_AUDIT_LOG_TABLE in get_existing_tables(pre_connection)

    if run_create_all:
        Base.metadata.create_all(bind=engine)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        created = create_operation_audit_log_schema(connection)
        connection.commit()
        verify_operation_audit_log_schema(connection)
        return {
            "tables": [OPERATION_AUDIT_LOG_TABLE] if (created or not existed_before) else [],
            "indexes": sorted(OPERATION_AUDIT_LOG_INDEXES),
        }
    finally:
        connection.close()


def main() -> None:
    result = upgrade()
    if result["tables"]:
        print("operation audit logs schema upgraded: operation_audit_logs")
    else:
        print("operation audit logs schema already up to date")


if __name__ == "__main__":
    main()
