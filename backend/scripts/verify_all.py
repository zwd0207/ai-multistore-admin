import subprocess
import sys
import os
import tempfile
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
PYTHON = sys.executable

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

VERIFY_DB_PATH = Path(tempfile.gettempdir()) / f"codex1-verify-all-{os.getpid()}-{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{VERIFY_DB_PATH.as_posix()}"
os.environ["REAL_API_TEST_ENABLED"] = "false"
os.environ["REAL_API_WRITE_ENABLED"] = "false"
for env_name in (
    "COUPANG_VENDOR_ID",
    "COUPANG_ACCESS_KEY",
    "COUPANG_SECRET_KEY",
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
    "NAVER_CHANNEL_NO",
    "NAVER_ACCESS_TOKEN",
    "NAVER_REFRESH_TOKEN",
    "NAVER_TOKEN_EXPIRES_AT",
):
    os.environ[env_name] = ""
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

GIT_CMD_DIR = Path("C:/Program Files/Git/cmd")
if GIT_CMD_DIR.exists():
    os.environ["PATH"] = f"{GIT_CMD_DIR}{os.pathsep}{os.environ.get('PATH', '')}"

EXPECTED_API_PATHS = {
    "/api/v1/health",
    "/api/v1/stores",
    "/api/v1/stores/{store_id}",
    "/api/v1/credentials",
    "/api/v1/api-credentials/readiness",
    "/api/v1/api-credentials/smoke-test",
    "/api/v1/credentials/{credential_id}",
    "/api/v1/platform-logins",
    "/api/v1/platform-logins/{login_id}",
    "/api/v1/sync-logs",
    "/api/v1/products",
    "/api/v1/orders",
    "/api/v1/customer-inquiries",
    "/api/v1/sync/products/mock",
    "/api/v1/sync/products/coupang/preview",
    "/api/v1/sync/products/coupang",
    "/api/v1/sync/sales/coupang/preview",
    "/api/v1/sync/settlements/coupang/preview",
    "/api/v1/sync/orders/mock",
    "/api/v1/sync/orders/coupang/preview",
    "/api/v1/sync/orders/coupang",
    "/api/v1/sync/customer-inquiries/mock",
    "/api/v1/stats/sales",
    "/api/v1/stats/sales/by-platform",
    "/api/v1/stats/sales/by-date",
    "/api/v1/dashboard/summary",
    "/api/v1/ai/daily-context",
    "/api/v1/api-capabilities",
    "/api/v1/api-capabilities/summary",
    "/api/v1/api-capabilities/{capability_id}",
    "/api/v1/api-capability-results",
    "/api/v1/api-capability-results/{result_id}",
    "/api/v1/device-environments",
    "/api/v1/device-environments/{environment_id}",
    "/api/v1/email-accounts",
    "/api/v1/email-accounts/{email_account_id}",
    "/api/v1/important-emails",
    "/api/v1/important-emails/{email_id}",
    "/api/v1/appeal-cases",
    "/api/v1/appeal-cases/{case_id}",
}

FORBIDDEN_TRACKED_PATTERNS = [
    ".env",
    "codex1.db",
    ".sqlite",
    ".sqlite3",
    ".venv",
    "__pycache__",
]

FORBIDDEN_DOC_PATTERNS = [
    "mock-email-token-stage-1f",
    "stage-1e-naver-access-token",
    "stage-1e-naver-secret-token",
    "stage-1e-coupang-access-token",
    "stage-1e-coupang-secret-token",
    "123.123.123.123",
    "900101-1234567",
    "4111-1111-1111-1111",
]

EXPECTED_CREDENTIAL_COLUMNS = {
    "vendor_id",
    "client_id",
    "encrypted_access_token",
    "encrypted_refresh_token",
    "token_expires_at",
    "market",
    "auth_status",
    "last_tested_at",
    "api_remark",
}

EXPECTED_API_CAPABILITY_TABLES = {
    "api_capability_checks",
    "api_capability_test_results",
}

EXPECTED_SYNC_SCHEMA_COLUMNS = {
    "orders": {"source_type", "last_synced_at"},
    "products": {"source_type", "last_synced_at"},
}

EXPECTED_SYNC_TABLES = {
    "sync_checkpoints",
}

EXPECTED_FINANCIAL_SCHEMA_COLUMNS = {
    "platform_sales_details": {
        "id",
        "store_id",
        "platform",
        "source_type",
        "external_sales_id",
        "recognition_date",
        "order_id",
        "order_sheet_id",
        "shipment_box_id",
        "product_id",
        "vendor_item_id",
        "sale_type",
        "status",
        "currency",
        "sale_amount",
        "total_sale",
        "discount_amount",
        "refund_amount",
        "commission_amount",
        "fee_amount",
        "settlement_target_amount",
        "settlement_amount",
        "observed_fields",
        "last_synced_at",
        "created_at",
        "updated_at",
    },
    "platform_settlement_details": {
        "id",
        "store_id",
        "platform",
        "source_type",
        "external_settlement_id",
        "revenue_recognition_year_month",
        "settlement_type",
        "settlement_date",
        "revenue_recognition_date_from",
        "revenue_recognition_date_to",
        "currency",
        "total_sale",
        "service_fee",
        "settlement_target_amount",
        "settlement_amount",
        "last_amount",
        "pending_released_amount",
        "dedicated_delivery_amount",
        "seller_service_fee",
        "courantee_fee",
        "deduction_amount",
        "final_amount",
        "observed_fields",
        "last_synced_at",
        "created_at",
        "updated_at",
    },
}

FORBIDDEN_FINANCIAL_COLUMNS = {
    "bankAccountHolder",
    "bankName",
    "bankAccount",
    "access_key",
    "secret_key",
    "header",
    "signature",
    "token",
    "authorization",
    "raw_data",
    "raw_response",
}

FORBIDDEN_TIME_PATTERNS = {
    "datetime.utcnow(": "use app.core.timezone.get_utc_now()",
    "date.today(": "use app.core.timezone.get_business_date() for business dates",
}


