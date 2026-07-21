from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.core.timezone import get_utc_now
from app.database import Base
from app.models.api_credential import ApiCredential
from app.models.auth import ErpSession, ErpUser
from app.models.operation_audit_log import OperationAuditLog
from app.models.order import Order
from app.models.store import Store
from app.models.tenant import Tenant, TenantInvitation
from app.services.session_service import generate_totp
from app.services.tenant_auth_service import accept_invitation, complete_mfa_enrollment
from scripts.migrate_sqlite_to_postgres import CONFIRMATION, migrate


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    now = get_utc_now()
    with Session(engine) as db:
        store = Store(id=11, tenant_id=None, name="Production Store", platform="naver", status="active")
        db.add(store)
        db.flush()
        db.add_all((
            ApiCredential(
                id=17,
                store_id=store.id,
                platform="naver",
                credential_name="Synthetic Naver API",
                client_id="masked-client-id",
                encrypted_secret_key="synthetic-encrypted-secret",
                status="active",
            ),
            Order(
                id=19,
                store_id=store.id,
                platform="naver",
                external_order_id="synthetic-order-1",
                product_name="Synthetic product",
                quantity=1,
                order_amount=100,
                currency="KRW",
                order_status="paid",
                ordered_at=now,
            ),
        ))
        db.commit()
    engine.dispose()


def _schema_url(base_url: str, schema: str) -> str:
    url = make_url(base_url)
    query = dict(url.query)
    query["options"] = f"-csearch_path={schema}"
    return url.update_query_dict(query).render_as_string(hide_password=False)


@contextmanager
def _bootstrap_settings(target_url: str, encryption_key: str):
    values = {
        "APP_ENV": "test",
        "DATABASE_URL": target_url,
        "CREDENTIAL_ENCRYPTION_KEY": encryption_key,
        "SESSION_TOKEN_PEPPER": "t22-bootstrap-session-pepper-longer-than-32-characters",
        "PUBLIC_APP_URL": "https://aiglxt.test",
        "LIFECYCLE_SCHEDULERS_ENABLED": "false",
    }
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    get_settings.cache_clear()
    try:
        yield values
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()


