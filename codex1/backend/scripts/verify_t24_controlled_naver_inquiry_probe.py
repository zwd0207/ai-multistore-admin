from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for path in (BACKEND_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

db_file = Path(tempfile.gettempdir()) / "t24-controlled-probe-verification.db"
db_file.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "test-key"
os.environ["T24_CONTROLLED_READ_APPROVAL"] = "owner-approved-one-get"
os.environ["T24_CONTROLLED_READ_APPROVED_STORE_ID"] = "1"
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
from app.database import Base
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.models.sync_log import SyncLog
from run_t24_controlled_naver_inquiry_probe import (
    ProbeBlocked,
    _single_get,
    run_probe,
)


def page_payload(content: list[dict]) -> dict:
    return {
        "content": content,
        "totalPages": 1,
        "totalElements": len(content),
        "number": 0,
        "last": True,
        "size": 10,
        "numberOfElements": len(content),
        "first": True,
        "empty": not content,
    }


def main() -> None:
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    now = datetime(2026, 7, 17, 13, 30, tzinfo=timezone.utc)
    store_name = "T24 Exact Store"
    name_hash = hashlib.sha256(store_name.encode("utf-8")).hexdigest()
    try:
        with Session(engine) as db:
            store = Store(id=1, name=store_name, platform="naver", status="active")
            credential = ApiCredential(
                id=1,
                store_id=1,
                platform="naver",
                credential_name="T24",
                client_id="configured-client",
                encrypted_secret_key="encrypted-secret",
                extra_config={"api_base": "https://api.test/external"},
                status="active",
            )
            db.add_all([store, credential])
            db.commit()

            get_calls = []

            def fake_request(**kwargs):
                get_calls.append(kwargs)
                return {
                    "success": True,
                    "http_status": 200,
                    "payload": page_payload([{"inquiryNo": "secret-id", "content": "private-body"}]),
                    "diagnostics": {"rate_limit": {}},
                }

            single = _single_get(
                credential,
                context_builder=lambda _credential: {"api_base": "https://api.test/external"},
                token_request=lambda _context: ("token-never-output", 200),
                inquiry_request=fake_request,
            )
            assert single["status"] == "passed" and single["business_get_count"] == 1
            assert len(get_calls) == 1 and get_calls[0]["page"] == 1 and get_calls[0]["size"] == 10
            assert all(secret not in json.dumps(single) for secret in ("private-body", "secret-id", "token-never-output"))

            malformed_calls = []
            malformed = _single_get(
                credential,
                context_builder=lambda _credential: {"api_base": "https://api.test/external"},
                token_request=lambda _context: ("token-never-output", 200),
                inquiry_request=lambda **kwargs: (
                    malformed_calls.append(kwargs)
                    or {"success": True, "http_status": 200, "payload": {"content": []}, "diagnostics": {}}
                ),
            )
            assert len(malformed_calls) == 1 and malformed["business_get_count"] == 1
            assert malformed["status"] == "blocked"
            assert malformed["error_code"] == "naver_inquiry_pagination_metadata_missing"

            run_calls = 0

            def fake_single_get(_credential):
                nonlocal run_calls
                run_calls += 1
                return single

            settings = Settings(app_env="production", credential_encryption_key="test-key")
            result = run_probe(
                db,
                store_id=1,
                expected_store_name_sha256=name_hash,
                settings=settings,
                now=now,
                single_get=fake_single_get,
            )
            assert result["status"] == "passed" and result["follow_up_get_count"] == 0
            assert result["business_state_unchanged"] is True and result["platform_write"] is False
            assert run_calls == 1
            capability = db.scalar(select(ApiCapabilityCheck).where(
                ApiCapabilityCheck.capability_key == "naver.customer_inquiry_read",
            ))
            evidence = db.scalar(select(ApiCapabilityTestResult).where(
                ApiCapabilityTestResult.capability_id == capability.id,
            ))
            assert evidence.test_status == "tested_success" and evidence.http_status == 200
            assert evidence.permission_result == "order_seller_confirmed"
            assert "private-body" not in str(evidence.notes) and "secret-id" not in str(evidence.response_fields_observed)

            db.add(SyncLog(
                store_id=1,
                platform="naver",
                sync_type="naver_readonly_inquiry_refresh",
                status="failed",
                started_at=now,
                finished_at=now,
                error_detail="naver_customer_inquiry_rate_limit",
                raw_summary={
                    "error_code": "naver_customer_inquiry_rate_limit",
                    "retry_after_seconds": 3600,
                },
            ))
            db.commit()
            try:
                run_probe(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=settings,
                    now=now,
                    single_get=lambda _credential: (_ for _ in ()).throw(AssertionError("network reached")),
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_rate_limit_cooldown_active"
            else:
                raise AssertionError("rate-limit cooldown must block before network access")

            blocked_settings = Settings(
                app_env="production",
                credential_encryption_key="test-key",
                real_api_write_enabled=True,
            )
            try:
                run_probe(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=blocked_settings,
                    now=now,
                    single_get=lambda _credential: single,
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_platform_write_gate_open"
            else:
                raise AssertionError("an open write gate must block before network access")

            os.environ["T24_CONTROLLED_READ_APPROVED_STORE_ID"] = "2"
            try:
                run_probe(
                    db,
                    store_id=1,
                    expected_store_name_sha256=name_hash,
                    settings=settings,
                    now=now,
                    single_get=lambda _credential: single,
                )
            except ProbeBlocked as exc:
                assert exc.error_code == "t24_approved_store_mismatch"
            else:
                raise AssertionError("approval must be bound to the exact store")

            source = (SCRIPTS_DIR / "run_t24_controlled_naver_inquiry_probe.py").read_text(encoding="utf-8")
            assert "refresh_naver_readonly_inquiries" not in source
            assert source.count("inquiry_request(") == 1
            assert db.scalar(select(func.count()).select_from(ApiCapabilityTestResult)) == 1
        print("verify_t24_controlled_naver_inquiry_probe: ok")
    finally:
        engine.dispose()
        db_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
