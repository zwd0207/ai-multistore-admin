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
    "pxg_naver_readonly_cleanup_statuses": {
        "id", "store_id", "platform", "status", "last_run_at", "last_success_at", "last_failure_at",
        "last_failure_code", "manual_review_count", "created_at", "updated_at",
    },
    "pxg_naver_readonly_sync_controls": {
        "id", "store_id", "platform", "write_and_refresh_blocked", "backup_retention_failed", "reason_code", "updated_at",
    },
    "pxg_naver_readonly_sync_batches": {
        "id", "batch_no", "store_id", "platform", "status", "actor_id_hash", "backup_id", "baseline_counts",
        "mutation_counts", "created_record_ids", "created_at", "completed_at", "rolled_back_at",
    },
    "pxg_naver_readonly_sync_backups": {
        "id", "batch_id", "store_id", "platform", "backup_ref", "encrypted_path", "checksum_sha256", "schema_version",
        "actor_id_hash", "baseline_manifest", "expires_at", "restore_drill_passed_at", "deleted_at", "created_at",
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
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_cleanup_statuses (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            status VARCHAR(40) NOT NULL DEFAULT 'healthy',
            last_run_at DATETIME,
            last_success_at DATETIME,
            last_failure_at DATETIME,
            last_failure_code VARCHAR(120),
            manual_review_count INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            UNIQUE(store_id, platform),
            CHECK (platform = 'naver'),
            CHECK (status IN ('healthy', 'manual_review_required', 'failed'))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_sync_controls (
            id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL, platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            write_and_refresh_blocked BOOLEAN NOT NULL DEFAULT 0, backup_retention_failed BOOLEAN NOT NULL DEFAULT 0,
            reason_code VARCHAR(120), updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id), UNIQUE(store_id, platform)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_sync_batches (
            id INTEGER PRIMARY KEY, batch_no VARCHAR(100) NOT NULL, store_id INTEGER NOT NULL, platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            status VARCHAR(40) NOT NULL, actor_id_hash VARCHAR(64) NOT NULL, backup_id INTEGER,
            baseline_counts JSON NOT NULL, mutation_counts JSON, created_record_ids JSON,
            created_at DATETIME NOT NULL, completed_at DATETIME, rolled_back_at DATETIME,
            FOREIGN KEY(store_id) REFERENCES stores(id), UNIQUE(batch_no)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pxg_naver_readonly_sync_backups (
            id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL, store_id INTEGER NOT NULL, platform VARCHAR(50) NOT NULL DEFAULT 'naver',
            backup_ref VARCHAR(160) NOT NULL, encrypted_path VARCHAR(500) NOT NULL, checksum_sha256 VARCHAR(64) NOT NULL,
            schema_version VARCHAR(60) NOT NULL, actor_id_hash VARCHAR(64) NOT NULL, baseline_manifest JSON NOT NULL, expires_at DATETIME NOT NULL,
            restore_drill_passed_at DATETIME, deleted_at DATETIME, created_at DATETIME NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES pxg_naver_readonly_sync_batches(id), FOREIGN KEY(store_id) REFERENCES stores(id), UNIQUE(backup_ref)
        )
    """)
    for index_name, (table_name, columns, unique) in INDEXES.items():
        unique_sql = "UNIQUE " if unique else ""
        connection.execute(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(columns)})"
        )


def _upgrade_existing_sync_backup_columns(connection: sqlite3.Connection) -> None:
    tables = _existing_tables(connection)
    if "pxg_naver_readonly_sync_backups" not in tables:
        return
    columns = {row[1] for row in connection.execute("PRAGMA table_info(pxg_naver_readonly_sync_backups)").fetchall()}
    if "baseline_manifest" not in columns:
        connection.execute("ALTER TABLE pxg_naver_readonly_sync_backups ADD COLUMN baseline_manifest JSON NOT NULL DEFAULT '{}'")


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


def _order_unique_columns(connection: sqlite3.Connection) -> set[tuple[str, ...]]:
    unique_indexes: set[tuple[str, ...]] = set()
    for row in connection.execute("PRAGMA index_list(orders)").fetchall():
        if not row[2]:
            continue
        columns = tuple(item[2] for item in connection.execute(f"PRAGMA index_info({row[1]})").fetchall())
        unique_indexes.add(columns)
    return unique_indexes


def _assert_no_order_duplicates(connection: sqlite3.Connection, *, source_where: str, key_column: str, message: str) -> None:
    duplicates = connection.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT store_id, platform, {key_column}
            FROM orders
            WHERE {source_where} AND {key_column} IS NOT NULL AND TRIM({key_column}) != ''
            GROUP BY store_id, platform, {key_column}
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    if duplicates:
        raise RuntimeError(message)


def _create_order_uniqueness_indexes(connection: sqlite3.Connection) -> None:
    _assert_no_order_duplicates(
        connection,
        source_where="source_type != 'pxg_naver_readonly_local_v1'",
        key_column="external_order_id",
        message="orders migration found duplicate non-PXG platform-order identifiers; manual reconciliation is required",
    )
    _assert_no_order_duplicates(
        connection,
        source_where="source_type = 'pxg_naver_readonly_local_v1'",
        key_column="external_product_order_id",
        message="orders migration found duplicate PXG product-order identifiers; manual reconciliation is required",
    )
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_order_non_pxg_external_id
        ON orders (store_id, platform, external_order_id)
        WHERE source_type != 'pxg_naver_readonly_local_v1'
    """)
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pxg_naver_readonly_product_order
        ON orders (store_id, platform, external_product_order_id)
        WHERE source_type = 'pxg_naver_readonly_local_v1'
          AND external_product_order_id IS NOT NULL
          AND TRIM(external_product_order_id) != ''
    """)


def _rebuild_orders_for_product_order_uniqueness(connection: sqlite3.Connection) -> None:
    """Add PXG-only product-order uniqueness without changing legacy semantics."""

    unique_indexes = _order_unique_columns(connection)
    desired_index_names = {"uq_order_non_pxg_external_id", "uq_pxg_naver_readonly_product_order"}
    legacy = ("store_id", "platform", "external_order_id")
    index_names = {row[1] for row in connection.execute("PRAGMA index_list(orders)").fetchall()}
    if desired_index_names.issubset(index_names):
        return
    if legacy not in unique_indexes:
        if "uq_pxg_naver_readonly_product_order" in index_names:
            _create_order_uniqueness_indexes(connection)
            return
        raise RuntimeError("orders table has an unsupported unique-key shape")
    _assert_no_order_duplicates(
        connection,
        source_where="source_type = 'pxg_naver_readonly_local_v1'",
        key_column="external_product_order_id",
        message="orders migration found duplicate PXG product-order identifiers; manual reconciliation is required",
    )

    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.execute("""
            CREATE TABLE orders__pxg_product_order_upgrade (
                id INTEGER NOT NULL PRIMARY KEY,
                store_id INTEGER NOT NULL,
                platform VARCHAR(50) NOT NULL,
                external_order_id VARCHAR(120) NOT NULL,
                external_product_order_id VARCHAR(120),
                buyer_name VARCHAR(120),
                buyer_phone VARCHAR(40),
                buyer_masked_phone VARCHAR(30),
                receiver_name VARCHAR(120),
                receiver_phone VARCHAR(40),
                receiver_address VARCHAR(300),
                zip_code VARCHAR(30),
                product_name VARCHAR(300) NOT NULL,
                quantity INTEGER NOT NULL,
                order_amount NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(10) NOT NULL,
                order_status VARCHAR(30) NOT NULL,
                paid_at DATETIME,
                ordered_at DATETIME NOT NULL,
                source_type VARCHAR(30) NOT NULL,
                last_synced_at DATETIME,
                raw_data JSON,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(store_id) REFERENCES stores(id)
            )
        """)
        connection.execute("""
            INSERT INTO orders__pxg_product_order_upgrade (
                id, store_id, platform, external_order_id, external_product_order_id,
                buyer_name, buyer_phone, buyer_masked_phone, receiver_name, receiver_phone,
                receiver_address, zip_code, product_name, quantity, order_amount, currency,
                order_status, paid_at, ordered_at, source_type, last_synced_at, raw_data,
                created_at, updated_at
            )
            SELECT
                id, store_id, platform, external_order_id, external_product_order_id,
                buyer_name, buyer_phone, buyer_masked_phone, receiver_name, receiver_phone,
                receiver_address, zip_code, product_name, quantity, order_amount, currency,
                order_status, paid_at, ordered_at, source_type, last_synced_at, raw_data,
                created_at, updated_at
            FROM orders
        """)
        connection.execute("DROP TABLE orders")
        connection.execute("ALTER TABLE orders__pxg_product_order_upgrade RENAME TO orders")
        _create_order_uniqueness_indexes(connection)
        for index_name, columns in {
            "ix_orders_store_id": "store_id",
            "ix_orders_platform": "platform",
            "ix_orders_external_order_id": "external_order_id",
            "ix_orders_external_product_order_id": "external_product_order_id",
            "ix_orders_order_status": "order_status",
            "ix_orders_source_type": "source_type",
        }.items():
            connection.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON orders ({columns})")
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
    foreign_key_issues = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_issues:
        raise RuntimeError("orders migration foreign-key verification failed")


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
        _rebuild_orders_for_product_order_uniqueness(connection)
        _create_schema(connection)
        _upgrade_existing_sync_backup_columns(connection)
        _verify_schema(connection)
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    upgrade()
    print("upgrade_pxg_naver_readonly_schema: ok")
