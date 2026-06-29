import subprocess
import sys
import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
PYTHON = sys.executable

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

GIT_CMD_DIR = Path("C:/Program Files/Git/cmd")
if GIT_CMD_DIR.exists():
    os.environ["PATH"] = f"{GIT_CMD_DIR}{os.pathsep}{os.environ.get('PATH', '')}"

EXPECTED_API_PATHS = {
    "/api/v1/health",
    "/api/v1/stores",
    "/api/v1/stores/{store_id}",
    "/api/v1/credentials",
    "/api/v1/credentials/{credential_id}",
    "/api/v1/platform-logins",
    "/api/v1/platform-logins/{login_id}",
    "/api/v1/sync-logs",
    "/api/v1/products",
    "/api/v1/orders",
    "/api/v1/customer-inquiries",
    "/api/v1/sync/products/mock",
    "/api/v1/sync/orders/mock",
    "/api/v1/sync/customer-inquiries/mock",
    "/api/v1/stats/sales",
    "/api/v1/stats/sales/by-platform",
    "/api/v1/stats/sales/by-date",
    "/api/v1/dashboard/summary",
    "/api/v1/ai/daily-context",
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
        store = client.post("/api/v1/stores", json={
            "name": "Phase 6A-3 Credential Verify Store",
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
        " M backend/app/api/v1/router.py",
        " M backend/app/models/api_credential.py",
        " M backend/app/models/__init__.py",
        " M backend/app/models/store.py",
        " M backend/app/schemas/credential.py",
        " M backend/app/services/credential_service.py",
        " M backend/docs/",
        " M backend/scripts/verify_all.py",
        "?? backend/app/api/v1/endpoints/platform_logins.py",
        "?? backend/app/models/platform_login_credential.py",
        "?? backend/app/schemas/platform_login.py",
        "?? backend/app/services/platform_login_service.py",
        "?? backend/docs/",
        "?? backend/scripts/upgrade_api_credentials_schema.py",
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    verify_compile()
    verify_stage_scripts()
    verify_openapi()
    verify_api_credential_schema_and_security()
    verify_git_tracking()
    verify_docs_no_real_secrets()
    print("verify_all: ok")


if __name__ == "__main__":
    main()
