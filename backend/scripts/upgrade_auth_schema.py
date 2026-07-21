import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, engine
from app.services.permission_service import ROLE_DEFINITIONS, SENSITIVE_ACTIONS


AUTH_TABLES = {
    "erp_users",
    "erp_roles",
    "erp_permissions",
    "erp_role_permissions",
    "erp_store_memberships",
    "erp_user_security",
    "erp_sessions",
}

AUTH_TABLE_COLUMNS = {
    "erp_users": {
        "id",
        "user_key_hash",
        "display_name",
        "login_identifier_hash",
        "login_identifier_masked",
        "status",
        "auth_provider",
        "last_login_at",
        "created_at",
        "updated_at",
    },
    "erp_roles": {
        "id",
        "role_key",
        "role_label_zh",
        "role_label_en",
        "system_role",
        "status",
        "created_at",
        "updated_at",
    },
    "erp_permissions": {
        "id",
        "permission_key",
        "permission_group",
        "permission_label_zh",
        "sensitive_action",
        "status",
        "created_at",
        "updated_at",
    },
    "erp_role_permissions": {
        "id",
        "role_id",
        "permission_id",
        "can_approve_sensitive",
        "created_at",
        "updated_at",
    },
    "erp_store_memberships": {
        "id",
        "user_id",
        "store_id",
        "role_id",
        "scope_type",
        "membership_status",
        "assigned_by_user_id",
        "assigned_at",
        "revoked_at",
        "created_at",
        "updated_at",
    },
    "erp_user_security": {
        "user_id", "password_hash", "mfa_type", "mfa_secret_encrypted", "mfa_enabled_at",
        "session_version", "authz_version", "failed_login_count", "blocked_until",
        "password_changed_at", "created_at", "updated_at",
    },
    "erp_sessions": {
        "id", "session_token_hash", "user_id", "environment", "authn_level", "session_version",
        "authz_version_at_issue", "csrf_token_hash", "created_at", "last_seen_at", "idle_expires_at",
        "absolute_expires_at", "last_reauthenticated_at", "revoked_at", "revoke_reason",
    },
}

AUTH_NOT_NULL_COLUMNS = {
    "erp_users": {
        "user_key_hash",
        "display_name",
        "status",
        "auth_provider",
        "created_at",
        "updated_at",
    },
    "erp_roles": {
        "role_key",
        "role_label_zh",
        "role_label_en",
        "system_role",
        "status",
        "created_at",
        "updated_at",
    },
    "erp_permissions": {
        "permission_key",
        "permission_group",
        "permission_label_zh",
        "sensitive_action",
        "status",
        "created_at",
        "updated_at",
    },
    "erp_role_permissions": {
        "role_id",
        "permission_id",
        "can_approve_sensitive",
        "created_at",
        "updated_at",
    },
    "erp_store_memberships": {
        "user_id",
        "store_id",
        "role_id",
        "scope_type",
        "membership_status",
        "assigned_at",
        "created_at",
        "updated_at",
    },
    "erp_user_security": {
        "user_id", "mfa_type", "session_version", "authz_version", "failed_login_count", "created_at", "updated_at",
    },
    "erp_sessions": {
        "id", "session_token_hash", "user_id", "environment", "authn_level", "session_version",
        "authz_version_at_issue", "created_at", "last_seen_at", "idle_expires_at", "absolute_expires_at",
    },
}

AUTH_INDEXES = {
    "ix_erp_users_status": ("erp_users", ["status"], False),
    "ix_erp_roles_status": ("erp_roles", ["status"], False),
    "ix_erp_permissions_group": ("erp_permissions", ["permission_group"], False),
    "ix_erp_role_permissions_role": ("erp_role_permissions", ["role_id"], False),
    "uq_erp_role_permissions_role_permission": ("erp_role_permissions", ["role_id", "permission_id"], True),
    "ix_erp_store_memberships_store_status": ("erp_store_memberships", ["store_id", "membership_status"], False),
    "ix_erp_store_memberships_user_status": ("erp_store_memberships", ["user_id", "membership_status"], False),
    "uq_erp_store_memberships_user_store_role": (
        "erp_store_memberships",
        ["user_id", "store_id", "role_id"],
        True,
    ),
    "ix_erp_sessions_token_hash": ("erp_sessions", ["session_token_hash"], True),
    "ix_erp_sessions_user_active": ("erp_sessions", ["user_id", "revoked_at", "absolute_expires_at"], False),
}

