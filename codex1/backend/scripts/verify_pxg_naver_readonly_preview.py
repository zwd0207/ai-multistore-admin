import json
import os
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


TEMP_DB = Path(tempfile.gettempdir()) / "verify-pxg-naver-readonly.db"
if TEMP_DB.exists():
    TEMP_DB.unlink()
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{TEMP_DB.as_posix()}",
    "CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    "SESSION_TOKEN_PEPPER": "pxg-readonly-test-session-pepper-32-characters",
    "OPERATOR_TRIAL_ENABLED": "true",
    "OPERATOR_TRIAL_ARTIFICIAL_DATA_ONLY": "false",
    "OPERATOR_TRIAL_REAL_READ_ENABLED": "true",
    "REAL_API_TEST_ENABLED": "true",
    "REAL_API_WRITE_ENABLED": "false",
})
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.services import api_credential_readiness_service, sync_service
from app.services.encryption import encrypt_value
from app.services.pxg_naver_readonly_service import preview_pxg_naver_real_reads


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        store = Store(id=37, name="pxg球包店", platform="Naver", status="active")
        db.add(store)
        db.flush()
        db.add(ApiCredential(
            store_id=store.id,
            platform="naver",
            credential_name="encrypted readonly test",
            client_id="masked-client",
            encrypted_secret_key=encrypt_value("never-output-this-secret"),
            extra_config={"api_base": "https://example.invalid", "channel_no": "masked-channel"},
            auth_status="configured",
            status="active",
        ))
        db.commit()

        originals = {
            "products": sync_service.preview_naver_products,
            "orders": sync_service.preview_naver_orders,
            "token": api_credential_readiness_service._request_naver_token_from_context,
            "inquiries": sync_service._request_naver_customer_inquiries,
        }
        sync_service.preview_naver_products = lambda *_args, **_kwargs: {
            "preview_status": "success", "sample_ids": ["hash-1", "hash-2"], "local_sync_result": {"products_written": False},
        }
        sync_service.preview_naver_orders = lambda *_args, **_kwargs: {
            "preview_status": "success", "sample_ids": ["hash-a", "hash-b", "hash-c"],
            "field_observation": {"detail_called": True, "detail_limit": 3, "privacy_fields_redacted": True},
            "local_sync_result": {"orders_written": False},
        }
        api_credential_readiness_service._request_naver_token_from_context = lambda _context: ("in-memory-test-token", 200)
        sync_service._request_naver_customer_inquiries = lambda **_kwargs: {
            "success": True,
            "payload": {"content": [{"customerName": "must-not-return"}, {"customerName": "must-not-return"}]},
        }
        try:
            result = preview_pxg_naver_real_reads(db, get_settings())
        finally:
            sync_service.preview_naver_products = originals["products"]
            sync_service.preview_naver_orders = originals["orders"]
            api_credential_readiness_service._request_naver_token_from_context = originals["token"]
            sync_service._request_naver_customer_inquiries = originals["inquiries"]

        assert result["store"] == {"name": "pxg球包店", "platform": "Naver"}
        assert result["limits"]["max_real_orders"] == 3
        assert result["counts"] == {"products": 2, "orders": 3, "customer_inquiries": 2, "logistics_order_details": 3}
        assert result["state_unchanged"] is True and result["writes"]["platform_write"] is False
        serialized = json.dumps(result, ensure_ascii=False).lower()
        for forbidden in ("must-not-return", "never-output-this-secret", "in-memory-test-token", "receiver_phone", "receiver_address"):
            assert forbidden not in serialized
    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_readonly_preview: ok")


if __name__ == "__main__":
    main()