def run(command: list[str], cwd: Path = BACKEND_DIR, echo: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if echo and result.stdout:
        print(result.stdout, end="")
    if echo and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")
    return result.stdout


def verify_compile() -> None:
    run([PYTHON, "-m", "compileall", "-q", "app", "scripts"])
    print("compile: ok")


def verify_stage_scripts() -> None:
    for script in [
        "verify_stage_1b.py",
        "verify_stage_1c.py",
        "verify_stage_1d.py",
        "verify_stage_1e.py",
        "verify_stage_1f.py",
    ]:
        print(f"running {script}")
        run([PYTHON, f"scripts/{script}"])
    print("stage scripts: ok")


def verify_openapi() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200, health.text
        docs = client.get("/docs")
        assert docs.status_code == 200, docs.text[:100]
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text[:100]
        paths = set(openapi.json()["paths"].keys())

    missing = sorted(EXPECTED_API_PATHS - paths)
    assert not missing, f"Missing OpenAPI paths: {missing}"
    assert "/api/v1/credentials/{credential_id}/decrypt" not in paths
    assert all(path.startswith("/api/v1") or path in {"/", "/health"} for path in paths), sorted(paths)
    print("openapi/docs: ok")


def verify_api_credential_schema_and_security() -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.database import SessionLocal
    from app.main import app
    from scripts.upgrade_api_credentials_schema import upgrade

    upgrade()
    upgrade()
    with SessionLocal() as db:
        columns = {row[1] for row in db.execute(text("PRAGMA table_info(api_credentials)")).all()}
    missing = sorted(EXPECTED_CREDENTIAL_COLUMNS - columns)
    assert not missing, f"Missing api_credentials columns: {missing}"

    with TestClient(app) as client:
        suffix = uuid.uuid4().hex[:8]
        store = client.post("/api/v1/stores", json={
            "name": f"Phase 6A-3 Credential Verify Store {suffix}",
            "platform": "naver",
            "country": "KR",
            "language": "ko-KR",
            "status": "active",
        }).json()["data"]
        created = client.post("/api/v1/credentials", json={
            "store_id": store["id"],
            "platform": "naver",
            "credential_name": "Phase 6A-3 Naver credential",
            "client_id": "naver-client-id",
            "access_key": "legacy-access-key",
            "secret_key": "naver-client-secret",
            "access_token": "naver-access-token",
            "refresh_token": "naver-refresh-token",
            "token_expires_at": "2026-12-31T00:00:00+00:00",
            "market": "KR",
            "auth_status": "configured",
            "api_remark": "local config only",
        })
        assert created.status_code == 201, created.text
        data = created.json()["data"]
        assert data["has_access_key"] is True
        assert data["has_secret_key"] is True
        assert data["has_access_token"] is True
        assert data["has_refresh_token"] is True
        assert data["client_id"] == "naver-client-id"
        assert data["auth_status"] == "configured"
        serialized = str(created.json())
        forbidden = [
            "legacy-access-key",
            "naver-client-secret",
            "naver-access-token",
            "naver-refresh-token",
            "encrypted_access_token",
            "encrypted_refresh_token",
        ]
        assert not any(item in serialized for item in forbidden), serialized

        updated = client.put(f"/api/v1/credentials/{data['id']}", json={
            "credential_name": "Phase 6A-3 Naver credential updated",
            "auth_status": "needs_test",
        })
        assert updated.status_code == 200, updated.text
        update_data = updated.json()["data"]
        assert update_data["has_access_token"] is True
        assert update_data["has_refresh_token"] is True
        assert update_data["auth_status"] == "needs_test"

        coupang = client.post("/api/v1/credentials", json={
            "store_id": store["id"],
            "platform": "coupang",
            "credential_name": "Phase 6A-3 Coupang credential",
            "vendor_id": "coupang-vendor-id",
            "access_key": "coupang-access-key",
            "secret_key": "coupang-secret-key",
            "market": "KR",
            "auth_status": "configured",
        })
        assert coupang.status_code == 201, coupang.text
        assert coupang.json()["data"]["vendor_id"] == "coupang-vendor-id"
        assert "coupang-secret-key" not in str(coupang.json())

    print("api credential schema/security: ok")


def verify_api_credential_readiness() -> None:
    from fastapi.testclient import TestClient

    import app.config as app_config
    from app.main import app
    from app.services import api_credential_readiness_service

    original_test_enabled = os.environ.get("REAL_API_TEST_ENABLED")
    original_write_enabled = os.environ.get("REAL_API_WRITE_ENABLED")
    os.environ["REAL_API_TEST_ENABLED"] = "false"
    os.environ["REAL_API_WRITE_ENABLED"] = "false"
    app_config.get_settings.cache_clear()
    with TestClient(app) as client:
        try:
            response = client.get("/api/v1/api-credentials/readiness")
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["real_api_test_enabled"] is False
            assert data["real_api_write_enabled"] is False
            assert "semantic_notice" in data
            assert {item["platform"] for item in data["platforms"]} == {"naver", "coupang"}
            for platform in data["platforms"]:
                assert platform["credential_status"] in {"configured", "missing"}
                assert platform["readiness_status"] in {"configured", "missing", "disabled"}
                assert platform["readiness_status"] == "disabled"
                for status_value in platform["fields"].values():
                    assert status_value in {"configured", "missing"}
            serialized = str(response.json()).lower()
            forbidden = [
                "phase-6b-secret-key",
                "phase-6b-access-token",
                "phase-6b-refresh-token",
                "coupang-secret-key",
                "naver-client-secret",
                "encrypted_access_key",
                "encrypted_secret_key",
                "encrypted_access_token",
                "encrypted_refresh_token",
            ]
            assert not any(item in serialized for item in forbidden), serialized

            original_client = api_credential_readiness_service.httpx.Client

            class ForbiddenHttpClient:
                def __init__(self, *args, **kwargs) -> None:
                    raise AssertionError("disabled smoke test must not create an HTTP client")

            api_credential_readiness_service.httpx.Client = ForbiddenHttpClient
            try:
                disabled = client.post("/api/v1/api-credentials/smoke-test", json={
                    "platform": "all",
                    "mode": "readonly",
                })
            finally:
                api_credential_readiness_service.httpx.Client = original_client
            assert disabled.status_code == 200, disabled.text
            smoke_data = disabled.json()["data"]
            assert smoke_data["real_api_test_enabled"] is False
            assert smoke_data["real_api_write_enabled"] is False
            assert smoke_data["mode"] == "readonly"
            assert {item["platform"] for item in smoke_data["results"]} == {"naver", "coupang"}
            allowed_result_keys = {
                "platform",
                "enabled",
                "configured",
                "http_status",
                "token_test",
                "seller_or_account_test",
                "product_read_test",
                "order_read_test",
                "settlement_read_test",
                "error_code",
                "masked_message",
                "tested_at",
            }
            for item in smoke_data["results"]:
                assert set(item.keys()) == allowed_result_keys, item
                assert item["enabled"] is False
                assert item["configured"] is False
                assert item["error_code"] == "real_api_test_disabled"
                assert item["token_test"] == "skipped"
                assert item["seller_or_account_test"] == "skipped"
                assert item["product_read_test"] == "skipped"
                assert item["order_read_test"] == "skipped"
                assert item["settlement_read_test"] == "skipped"
            smoke_serialized = str(disabled.json()).lower()
            assert not any(item in smoke_serialized for item in forbidden), smoke_serialized

            invalid_mode = client.post("/api/v1/api-credentials/smoke-test", json={
                "platform": "naver",
                "mode": "write",
            })
            assert invalid_mode.status_code == 422, invalid_mode.text
        finally:
            if original_test_enabled is None:
                os.environ.pop("REAL_API_TEST_ENABLED", None)
            else:
                os.environ["REAL_API_TEST_ENABLED"] = original_test_enabled
            if original_write_enabled is None:
                os.environ.pop("REAL_API_WRITE_ENABLED", None)
            else:
                os.environ["REAL_API_WRITE_ENABLED"] = original_write_enabled
            app_config.get_settings.cache_clear()
    print("api credential readiness: ok")


def verify_api_capabilities() -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.database import SessionLocal
    from app.main import app

    with SessionLocal() as db:
        tables = {row[0] for row in db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()}
    missing_tables = sorted(EXPECTED_API_CAPABILITY_TABLES - tables)
    assert not missing_tables, f"Missing API capability tables: {missing_tables}"

    with TestClient(app) as client:
        suffix = uuid.uuid4().hex[:8]
        store = client.post("/api/v1/stores", json={
            "name": f"Phase 6B-1 Capability Verify Store {suffix}",
            "platform": "naver",
            "country": "KR",
            "language": "ko-KR",
            "status": "active",
        }).json()["data"]
        other_store = client.post("/api/v1/stores", json={
            "name": f"Phase 6B-1 Capability Other Store {suffix}",
            "platform": "coupang",
            "country": "KR",
            "language": "ko-KR",
            "status": "active",
        }).json()["data"]

        naver_credential = client.post("/api/v1/credentials", json={
            "store_id": store["id"],
            "platform": "naver",
            "credential_name": "Phase 6B-1 Naver credential",
            "client_id": "phase-6b-client-id",
            "access_key": "phase-6b-access-key",
            "secret_key": "phase-6b-secret-key",
            "access_token": "phase-6b-access-token",
            "refresh_token": "phase-6b-refresh-token",
            "market": "KR",
            "auth_status": "needs_test",
        })
        assert naver_credential.status_code == 201, naver_credential.text
        credential_id = naver_credential.json()["data"]["id"]
        assert "phase-6b-secret-key" not in str(naver_credential.json())
        assert "phase-6b-access-token" not in str(naver_credential.json())

        coupang_credential = client.post("/api/v1/credentials", json={
            "store_id": other_store["id"],
            "platform": "coupang",
            "credential_name": "Phase 6B-1 Coupang credential",
            "vendor_id": "phase-6b-vendor",
            "access_key": "phase-6b-coupang-access",
            "secret_key": "phase-6b-coupang-secret",
            "market": "KR",
            "auth_status": "needs_test",
        })
        assert coupang_credential.status_code == 201, coupang_credential.text
        coupang_credential_id = coupang_credential.json()["data"]["id"]

        coupang_capability = client.post("/api/v1/api-capabilities", json={
            "platform": "coupang",
            "capability_key": "orders.list",
            "capability_name": "Coupang order list docs-only check",
            "api_category": "orders",
            "endpoint_path": "/v2/providers/openapi/apis/api/v4/vendors/{vendorId}/ordersheets",
            "method": "GET",
            "required_credential_type": "vendor_id + access_key + secret_key",
            "required_permission": "Local docs/manual record only",
            "ordinary_store_supported": "unknown",
            "test_status": "planned",
            "test_mode": "docs_only",
            "request_params_summary": "createdAtFrom, createdAtTo",
            "response_fields_summary": "order id, status, amount fields need future readonly confirmation",
            "error_codes_summary": "permission and throttling codes need future readonly confirmation",
            "data_usefulness": "high",
            "first_phase_candidate": True,
            "sales_source_type": "order-derived",
            "official_doc_url": "https://example.invalid/coupang-doc-placeholder",
            "notes": "Platform-level docs-only record; not a store credential validation.",
        })
        assert coupang_capability.status_code == 201, coupang_capability.text
        coupang_capability_id = coupang_capability.json()["data"]["id"]

        naver_capability = client.post("/api/v1/api-capabilities", json={
            "platform": "naver",
            "capability_key": "products.list",
            "capability_name": "Naver product list docs-only check",
            "api_category": "products",
            "endpoint_path": "/external/v1/products",
            "method": "GET",
            "required_credential_type": "client_id + client_secret + token",
            "ordinary_store_supported": "unknown",
            "test_status": "not_tested",
            "test_mode": "manual",
            "data_usefulness": "high",
            "first_phase_candidate": True,
            "sales_source_type": "not_applicable",
            "notes": "Manual capability note only; no real API request is performed.",
        })
        assert naver_capability.status_code == 201, naver_capability.text
        naver_data = naver_capability.json()["data"]

        by_platform = client.get("/api/v1/api-capabilities?platform=naver")
        assert by_platform.status_code == 200, by_platform.text
        assert by_platform.json()["data"]["total"] >= 1
        assert all(item["platform"] == "naver" for item in by_platform.json()["data"]["items"])

        by_category = client.get("/api/v1/api-capabilities?api_category=orders")
        assert by_category.status_code == 200, by_category.text
        assert any(item["capability_key"] == "orders.list" for item in by_category.json()["data"]["items"])

        by_status = client.get("/api/v1/api-capabilities?test_status=planned")
        assert by_status.status_code == 200, by_status.text
        assert any(item["id"] == coupang_capability_id for item in by_status.json()["data"]["items"])

        updated = client.put(f"/api/v1/api-capabilities/{naver_data['id']}", json={
            "test_status": "planned",
            "response_fields_summary": "Product fields need future readonly confirmation.",
            "last_checked_at": "2026-06-30T00:00:00+00:00",
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["test_status"] == "planned"

        result = client.post("/api/v1/api-capability-results", json={
            "store_id": store["id"],
            "credential_id": credential_id,
            "capability_id": naver_data["id"],
            "test_mode": "manual",
            "test_status": "planned",
            "permission_result": "Manual planning record only.",
            "response_fields_observed": "No real response observed.",
            "notes": "No real Naver/Coupang API call was made.",
        })
        assert result.status_code == 201, result.text
        result_text = str(result.json())
        for forbidden in [
            "phase-6b-access-key",
            "phase-6b-secret-key",
            "phase-6b-access-token",
            "phase-6b-refresh-token",
            "encrypted_access_key",
            "encrypted_secret_key",
            "encrypted_access_token",
            "encrypted_refresh_token",
        ]:
            assert forbidden not in result_text, result_text

        missing_store = client.post("/api/v1/api-capability-results", json={
            "store_id": 999999,
            "credential_id": credential_id,
            "capability_id": naver_data["id"],
            "test_mode": "manual",
            "test_status": "planned",
        })
        assert missing_store.status_code == 404, missing_store.text
        assert missing_store.json()["error_code"] == "STORE_NOT_FOUND"

        missing_credential = client.post("/api/v1/api-capability-results", json={
            "store_id": store["id"],
            "credential_id": 999999,
            "capability_id": naver_data["id"],
            "test_mode": "manual",
            "test_status": "planned",
        })
        assert missing_credential.status_code == 404, missing_credential.text
        assert missing_credential.json()["error_code"] == "CREDENTIAL_NOT_FOUND"

        missing_capability = client.post("/api/v1/api-capability-results", json={
            "store_id": store["id"],
            "credential_id": credential_id,
            "capability_id": 999999,
            "test_mode": "manual",
            "test_status": "planned",
        })
        assert missing_capability.status_code == 404, missing_capability.text
        assert missing_capability.json()["error_code"] == "API_CAPABILITY_NOT_FOUND"

        platform_mismatch = client.post("/api/v1/api-capability-results", json={
            "store_id": other_store["id"],
            "credential_id": coupang_credential_id,
            "capability_id": naver_data["id"],
            "test_mode": "manual",
            "test_status": "planned",
        })
        assert platform_mismatch.status_code == 400, platform_mismatch.text
        assert platform_mismatch.json()["error_code"] == "CREDENTIAL_PLATFORM_MISMATCH"

        reserved_real_readonly = client.post("/api/v1/api-capability-results", json={
            "store_id": store["id"],
            "credential_id": credential_id,
            "capability_id": naver_data["id"],
            "test_mode": "real_readonly",
            "test_status": "planned",
        })
        assert reserved_real_readonly.status_code == 400, reserved_real_readonly.text
        assert reserved_real_readonly.json()["error_code"] == "REAL_READONLY_TEST_RESERVED"

        summary = client.get("/api/v1/api-capabilities/summary")
        assert summary.status_code == 200, summary.text
        summary_data = summary.json()["data"]
        assert "semantic_notice" in summary_data
        assert "platform_summary" in summary_data
        assert "store_result_summary" in summary_data
        assert summary_data["store_result_summary"] == []
        assert any(item["platform"] == "naver" for item in summary_data["platform_summary"])

        naver_summary = client.get("/api/v1/api-capabilities/summary?platform=naver")
        assert naver_summary.status_code == 200, naver_summary.text
        naver_summary_data = naver_summary.json()["data"]
        assert naver_summary_data["platform_summary"], naver_summary_data
        assert all(item["platform"] == "naver" for item in naver_summary_data["platform_summary"])

        store_summary = client.get(f"/api/v1/api-capabilities/summary?store_id={store['id']}")
        assert store_summary.status_code == 200, store_summary.text
        store_summary_data = store_summary.json()["data"]
        assert any(item["store_id"] == store["id"] for item in store_summary_data["store_result_summary"])
        naver_store_summary = next(
            item for item in store_summary_data["store_result_summary"] if item["platform"] == "naver"
        )
        assert naver_store_summary["total_results"] >= 1
        assert naver_store_summary["credential_bound_results"] >= 1
        assert naver_store_summary["manual_count"] >= 1
        assert isinstance(naver_store_summary["missing_first_phase_candidates"], list)

        scoped_store_summary = client.get(f"/api/v1/api-capabilities/summary?store_id={store['id']}&platform=naver")
        assert scoped_store_summary.status_code == 200, scoped_store_summary.text
        assert all(
            item["platform"] == "naver"
            for item in scoped_store_summary.json()["data"]["store_result_summary"]
        )

        missing_store_summary = client.get("/api/v1/api-capabilities/summary?store_id=999999")
        assert missing_store_summary.status_code == 404, missing_store_summary.text
        assert missing_store_summary.json()["error_code"] == "STORE_NOT_FOUND"

        dashboard = client.get(f"/api/v1/dashboard/summary?store_id={store['id']}")
        assert dashboard.status_code == 200, dashboard.text
        dashboard_data = dashboard.json()["data"]
        assert "api_capability_summary" in dashboard_data
        assert "business_timezone" in dashboard_data
        assert dashboard_data["api_capability_summary"]["semantic_notice"] == summary_data["semantic_notice"]

        context = client.get(f"/api/v1/ai/daily-context?store_id={store['id']}")
        assert context.status_code == 200, context.text
        context_data = context.json()["data"]
        assert "api_capability_context" in context_data
        assert "sales_summary" in context_data
        assert context_data["api_capability_context"]["semantic_notice"] == summary_data["semantic_notice"]

        combined_summary_text = str(summary.json()) + str(dashboard.json()) + str(context.json())
        for forbidden in [
            "phase-6b-access-key",
            "phase-6b-secret-key",
            "phase-6b-access-token",
            "phase-6b-refresh-token",
            "encrypted_access_key",
            "encrypted_secret_key",
            "encrypted_access_token",
            "encrypted_refresh_token",
            "password",
        ]:
            assert forbidden not in combined_summary_text, combined_summary_text

    print("api capabilities docs/manual base: ok")


def verify_sync_preview_schema_and_security() -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import select, text
    from urllib.parse import parse_qs

    import httpx
    import app.config as app_config
    from app.database import SessionLocal
    from app.main import app
    from app.models.financial import PlatformSalesDetail, PlatformSettlementDetail
    from app.models.order import Order
    from app.models.product import Product
    from app.models.sync_log import SyncLog
    from app.services import sync_service
    from scripts.upgrade_sync_schema import upgrade

    upgrade()
    upgrade()
    with SessionLocal() as db:
        tables = {row[0] for row in db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()}
        missing_tables = sorted((EXPECTED_SYNC_TABLES | set(EXPECTED_FINANCIAL_SCHEMA_COLUMNS)) - tables)
        assert not missing_tables, f"Missing sync tables: {missing_tables}"
        for table_name, expected_columns in EXPECTED_SYNC_SCHEMA_COLUMNS.items():
            columns = {row[1] for row in db.execute(text(f"PRAGMA table_info({table_name})")).all()}
            missing_columns = sorted(expected_columns - columns)
            assert not missing_columns, f"Missing {table_name} columns: {missing_columns}"
        for table_name, expected_columns in EXPECTED_FINANCIAL_SCHEMA_COLUMNS.items():
            table_info = db.execute(text(f"PRAGMA table_info({table_name})")).all()
            columns = {row[1] for row in table_info}
            missing_columns = sorted(expected_columns - columns)
            assert not missing_columns, f"Missing {table_name} columns: {missing_columns}"
            forbidden_columns = sorted({column.lower() for column in columns} & {item.lower() for item in FORBIDDEN_FINANCIAL_COLUMNS})
            assert not forbidden_columns, f"Forbidden {table_name} columns: {forbidden_columns}"
            integer_amount_columns = {
                row[1]: row[2].upper()
                for row in table_info
                if row[1].endswith("_amount") or row[1] in {"total_sale", "service_fee", "courantee_fee"}
            }
            assert integer_amount_columns, f"Missing integer amount columns for {table_name}"
            assert all(column_type == "BIGINT" for column_type in integer_amount_columns.values()), integer_amount_columns

            index_rows = db.execute(text(f"PRAGMA index_list({table_name})")).all()
            index_names = {row[1] for row in index_rows}
            unique_indexes = {row[1] for row in index_rows if row[2]}
            if table_name == "platform_sales_details":
                assert "sqlite_autoindex_platform_sales_details_1" in unique_indexes or "uq_platform_sales_external_id" in unique_indexes, unique_indexes
                assert "ix_platform_sales_store_platform_date" in index_names, index_names
            if table_name == "platform_settlement_details":
                assert "sqlite_autoindex_platform_settlement_details_1" in unique_indexes or "uq_platform_settlement_external_id" in unique_indexes, unique_indexes
                assert "ix_platform_settlement_store_platform_month" in index_names, index_names
                assert "ix_platform_settlement_store_platform_date" in index_names, index_names

        PlatformSalesDetail(observed_fields=["revenueId", "saleAmount"])
        PlatformSettlementDetail(observed_fields=["settlementId", "settlementAmount"])
        for model in (PlatformSalesDetail, PlatformSettlementDetail):
            try:
                model(observed_fields=["bankName"])
            except ValueError:
                pass
            else:
                raise AssertionError(f"{model.__name__} accepted forbidden observed_fields")

    original_test_enabled = os.environ.get("REAL_API_TEST_ENABLED")
    try:
        suffix = uuid.uuid4().hex[:8]
        with TestClient(app) as client:
            store = client.post("/api/v1/stores", json={
                "name": f"Phase 6C-6A Preview Store {suffix}",
                "platform": "coupang",
                "country": "KR",
                "language": "ko-KR",
                "status": "active",
            })
            assert store.status_code == 201, store.text
            store_id = store.json()["data"]["id"]

            credential = client.post("/api/v1/credentials", json={
                "store_id": store_id,
                "platform": "coupang",
                "credential_name": "Phase 6C-6A Preview Credential",
                "vendor_id": "phase-6c6a-vendor",
                "access_key": "phase-6c6a-access-key",
                "secret_key": "phase-6c6a-secret-key",
                "market": "KR",
                "auth_status": "configured",
            })
            assert credential.status_code == 201, credential.text
            credential_text = str(credential.json()).lower()
            for forbidden in [
                "phase-6c6a-access-key",
                "phase-6c6a-secret-key",
                "authorization",
                "signature",
            ]:
                assert forbidden not in credential_text, credential_text

            os.environ["REAL_API_TEST_ENABLED"] = "false"
            app_config.get_settings.cache_clear()
            original_http_client = sync_service.httpx.Client

            class ForbiddenHttpClient:
                def __init__(self, *args, **kwargs) -> None:
                    raise AssertionError("disabled preview must not create an HTTP client")

            sync_service.httpx.Client = ForbiddenHttpClient
            try:
                disabled = client.post("/api/v1/sync/orders/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-30",
                    "end_date": "2026-06-30",
                    "max_pages": 1,
                })
                disabled_product = client.post("/api/v1/sync/products/coupang/preview", json={
                    "store_id": store_id,
                    "status": "APPROVED",
                    "max_pages": 1,
                })
                disabled_sales = client.post("/api/v1/sync/sales/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-29",
                    "end_date": "2026-06-30",
                    "max_pages": 1,
                })
                disabled_settlement = client.post("/api/v1/sync/settlements/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-29",
                    "end_date": "2026-06-30",
                })
            finally:
                sync_service.httpx.Client = original_http_client
                app_config.get_settings.cache_clear()
            assert disabled.status_code == 403, disabled.text
            assert disabled.json()["error_code"] == "REAL_API_TEST_DISABLED", disabled.text
            assert disabled_product.status_code == 403, disabled_product.text
            assert disabled_product.json()["error_code"] == "REAL_API_TEST_DISABLED", disabled_product.text
            assert disabled_sales.status_code == 403, disabled_sales.text
            assert disabled_sales.json()["error_code"] == "REAL_API_TEST_DISABLED", disabled_sales.text
            assert disabled_settlement.status_code == 403, disabled_settlement.text
            assert disabled_settlement.json()["error_code"] == "REAL_API_TEST_DISABLED", disabled_settlement.text

            with SessionLocal() as db:
                db.add(Order(
                    store_id=store_id,
                    platform="coupang",
                    external_order_id="preview-existing-001",
                    buyer_name="Preview Buyer",
                    buyer_masked_phone="010-****-0000",
                    product_name="Existing Preview Order",
                    quantity=1,
                    order_amount=Decimal("1000.00"),
                    currency="KRW",
                    order_status="paid",
                    paid_at=datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc),
                    ordered_at=datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc),
                    source_type="mock_sync",
                    last_synced_at=datetime(2026, 6, 30, 1, 0, tzinfo=timezone.utc),
                    raw_data={"source": "verify_sync_preview_schema_and_security"},
                ))
                db.commit()

            os.environ["REAL_API_TEST_ENABLED"] = "true"
            app_config.get_settings.cache_clear()
            original_get = sync_service._coupang_get_with_credential

            def fake_coupang_get(credential, path, query_string):
                query = parse_qs(query_string)
                request = httpx.Request("GET", f"https://example.invalid{path}?{query_string}")
                if query.get("nextToken") == ["token-page-2"]:
                    return httpx.Response(
                        200,
                        request=request,
                        json={"data": [{"orderId": "preview-order-002"}]},
                    )
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "data": [
                            {"orderId": "preview-existing-001"},
                            {"shipmentBoxId": "preview-order-001"},
                        ],
                        "nextToken": "token-page-2",
                    },
                )

            sync_service._coupang_get_with_credential = fake_coupang_get
            try:
                preview = client.post("/api/v1/sync/orders/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-30",
                    "end_date": "2026-07-01",
                    "max_pages": 3,
                })
            finally:
                sync_service._coupang_get_with_credential = original_get

            assert preview.status_code == 200, preview.text
            preview_data = preview.json()["data"]
            assert preview_data["store_id"] == store_id, preview_data
            assert preview_data["platform"] == "coupang", preview_data
            assert preview_data["source_type"] == "real_coupang", preview_data
            assert preview_data["page_count"] == 2, preview_data
            assert preview_data["next_cursor_exists"] is False, preview_data
            assert preview_data["would_update"] == 1, preview_data
            assert preview_data["would_create"] == 2, preview_data
            assert set(preview_data["sample_ids"]) == {"preview-existing-001", "preview-order-001", "preview-order-002"}
            assert preview_data["window_start_at"].startswith("2026-06-29T15:00:00+00:00"), preview_data
            assert preview_data["window_end_at"].startswith("2026-07-01T15:00:00+00:00"), preview_data

            with SessionLocal() as db:
                latest_log = db.scalars(
                    select(SyncLog)
                    .where(
                        SyncLog.store_id == store_id,
                        SyncLog.sync_type == "orders_coupang_real_preview",
                    )
                    .order_by(SyncLog.id.desc())
                ).first()
                assert latest_log is not None
                assert latest_log.status == "success", latest_log
                assert latest_log.raw_summary is not None, latest_log
                log_text = str(latest_log.raw_summary).lower()
                for forbidden in [
                    "phase-6c6a-access-key",
                    "phase-6c6a-secret-key",
                    "authorization",
                    "signature",
                    "token-page-2",
                ]:
                    assert forbidden not in log_text, log_text
                store_orders = db.scalars(select(Order).where(Order.store_id == store_id)).all()
                assert len(store_orders) == 1, store_orders

            original_get = sync_service._coupang_get_with_credential
            product_statuses_seen = []

            def fake_coupang_product_get(credential, path, query_string):
                query = parse_qs(query_string)
                request = httpx.Request("GET", f"https://example.invalid{path}?{query_string}")
                assert "seller-products" in path, path
                status = query.get("status", [""])[0]
                product_statuses_seen.append(status)
                if status == "APPROVED":
                    return httpx.Response(
                        200,
                        request=request,
                        json={
                            "data": [
                                {
                                    "sellerProductId": "product-approved-001",
                                    "sellerProductName": "Approved Product 1",
                                    "statusName": "APPROVED",
                                    "brand": "VerifyBrand",
                                    "displayCategoryCode": "1234",
                                    "salePrice": 12000,
                                },
                                {
                                    "sellerProductId": "product-approved-002",
                                    "sellerProductName": "Approved Product 2",
                                    "statusName": "APPROVED",
                                    "brand": "VerifyBrand",
                                    "displayCategoryCode": "5678",
                                    "salePrice": 34000,
                                },
                            ]
                        },
                    )
                if status == "PARTIAL_APPROVED":
                    return httpx.Response(
                        200,
                        request=request,
                        json={"data": [{"sellerProductName": "Missing ID Product", "statusName": "PARTIAL_APPROVED"}]},
                    )
                return httpx.Response(200, request=request, json={"data": []})

            sync_service._coupang_get_with_credential = fake_coupang_product_get
            try:
                product_preview = client.post("/api/v1/sync/products/coupang/preview", json={
                    "store_id": store_id,
                    "status": "all",
                    "max_pages": 1,
                })
            finally:
                sync_service._coupang_get_with_credential = original_get

            assert set(product_statuses_seen) == {
                "IN_REVIEW",
                "SAVED",
                "APPROVING",
                "APPROVED",
                "PARTIAL_APPROVED",
                "DENIED",
                "DELETED",
            }, product_statuses_seen
            assert product_preview.status_code == 200, product_preview.text
            product_preview_data = product_preview.json()["data"]
            assert product_preview_data["would_create"] == 2, product_preview_data
            assert product_preview_data["would_update"] == 0, product_preview_data
            assert len(product_preview_data["per_status"]) == 7, product_preview_data
            assert product_preview_data["status_semantic_notice"], product_preview_data
            with SessionLocal() as db:
                assert not db.scalars(select(Product).where(Product.store_id == store_id)).all()

            product_statuses_seen.clear()
            sync_service._coupang_get_with_credential = fake_coupang_product_get
            try:
                product_sync = client.post("/api/v1/sync/products/coupang", json={
                    "store_id": store_id,
                    "status": "all",
                    "max_pages": 1,
                })
            finally:
                sync_service._coupang_get_with_credential = original_get
            assert set(product_statuses_seen) == {
                "IN_REVIEW",
                "SAVED",
                "APPROVING",
                "APPROVED",
                "PARTIAL_APPROVED",
                "DENIED",
                "DELETED",
            }, product_statuses_seen

            assert product_sync.status_code == 200, product_sync.text
            product_sync_data = product_sync.json()["data"]
            assert product_sync_data["created_count"] == 2, product_sync_data
            assert product_sync_data["updated_count"] == 0, product_sync_data
            assert product_sync_data["skipped_count"] == 1, product_sync_data
            assert product_sync_data["checkpoint"]["sync_type"] == "products", product_sync_data
            with SessionLocal() as db:
                store_products = db.scalars(select(Product).where(Product.store_id == store_id)).all()
                assert len(store_products) == 2, store_products
                assert {item.source_type for item in store_products} == {"real_coupang"}
                assert all(item.last_synced_at is not None for item in store_products)
                latest_product_log = db.scalars(
                    select(SyncLog)
                    .where(
                        SyncLog.store_id == store_id,
                        SyncLog.sync_type == "products_coupang_real",
                    )
                    .order_by(SyncLog.id.desc())
                ).first()
                assert latest_product_log is not None
                product_log_text = str(latest_product_log.raw_summary).lower()
                for forbidden in [
                    "phase-6c6a-access-key",
                    "phase-6c6a-secret-key",
                    "authorization",
                    "signature",
                    "token",
                ]:
                    assert forbidden not in product_log_text, product_log_text

            today_sales = client.post("/api/v1/sync/sales/coupang/preview", json={
                "store_id": store_id,
                "start_date": "2026-07-01",
                "end_date": "2026-07-01",
                "max_pages": 1,
            })
            assert today_sales.status_code == 400, today_sales.text
            assert today_sales.json()["error_code"] == "SALES_DATE_NOT_AVAILABLE", today_sales.text

            financial_paths_seen = []

            def fake_coupang_financial_get(credential, path, query_string):
                query = parse_qs(query_string)
                financial_paths_seen.append((path, query))
                request = httpx.Request("GET", f"https://example.invalid{path}?{query_string}")
                if "revenue-history" in path:
                    assert query["vendorId"] == ["phase-6c6a-vendor"], query
                    assert query["recognitionDateFrom"] == ["2026-06-29"], query
                    assert query["recognitionDateTo"] == ["2026-06-30"], query
                    assert query["maxPerPage"] == ["50"], query
                    if query.get("token") == ["token-2"]:
                        return httpx.Response(
                            200,
                            request=request,
                            json={"data": [{"revenueId": "sales-row-002", "recognitionDate": "2026-06-30", "saleAmount": "2000"}]},
                        )
                    return httpx.Response(
                        200,
                        request=request,
                        json={
                            "data": [
                                {
                                    "revenueId": "sales-row-001",
                                    "recognitionDate": "2026-06-29",
                                    "saleAmount": "1000",
                                    "authorization": "must-not-be-saved",
                                    "signature": "must-not-be-saved",
                                }
                            ],
                            "nextToken": "token-2",
                        },
                    )
                if "settlement-histories" in path:
                    month = query["revenueRecognitionYearMonth"][0]
                    return httpx.Response(
                        200,
                        request=request,
                        json={
                            "data": [
                                {
                                    "settlementId": f"settlement-{month}",
                                    "revenueRecognitionYearMonth": month,
                                    "settlementAmount": "7000",
                                    "bankAccountHolder": "masked holder",
                                    "bankName": "masked bank",
                                    "bankAccount": "***1234",
                                    "token": "must-not-be-saved",
                                }
                            ]
                        },
                    )
                raise AssertionError(f"Unexpected financial path: {path}")

            original_get = sync_service._coupang_get_with_credential
            sync_service._coupang_get_with_credential = fake_coupang_financial_get
            try:
                sales_preview = client.post("/api/v1/sync/sales/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-29",
                    "end_date": "2026-06-30",
                    "max_pages": 3,
                })
                settlement_preview = client.post("/api/v1/sync/settlements/coupang/preview", json={
                    "store_id": store_id,
                    "start_date": "2026-06-29",
                    "end_date": "2026-07-01",
                })
            finally:
                sync_service._coupang_get_with_credential = original_get

            assert sales_preview.status_code == 200, sales_preview.text
            sales_data = sales_preview.json()["data"]
            assert sales_data["sync_type"] == "sales_coupang_real_preview", sales_data
            assert sales_data["total_rows"] == 2, sales_data
            assert sales_data["page_count"] == 2, sales_data
            assert sales_data["next_cursor_exists"] is False, sales_data
            assert set(sales_data["sample_ids"]) == {"sales-row-001", "sales-row-002"}, sales_data
            assert sales_data["summary_totals"]["saleAmount"] == "3000", sales_data
            sales_text = str(sales_data).lower()
            for forbidden in ["authorization", "signature", "token-2", "must-not-be-saved"]:
                assert forbidden not in sales_text, sales_text

            assert settlement_preview.status_code == 200, settlement_preview.text
            settlement_data = settlement_preview.json()["data"]
            assert settlement_data["sync_type"] == "settlements_coupang_real_preview", settlement_data
            assert settlement_data["months"] == ["2026-06", "2026-07"], settlement_data
            assert settlement_data["total_rows"] == 2, settlement_data
            assert settlement_data["page_count"] == 2, settlement_data
            assert settlement_data["month_semantic_notice"], settlement_data
            assert settlement_data["field_mapping_suggestion"]["excluded_fields"] == ["bankAccountHolder", "bankName", "bankAccount"], settlement_data
            settlement_sample_text = str(settlement_data["sample_rows"]).lower()
            for forbidden in ["bankaccountholder", "bankname", "bankaccount", "masked holder", "masked bank", "***1234", "token", "must-not-be-saved"]:
                assert forbidden not in settlement_sample_text, settlement_sample_text

            with SessionLocal() as db:
                latest_sales_log = db.scalars(
                    select(SyncLog)
                    .where(
                        SyncLog.store_id == store_id,
                        SyncLog.sync_type == "sales_coupang_real_preview",
                    )
                    .order_by(SyncLog.id.desc())
                ).first()
                latest_settlement_log = db.scalars(
                    select(SyncLog)
                    .where(
                        SyncLog.store_id == store_id,
                        SyncLog.sync_type == "settlements_coupang_real_preview",
                    )
                    .order_by(SyncLog.id.desc())
                ).first()
                assert latest_sales_log is not None
                assert latest_sales_log.status == "success", latest_sales_log
                assert latest_settlement_log is not None
                assert latest_settlement_log.status == "success", latest_settlement_log
                combined_financial_log_text = f"{latest_sales_log.raw_summary} {latest_settlement_log.raw_summary}".lower()
                for forbidden in [
                    "phase-6c6a-access-key",
                    "phase-6c6a-secret-key",
                    "authorization",
                    "signature",
                    "token-2",
                    "bankaccountholder",
                    "bankname",
                    "bankaccount",
                    "masked holder",
                    "masked bank",
                    "***1234",
                    "must-not-be-saved",
                ]:
                    assert forbidden not in combined_financial_log_text, combined_financial_log_text
    finally:
        if original_test_enabled is None:
            os.environ.pop("REAL_API_TEST_ENABLED", None)
        else:
            os.environ["REAL_API_TEST_ENABLED"] = original_test_enabled
        app_config.get_settings.cache_clear()

    print("sync preview schema/security: ok")


