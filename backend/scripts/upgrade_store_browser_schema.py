import sqlite3
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


STORE_BROWSER_COLUMNS = {
    "browser_provider": "VARCHAR(30)",
    "browser_profile_name": "VARCHAR(200)",
}


def _database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_store_browser_schema.py only supports sqlite:/// database URLs")
    path = Path(url.removeprefix("sqlite:///"))
    return path if path.is_absolute() else Path.cwd() / path


def upgrade() -> list[str]:
    connection = sqlite3.connect(_database_path())
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stores'"
        ).fetchone()
        if not exists:
            raise RuntimeError("stores table is required before the browser binding upgrade")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(stores)").fetchall()}
        changed: list[str] = []
        for name, definition in STORE_BROWSER_COLUMNS.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE stores ADD COLUMN {name} {definition}")
                changed.append(name)
        connection.commit()
        return changed
    finally:
        connection.close()


if __name__ == "__main__":
    print("store browser schema upgraded: " + ", ".join(upgrade()))
