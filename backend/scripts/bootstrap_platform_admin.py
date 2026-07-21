from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.core.exceptions import ApiError
from app.services.schema_version_service import verify_production_schema
from app.services.tenant_auth_service import create_platform_admin_bootstrap_invitation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the one-time initial platform administrator invitation.")
    parser.add_argument("--tenant-id", required=True, type=int)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--secrets-output", required=True, type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    settings = get_settings()
    if not settings.database_url.startswith(("postgresql+psycopg://", "postgresql://")):
        raise SystemExit("platform administrator bootstrap requires PostgreSQL")
    try:
        email = validate_email(args.email, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as exc:
        raise SystemExit("bootstrap email is invalid") from exc
    display_name = args.display_name.strip()
    if not display_name:
        raise SystemExit("display name is required")
    output_path = args.secrets_output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SystemExit("secrets output already exists; refusing to overwrite") from exc

    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    committed = False
    try:
        verify_production_schema(engine)
        with Session(engine) as db:
            result = create_platform_admin_bootstrap_invitation(
                db,
                email=email,
                display_name=display_name,
                tenant_id=args.tenant_id,
                commit=False,
            )
            secret_payload = {
                "invitation_url": result["invitation_url"],
                "invitation_token": result["invitation_token"],
                "expires_at": result["expires_at"],
                "email": result["email"],
                "target_tenant_id": result["target_tenant_id"],
                "platform_role": result["platform_role"],
            }
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                json.dump(secret_payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            db.commit()
            committed = True
        print(json.dumps({
            "status": "platform_admin_invitation_created",
            "invitation_id": result["id"],
            "email": result["email"],
            "expires_at": result["expires_at"],
            "secrets_output": str(output_path),
        }, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        if descriptor >= 0:
            os.close(descriptor)
        if not committed:
            output_path.unlink(missing_ok=True)
        if isinstance(exc, ApiError):
            raise SystemExit(f"platform administrator bootstrap rejected: {exc.error_code}") from None
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