def verify_kst_business_timezone() -> None:
    from fastapi.testclient import TestClient

    from app.core.timezone import get_business_date, get_business_day_range, get_business_timezone, get_utc_now, to_business_timezone
    from app.database import SessionLocal
    from app.main import app
    from app.models.order import Order

    assert get_business_timezone().key == "Asia/Seoul"
    assert get_business_date() == get_utc_now().astimezone(get_business_timezone()).date()
    start, end = get_business_day_range("2026-06-30")
    assert start.isoformat() == "2026-06-29T15:00:00+00:00", start
    assert end.isoformat() == "2026-06-30T15:00:00+00:00", end

    for path in (BACKEND_DIR / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern, suggestion in FORBIDDEN_TIME_PATTERNS.items():
            assert pattern not in text, f"{pattern} found in {path}; {suggestion}"

    with TestClient(app) as client:
        suffix = uuid.uuid4().hex[:8]
        store = client.post("/api/v1/stores", json={
            "name": f"Phase 6B-0A KST Time Store {suffix}",
            "platform": "naver",
            "country": "KR",
            "language": "ko-KR",
            "status": "active",
        })
        assert store.status_code == 201, store.text
        store_id = store.json()["data"]["id"]

        with SessionLocal() as db:
            db.add_all([
                Order(
                    store_id=store_id,
                    platform="naver",
                    external_order_id=f"kst-prev-{suffix}",
                    buyer_name="KST boundary buyer",
                    buyer_masked_phone="010-****-0001",
                    product_name="KST previous day order",
                    quantity=1,
                    order_amount=Decimal("1000.00"),
                    currency="KRW",
                    order_status="paid",
                    paid_at=datetime(2026, 6, 29, 14, 59, tzinfo=timezone.utc),
                    ordered_at=datetime(2026, 6, 29, 14, 59, tzinfo=timezone.utc),
                    raw_data={"source": "verify_kst_business_timezone"},
                ),
                Order(
                    store_id=store_id,
                    platform="naver",
                    external_order_id=f"kst-current-{suffix}",
                    buyer_name="KST boundary buyer",
                    buyer_masked_phone="010-****-0002",
                    product_name="KST current day order",
                    quantity=1,
                    order_amount=Decimal("2000.00"),
                    currency="KRW",
                    order_status="paid",
                    paid_at=datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc),
                    ordered_at=datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc),
                    raw_data={"source": "verify_kst_business_timezone"},
                ),
            ])
            db.commit()

        by_date = client.get(f"/api/v1/stats/sales/by-date?store_id={store_id}&start_date=2026-06-29&end_date=2026-06-30")
        assert by_date.status_code == 200, by_date.text
        grouped = {item["date"]: item for item in by_date.json()["data"]["items"]}
        assert grouped["2026-06-29"]["total_sales_amount"] == "1000.00", grouped
        assert grouped["2026-06-30"]["total_sales_amount"] == "2000.00", grouped

        daily_sales = client.get(f"/api/v1/stats/sales?store_id={store_id}&start_date=2026-06-30&end_date=2026-06-30")
        assert daily_sales.status_code == 200, daily_sales.text
        assert daily_sales.json()["data"]["total_orders"] == 1, daily_sales.text
        assert daily_sales.json()["data"]["total_sales_amount"] == "2000.00", daily_sales.text

        dashboard = client.get(f"/api/v1/dashboard/summary?store_id={store_id}")
        assert dashboard.status_code == 200, dashboard.text
        dashboard_data = dashboard.json()["data"]
        assert dashboard_data["business_timezone"] == "Asia/Seoul", dashboard_data
        assert "business_day_start" in dashboard_data and "business_day_end" in dashboard_data
        assert "api_capability_summary" in dashboard_data

        context = client.get(f"/api/v1/ai/daily-context?store_id={store_id}")
        assert context.status_code == 200, context.text
        context_data = context.json()["data"]
        assert context_data["date"] == get_business_date().isoformat(), context_data
        assert context_data["business_timezone"] == "Asia/Seoul", context_data
        assert context_data["business_day_start"] == get_business_day_range(get_business_date())[0].isoformat()
        assert "api_capability_context" in context_data

        converted = to_business_timezone(datetime(2026, 6, 29, 15, 0, tzinfo=timezone.utc))
        assert converted.date() == date(2026, 6, 30), converted

    print("KST business timezone: ok")