AUTH_PARTIAL_INDEXES = {
    "uq_erp_users_login_identifier_hash": (
        "erp_users",
        ["login_identifier_hash"],
        "login_identifier_hash IS NOT NULL",
    ),
}

FORBIDDEN_AUTH_COLUMNS = {
    "access_token",
    "authorization",
    "bcrypt",
    "buyer_name",
    "buyer_phone",
    "channel_no",
    "client_secret",
    "detailed_address",
    "external_order_id",
    "external_product_id",
    "headers",
    "order_id",
    "password",
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

ROLE_LABELS = {
    "owner": ("所有者", "Owner"),
    "admin": ("管理员", "Admin"),
    "operator": ("运营", "Operator"),
    "auditor": ("审计员", "Auditor"),
    "viewer": ("只读查看", "Viewer"),
}

PERMISSION_LABELS = {
    "dashboard.read": "查看工作台",
    "products.read": "查看商品",
    "products.preview": "预览商品接口",
    "products.batch_sync_write": "受控批量写入本地商品",
    "platform.readonly.persist": "PXG Naver 只读本地持久化",
    "platform.browser.open": "打开已授权店铺后台",
    "orders.read": "查看订单",
    "orders.preview": "预览订单接口",
    "orders.local_write": "受控写入本地订单",
    "orders.batch_sync_write": "受控批量写入本地订单",
    "orders.refresh_batch_write": "受控刷新本地订单",
    "audit.read": "查看审计记录",
    "backup.read": "查看备份报告",
    "backup.create": "创建本地备份",
    "store_membership.assign": "受控分配店铺成员",
}


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("upgrade_auth_schema.py only supports sqlite:/// database URLs")
    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def create_auth_schema(connection: sqlite3.Connection) -> list[str]:
    existing_tables = get_existing_tables(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_users (
            id INTEGER PRIMARY KEY,
            user_key_hash VARCHAR(120) NOT NULL UNIQUE,
            display_name VARCHAR(160) NOT NULL,
            login_identifier_hash VARCHAR(120),
            login_identifier_masked VARCHAR(160),
            status VARCHAR(30) NOT NULL DEFAULT 'invited',
            auth_provider VARCHAR(40) NOT NULL DEFAULT 'local_pending',
            last_login_at DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CHECK (status IN ('invited', 'active', 'inactive', 'locked')),
            CHECK (auth_provider IN ('local_pending', 'password', 'sso', 'api_operator'))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_roles (
            id INTEGER PRIMARY KEY,
            role_key VARCHAR(80) NOT NULL UNIQUE,
            role_label_zh VARCHAR(120) NOT NULL,
            role_label_en VARCHAR(120) NOT NULL,
            system_role BOOLEAN NOT NULL DEFAULT 1,
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CHECK (status IN ('active', 'inactive'))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_permissions (
            id INTEGER PRIMARY KEY,
            permission_key VARCHAR(120) NOT NULL UNIQUE,
            permission_group VARCHAR(80) NOT NULL,
            permission_label_zh VARCHAR(160) NOT NULL,
            sensitive_action BOOLEAN NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CHECK (status IN ('active', 'inactive'))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_role_permissions (
            id INTEGER PRIMARY KEY,
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            can_approve_sensitive BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (role_id) REFERENCES erp_roles(id),
            FOREIGN KEY (permission_id) REFERENCES erp_permissions(id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_store_memberships (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            scope_type VARCHAR(30) NOT NULL DEFAULT 'assigned',
            membership_status VARCHAR(30) NOT NULL DEFAULT 'active',
            assigned_by_user_id INTEGER,
            assigned_at DATETIME NOT NULL,
            revoked_at DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES erp_users(id),
            FOREIGN KEY (store_id) REFERENCES stores(id),
            FOREIGN KEY (role_id) REFERENCES erp_roles(id),
            FOREIGN KEY (assigned_by_user_id) REFERENCES erp_users(id),
            CHECK (store_id > 0),
            CHECK (scope_type IN ('all', 'assigned')),
            CHECK (membership_status IN ('active', 'inactive', 'revoked'))
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_user_security (
            user_id INTEGER PRIMARY KEY,
            password_hash TEXT,
            mfa_type VARCHAR(30) NOT NULL DEFAULT 'totp',
            mfa_secret_encrypted TEXT,
            mfa_enabled_at DATETIME,
            session_version INTEGER NOT NULL DEFAULT 1,
            authz_version INTEGER NOT NULL DEFAULT 1,
            failed_login_count INTEGER NOT NULL DEFAULT 0,
            blocked_until DATETIME,
            password_changed_at DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES erp_users(id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS erp_sessions (
            id VARCHAR(64) PRIMARY KEY,
            session_token_hash VARCHAR(128) NOT NULL,
            user_id INTEGER NOT NULL,
            environment VARCHAR(30) NOT NULL,
            authn_level VARCHAR(30) NOT NULL,
            session_version INTEGER NOT NULL,
            authz_version_at_issue INTEGER NOT NULL,
            csrf_token_hash VARCHAR(128),
            created_at DATETIME NOT NULL,
            last_seen_at DATETIME NOT NULL,
            idle_expires_at DATETIME NOT NULL,
            absolute_expires_at DATETIME NOT NULL,
            last_reauthenticated_at DATETIME,
            revoked_at DATETIME,
            revoke_reason VARCHAR(120),
            FOREIGN KEY (user_id) REFERENCES erp_users(id),
            CHECK (environment IN ('development', 'test', 'production')),
            CHECK (authn_level IN ('mfa_pending', 'mfa_verified'))
        )
    """)

    for index_name, (table_name, columns, unique) in AUTH_INDEXES.items():
        unique_sql = "UNIQUE " if unique else ""
        connection.execute(
            f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} ({', '.join(columns)})"
        )
    for index_name, (table_name, columns, predicate) in AUTH_PARTIAL_INDEXES.items():
        connection.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} ({', '.join(columns)}) WHERE {predicate}"
        )

    return sorted(AUTH_TABLES - existing_tables)


def seed_system_roles_and_permissions(connection: sqlite3.Connection) -> dict[str, int]:
    now = datetime.now(timezone.utc).isoformat()
    for role_key in sorted(ROLE_DEFINITIONS):
        label_zh, label_en = ROLE_LABELS.get(role_key, (role_key, role_key.title()))
        connection.execute("""
            INSERT OR IGNORE INTO erp_roles (
                role_key, role_label_zh, role_label_en, system_role, status, created_at, updated_at
            ) VALUES (?, ?, ?, 1, 'active', ?, ?)
        """, (role_key, label_zh, label_en, now, now))

    permission_keys = sorted({
        permission
        for role in ROLE_DEFINITIONS.values()
        for permission in role["permissions"]
        if permission != "*"
    })
    for permission_key in permission_keys:
        connection.execute("""
            INSERT OR IGNORE INTO erp_permissions (
                permission_key, permission_group, permission_label_zh,
                sensitive_action, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'active', ?, ?)
        """, (
            permission_key,
            permission_key.split(".", 1)[0],
            PERMISSION_LABELS.get(permission_key, permission_key),
            1 if permission_key in SENSITIVE_ACTIONS else 0,
            now,
            now,
        ))

    role_rows = connection.execute("SELECT id, role_key FROM erp_roles").fetchall()
    permission_rows = connection.execute("SELECT id, permission_key FROM erp_permissions").fetchall()
    role_ids = {row[1]: row[0] for row in role_rows}
    permission_ids = {row[1]: row[0] for row in permission_rows}

    for role_key, definition in ROLE_DEFINITIONS.items():
        role_id = role_ids[role_key]
        approval_actions = definition.get("sensitive_approval_actions", set())
        for permission_key, permission_id in permission_ids.items():
            if "*" not in definition["permissions"] and permission_key not in definition["permissions"]:
                continue
            can_approve = "*" in approval_actions or permission_key in approval_actions
            connection.execute("""
                INSERT OR IGNORE INTO erp_role_permissions (
                    role_id, permission_id, can_approve_sensitive, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (role_id, permission_id, 1 if can_approve else 0, now, now))

    return {
        "roles": connection.execute("SELECT COUNT(*) FROM erp_roles").fetchone()[0],
        "permissions": connection.execute("SELECT COUNT(*) FROM erp_permissions").fetchone()[0],
        "role_permissions": connection.execute("SELECT COUNT(*) FROM erp_role_permissions").fetchone()[0],
        "users": connection.execute("SELECT COUNT(*) FROM erp_users").fetchone()[0],
        "store_memberships": connection.execute("SELECT COUNT(*) FROM erp_store_memberships").fetchone()[0],
    }


def verify_auth_schema(connection: sqlite3.Connection) -> None:
    tables = get_existing_tables(connection)
    missing_tables = sorted(AUTH_TABLES - tables)
    if missing_tables:
        raise RuntimeError(f"Missing auth tables: {missing_tables}")

    for table_name, expected_columns in AUTH_TABLE_COLUMNS.items():
        table_info = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        columns = {row[1] for row in table_info}
        missing_columns = sorted(expected_columns - columns)
        if missing_columns:
            raise RuntimeError(f"Missing {table_name} columns: {missing_columns}")

        forbidden_columns = sorted({column.lower() for column in columns} & FORBIDDEN_AUTH_COLUMNS)
        if forbidden_columns:
            raise RuntimeError(f"Forbidden auth columns in {table_name}: {forbidden_columns}")

        not_null = {row[1]: bool(row[3]) for row in table_info}
        missing_not_null = sorted(
            column
            for column in AUTH_NOT_NULL_COLUMNS[table_name]
            if not not_null.get(column)
        )
        if missing_not_null:
            raise RuntimeError(f"Missing {table_name} NOT NULL columns: {missing_not_null}")

    all_indexes = {}
    for table_name in AUTH_TABLES:
        for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall():
            all_indexes[row[1]] = (table_name, bool(row[2]))

    missing_indexes = sorted((set(AUTH_INDEXES) | set(AUTH_PARTIAL_INDEXES)) - set(all_indexes))
    if missing_indexes:
        raise RuntimeError(f"Missing auth indexes: {missing_indexes}")

    for index_name, (expected_table, expected_columns, expected_unique) in AUTH_INDEXES.items():
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

    for index_name, (expected_table, expected_columns, predicate) in AUTH_PARTIAL_INDEXES.items():
        observed_table, observed_unique = all_indexes[index_name]
        if observed_table != expected_table or not observed_unique:
            raise RuntimeError(f"Unexpected partial unique index {index_name}")
        observed_columns = [row[2] for row in connection.execute(f"PRAGMA index_info({index_name})")]
        if observed_columns != expected_columns:
            raise RuntimeError(f"Unexpected {index_name} columns: {observed_columns}")
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
        ).fetchone()[0]
        if predicate.upper() not in str(sql).upper():
            raise RuntimeError(f"Unexpected {index_name} predicate")

    role_keys = {
        row[0]
        for row in connection.execute("SELECT role_key FROM erp_roles WHERE status='active'").fetchall()
    }
    missing_roles = sorted(set(ROLE_DEFINITIONS) - role_keys)
    if missing_roles:
        raise RuntimeError(f"Missing system roles: {missing_roles}")

    permission_keys = {
        row[0]
        for row in connection.execute("SELECT permission_key FROM erp_permissions WHERE status='active'").fetchall()
    }
    required_permissions = {
        permission
        for role in ROLE_DEFINITIONS.values()
        for permission in role["permissions"]
        if permission != "*"
    }
    missing_permissions = sorted(required_permissions - permission_keys)
    if missing_permissions:
        raise RuntimeError(f"Missing permissions: {missing_permissions}")

    admin_product_batch_approval = connection.execute("""
        SELECT rp.can_approve_sensitive
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='admin' AND p.permission_key='products.batch_sync_write'
    """).fetchone()
    if not admin_product_batch_approval or int(admin_product_batch_approval[0]) != 1:
        raise RuntimeError("Admin product batch approval permission was not seeded")

    admin_order_batch_approval = connection.execute("""
        SELECT rp.can_approve_sensitive
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='admin' AND p.permission_key='orders.batch_sync_write'
    """).fetchone()
    if not admin_order_batch_approval or int(admin_order_batch_approval[0]) != 1:
        raise RuntimeError("Admin order batch approval permission was not seeded")

    admin_membership_assign_approval = connection.execute("""
        SELECT rp.can_approve_sensitive
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='admin' AND p.permission_key='store_membership.assign'
    """).fetchone()
    if not admin_membership_assign_approval or int(admin_membership_assign_approval[0]) != 1:
        raise RuntimeError("Admin store membership assignment approval permission was not seeded")

    admin_refresh_approval = connection.execute("""
        SELECT rp.can_approve_sensitive
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='admin' AND p.permission_key='orders.refresh_batch_write'
    """).fetchone()
    if not admin_refresh_approval or int(admin_refresh_approval[0]) != 1:
        raise RuntimeError("Admin refresh approval permission was not seeded")

    operator_product_batch_permission = connection.execute("""
        SELECT COUNT(*)
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='operator' AND p.permission_key='products.batch_sync_write'
    """).fetchone()[0]
    if operator_product_batch_permission != 0:
        raise RuntimeError("Operator should not receive products.batch_sync_write permission")

    operator_membership_assign_permission = connection.execute("""
        SELECT COUNT(*)
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='operator' AND p.permission_key='store_membership.assign'
    """).fetchone()[0]
    if operator_membership_assign_permission != 0:
        raise RuntimeError("Operator should not receive store_membership.assign permission")

    operator_refresh_permission = connection.execute("""
        SELECT COUNT(*)
        FROM erp_role_permissions rp
        JOIN erp_roles r ON r.id = rp.role_id
        JOIN erp_permissions p ON p.id = rp.permission_id
        WHERE r.role_key='operator' AND p.permission_key='orders.refresh_batch_write'
    """).fetchone()[0]
    if operator_refresh_permission != 0:
        raise RuntimeError("Operator should not receive orders.refresh_batch_write permission")


def upgrade(*, run_create_all: bool = True) -> dict[str, object]:
    import app.models  # noqa: F401

    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        if run_create_all:
            Base.metadata.create_all(bind=engine)
        return {"tables": [], "indexes": [], "seed_counts": {}}

    database_path = resolve_sqlite_path(settings.database_url)
    if run_create_all:
        Base.metadata.create_all(bind=engine)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        created_tables = create_auth_schema(connection)
        seed_counts = seed_system_roles_and_permissions(connection)
        connection.commit()
        verify_auth_schema(connection)
        return {
            "tables": created_tables,
            "indexes": sorted(set(AUTH_INDEXES) | set(AUTH_PARTIAL_INDEXES)),
            "seed_counts": seed_counts,
        }
    finally:
        connection.close()


def main() -> None:
    result = upgrade()
    if result["tables"]:
        print("auth schema upgraded: " + ", ".join(result["tables"]))
    else:
        print("auth schema already up to date")
    print("auth seed counts: " + str(result["seed_counts"]))


if __name__ == "__main__":
    main()
