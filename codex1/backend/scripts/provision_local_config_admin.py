from __future__ import annotations

import base64
import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
HANDOFF_PATH = BACKEND_DIR / ".local-trial" / "config-admin-credentials.txt"
LOGIN_IDENTIFIER = "pxg-config-admin@local.test"
ROLE_KEY = "pxg_connection_config_admin"
PERMISSION_KEYS = {
    "dashboard.read",
    "products.read",
    "orders.read",
    "orders.preview",
    "recipient_pii.view",
    "recipient_pii.export",
    "shipping.batch.manage",
    "platform.sync",
    "customer.inquiries.content.read",
    "platform.readonly.persist",
    "store.manage",
    "credentials.manage",
}


def _restrict_acl(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)
        return
    user = os.environ.get("USERNAME")
    if user:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _credentials() -> dict[str, str]:
    if HANDOFF_PATH.exists():
        values = dict(
            line.split("=", 1)
            for line in HANDOFF_PATH.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        if {"login_identifier", "password", "totp_secret"} <= values.keys():
            return values
    values = {
        "login_identifier": LOGIN_IDENTIFIER,
        "password": secrets.token_urlsafe(24),
        "totp_secret": base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("="),
    }
    HANDOFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    HANDOFF_PATH.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    _restrict_acl(HANDOFF_PATH)
    return values


def main() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from sqlalchemy import delete, select

    from app.core.timezone import get_utc_now
    from app.database import SessionLocal, init_db
    from app.models.auth import (
        ErpPermission,
        ErpRole,
        ErpRolePermission,
        ErpStoreMembership,
        ErpUser,
        ErpUserSecurity,
    )
    from app.services.encryption import encrypt_value
    from app.services.operator_trial_service import resolve_trial_store
    from app.services.session_service import hash_login_identifier, hash_password

    values = _credentials()
    init_db()
    with SessionLocal() as db:
        store = resolve_trial_store(db)

        permissions = []
        for key in sorted(PERMISSION_KEYS):
            permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == key))
            if permission is None:
                permission = ErpPermission(
                    permission_key=key,
                    permission_group="local_configuration",
                    permission_label_zh=key,
                    sensitive_action=key in {"store.manage", "credentials.manage"},
                    status="active",
                )
                db.add(permission)
                db.flush()
            permissions.append(permission)

        role = db.scalar(select(ErpRole).where(ErpRole.role_key == ROLE_KEY))
        if role is None:
            role = ErpRole(
                role_key=ROLE_KEY,
                role_label_zh="PXG connection configuration admin",
                role_label_en="PXG connection configuration admin",
                system_role=False,
                status="active",
            )
            db.add(role)
            db.flush()
        role.status = "active"
        db.execute(delete(ErpRolePermission).where(ErpRolePermission.role_id == role.id))
        for permission in permissions:
            db.add(ErpRolePermission(
                role_id=role.id,
                permission_id=permission.id,
                can_approve_sensitive=permission.permission_key in {"store.manage", "credentials.manage"},
            ))

        login_hash = hash_login_identifier(values["login_identifier"])
        user = db.scalar(select(ErpUser).where(ErpUser.login_identifier_hash == login_hash))
        if user is None:
            user = ErpUser(
                user_key_hash=hashlib.sha256(f"config:{login_hash}".encode()).hexdigest(),
                display_name="PXG connection configuration admin",
                login_identifier_hash=login_hash,
                login_identifier_masked="pxg-config-admin",
                status="active",
                auth_provider="password",
            )
            db.add(user)
            db.flush()
        user.status = "active"
        user.auth_provider = "password"

        security = db.get(ErpUserSecurity, user.id)
        if security is None:
            security = ErpUserSecurity(user_id=user.id)
            db.add(security)
        security.password_hash = hash_password(values["password"])
        security.mfa_type = "totp"
        security.mfa_secret_encrypted = encrypt_value(values["totp_secret"])
        security.mfa_enabled_at = get_utc_now()
        security.password_changed_at = get_utc_now()
        security.session_version = (security.session_version or 0) + 1
        security.authz_version = (security.authz_version or 0) + 1

        # Reconcile only the PXG assignment. Local fixture assignments for this
        # same stable account must survive a normal config-admin reprovision.
        db.execute(delete(ErpStoreMembership).where(
            ErpStoreMembership.user_id == user.id,
            ErpStoreMembership.store_id == store.id,
        ))
        db.add(ErpStoreMembership(
            user_id=user.id,
            store_id=store.id,
            role_id=role.id,
            scope_type="assigned",
            membership_status="active",
        ))
        db.commit()
    print("PXG local configuration administrator provisioned")


if __name__ == "__main__":
    main()
