import os
import sys
import tempfile
import uuid
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

VERIFY_DB_PATH = Path(tempfile.gettempdir()) / (
    f"codex1-product-guardrail-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
)
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB_PATH.as_posix()}"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
os.environ["REAL_API_TEST_ENABLED"] = "true"
os.environ["REAL_API_WRITE_ENABLED"] = "false"

import app.models  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.core.exceptions import ApiError  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.api_credential import ApiCredential  # noqa: E402
from app.models.store import Store  # noqa: E402
from app.services import sync_service  # noqa: E402
from app.services.encryption import encrypt_value  # noqa: E402


def expect_api_error(error_code: str, callback) -> None:
    try:
        callback()
    except ApiError as exc:
        assert exc.error_code == error_code, exc.error_code
    else:
        raise AssertionError(f"Expected ApiError with error_code={error_code}")


def verify_guardrail() -> None:
    Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            first_store = Store(name="Guardrail Naver Store 1", platform="naver")
            second_store = Store(name="Guardrail Naver Store 2", platform="naver")
            db.add_all([first_store, second_store])
            db.flush()

            first_credential = ApiCredential(
                store_id=first_store.id,
                platform="naver",
                credential_name="Store 1 Credential",
                client_id="store-1-client",
                encrypted_secret_key=encrypt_value("store-1-secret"),
                extra_config={"channel_no": "store-1-channel"},
                status="active",
            )
            second_credential = ApiCredential(
                store_id=second_store.id,
                platform="naver",
                credential_name="Store 2 Credential",
                client_id="store-2-client",
                encrypted_secret_key=encrypt_value("store-2-secret"),
                extra_config={"channel_no": "store-2-channel"},
                status="active",
            )
            db.add_all([first_credential, second_credential])
            db.commit()
            db.refresh(first_store)
            db.refresh(first_credential)
            db.refresh(second_credential)

            assert (first_store.id, first_credential.id) != (8, 7)
            selected = sync_service._ensure_naver_product_preview_credential(
                db,
                store_id=first_store.id,
                credential_id=first_credential.id,
            )
            assert selected.id == first_credential.id

            sync_service._ensure_naver_product_real_preview_allowed(
                store_id=first_store.id,
                credential_id=first_credential.id,
                page=1,
                size=5,
                keyword=None,
                seller_product_id=None,
                field_observation={"channel_no_configured": True},
            )

            expect_api_error(
                "credential_not_ready",
                lambda: sync_service._ensure_naver_product_preview_credential(
                    db,
                    store_id=first_store.id,
                    credential_id=second_credential.id,
                ),
            )

            settings = get_settings()
            settings.real_api_write_enabled = True
            try:
                expect_api_error(
                    "guardrail_blocked",
                    lambda: sync_service._ensure_naver_product_real_preview_allowed(
                        store_id=first_store.id,
                        credential_id=first_credential.id,
                        page=1,
                        size=5,
                        keyword=None,
                        seller_product_id=None,
                        field_observation={"channel_no_configured": True},
                    ),
                )
            finally:
                settings.real_api_write_enabled = False
    finally:
        engine.dispose()
        VERIFY_DB_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    verify_guardrail()
    print("Naver product preview guardrail verification ok")
    print("valid store-bound credential with arbitrary IDs: allowed")
    print("cross-store credential: blocked")
    print("REAL_API_WRITE_ENABLED=true: blocked")