def main() -> None:
    base_url = os.environ.get("T22_TEST_POSTGRES_URL", "").strip()
    if not base_url:
        print("verify_t22_postgres_migration: skipped (T22_TEST_POSTGRES_URL not configured)")
        return
    schema = "t22_" + uuid.uuid4().hex[:16]
    admin_engine = create_engine(base_url, future=True)
    source_path = Path(tempfile.gettempdir()) / f"codex1-t22-source-{uuid.uuid4().hex}.db"
    secrets_path = Path(tempfile.gettempdir()) / f"codex1-t22-bootstrap-{uuid.uuid4().hex}.json"
    duplicate_secrets_path = Path(tempfile.gettempdir()) / f"codex1-t22-bootstrap-{uuid.uuid4().hex}.json"
    target_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        target_url = _schema_url(base_url, schema)
        previous_database_url = os.environ.get("DATABASE_URL")
        previous_app_env = os.environ.get("APP_ENV")
        os.environ["DATABASE_URL"] = target_url
        os.environ["APP_ENV"] = "test"
        get_settings.cache_clear()
        try:
            config = Config(str(BACKEND_DIR / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
            command.upgrade(config, "head")
        finally:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url
            if previous_app_env is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = previous_app_env
            get_settings.cache_clear()

        _fixture(source_path)
        source_hash = _file_sha256(source_path)
        target_engine = create_engine(target_url, future=True)
        dry_run = migrate(
            source_path=source_path,
            target_engine=target_engine,
            tenant_name="Initial production tenant",
            platform_admin_user_id=None,
            execute=False,
            confirmation=None,
        )
        assert dry_run["status"] == "migration_ready"
        assert dry_run["skipped_counts"] == {"erp_sessions": 0}
        assert dry_run["platform_admin_bootstrap_required"] is True

        result = migrate(
            source_path=source_path,
            target_engine=target_engine,
            tenant_name="Initial production tenant",
            platform_admin_user_id=None,
            execute=True,
            confirmation=CONFIRMATION,
            expected_source_sha256=source_hash,
        )
        assert result["status"] == "migration_completed"
        assert result["source_unchanged"] is True
        assert _file_sha256(source_path) == source_hash
        with Session(target_engine) as db:
            tenant = db.get(Tenant, 1)
            store = db.get(Store, 11)
            assert tenant is not None and store is not None
            assert tenant.id == 1
            assert store.tenant_id == tenant.id
            assert db.scalar(select(func.count()).select_from(ErpUser)) == 0
            assert db.scalar(select(func.count()).select_from(Order)) == 1
            assert db.scalar(select(func.count()).select_from(ErpSession)) == 0
            secret = db.scalar(select(ApiCredential.encrypted_secret_key).where(ApiCredential.id == 17))
            assert secret == "synthetic-encrypted-secret"

        encryption_key = Fernet.generate_key().decode("ascii")
        with _bootstrap_settings(target_url, encryption_key) as runtime_values:
            bootstrap_env = os.environ.copy()
            bootstrap_env.update(runtime_values)
            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(BACKEND_DIR / "scripts" / "bootstrap_platform_admin.py"),
                    "--tenant-id", "1",
                    "--email", "initial-admin@example.com",
                    "--display-name", "Initial platform administrator",
                    "--secrets-output", str(secrets_path),
                ],
                cwd=BACKEND_DIR,
                env=bootstrap_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            assert bootstrap.returncode == 0, bootstrap.stderr
            bootstrap_status = json.loads(bootstrap.stdout)
            bootstrap_secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
            invitation_token = bootstrap_secrets["invitation_token"]
            assert bootstrap_status["status"] == "platform_admin_invitation_created"
            assert bootstrap_status["secrets_output"] == str(secrets_path.resolve())
            assert invitation_token not in bootstrap.stdout
            assert bootstrap_secrets["platform_role"] == "platform_admin"
            assert bootstrap_secrets["target_tenant_id"] == 1

            with Session(target_engine) as db:
                invitation = db.scalar(select(TenantInvitation).where(
                    TenantInvitation.invited_platform_role == "platform_admin",
                ))
                audit = db.scalar(select(OperationAuditLog).where(
                    OperationAuditLog.action == "platform_admin_invitation_created",
                ))
                assert invitation is not None and invitation.invited_by_user_id is None
                assert invitation.target_tenant_id == 1
                assert audit is not None
                assert audit.secrets_saved is False and audit.raw_response_saved is False
                assert invitation_token not in json.dumps({
                    "actor_id": audit.actor_id,
                    "notes": audit.notes,
                    "safety_flags": audit.safety_flags,
                }, sort_keys=True)

            with Session(target_engine) as db:
                enrollment = accept_invitation(
                    db,
                    token=invitation_token,
                    password="BootstrapPassword2026",
                )
            assert enrollment["status"] == "mfa_enrollment_required"
            assert enrollment["tenant"]["id"] == 1
            with Session(target_engine) as db:
                activated = complete_mfa_enrollment(
                    db,
                    enrollment_token=enrollment["enrollment_token"],
                    code=generate_totp(enrollment["mfa_secret"]),
                )
            assert activated["status"] == "account_active"
            assert activated["tenant_id"] == 1
            assert len(activated["recovery_codes"]) == 10

            duplicate = subprocess.run(
                [
                    sys.executable,
                    str(BACKEND_DIR / "scripts" / "bootstrap_platform_admin.py"),
                    "--tenant-id", "1",
                    "--email", "second-admin@example.com",
                    "--display-name", "Second platform administrator",
                    "--secrets-output", str(duplicate_secrets_path),
                ],
                cwd=BACKEND_DIR,
                env=bootstrap_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            assert duplicate.returncode != 0
            assert "platform_admin_already_exists" in duplicate.stderr
            assert not duplicate_secrets_path.exists()

        with Session(target_engine) as db:
            platform_admin = db.scalar(select(ErpUser).where(ErpUser.platform_role == "platform_admin"))
            assert platform_admin is not None
            assert platform_admin.tenant_id == 1
            assert platform_admin.status == "active"
            assert db.scalar(select(func.count()).select_from(Tenant)) == 1
        try:
            migrate(
                source_path=source_path,
                target_engine=target_engine,
                tenant_name="Initial production tenant",
                platform_admin_user_id=None,
                execute=False,
                confirmation=None,
            )
        except RuntimeError as exc:
            assert "not empty" in str(exc)
        else:
            raise AssertionError("migration replay must reject a non-empty target")
        print("verify_t22_postgres_migration: ok")
    finally:
        if target_engine is not None:
            target_engine.dispose()
        source_path.unlink(missing_ok=True)
        secrets_path.unlink(missing_ok=True)
        duplicate_secrets_path.unlink(missing_ok=True)
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


if __name__ == "__main__":
    main()
