from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for path in (BACKEND_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

db_file = Path(tempfile.gettempdir()) / "t24-one-time-inquiry-import-verification.db"
db_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = ENCRYPTION_KEY
os.environ["T24_ONE_TIME_INQUIRY_IMPORT_APPROVAL"] = "owner-approved-one-time-30-day-import"
os.environ["T24_ONE_TIME_INQUIRY_IMPORT_STORE_ID"] = "1"
for flag in (
    "REAL_API_TEST_ENABLED",
    "REAL_API_WRITE_ENABLED",
    "AUTOMATIC_READ_SYNC_ENABLED",
    "NAVER_READONLY_INQUIRY_REAL_READ_ENABLED",
    "PLATFORM_PRODUCT_WRITE_ENABLED",
    "PLATFORM_INVENTORY_WRITE_ENABLED",
    "PLATFORM_ORDER_WRITE_ENABLED",
    "CUSTOMER_PLATFORM_WRITE_ENABLED",
    "SHIPPING_PLATFORM_WRITE_ENABLED",
    "PXG_NAVER_SHIPPING_PILOT_ENABLED",
    "AI_AUTOMATIC_OPERATIONS_ENABLED",
):
    os.environ[flag] = "false"

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ApiError
from app.database import Base
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.customer_inquiry import CustomerInquiry
from app.models.pxg_naver_readonly import (
    PxgNaverReadonlyCleanupStatus,
    PxgNaverReadonlyCustomerInquiry,
)
from app.models.store import Store
from app.models.sync_log import SyncLog
from app.services.encryption import encrypt_value
from app.services import naver_readonly_inquiry_service
from app.services.customer_inquiry_service import _is_superseded_naver_legacy
from app.services.naver_inquiry_identity import naver_inquiry_external_id_hash
from run_t24_controlled_naver_inquiry_probe import ProbeBlocked
from run_t24_one_time_naver_inquiry_import import IMPORT_SYNC_TYPE, run_import


def main() -> None:
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)
    store_name = "T24 Import Store"
    name_hash = hashlib.sha256(store_name.encode("utf-8")).hexdigest()
    try:
        with Session(engine) as db:
            store = Store(id=1, name=store_name, platform="naver", status="active")
            credential = ApiCredential(
                id=1,
                store_id=1,
                platform="naver",
                credential_name="T24 import",
                client_id="configured-client",
                encrypted_secret_key="encrypted-secret",
                extra_config={"api_base": "https://api.test/external"},
                status="active",
            )
            capability = ApiCapabilityCheck(
                platform="naver",
                capability_key="naver.customer_inquiry_read",
                capability_name="Naver customer inquiry read",
                api_category="customer_service",
                endpoint_path="/v1/pay-user/inquiries",
                method="GET",
                ordinary_store_supported="yes",
                test_status="tested_success",
                test_mode="real_readonly",
                data_usefulness="high",
                sales_source_type="not_applicable",
            )
            db.add_all([store, credential, capability])
            db.flush()
            db.add(ApiCapabilityTestResult(
                store_id=1,
                credential_id=1,
                capability_id=capability.id,
                test_mode="real_readonly",
                test_status="tested_success",
                http_status=200,
                permission_result="order_seller_confirmed",
                tested_at=now,
            ))
            db.add(CustomerInquiry(
                store_id=1,
                platform="naver",
                external_inquiry_id="legacy-answered",
                inquiry_type="delivery",
                customer_name="Legacy Customer",
                title="Private legacy title",
                content="When will this ship?",
                status="answered",
                received_at=now,
                answered_at=now + timedelta(minutes=5),
                raw_data={
                    "source_type": "naver_customer_inquiry_real_sync",
                    "answer_content": "It ships today.",
                    "nested": {"inquiryContent": "must be removed"},
                    "order_id": "ORDER-1",
                },
            ))
            db.add(PxgNaverReadonlyCleanupStatus(
                store_id=1,
                platform="naver",
                status="failed",
                last_run_at=now,
                last_failure_at=now,
                last_failure_code="readonly_retention_cleanup_disabled",
            ))
            db.commit()

            runner_calls = 0

            def fake_refresh(session, *, store_id, actor_id, settings):
                nonlocal runner_calls
                runner_calls += 1
                assert store_id == 1 and len(actor_id) == 64
                assert settings.naver_readonly_inquiry_real_read_enabled is True
                assert settings.naver_readonly_inquiry_approved_store_id == 1
                assert settings.automatic_read_sync_enabled is False
                session.add_all([
                    PxgNaverReadonlyCustomerInquiry(
                        store_id=1,
                        platform="naver",
                        external_inquiry_id_hash=naver_inquiry_external_id_hash("legacy-answered"),
                        inquiry_type="delivery",
                        status="answered",
                        customer_display_masked="L*************r",
                        encrypted_customer_name=encrypt_value("Legacy Customer"),
                        customer_name_hash=hashlib.sha256(b"Legacy Customer").hexdigest(),
                        customer_name_length=len("Legacy Customer"),
                        content_available=True,
                        encrypted_content=encrypt_value("When will this ship?"),
                        encrypted_title=encrypt_value("Private legacy title"),
                        content_hash=hashlib.sha256(b"When will this ship?").hexdigest(),
                        content_length=len("When will this ship?"),
                        encrypted_answer_content=encrypt_value("It ships today."),
                        answer_content_hash=hashlib.sha256(b"It ships today.").hexdigest(),
                        answer_content_length=len("It ships today."),
                        received_at=now,
                        answered_at=now + timedelta(minutes=5),
                        source_updated_at=now + timedelta(minutes=5),
                        source_observed_at=now,
                        expires_at=now + timedelta(days=30),
                    ),
                    PxgNaverReadonlyCustomerInquiry(
                        store_id=1,
                        platform="naver",
                        external_inquiry_id_hash="d" * 64,
                        inquiry_type="product",
                        status="open",
                        content_available=True,
                        encrypted_content="encrypted-customer-two",
                        content_hash="e" * 64,
                        content_length=20,
                        answer_content_length=0,
                        received_at=now,
                        source_updated_at=now,
                        source_observed_at=now,
                        expires_at=now + timedelta(days=30),
                    ),
                ])
                session.flush()
                return {
                    "created_count": 2,
                    "updated_count": 0,
                    "skipped_count": 0,
                    "pages_read": 1,
                    "raw_response_saved": False,
                    "platform_write": False,
                }

            settings = Settings(
                app_env="production",
                credential_encryption_key=ENCRYPTION_KEY,
                pxg_naver_local_read_retention_cleanup_enabled=True,
            )
            result = run_import(
                db,
                store_id=1,
                expected_store_name_sha256=name_hash,
                settings=settings,
                now=now,
                refresh_runner=fake_refresh,
            )
            assert runner_calls == 1
            assert result["classification_counts"] == {"all": 2, "answered": 1, "unanswered": 1}
            assert result["cleanup_recovery_status"] == "completed"
            assert result["legacy_plaintext_sanitized_count"] == 1
            assert result["automatic_sync_enabled"] is False and result["reply_enabled"] is False
            marker = db.scalar(select(SyncLog).where(SyncLog.sync_type == IMPORT_SYNC_TYPE))
            assert marker.status == "success" and marker.raw_summary["platform_write"] is False
            assert marker.raw_summary["legacy_plaintext_sanitized"] == 1
            cleanup_status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
                PxgNaverReadonlyCleanupStatus.store_id == 1,
            ))
            assert cleanup_status.status == "healthy" and cleanup_status.last_success_at is not None
            legacy = db.scalar(select(CustomerInquiry).where(CustomerInquiry.external_inquiry_id == "legacy-answered"))
            assert legacy.customer_name is None and legacy.content == ""
            assert legacy.title == "Migrated to encrypted readonly inquiry"
            assert legacy.raw_data["superseded_by_readonly"] is True
            assert "answer_content" not in legacy.raw_data and "inquiryContent" not in str(legacy.raw_data)
            assert _is_superseded_naver_legacy(legacy, set()) is True

            try:
                run_import(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=settings,
                    now=now + timedelta(minutes=1),
                    refresh_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("runner reached")),
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_import_already_started"
            else:
                raise AssertionError("a completed one-time import must not run again")

            blocked_settings = Settings(
                app_env="production",
                credential_encryption_key=ENCRYPTION_KEY,
                customer_platform_write_enabled=True,
            )
            try:
                run_import(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=blocked_settings,
                    now=now,
                    refresh_runner=fake_refresh,
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_platform_write_gate_open"
            else:
                raise AssertionError("an open write gate must block the import")
            os.environ["T24_ONE_TIME_INQUIRY_IMPORT_STORE_ID"] = "2"
            try:
                run_import(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=blocked_settings,
                    now=now,
                    refresh_runner=fake_refresh,
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_import_approved_store_mismatch"
            else:
                raise AssertionError("process approval must remain bound to the exact store")
            db.add(Store(id=2, name="Other cleanup failure", platform="naver", status="active"))
            db.add(PxgNaverReadonlyCleanupStatus(
                store_id=2,
                platform="naver",
                status="failed",
                last_run_at=now,
                last_failure_at=now,
                last_failure_code="readonly_inquiry_cleanup_failed",
            ))
            db.commit()
            try:
                naver_readonly_inquiry_service.run_naver_inquiry_retention_cleanup(
                    db,
                    store_id=2,
                    settings=settings,
                    allow_configuration_recovery=True,
                )
            except ApiError as exc:
                assert exc.error_code == "readonly_retention_cleanup_failed"
            else:
                raise AssertionError("non-configuration cleanup failures must remain blocked")
            assert db.scalar(select(func.count()).select_from(PxgNaverReadonlyCustomerInquiry)) == 2
        print("verify_t24_one_time_naver_inquiry_import: ok")
    finally:
        engine.dispose()
        db_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
