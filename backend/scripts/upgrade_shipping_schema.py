import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine


SHIPPING_TABLES = {
    "logistics_inventory_mappings",
    "logistics_inventory_items",
}

SHIPPING_TABLE_COLUMNS = {
    "logistics_inventory_mappings": {
        "id",
        "store_id",
        "platform",
        "match_product_name",
        "match_option_name",
        "normalized_product_name",
        "normalized_option_name",
        "platform_product_id_hash",
        "platform_option_id_hash",
        "internal_sku",
        "logistics_inventory_code",
        "logistics_provider_name",
        "match_priority",
        "is_active",
        "mapping_version",
        "created_by_actor_hash",
        "updated_by_actor_hash",
        "created_at",
        "updated_at",
    },
    "logistics_inventory_items": {
        "id",
        "store_id",
        "platform",
        "logistics_inventory_code",
        "logistics_provider_name",
        "current_stock_quantity",
        "stock_status",
        "last_manual_checked_at",
        "last_manual_updated_by_actor_hash",
        "note",
        "is_active",
        "created_at",
        "updated_at",
    },
}

SHIPPING_NOT_NULL_COLUMNS = {
    "logistics_inventory_mappings": {
        "store_id",
        "platform",
        "match_product_name",
        "match_option_name",
        "normalized_product_name",
        "normalized_option_name",
        "logistics_inventory_code",
        "match_priority",
        "is_active",
        "mapping_version",
        "created_at",
        "updated_at",
    },
    "logistics_inventory_items": {
        "store_id",
        "platform",
        "logistics_inventory_code",
        "current_stock_quantity",
        "stock_status",
        "is_active",
        "created_at",
        "updated_at",
    },
}

SHIPPING_INDEXES = {
    "uq_logistics_mapping_product_option": (
        "logistics_inventory_mappings",
        ["store_id", "platform", "normalized_product_name", "normalized_option_name"],
        True,
    ),
    "ix_logistics_mappings_store_platform": (
        "logistics_inventory_mappings",
        ["store_id", "platform"],
        False,
    ),
    "ix_logistics_mappings_match_key": (
        "logistics_inventory_mappings",
        ["store_id", "platform", "normalized_product_name", "normalized_option_name"],
        False,
    ),
    "ix_logistics_mappings_inventory_code": (
        "logistics_inventory_mappings",
        ["logistics_inventory_code"],
        False,
    ),
    "uq_logistics_inventory_item_code": (
        "logistics_inventory_items",
        ["store_id", "platform", "logistics_inventory_code"],
        True,
    ),
    "ix_logistics_inventory_items_store_platform": (
        "logistics_inventory_items",
        ["store_id", "platform"],
        False,
    ),
    "ix_logistics_inventory_items_code": (
        "logistics_inventory_items",
        ["logistics_inventory_code"],
        False,
    ),
    "ix_logistics_inventory_items_status": (
        "logistics_inventory_items",
        ["store_id", "platform", "stock_status"],
        False,
    ),
}

