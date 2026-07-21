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


def _customer_inquiry_result_for_request_error(db):
    originals = {
        "products": sync_service.preview_naver_products,
        "orders": sync_service.preview_naver_orders,
        "token": api_credential_readiness_service._request_naver_token_from_context,
        "inquiries": sync_service._request_naver_customer_inquiries,
    }
    sync_service.preview_naver_products = lambda *_args, **_kwargs: {
        "preview_status": "success", "sample_ids": ["hash-1"], "local_sync_result": {"products_written": False},
    }
    sync_service.preview_naver_orders = lambda *_args, **_kwargs: {
        "preview_status": "success", "sample_ids": ["hash-a"],
        "field_observation": {"detail_called": True, "detail_limit": 1, "privacy_fields_redacted": True},
        "local_sync_result": {"orders_written": False},
    }
    api_credential_readiness_service._request_naver_token_from_context = lambda _context: ("in-memory-test-token", 200)
    sync_service._request_naver_customer_inquiries = lambda **_kwargs: {
        "success": False,
        "http_status": 400,
        "error_code": "raw-error-must-not-return",
        "safe_error": {
            "platform_error_code": "INVALID_DATE_PARAMETER",
            "platform_error_fields": ["startSearchDate", "endSearchDate", "customerName"],
        },
    }
    try:
        return preview_pxg_naver_real_reads(db, get_settings())
    finally:
        sync_service.preview_naver_products = originals["products"]
        sync_service.preview_naver_orders = originals["orders"]
        api_credential_readiness_service._request_naver_token_from_context = originals["token"]
        sync_service._request_naver_customer_inquiries = originals["inquiries"]


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
        assert result["limits"] == {"max_real_orders": 3, "order_window_days": 7, "customer_inquiry_window_days": 1}
        assert result["counts"] == {"products": 2, "orders": 3, "customer_inquiries": 2, "logistics_order_details": 3}
        assert result["state_unchanged"] is True and result["writes"]["platform_write"] is False
        serialized = json.dumps(result, ensure_ascii=False).lower()
        for forbidden in ("must-not-return", "never-output-this-secret", "in-memory-test-token", "receiver_phone", "receiver_address"):
            assert forbidden not in serialized

        order_windows = []
        def empty_order_preview(*_args, **kwargs):
            order_windows.append((kwargs["end_datetime"] - kwargs["start_datetime"]).days)
            return {
                "preview_status": "success_empty",
                "sample_ids": [],
                "field_observation": {"detail_called": False, "detail_limit": 0, "privacy_fields_redacted": True},
                "local_sync_result": {"orders_written": False},
            }
        sync_service.preview_naver_orders = empty_order_preview
        sync_service.preview_naver_products = lambda *_args, **_kwargs: {
            "preview_status": "success", "sample_ids": ["hash-1"], "local_sync_result": {"products_written": False},
        }
        api_credential_readiness_service._request_naver_token_from_context = lambda _context: ("in-memory-test-token", 200)
        sync_service._request_naver_customer_inquiries = lambda **_kwargs: {
            "success": False,
            "http_status": 403,
            "error_code": "secret-platform-message-must-not-return",
            "safe_error": {"platform_error_code": "NOT_AUTHORIZED", "platform_error_fields": ["startSearchDate"]},
            "diagnostics": {"customerContent": "private-content-must-not-return"},
        }
        try:
            unavailable_result = preview_pxg_naver_real_reads(db, get_settings())
        finally:
            sync_service.preview_naver_products = originals["products"]
            sync_service.preview_naver_orders = originals["orders"]
            api_credential_readiness_service._request_naver_token_from_context = originals["token"]
            sync_service._request_naver_customer_inquiries = originals["inquiries"]
        assert order_windows == [7, 30]
        assert unavailable_result["status"] == "completed"
        assert unavailable_result["limits"]["order_window_days"] == 30
        assert unavailable_result["reads"]["orders"] == "current_no_orders"
        assert unavailable_result["reads"]["logistics"] == "not_required"
        assert unavailable_result["customer_inquiry_result"] == {
            "status": "platform_not_authorized_or_unavailable",
            "endpoint": "/v1/pay-user/inquiries",
            "http_status": 403,
            "platform_error_category": "platform_not_authorized",
            "platform_error_code": "NOT_AUTHORIZED",
            "platform_error_fields": ["startSearchDate"],
        }
        unavailable_serialized = json.dumps(unavailable_result, ensure_ascii=False).lower()
        assert "secret-platform-message" not in unavailable_serialized
        assert "private-content" not in unavailable_serialized

        request_error_result = _customer_inquiry_result_for_request_error(db)
        assert request_error_result["status"] == "blocked"
        assert request_error_result["customer_inquiry_result"] == {
            "status": "blocked_request_error",
            "endpoint": "/v1/pay-user/inquiries",
            "http_status": 400,
            "platform_error_category": "request_error",
            "platform_error_code": "INVALID_DATE_PARAMETER",
            "platform_error_fields": ["startSearchDate", "endSearchDate"],
        }
    engine.dispose()
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    print("verify_pxg_naver_readonly_preview: ok")


if __name__ == "__main__":
    main()
