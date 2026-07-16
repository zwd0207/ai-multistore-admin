import sqlite3
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


COLUMNS = {
    "erp_users": {
        "tenant_id": "INTEGER",
        "email_encrypted": "TEXT",
        "email_verified_at": "DATETIME",
        "platform_role": "VARCHAR(30) NOT NULL DEFAULT 'tenant_owner'",
    },
    "stores": {
        "tenant_id": "INTEGER",
    },
    "store_onboardings": {
        "tenant_id": "INTEGER",
    },
    "erp_sessions": {
        "selected_tenant_id": "INTEGER",
    },
    "tenant_invitations": {
        "target_tenant_id": "INTEGER",
        "invited_platform_role": "VARCHAR(30) NOT NULL DEFAULT 'tenant_owner'",
    },
}

INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_erp_users_tenant_id ON erp_users(tenant_id)",
    "CREATE INDEX IF NOT EXISTS ix_stores_tenant_id ON stores(tenant_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_stores_tenant_name ON stores(tenant_id, name)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_stores_tenant_ziniao_external_hash "
    "ON stores(tenant_id, ziniao_external_id_hash) WHERE ziniao_external_id_hash IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_store_onboardings_tenant_id ON store_onboardings(tenant_id)",
    "CREATE INDEX IF NOT EXISTS ix_erp_sessions_selected_tenant_id ON erp_sessions(selected_tenant_id)",
)


def _database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_tenant_schema.py only supports sqlite:/// database URLs")
    path = Path(url.removeprefix("sqlite:///"))
    return path if path.is_absolute() else Path.cwd() / path


def upgrade() -> dict[str, list[str]]:
    connection = sqlite3.connect(_database_path())
    changed = {table: [] for table in COLUMNS}
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table_name, definitions in COLUMNS.items():
            if table_name not in tables:
                continue
            existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}
            for column_name, definition in definitions.items():
                if column_name not in existing:
                    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                    changed[table_name].append(column_name)
        connection.execute("DROP INDEX IF EXISTS uq_stores_ziniao_external_hash")
        for statement in INDEXES:
            table_name = statement.split(" ON ", 1)[1].split("(", 1)[0].strip()
            if table_name in tables:
                connection.execute(statement)
        connection.commit()
        return changed
    finally:
        connection.close()


if __name__ == "__main__":
    print("tenant schema upgraded: " + str(upgrade()))