FORBIDDEN_SHIPPING_COLUMNS = {
    "access_token",
    "authorization",
    "buyer_name",
    "buyer_phone",
    "channel_no",
    "client_secret",
    "detailed_address",
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
        raise RuntimeError("upgrade_shipping_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def create_shipping_schema(connection: sqlite3.Connection) -> list[str]:
    existing_tables = get_existing_tables(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS logistics_inventory_mappings (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL,
            match_product_name VARCHAR(300) NOT NULL,
            match_option_name VARCHAR(300) NOT NULL DEFAULT '',
            normalized_product_name VARCHAR(300) NOT NULL,
            normalized_option_name VARCHAR(300) NOT NULL DEFAULT '',
            platform_product_id_hash VARCHAR(160),
            platform_option_id_hash VARCHAR(160),
            internal_sku VARCHAR(120),
            logistics_inventory_code VARCHAR(120) NOT NULL,
            logistics_provider_name VARCHAR(160),
            match_priority INTEGER NOT NULL DEFAULT 100,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            mapping_version VARCHAR(80) NOT NULL DEFAULT 'shipping_mapping_v1',
            created_by_actor_hash VARCHAR(160),
            updated_by_actor_hash VARCHAR(160),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            CHECK (store_id > 0),
            CHECK (length(trim(platform)) > 0),
            CHECK (length(trim(match_product_name)) > 0),
            CHECK (length(trim(normalized_product_name)) > 0),
            CHECK (length(trim(logistics_inventory_code)) > 0),
            CHECK (match_priority >= 0),
            CHECK (is_active IN (0, 1))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS logistics_inventory_items (
            id INTEGER PRIMARY KEY,
            store_id INTEGER NOT NULL,
            platform VARCHAR(50) NOT NULL,
            logistics_inventory_code VARCHAR(120) NOT NULL,
            logistics_provider_name VARCHAR(160),
            current_stock_quantity INTEGER NOT NULL DEFAULT 0,
            stock_status VARCHAR(30) NOT NULL DEFAULT 'available',
            last_manual_checked_at DATETIME,
            last_manual_updated_by_actor_hash VARCHAR(160),
            note TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id),
            CHECK (store_id > 0),
            CHECK (length(trim(platform)) > 0),
            CHECK (length(trim(logistics_inventory_code)) > 0),
            CHECK (current_stock_quantity >= 0),
            CHECK (stock_status IN ('available', 'low_stock', 'out_of_stock', 'unknown')),
            CHECK (is_active IN (0, 1))
        )
    """)

    for index_name, (table_name, columns, unique) in SHIPPING_INDEXES.items():
        unique_sql = "UNIQUE " if unique else ""
        connection.execute(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} ({', '.join(columns)})"
        )

    return sorted(SHIPPING_TABLES - existing_tables)


def verify_shipping_schema(connection: sqlite3.Connection) -> None:
    tables = get_existing_tables(connection)
    missing_tables = sorted(SHIPPING_TABLES - tables)
    if missing_tables:
        raise RuntimeError(f"Missing shipping tables: {missing_tables}")

    for table_name, expected_columns in SHIPPING_TABLE_COLUMNS.items():
        table_info = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        columns = {row[1] for row in table_info}
        missing_columns = sorted(expected_columns - columns)
        if missing_columns:
            raise RuntimeError(f"Missing {table_name} columns: {missing_columns}")

        forbidden_columns = sorted({column.lower() for column in columns} & FORBIDDEN_SHIPPING_COLUMNS)
        if forbidden_columns:
            raise RuntimeError(f"Forbidden shipping columns in {table_name}: {forbidden_columns}")

        not_null = {row[1]: bool(row[3]) for row in table_info}
        missing_not_null = sorted(
            column
            for column in SHIPPING_NOT_NULL_COLUMNS[table_name]
            if not not_null.get(column)
        )
        if missing_not_null:
            raise RuntimeError(f"Missing {table_name} NOT NULL columns: {missing_not_null}")

    all_indexes = {}
    for table_name in SHIPPING_TABLES:
        for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall():
            all_indexes[row[1]] = (table_name, bool(row[2]))

    missing_indexes = sorted(set(SHIPPING_INDEXES) - set(all_indexes))
    if missing_indexes:
        raise RuntimeError(f"Missing shipping indexes: {missing_indexes}")

    for index_name, (expected_table, expected_columns, expected_unique) in SHIPPING_INDEXES.items():
        observed_table, observed_unique = all_indexes[index_name]
        if observed_table != expected_table:
            raise RuntimeError(f"Unexpected table for {index_name}: {observed_table}")
        if observed_unique != expected_unique:
            raise RuntimeError(f"Unexpected unique flag for {index_name}: {observed_unique}")
        rows = connection.execute(f"PRAGMA index_info({index_name})").fetchall()
        observed_columns = [row[2] for row in rows]
        if observed_columns != expected_columns:
            raise RuntimeError(
                f"Unexpected {index_name} columns: {observed_columns}; expected {expected_columns}"
            )


def upgrade(*, run_create_all: bool = True) -> dict[str, object]:
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
        created_tables = create_shipping_schema(connection)
        connection.commit()
        verify_shipping_schema(connection)
        return {
            "tables": created_tables,
            "indexes": sorted(SHIPPING_INDEXES),
        }
    finally:
        connection.close()


def main() -> None:
    result = upgrade()
    if result["tables"]:
        print("shipping schema upgraded: " + ", ".join(result["tables"]))
    else:
        print("shipping schema already up to date")


if __name__ == "__main__":
    main()
