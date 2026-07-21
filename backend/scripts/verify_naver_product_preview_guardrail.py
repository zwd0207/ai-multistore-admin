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
from app.services import api_credential_readiness_service, sync_service  # noqa: E402
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
            third_store = Store(name="Guardrail Naver Store 3", platform="naver")
            db.add_all([first_store, second_store, third_store])
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
            third_credential = ApiCredential(
                store_id=third_store.id,
                platform="naver",
                credential_name="Store 3 Credential",
                client_id="store-3-client",
                encrypted_secret_key=encrypt_value("store-3-secret"),
                extra_config={"api_base": "https://api.commerce.naver.com/external"},
                status="active",
            )
            db.add_all([first_credential, second_credential, third_credential])
            db.commit()
            db.refresh(first_store)
            db.refresh(first_credential)
            db.refresh(second_credential)
            db.refresh(third_credential)

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

            original_smoke_test = api_credential_readiness_service.run_api_credential_smoke_test
            smoke_calls = []

            def fake_seller_channel_smoke_test(**kwargs):
                smoke_calls.append(kwargs)
                assert kwargs["platform"] == "naver"
                assert kwargs["store_id"] == third_store.id
                assert kwargs["credential_id"] == third_credential.id
                assert kwargs["capability_scope"] == "seller_channels"
                assert kwargs["persist_channel_no"] is True
                api_credential_readiness_service._persist_naver_channel_no(
                    kwargs["db"],
                    {"store_id": third_store.id, "credential_id": third_credential.id},
                    "auto-detected-channel",
                )
                kwargs["db"].commit()
                return {
                    "results": [{
                        "channel_no_observed": True,
                        "channel_no_persisted": True,
                        "multiple_channels_observed": False,
                        "error_code": None,
                    }],
                }

            api_credential_readiness_service.run_api_credential_smoke_test = fake_seller_channel_smoke_test
            try:
                sync_service._ensure_naver_manual_sync_channel_no(db, first_store.id)
                assert smoke_calls == []
                sync_service._ensure_naver_manual_sync_channel_no(db, third_store.id)
                assert len(smoke_calls) == 1
                db.refresh(third_credential)
                assert third_credential.extra_config["channel_no"] == "auto-detected-channel"
                assert third_credential.auth_status == "test_passed"
            finally:
                api_credential_readiness_service.run_api_credential_smoke_test = original_smoke_test

            original_channel_preflight = sync_service._ensure_naver_manual_sync_channel_no
            original_product_sync = sync_service._manual_sync_naver_products
            original_order_sync = sync_service._manual_sync_naver_orders
            original_inquiry_sync = sync_service._manual_sync_customer_inquiries
            call_order = []

            def fake_channel_preflight(_db, store_id):
                assert store_id == first_store.id
                call_order.append("channel_preflight")

            def fake_manual_item(resource):
                expected_prefixes = {
                    "products": ["channel_preflight"],
                    "orders": ["channel_preflight", "products"],
                    "customer_inquiries": ["channel_preflight", "products", "orders"],
                }
                assert call_order == expected_prefixes[resource]
                call_order.append(resource)
                return sync_service._manual_batch_item(
                    platform="naver",
                    resource=resource,
                    status="success",
                    message=f"{resource} synced",
                )

            sync_service._ensure_naver_manual_sync_channel_no = fake_channel_preflight
            sync_service._manual_sync_naver_products = lambda _db, _store_id: fake_manual_item("products")
            sync_service._manual_sync_naver_orders = lambda _db, _store_id: fake_manual_item("orders")
            sync_service._manual_sync_customer_inquiries = (
                lambda _db, _store_id, _platform: fake_manual_item("customer_inquiries")
            )
            try:
                manual_result = sync_service.manual_batch_sync(
                    db,
                    store_id=first_store.id,
                    platforms=["naver"],
                )
                assert manual_result["status"] == "success"
                assert [item["resource"] for item in manual_result["items"]] == [
                    "products",
                    "orders",
                    "customer_inquiries",
                ]
                assert manual_result["platform_write"] is False
            finally:
                sync_service._ensure_naver_manual_sync_channel_no = original_channel_preflight
                sync_service._manual_sync_naver_products = original_product_sync
                sync_service._manual_sync_naver_orders = original_order_sync
                sync_service._manual_sync_customer_inquiries = original_inquiry_sync

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
    print("missing single seller channel: auto-detected and persisted")
    print("manual batch sync: channel preflight runs before Naver reads")
    print("REAL_API_WRITE_ENABLED=true: blocked")