def verify_git_tracking() -> None:
    tracked = run(["git", "ls-files"], cwd=ROOT_DIR, echo=False).splitlines()
    forbidden = [
        path
        for path in tracked
        if any(pattern in path for pattern in FORBIDDEN_TRACKED_PATTERNS)
        and path != "backend/.env.example"
    ]
    assert not forbidden, f"Forbidden tracked files: {forbidden}"
    status = run(["git", "status", "--short"], cwd=ROOT_DIR, echo=False)
    allowed_prefixes = (
        " M backend/README.md",
        " M backend/.env.example",
        " M backend/app/api/v1/router.py",
        " M backend/app/api/v1/endpoints/api_capabilities.py",
        " M backend/app/api/v1/endpoints/api_credential_readiness.py",
        " M backend/app/api/v1/endpoints/sync.py",
        " M backend/app/config.py",
        " M backend/app/database.py",
        " M backend/app/models/__init__.py",
        " M backend/app/models/api_credential.py",
        " M backend/app/models/order.py",
        " M backend/app/models/product.py",
        " M backend/app/models/store.py",
        " M backend/app/schemas/credential.py",
        " M backend/app/schemas/order.py",
        " M backend/app/schemas/product.py",
        " M backend/app/schemas/sync.py",
        " M backend/app/services/stats_service.py",
        " M backend/app/services/api_capability_service.py",
        " M backend/app/services/api_credential_readiness_service.py",
        " M backend/app/services/credential_service.py",
        " M backend/app/services/sync_service.py",
        " M backend/docs/",
        " M backend/requirements.txt",
        " M backend/scripts/verify_all.py",
        " M backend/scripts/verify_stage_1e.py",
        " M backend/scripts/upgrade_sync_schema.py",
        "?? backend/app/core/timezone.py",
        "?? backend/app/api/v1/endpoints/api_capabilities.py",
        "?? backend/app/api/v1/endpoints/api_credential_readiness.py",
        "?? backend/app/models/api_capability.py",
        "?? backend/app/models/financial.py",
        "?? backend/app/models/sync_checkpoint.py",
        "?? backend/app/schemas/api_credential_readiness.py",
        "?? backend/app/schemas/api_capability.py",
        "?? backend/app/schemas/sync.py",
        "?? backend/app/services/api_capability_service.py",
        "?? backend/app/services/api_credential_readiness_service.py",
        "?? backend/app/api/v1/endpoints/platform_logins.py",
        "?? backend/app/models/platform_login_credential.py",
        "?? backend/app/schemas/platform_login.py",
        "?? backend/app/services/platform_login_service.py",
        "?? backend/docs/",
        "?? backend/scripts/upgrade_api_credentials_schema.py",
        "?? backend/scripts/upgrade_sync_schema.py",
        "?? backend/scripts/verify_all.py",
    )
    unexpected = [line for line in status.splitlines() if not line.startswith(allowed_prefixes)]
    assert not unexpected, f"Unexpected git status lines: {unexpected}"
    print("git tracking: ok")


