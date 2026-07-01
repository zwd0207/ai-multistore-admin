import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine


ORDER_COLUMNS = {
    "source_type": "VARCHAR(30) NOT NULL DEFAULT 'legacy'",
    "last_synced_at": "DATETIME",
}

PRODUCT_COLUMNS = {
    "source_type": "VARCHAR(30) NOT NULL DEFAULT 'legacy'",
    "last_synced_at": "DATETIME",
}

FINANCIAL_TABLES = {
    "platform_sales_details",
    "platform_settlement_details",
}


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_sync_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if not rows:
        raise RuntimeError(f"{table_name} table does not exist; run backend startup/init first")
    return {row[1] for row in rows}


def get_existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def add_missing_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> list[str]:
    existing = get_existing_columns(connection, table_name)
    added: list[str] = []
    for name, definition in columns.items():
        if name in existing:
            continue
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}")
        added.append(name)
    return added


def upgrade(*, run_create_all: bool = True) -> dict[str, list[str]]:
    import app.models  # noqa: F401

    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        if run_create_all:
            Base.metadata.create_all(bind=engine)
        return {"orders": [], "products": [], "tables": [], "financial_tables": []}

    database_path = resolve_sqlite_path(settings.database_url)
    connection = sqlite3.connect(database_path)
    try:
        existing_tables = get_existing_tables(connection)
    finally:
        connection.close()

    if run_create_all:
        Base.metadata.create_all(bind=engine)

    connection = sqlite3.connect(database_path)
    try:
        orders_added = add_missing_columns(connection, "orders", ORDER_COLUMNS)
        products_added = add_missing_columns(connection, "products", PRODUCT_COLUMNS)
        connection.commit()
        current_tables = get_existing_tables(connection)
        financial_tables_added = sorted(FINANCIAL_TABLES - existing_tables)
        financial_tables_missing = sorted(FINANCIAL_TABLES - current_tables)
        if financial_tables_missing:
            raise RuntimeError(f"Financial tables were not created: {financial_tables_missing}")
        return {
            "orders": orders_added,
            "products": products_added,
            "tables": ["sync_checkpoints"] if "sync_checkpoints" not in existing_tables else [],
            "financial_tables": financial_tables_added,
        }
    finally:
        connection.close()


def main() -> None:
    added = upgrade()
    if any(added.values()):
        print(
            "sync schema upgraded: "
            f"orders({', '.join(added['orders']) or 'no new columns'}), "
            f"products({', '.join(added['products']) or 'no new columns'}), "
            f"tables({', '.join(added['tables']) or 'none'}), "
            f"financial_tables({', '.join(added['financial_tables']) or 'none'})"
        )
    else:
        print("sync schema already up to date")


if __name__ == "__main__":
    main()
