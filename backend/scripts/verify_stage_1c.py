import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.clients.coupang_client import CoupangClient
from app.clients.naver_client import NaverClient
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.api_credential import ApiCredential
from app.schemas.credential import CredentialCreate
from app.services import credential_service, sync_log_service


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


NAVER_ACCESS_KEY = "naver-test-access-key"
NAVER_SECRET_KEY = "naver-test-secret-key"
COUPANG_ACCESS_KEY = "coupang-test-access-key"
COUPANG_SECRET_KEY = "coupang-test-secret-key"


def assert_success(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["success"] is True, payload
    return payload


def assert_no_plain_secret(payload: dict) -> None:
    serialized = str(payload)
    for secret in [NAVER_ACCESS_KEY, NAVER_SECRET_KEY, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY]:
        assert secret not in serialized, serialized


def main() -> None:
    generated_key = os.environ["CREDENTIAL_ENCRYPTION_KEY"]
    assert generated_key and len(generated_key) > 20

    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:
        health = assert_success(client.get("/api/v1/health"))
        assert health["data"]["status"] == "ok", health

        store = assert_success(
            client.post(
                "/api/v1/stores",
                json={
                    "name": "1C凭证测试店",
                    "platform": "naver",
                    "country": "KR",
                    "language": "mixed",
                    "status": "active",
                    "owner_name": "加密测试负责人",
                    "remark": "凭证测试 / 자격 증명 테스트 / 中文+韩文",
                },
            ),
            expected_status=201,
        )
        store_id = store["data"]["id"]

        naver = assert_success(
            client.post(
                "/api/v1/credentials",
                json={
                    "store_id": store_id,
                    "platform": "naver",
                    "credential_name": "Naver mock credential",
                    "access_key": NAVER_ACCESS_KEY,
                    "secret_key": NAVER_SECRET_KEY,
                    "extra_config": {"allowed_ip": "127.0.0.1", "备注": "네이버 테스트"},
                    "status": "active",
                },
            ),
            expected_status=201,
        )
        naver_id = naver["data"]["id"]
        assert naver["data"]["has_access_key"] is True, naver
        assert naver["data"]["has_secret_key"] is True, naver
        assert_no_plain_secret(naver)

        coupang = assert_success(
            client.post(
                "/api/v1/credentials",
                json={
                    "store_id": store_id,
                    "platform": "coupang",
                    "credential_name": "Coupang mock credential",
                    "access_key": COUPANG_ACCESS_KEY,
                    "secret_key": COUPANG_SECRET_KEY,
                    "extra_config": {"market": "KR", "비고": "쿠팡 테스트"},
                    "status": "active",
                },
            ),
            expected_status=201,
        )
        coupang_id = coupang["data"]["id"]
        assert_no_plain_secret(coupang)

        invalid_platform = client.post(
            "/api/v1/credentials",
            json={
                "store_id": store_id,
                "platform": "unsupported",
                "credential_name": "Invalid platform credential",
                "access_key": "invalid-access-key",
                "secret_key": "invalid-secret-key",
                "status": "active",
            },
        )
        assert invalid_platform.status_code == 422, invalid_platform.text
        assert invalid_platform.json()["error_code"] == "VALIDATION_ERROR", invalid_platform.text

        listing = assert_success(client.get(f"/api/v1/credentials?store_id={store_id}"))
        assert listing["data"]["total"] == 2, listing
        assert_no_plain_secret(listing)

        missing_store_credentials = client.get("/api/v1/credentials?store_id=999999")
        assert missing_store_credentials.status_code == 404, missing_store_credentials.text
        assert missing_store_credentials.json()["error_code"] == "STORE_NOT_FOUND", missing_store_credentials.text

        single = assert_success(client.get(f"/api/v1/credentials/{naver_id}"))
        assert single["data"]["credential_name"] == "Naver mock credential", single
        assert_no_plain_secret(single)

        updated = assert_success(
            client.put(
                f"/api/v1/credentials/{naver_id}",
                json={
                    "credential_name": "Naver mock credential updated",
                    "access_key": "naver-test-access-key-updated",
                    "secret_key": "naver-test-secret-key-updated",
                    "extra_config": {"allowed_ip": "127.0.0.1", "备注": "수정됨"},
                },
            )
        )
        assert updated["data"]["credential_name"] == "Naver mock credential updated", updated
        assert "naver-test-access-key-updated" not in str(updated), updated
        assert "naver-test-secret-key-updated" not in str(updated), updated

    with SessionLocal() as db:
        credentials = db.scalars(select(ApiCredential).order_by(ApiCredential.id.asc())).all()
        encrypted_values = [
            value
            for credential in credentials
            for value in [credential.encrypted_access_key, credential.encrypted_secret_key]
            if value
        ]
        for encrypted_value in encrypted_values:
            for plain_value in [
                NAVER_ACCESS_KEY,
                NAVER_SECRET_KEY,
                COUPANG_ACCESS_KEY,
                COUPANG_SECRET_KEY,
                "naver-test-access-key-updated",
                "naver-test-secret-key-updated",
            ]:
                assert plain_value not in encrypted_value, encrypted_value

        naver_decrypted = credential_service.get_decrypted_credential_for_internal_use(db, naver_id)
        coupang_decrypted = credential_service.get_decrypted_credential_for_internal_use(db, coupang_id)
        assert naver_decrypted.access_key == "naver-test-access-key-updated", naver_decrypted
        assert naver_decrypted.secret_key == "naver-test-secret-key-updated", naver_decrypted
        assert coupang_decrypted.access_key == COUPANG_ACCESS_KEY, coupang_decrypted
        assert coupang_decrypted.secret_key == COUPANG_SECRET_KEY, coupang_decrypted

        naver_client_result = NaverClient(naver_decrypted).test_connection()
        coupang_client_result = CoupangClient(coupang_decrypted).test_connection()
        assert naver_client_result["success"] is True, naver_client_result
        assert coupang_client_result["success"] is True, coupang_client_result
        assert "secret" not in str(naver_client_result).lower(), naver_client_result
        assert "secret" not in str(coupang_client_result).lower(), coupang_client_result

        chinese_log = sync_log_service.create_sync_log(
            db,
            store_id=store_id,
            platform="naver",
            sync_type="credentials_test",
            message="中文日志：凭证连接测试开始",
            raw_summary={"阶段": "开始", "说明": "中文 message 测试"},
        )
        korean_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=chinese_log["id"],
            message="한글 로그: 자격 증명 테스트 성공",
            raw_summary={"결과": "성공", "中文": "通过", "정품": "소명 자료"},
        )
        failed_log = sync_log_service.create_sync_log(
            db,
            store_id=store_id,
            platform="coupang",
            sync_type="mock",
            message="혼합 로그: Coupang 凭证 mock 시작",
            raw_summary={"中文": "订单", "한국어": "고객문의"},
        )
        failed_log = sync_log_service.fail_sync_log(
            db,
            sync_log_id=failed_log["id"],
            message="混合日志：mock 실패 / 中文失败",
            error_detail="错误详情：테스트 오류",
            raw_summary={"中文": "失败摘要", "한국어": "실패 요약"},
        )
        logs = sync_log_service.list_sync_logs(db, store_id=store_id)
        assert len(logs) == 2, logs
        assert korean_log["message"] == "한글 로그: 자격 증명 테스트 성공", korean_log
        assert failed_log["raw_summary"]["한국어"] == "실패 요약", failed_log

    with TestClient(app) as client:
        sync_logs = assert_success(client.get(f"/api/v1/sync-logs?store_id={store_id}"))
        assert sync_logs["data"]["total"] == 2, sync_logs
        assert "한글 로그" in str(sync_logs), sync_logs
        assert "失败摘要" in str(sync_logs), sync_logs

        deleted = assert_success(client.delete(f"/api/v1/credentials/{coupang_id}"))
        assert deleted["data"]["id"] == coupang_id, deleted
        assert_no_plain_secret(deleted)

    print("stage 1C verification ok")
    print("generated CREDENTIAL_ENCRYPTION_KEY: ok")
    print("backend startup with configured key: ok")
    print("POST /api/v1/credentials Naver: ok")
    print("POST /api/v1/credentials Coupang: ok")
    print("database plaintext access_key/secret_key check: ok")
    print("GET credentials plaintext response check: ok")
    print("internal decrypt service: ok")
    print(f"NaverClient.test_connection(): {naver_client_result}")
    print(f"CoupangClient.test_connection(): {coupang_client_result}")
    print("sync log Chinese message: 中文日志：凭证连接测试开始")
    print("sync log Korean message: 한글 로그: 자격 증명 테스트 성공")
    print("sync log mixed raw_summary: {'中文': '失败摘要', '한국어': '실패 요약'}")


if __name__ == "__main__":
    main()