def verify_docs_no_real_secrets() -> None:
    docs = list((BACKEND_DIR / "docs").glob("*.md")) + [BACKEND_DIR / "README.md"]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_DOC_PATTERNS:
            assert pattern not in text, f"Forbidden pattern {pattern} found in {path}"
    print("docs secret scan: ok")


def cleanup_verify_database() -> None:
    try:
        from app.database import engine

        engine.dispose()
    except Exception:
        pass

    removed: list[Path] = []
    retained: list[Path] = []
    for path in (VERIFY_DB_PATH, VERIFY_DB_PATH.with_suffix(VERIFY_DB_PATH.suffix + "-wal"), VERIFY_DB_PATH.with_suffix(VERIFY_DB_PATH.suffix + "-shm")):
        if not path.exists():
            continue
        try:
            path.unlink()
            removed.append(path)
        except PermissionError:
            retained.append(path)

    if removed:
        print("verify_all database removed: " + ", ".join(str(path) for path in removed))
    if retained:
        print("verify_all database retained outside project: " + ", ".join(str(path) for path in retained))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"verify_all database: {VERIFY_DB_PATH}")
    try:
        verify_compile()
        verify_stage_scripts()
        verify_openapi()
        verify_api_credential_schema_and_security()
        verify_api_credential_readiness()
        verify_api_capabilities()
        verify_sync_preview_schema_and_security()
        verify_kst_business_timezone()
        verify_git_tracking()
        verify_docs_no_real_secrets()
        print("verify_all: ok")
    finally:
        cleanup_verify_database()


if __name__ == "__main__":
    main()
