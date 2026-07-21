import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings


def _database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_store_onboarding_schema.py only supports sqlite:/// database URLs")
    path = Path(url.removeprefix("sqlite:///"))
    return path if path.is_absolute() else Path.cwd() / path


def upgrade() -> list[str]:
    connection = sqlite3.connect(_database_path())
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='store_onboardings'"
        ).fetchone()
        changed: list[str] = []
        if not exists:
            connection.execute("""
            CREATE TABLE store_onboardings (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                idempotency_key VARCHAR(120) NOT NULL,
                requested_store_name VARCHAR(200) NOT NULL,
                creator_user_id INTEGER NOT NULL,
                store_id INTEGER UNIQUE,
                credential_id INTEGER UNIQUE,
                encrypted_client_id TEXT,
                encrypted_client_secret TEXT,
                requested_channel_no VARCHAR(120),
                status VARCHAR(30) NOT NULL DEFAULT 'validating',
                snapshot_end_at DATETIME,
                initial_window_start_at DATETIME,
                retry_count INTEGER NOT NULL DEFAULT 0,
                configuration_version INTEGER NOT NULL DEFAULT 1,
                next_retry_at DATETIME,
                last_error_code VARCHAR(80),
                worker_claim_token VARCHAR(64),
                worker_claimed_at DATETIME,
                validation_summary JSON,
                progress_summary JSON,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(creator_user_id) REFERENCES erp_users(id),
                FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                FOREIGN KEY(store_id) REFERENCES stores(id),
                FOREIGN KEY(credential_id) REFERENCES api_credentials(id),
                CHECK(status IN ('validating', 'blocked', 'provisioning', 'backfilling', 'partially_synced', 'active_incremental', 'retry_wait', 'cancelled'))
            )
            """)
            changed.append("store_onboardings")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(store_onboardings)").fetchall()}
        for name, definition in {
            "tenant_id": "INTEGER",
            "worker_claim_token": "VARCHAR(64)",
            "worker_claimed_at": "DATETIME",
            "configuration_version": "INTEGER NOT NULL DEFAULT 1",
        }.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE store_onboardings ADD COLUMN {name} {definition}")
                changed.append(name)
        connection.execute("CREATE INDEX IF NOT EXISTS ix_store_onboardings_idempotency_key ON store_onboardings(idempotency_key)")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_store_onboardings_tenant_id ON store_onboardings(tenant_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_store_onboardings_creator_user_id ON store_onboardings(creator_user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_store_onboardings_status ON store_onboardings(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS ix_store_onboardings_worker_claim_token ON store_onboardings(worker_claim_token)")
        connection.commit()
        return changed
    finally:
        connection.close()


if __name__ == "__main__":
    print("store onboarding schema upgraded: " + ", ".join(upgrade()))
