import sqlite3
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


TABLE_COLUMNS = {
    "stores": {
        "ziniao_external_id_encrypted": "TEXT",
        "ziniao_external_id_hash": "VARCHAR(64)",
        "ziniao_source_name": "VARCHAR(200)",
        "ziniao_source_platform": "VARCHAR(500)",
        "ziniao_source_site": "VARCHAR(200)",
        "ziniao_auto_managed": "BOOLEAN NOT NULL DEFAULT 0",
        "ziniao_name_managed": "BOOLEAN NOT NULL DEFAULT 0",
        "ziniao_directory_status": "VARCHAR(30) NOT NULL DEFAULT 'unmanaged'",
        "ziniao_operational_mode": "VARCHAR(30) NOT NULL DEFAULT 'business'",
        "ziniao_last_seen_at": "DATETIME",
        "ziniao_directory_checked_at": "DATETIME",
        "ziniao_missing_count": "INTEGER NOT NULL DEFAULT 0",
        "ziniao_missing_since": "DATETIME",
    },
    "device_environments": {
        "source_provider": "VARCHAR(30)",
        "encrypted_ip_address": "TEXT",
        "ip_address_hash": "VARCHAR(64)",
        "masked_ip_address": "VARCHAR(80)",
        "network_country": "VARCHAR(100)",
        "network_region": "VARCHAR(100)",
        "network_city": "VARCHAR(100)",
        "network_status": "VARCHAR(30) NOT NULL DEFAULT 'not_configured'",
        "network_checked_at": "DATETIME",
    },
    "erp_store_memberships": {
        "assignment_source": "VARCHAR(30) NOT NULL DEFAULT 'manual'",
    },
}

INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_stores_ziniao_external_hash "
    "ON stores(ziniao_external_id_hash) WHERE ziniao_external_id_hash IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_stores_ziniao_directory_status "
    "ON stores(ziniao_directory_status)",
    "CREATE INDEX IF NOT EXISTS ix_stores_ziniao_operational_mode "
    "ON stores(ziniao_operational_mode)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_environments_store_source "
    "ON device_environments(store_id, source_provider) WHERE source_provider IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_device_environments_source_provider "
    "ON device_environments(source_provider)",
    "CREATE INDEX IF NOT EXISTS ix_device_environments_ip_hash "
    "ON device_environments(ip_address_hash)",
    "CREATE INDEX IF NOT EXISTS ix_device_environments_network_status "
    "ON device_environments(network_status)",
    "CREATE INDEX IF NOT EXISTS ix_erp_store_memberships_assignment_source "
    "ON erp_store_memberships(assignment_source)",
)


def _database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_ziniao_directory_schema.py only supports sqlite:/// database URLs")
    path = Path(url.removeprefix("sqlite:///"))
    return path if path.is_absolute() else Path.cwd() / path


def upgrade() -> dict[str, list[str]]:
    connection = sqlite3.connect(_database_path())
    changed: dict[str, list[str]] = {table: [] for table in TABLE_COLUMNS}
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table_name, definitions in TABLE_COLUMNS.items():
            if table_name not in tables:
                continue
            columns = {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, definition in definitions.items():
                if column_name not in columns:
                    connection.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                    )
                    changed[table_name].append(column_name)
        for statement in INDEXES:
            table_name = statement.split(" ON ", 1)[1].split("(", 1)[0].strip()
            if table_name in tables:
                connection.execute(statement)
        connection.commit()
        return changed
    finally:
        connection.close()


if __name__ == "__main__":
    result = upgrade()
    summary = ", ".join(
        f"{table}={len(columns)}" for table, columns in result.items()
    )
    print(f"ziniao directory schema upgraded: {summary}")
