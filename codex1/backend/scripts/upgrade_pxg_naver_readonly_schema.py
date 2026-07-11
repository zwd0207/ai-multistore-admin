"""Create and verify the isolated PXG/Naver readonly-local persistence schema."""

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine


TABLE_COLUMNS = {
    "pxg_naver_readonly_record_states": {
        "id", "store_id", "platform", "resource_type", "source_key_hash", "local_record_id",
        "content_fingerprint", "source_updated_at", "source_observed_at", "expires_at",
        "retention_review_at", "is_stale", "created_at", "updated_at",
    },
    "pxg_naver_order_recipient_secure_records": {
        "id", "order_id", "store_id", "platform", "encrypted_recipient_payload",
        "recipient_payload_hash", "source_updated_at", "source_observed_at", "expires_at",
        "is_stale", "created_at", "updated_at",
    },
    "pxg_naver_readonly_logistics_records": {
        "id", "order_id", "store_id", "platform", "carrier", "encrypted_tracking_number",
        "tracking_number_hash", "tracking_number_masked", "shipment_status", "shipped_at",
        "source_updated_at", "source_observed_at", "expires_at", "is_stale", "created_at", "updated_at",
    },
    "pxg_naver_readonly_customer_inquiries": {
        "id", "store_id", "platform", "external_inquiry_id_hash", "related_order_id", "inquiry_type",
        "status", "customer_display_masked", "subject_category", "content_available", "received_at",
        "answered_at", "source_updated_at", "source_observed_at", "expires_at", "is_stale",
        "created_at", "updated_at",
    },
}

INDEXES = {
    "uq_pxg_naver_readonly_state_source": ("pxg_naver_readonly_record_states", ["store_id", "platform", "resource_type", "source_key_hash"], True),
    "ix_pxg_naver_readonly_state_store_resource": ("pxg_naver_readonly_record_states", ["store_id", "platform", "resource_type", "is_stale"], False),
    "ix_pxg_naver_readonly_state_expiry": ("pxg_naver_readonly_record_states", ["expires_at", "is_stale"], False),
    "uq_pxg_naver_recipient_order": ("pxg_naver_order_recipient_secure_records", ["order_id"], True),
    "ix_pxg_naver_recipient_store_order": ("pxg_naver_order_recipient_secure_records", ["store_id", "order_id"], False),
    "ix_pxg_naver_recipient_expiry": ("pxg_naver_order_recipient_secure_records", ["expires_at", "is_stale"], False),
    "uq_pxg_naver_logistics_order": ("pxg_naver_readonly_logistics_records", ["order_id"], True),
    "ix_pxg_naver_logistics_store_status": ("pxg_naver_readonly_logistics_records", ["store_id", "platform", "is_stale"], False),
    "ix_pxg_naver_logistics_expiry": ("pxg_naver_readonly_logistics_records", ["expires_at", "is_stale"], False),
    "uq_pxg_naver_readonly_inquiry": ("pxg_naver_readonly_customer_inquiries", ["store_id", "platform", "external_inquiry_id_hash"], True),
    "ix_pxg_naver_readonly_inquiry_store_status": ("pxg_naver_readonly_customer_inquiries", ["store_id", "platform", "status"], False),
    "ix_pxg_naver_readonly_inquiry_expiry": ("pxg_naver_readonly_customer_inquiries", ["expires_at", "is_stale"], False),
}


def _resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_pxg_naver_readonly_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    return path if path.is_absolute() else Path.cwd() / path


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_record_states (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            resource_type VARCHAR(40) NOT NULL,
            source_key_hash VARCHAR(64) NOT NULL,
            local_record_id INTEGER,
            content_fingerprint VARCHAR(64) NOT NULL,
            source_updated_at DATETIME NOT NULL,
            source_observed_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            retention_review_at DATETIME NOT NULL,
            is_stale BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            UNIQUE(store_id, platform, resource_type, source_key_hash),
            CHECK (platform = 'naver'),
            CHECK (resource_type IN ('product', 'order', 'recipient', 'logistics', 'customer_inquiry')),
            CHECK (is_stale IN (0, 1))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_order_recipient_secure_records (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            encrypted_recipient_payload TEXT NOT NULL,
            recipient_payload_hash VARCHAR(64) NOT NULL,
            source_updated_at DATETIME NOT NULL,
            source_observed_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            is_stale BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(store_id) REFERENCES stores(id),
            UNIQUE(order_id),
            CHECK (platform = 'naver'),
            CHECK (is_stale IN (0, 1))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_logistics_records (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            carrier VARCHAR(120),
            encrypted_tracking_number TEXT NOT NULL,
            tracking_number_hash VARCHAR(64) NOT NULL,
            tracking_number_masked VARCHAR(120) NOT NULL,
            shipment_status VARCHAR(60) NOT NULL DEFAULT 'observed',
            shipped_at DATETIME,
            source_updated_at DATETIME NOT NULL,
            source_observed_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            is_stale BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(store_id) REFERENCES stores(id),
            UNIQUE(order_id),
            CHECK (platform = 'naver'),
            CHECK (is_stale IN (0, 1))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_customer_inquiries (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            external_inquiry_id_hash VARCHAR(64) NOT NULL,
            related_order_id INTEGER,
            inquiry_type VARCHAR(60) NOT NULL,
            status VARCHAR(40) NOT NULL,
            customer_display_masked VARCHAR(120),
            subject_category VARCHAR(120),
            content_available BOOLEAN NOT NULL DEFAULT 0,
            received_at DATETIME,
            answered_at DATETIME,
            source_updated_at DATETIME NOT NULL,
            source_observed_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            is_stale BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            FOREIGN KEY(related_order_id) REFERENCES orders(id),
            UNIQUE(store_id, platform, external_inquiry_id_hash),
            CHECK (platform = 'naver'),
            CHECK (is_stale IN (0, 1))
        )
    """)
    for index_name, (table_name, columns, unique) in INDEXES.items():
        unique_sql = "UNIQUE " if unique else ""
        connection.execute(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(columns)})"
        )


def _verify_schema(connection: sqlite3.Connection) -> None:
    tables = _existing_tables(connection)
    missing_tables = sorted(set(TABLE_COLUMNS) - tables)
    if missing_tables:
        raise RuntimeError(f"Missing PXG/Naver readonly tables: {missing_tables}")
    for table_name, expected_columns in TABLE_COLUMNS.items():
        observed = {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}
        missing_columns = sorted(expected_columns - observed)
        if missing_columns:
            raise RuntimeError(f"Missing columns in {table_name}: {missing_columns}")
        forbidden = {"raw_response", "raw_request", "headers", "authorization", "access_token", "client_secret"} & {
            column.lower() for column in observed
        }
        if forbidden:
            raise RuntimeError(f"Forbidden persistence columns in {table_name}: {sorted(forbidden)}")
    indexes = {
        row[1]
        for table_name in TABLE_COLUMNS
        for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
    }
    missing_indexes = sorted(set(INDEXES) - indexes)
    if missing_indexes:
        raise RuntimeError(f"Missing PXG/Naver readonly indexes: {missing_indexes}")


def upgrade(*, run_create_all: bool = True) -> None:
    import app.models  # noqa: F401

    if run_create_all:
        Base.metadata.create_all(bind=engine)
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        return
    path = _resolve_sqlite_path(settings.database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        _create_schema(connection)
        _verify_schema(connection)
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    upgrade()
    print("upgrade_pxg_naver_readonly_schema: ok")
