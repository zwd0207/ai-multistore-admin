import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine


ORDER_STATUS_EVENT_TABLE = "order_status_events"

ORDER_STATUS_EVENT_COLUMNS = {
    "id",
    "store_id",
    "order_id",
    "platform",
    "external_order_id_hash",
    "external_product_order_id_hash",
    "event_type",
    "status_raw",
    "status_label_zh",
    "payment_status_raw",
    "payment_status_label_zh",
    "delivery_status_raw",
    "delivery_status_label_zh",
    "claim_status_raw",
    "claim_status_label_zh",
    "observed_at",
    "source_phase",
    "source_type",
    "mapping_version",
    "dedupe_key",
    "raw_response_saved",
    "privacy_fields_redacted",
    "address_saved",
    "safe_metadata",
    "created_at",
    "updated_at",
}

ORDER_STATUS_EVENT_NOT_NULL_COLUMNS = {
    "store_id",
    "order_id",
    "platform",
    "external_product_order_id_hash",
    "event_type",
    "source_phase",
    "source_type",
    "mapping_version",
    "dedupe_key",
    "raw_response_saved",
    "privacy_fields_redacted",
    "address_saved",
    "created_at",
    "updated_at",
}

ORDER_STATUS_EVENT_INDEXES = {
    "uq_order_status_event_dedupe": ["store_id", "platform", "dedupe_key"],
    "ix_order_status_events_store_platform_observed": ["store_id", "platform", "observed_at"],
    "ix_order_status_events_order_observed": ["order_id", "observed_at"],
    "ix_order_status_events_store_event_type": ["store_id", "platform", "event_type"],
    "ix_order_status_events_product_order_hash": ["external_product_order_id_hash"],
}

ORDER_STATUS_EVENT_UNPLANNED_INDEXES = {
    "ix_order_status_events_event_type",
    "ix_order_status_events_external_order_id_hash",
    "ix_order_status_events_external_product_order_id_hash",
    "ix_order_status_events_id",
    "ix_order_status_events_observed_at",
    "ix_order_status_events_order_id",
    "ix_order_status_events_platform",
    "ix_order_status_events_source_type",
    "ix_order_status_events_store_id",
}


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_order_status_events_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def create_order_status_event_schema(connection: sqlite3.Connection) -> bool:
    existed = ORDER_STATUS_EVENT_TABLE in get_existing_tables(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS order_status_events (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL,
            external_order_id_hash VARCHAR(120),
            external_product_order_id_hash VARCHAR(120) NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            status_raw VARCHAR(60),
            status_label_zh VARCHAR(120),
            payment_status_raw VARCHAR(60),
            payment_status_label_zh VARCHAR(120),
            delivery_status_raw VARCHAR(60),
            delivery_status_label_zh VARCHAR(120),
            claim_status_raw VARCHAR(60),
            claim_status_label_zh VARCHAR(120),
            observed_at DATETIME,
            source_phase VARCHAR(80) NOT NULL,
            source_type VARCHAR(80) NOT NULL,
            mapping_version VARCHAR(100) NOT NULL,
            dedupe_key VARCHAR(320) NOT NULL,
            raw_response_saved BOOLEAN NOT NULL DEFAULT 0,
            privacy_fields_redacted BOOLEAN NOT NULL DEFAULT 1,
            address_saved BOOLEAN NOT NULL DEFAULT 0,
            safe_metadata JSON,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(store_id) REFERENCES stores(id)
        )
    """)
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_order_status_event_dedupe
        ON order_status_events (store_id, platform, dedupe_key)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_order_status_events_store_platform_observed
        ON order_status_events (store_id, platform, observed_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_order_status_events_order_observed
        ON order_status_events (order_id, observed_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_order_status_events_store_event_type
        ON order_status_events (store_id, platform, event_type)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_order_status_events_product_order_hash
        ON order_status_events (external_product_order_id_hash)
    """)
    for index_name in ORDER_STATUS_EVENT_UNPLANNED_INDEXES:
        connection.execute(f"DROP INDEX IF EXISTS {index_name}")
    return not existed


def verify_order_status_event_schema(connection: sqlite3.Connection) -> None:
    table_info = connection.execute("PRAGMA table_info(order_status_events)").fetchall()
    columns = {row[1] for row in table_info}
    missing_columns = sorted(ORDER_STATUS_EVENT_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError(f"Missing order_status_events columns: {missing_columns}")

    not_null = {row[1]: bool(row[3]) for row in table_info}
    missing_not_null = sorted(
        column
        for column in ORDER_STATUS_EVENT_NOT_NULL_COLUMNS
        if not not_null.get(column)
    )
    if missing_not_null:
        raise RuntimeError(f"Missing order_status_events NOT NULL columns: {missing_not_null}")

    index_rows = connection.execute("PRAGMA index_list(order_status_events)").fetchall()
    index_names = {row[1] for row in index_rows}
    unique_index_names = {row[1] for row in index_rows if row[2]}
    missing_indexes = sorted(set(ORDER_STATUS_EVENT_INDEXES) - index_names)
    if missing_indexes:
        raise RuntimeError(f"Missing order_status_events indexes: {missing_indexes}")
    unplanned_indexes = sorted(ORDER_STATUS_EVENT_UNPLANNED_INDEXES & index_names)
    if unplanned_indexes:
        raise RuntimeError(f"Unplanned order_status_events indexes remain: {unplanned_indexes}")
    if "uq_order_status_event_dedupe" not in unique_index_names:
        raise RuntimeError("Missing unique order_status_events dedupe index")

    for index_name, expected_columns in ORDER_STATUS_EVENT_INDEXES.items():
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
    if run_create_all:
        Base.metadata.create_all(bind=engine)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        created = create_order_status_event_schema(connection)
        connection.commit()
        verify_order_status_event_schema(connection)
        return {
            "tables": [ORDER_STATUS_EVENT_TABLE] if created else [],
            "indexes": sorted(ORDER_STATUS_EVENT_INDEXES),
        }
    finally:
        connection.close()


def main() -> None:
    result = upgrade()
    if result["tables"]:
        print("order status events schema upgraded: order_status_events")
    else:
        print("order status events schema already up to date")


if __name__ == "__main__":
    main()
