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

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.appeal_case import AppealCase
from app.models.device_environment import DeviceEnvironment
from app.models.email_account import EmailAccount
from app.models.important_email import ImportantEmail


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


EMAIL_TEST_TOKEN = "mock-email-token-stage-1f"
FORBIDDEN_VALUES = [
    EMAIL_TEST_TOKEN,
    "proxy-password",
    "remote-desktop-password",
    "123.123.123.123",
    "010-1111-2222",
    "서울시 강남구 실제주소",
    "900101-1234567",
    "4111-1111-1111-1111",
    "access_key",
    "secret_key",
]


def assert_no_sensitive(payload: object) -> None:
    serialized = str(payload)
    for value in FORBIDDEN_VALUES:
        assert value not in serialized, serialized


def assert_success(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["success"] is True, payload
    assert_no_sensitive(payload)
    return payload


def create_store(client: TestClient) -> int:
    store = assert_success(
        client.post(
            "/api/v1/stores",
            json={
                "name": "1F 환경 메일申诉 테스트店",
                "platform": "naver",
                "country": "KR",
                "language": "mixed",
                "status": "active",
                "owner_name": "1F测试负责人",
                "remark": "设备环境 / 메일 / 申诉案件 mock 测试",
            },
        ),
        expected_status=201,
    )
    return store["data"]["id"]


def main() -> None:
    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:
        store_id = create_store(client)

        device = assert_success(
            client.post(
                "/api/v1/device-environments",
                json={
                    "store_id": store_id,
                    "environment_name": "韩国本土运营环境-测试",
                    "device_type": "desktop",
                    "os_name": "Windows 10",
                    "browser_name": "Chrome",
                    "ip_label": "韩国住宅IP-测试",
                    "proxy_label": "Seoul Proxy Label",
                    "status": "active",
                    "remark": "用于 Naver / Coupang 店铺运营环境测试，不保存真实代理密码。",
                },
            ),
            expected_status=201,
        )
        device_id = device["data"]["id"]
        assert device["data"]["store_id"] == store_id, device
        assert "韩国住宅IP-测试" in str(device), device

        device_list = assert_success(client.get(f"/api/v1/device-environments?store_id={store_id}"))
        assert device_list["data"]["total"] == 1, device_list
        device_single = assert_success(client.get(f"/api/v1/device-environments/{device_id}"))
        assert device_single["data"]["environment_name"] == "韩国本土运营环境-测试", device_single
        device_updated = assert_success(
            client.put(
                f"/api/v1/device-environments/{device_id}",
                json={"remark": "수정된 비고 / 中文备注：仍不保存真实 IP 或代理密码"},
            )
        )
        assert "수정된 비고" in device_updated["data"]["remark"], device_updated

        email_account = assert_success(
            client.post(
                "/api/v1/email-accounts",
                json={
                    "store_id": store_id,
                    "email_address": "test-store@example.com",
                    "provider": "gmail",
                    "account_label": "Naver 正品申诉接收邮箱",
                    "password_or_token": EMAIL_TEST_TOKEN,
                    "status": "active",
                    "remark": "네이버 정품 소명 / Coupang 정산 보류 메일 수신 테스트",
                },
            ),
            expected_status=201,
        )
        email_account_id = email_account["data"]["id"]
        assert email_account["data"]["has_password_or_token"] is True, email_account
        assert "encrypted_password_or_token" not in str(email_account), email_account
        email_list = assert_success(client.get(f"/api/v1/email-accounts?store_id={store_id}"))
        assert email_list["data"]["total"] == 1, email_list
        email_single = assert_success(client.get(f"/api/v1/email-accounts/{email_account_id}"))
        assert "정품 소명" in email_single["data"]["remark"], email_single

        important_email = assert_success(
            client.post(
                "/api/v1/important-emails",
                json={
                    "store_id": store_id,
                    "email_account_id": email_account_id,
                    "platform": "naver",
                    "mail_type": "authenticity",
                    "sender": "no-reply@mock.naver.test",
                    "subject": "정품 소명 자료 제출 안내",
                    "snippet": "카드명세서와 구매영수증 제출이 필요합니다.",
                    "body_text": "Naver 正品申诉 / 정품 소명 자료 / 中文运营备注",
                    "received_at": "2026-06-29T10:00:00+00:00",
                    "status": "unread",
                    "priority": "urgent",
                    "raw_data": {"中文": "重点邮件", "한국어": "중요 메일"},
                },
            ),
            expected_status=201,
        )
        important_email_id = important_email["data"]["id"]
        assert "정품 소명 자료 제출 안내" in important_email["data"]["subject"], important_email
        assert "中文运营备注" in important_email["data"]["body_text"], important_email
        important_list = assert_success(client.get(f"/api/v1/important-emails?store_id={store_id}"))
        assert important_list["data"]["total"] == 1, important_list
        important_updated = assert_success(
            client.put(
                f"/api/v1/important-emails/{important_email_id}",
                json={"status": "processed", "snippet": "수정된 스니펫 / 中文摘要"},
            )
        )
        assert important_updated["data"]["status"] == "processed", important_updated

        appeal_case = assert_success(
            client.post(
                "/api/v1/appeal-cases",
                json={
                    "store_id": store_id,
                    "platform": "coupang",
                    "case_type": "settlement_hold",
                    "case_title": "Coupang 结算扣款申诉测试",
                    "case_status": "preparing",
                    "external_case_id": "MOCK-CASE-001",
                    "summary": "Coupang 정산 보류 / 销售资料准备 / 中文备注",
                    "action_required": "准备采购表、销售明细、沟通邮件",
                    "raw_data": {"中文": "申诉案件", "한국어": "정산 보류"},
                },
            ),
            expected_status=201,
        )
        case_id = appeal_case["data"]["id"]
        assert "정산 보류" in appeal_case["data"]["summary"], appeal_case
        assert "准备采购表" in appeal_case["data"]["action_required"], appeal_case
        appeal_list = assert_success(client.get(f"/api/v1/appeal-cases?store_id={store_id}"))
        assert appeal_list["data"]["total"] == 1, appeal_list
        appeal_single = assert_success(client.get(f"/api/v1/appeal-cases/{case_id}"))
        assert appeal_single["data"]["external_case_id"] == "MOCK-CASE-001", appeal_single
        appeal_updated = assert_success(
            client.put(
                f"/api/v1/appeal-cases/{case_id}",
                json={"case_status": "waiting", "summary": "업데이트됨 / 中文更新备注"},
            )
        )
        assert appeal_updated["data"]["case_status"] == "waiting", appeal_updated

        missing_store = client.get("/api/v1/email-accounts?store_id=999999")
        assert missing_store.status_code == 404, missing_store.text
        assert missing_store.json()["success"] is False, missing_store.text
        assert missing_store.json()["error_code"] == "STORE_NOT_FOUND", missing_store.text

    with SessionLocal() as db:
        devices = db.scalars(select(DeviceEnvironment)).all()
        email_accounts = db.scalars(select(EmailAccount)).all()
        important_emails = db.scalars(select(ImportantEmail)).all()
        appeal_cases = db.scalars(select(AppealCase)).all()

        assert devices and all(item.store_id == store_id for item in devices), devices
        assert email_accounts and all(item.store_id == store_id for item in email_accounts), email_accounts
        assert important_emails and all(item.store_id == store_id for item in important_emails), important_emails
        assert appeal_cases and all(item.store_id == store_id for item in appeal_cases), appeal_cases

        encrypted_value = email_accounts[0].encrypted_password_or_token
        assert encrypted_value and EMAIL_TEST_TOKEN not in encrypted_value, encrypted_value
        assert_no_sensitive(devices)
        assert_no_sensitive(important_emails)
        assert_no_sensitive(appeal_cases)

    print("stage 1F verification ok")
    print("device environment: 韩国本土运营环境-测试 / 한국 주거 IP label only")
    print("email account: token encrypted and never returned")
    print("important email: 정품 소명 자료 제출 안내 / Naver 正品申诉 / 中文运营备注")
    print("appeal case: Coupang 정산 보류 / 销售资料准备 / 中文备注")
    print("security: no plaintext email token, no platform keys, no full IP/proxy password/privacy data")


if __name__ == "__main__":
    main()
