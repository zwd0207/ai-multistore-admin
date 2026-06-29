import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


COLUMNS = {
    "vendor_id": "VARCHAR(120)",
    "client_id": "VARCHAR(120)",
    "encrypted_access_token": "VARCHAR(1000)",
    "encrypted_refresh_token": "VARCHAR(1000)",
    "token_expires_at": "DATETIME",
    "market": "VARCHAR(30)",
    "auth_status": "VARCHAR(30) NOT NULL DEFAULT 'not_configured'",
    "last_tested_at": "DATETIME",
    "api_remark": "VARCHAR(500)",
}


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_api_credentials_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_columns(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("PRAGMA table_info(api_credentials)").fetchall()
    if not rows:
        raise RuntimeError("api_credentials table does not exist; run backend startup/init first")
    return {row[1] for row in rows}


def upgrade() -> list[str]:
    database_path = resolve_sqlite_path(get_settings().database_url)
    connection = sqlite3.connect(database_path)
    try:
        existing = get_existing_columns(connection)
        added: list[str] = []
        for name, definition in COLUMNS.items():
            if name in existing:
                continue
            connection.execute(f"ALTER TABLE api_credentials ADD COLUMN {name} {definition}")
            added.append(name)
        connection.commit()
        return added
    finally:
        connection.close()


def main() -> None:
    added = upgrade()
    if added:
        print(f"api_credentials schema upgraded: {', '.join(added)}")
    else:
        print("api_credentials schema already up to date")


if __name__ == "__main__":
    main()
