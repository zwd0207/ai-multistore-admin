import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services import sync_log_service


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


NAVER_ACCESS_KEY = "stage-1e-naver-access-token"
NAVER_SECRET_KEY = "stage-1e-naver-secret-token"
COUPANG_ACCESS_KEY = "stage-1e-coupang-access-token"
COUPANG_SECRET_KEY = "stage-1e-coupang-secret-token"
FULL_PHONE_CANDIDATES = ["010-1111-1234", "010-2222-5678", "010-3333-9012"]


def assert_no_secret(payload: object) -> None:
    serialized = str(payload)
    for secret in [NAVER_ACCESS_KEY, NAVER_SECRET_KEY, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY]:
        assert secret not in serialized, serialized


def assert_no_full_phone(payload: object) -> None:
    serialized = str(payload)
    for phone in FULL_PHONE_CANDIDATES:
        assert phone not in serialized, serialized


def assert_success(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["success"] is True, payload
    assert_no_secret(payload)
    assert_no_full_phone(payload)
    return payload


def create_store_and_credentials(client: TestClient) -> int:
    store = assert_success(
        client.post(
            "/api/v1/stores",
            json={
                "name": "1E Dashboard AI Context Store",
                "platform": "naver",
                "country": "KR",
                "language": "mixed",
                "status": "active",
                "owner_name": "统计测试负责人",
                "remark": "销售统计 / 대시보드 / AI context 测试",
            },
        ),
        expected_status=201,
    )
    store_id = store["data"]["id"]

    assert_success(
        client.post(
            "/api/v1/credentials",
            json={
                "store_id": store_id,
                "platform": "naver",
                "credential_name": "1E Naver mock credential",
                "access_key": NAVER_ACCESS_KEY,
                "secret_key": NAVER_SECRET_KEY,
                "extra_config": {"用途": "统计测试", "한국어": "통계 테스트"},
                "status": "active",
            },
        ),
        expected_status=201,
    )
    assert_success(
        client.post(
            "/api/v1/credentials",
            json={
                "store_id": store_id,
                "platform": "coupang",
                "credential_name": "1E Coupang mock credential",
                "access_key": COUPANG_ACCESS_KEY,
                "secret_key": COUPANG_SECRET_KEY,
                "extra_config": {"用途": "统计测试", "한국어": "통계 테스트"},
                "status": "active",
            },
        ),
        expected_status=201,
    )
    return store_id


def prepare_data(client: TestClient, store_id: int) -> None:
    assert_success(client.post(f"/api/v1/sync/products/mock?store_id={store_id}&platform=naver"))
    assert_success(client.post(f"/api/v1/sync/orders/mock?store_id={store_id}&platform=naver"))
    assert_success(client.post(f"/api/v1/sync/customer-inquiries/mock?store_id={store_id}&platform=naver"))
    with SessionLocal() as db:
        failed = sync_log_service.create_sync_log(
            db,
            store_id=store_id,
            platform="naver",
            sync_type="mock",
            message="中文失败日志：用于 dashboard risk flag",
            raw_summary={"한국어": "실패 위험 플래그", "中文": "失败风险标记"},
        )
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=failed["id"],
            message="한글 실패 로그: dashboard 확인",
            error_detail="模拟失败 / 모의 실패",
            raw_summary={"中文": "同步失败", "한국어": "동기화 실패"},
        )


def main() -> None:
    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:
        store_id = create_store_and_credentials(client)
        prepare_data(client, store_id)

        sales = assert_success(client.get(f"/api/v1/stats/sales?store_id={store_id}"))
        assert sales["data"]["total_orders"] == 3, sales
        assert sales["data"]["paid_orders"] == 3, sales
        assert sales["data"]["total_sales_amount"] == "916000.00", sales
        assert sales["data"]["currency"] == "KRW", sales

        by_platform = assert_success(client.get(f"/api/v1/stats/sales/by-platform?store_id={store_id}"))
        assert by_platform["data"]["total"] == 1, by_platform
        assert by_platform["data"]["items"][0]["platform"] == "naver", by_platform

        by_date = assert_success(client.get(f"/api/v1/stats/sales/by-date?store_id={store_id}"))
        assert by_date["data"]["total"] >= 1, by_date

        dashboard = assert_success(client.get(f"/api/v1/dashboard/summary?store_id={store_id}"))
        data = dashboard["data"]
        assert data["store_count"] == 1, dashboard
        assert data["product_count"] == 3, dashboard
        assert data["order_count"] == 3, dashboard
        assert data["customer_inquiry_count"] == 3, dashboard
        assert data["open_customer_inquiries"] == 3, dashboard
        assert data["total_sales_amount"] == "916000.00", dashboard
        assert len(data["latest_sync_logs"]) <= 5, dashboard
        assert len(data["recent_orders"]) <= 5, dashboard
        risk_codes = {item["code"] for item in data["risk_flags"]}
        assert "FAILED_SYNC_LOG" in risk_codes, dashboard
        assert "OPEN_CUSTOMER_INQUIRIES" in risk_codes, dashboard
        assert "한글 실패 로그" in str(dashboard), dashboard
        assert "ECCO 골프화 / 中文运营测试" in str(dashboard), dashboard
        assert "010-****-1234" in str(dashboard), dashboard
        assert "010-****-5678" in str(dashboard), dashboard
        assert "010-****-9012" in str(dashboard), dashboard

        context = assert_success(client.get(f"/api/v1/ai/daily-context?store_id={store_id}&date=2026-06-29"))
        context_data = context["data"]
        assert context_data["date"] == "2026-06-29", context
        assert context_data["scope"]["store_id"] == store_id, context
        assert context_data["sales_summary"]["total_orders"] == 3, context
        assert context_data["order_summary"]["recent_orders"], context
        assert context_data["customer_inquiry_summary"]["open"] == 3, context
        assert context_data["sync_summary"]["failed_count"] >= 1, context
        focus_codes = {item["code"] for item in context_data["recommended_focus"]}
        assert "CHECK_OPEN_INQUIRIES" in focus_codes, context
        assert "CHECK_SYNC_FAILURES" in focus_codes, context
        assert "AUTHENTICITY_INQUIRIES" in focus_codes, context
        assert "检查未处理客服咨询" in str(context), context
        assert "정품 소명 문의 처리" in str(context), context
        assert "010-****-1234" in str(context), context

        missing_store = client.get("/api/v1/dashboard/summary?store_id=999999")
        assert missing_store.status_code == 404, missing_store.text
        assert missing_store.json()["success"] is False, missing_store.text
        assert missing_store.json()["error_code"] == "STORE_NOT_FOUND", missing_store.text

        invalid_date = client.get(f"/api/v1/stats/sales?store_id={store_id}&start_date=2026-99-99")
        assert invalid_date.status_code == 400, invalid_date.text
        assert invalid_date.json()["error_code"] == "INVALID_DATE_FORMAT", invalid_date.text

        empty_store = assert_success(
            client.post(
                "/api/v1/stores",
                json={
                    "name": "1E Empty Store",
                    "platform": "coupang",
                    "country": "KR",
                    "language": "mixed",
                    "status": "active",
                    "owner_name": "空数据测试",
                    "remark": "无订单 / 주문 없음",
                },
            ),
            expected_status=201,
        )
        empty_store_id = empty_store["data"]["id"]
        empty_sales = assert_success(client.get(f"/api/v1/stats/sales?store_id={empty_store_id}"))
        assert empty_sales["data"]["total_orders"] == 0, empty_sales
        assert empty_sales["data"]["total_sales_amount"] == "0.00", empty_sales
        empty_context = assert_success(client.get(f"/api/v1/ai/daily-context?store_id={empty_store_id}"))
        assert empty_context["data"]["order_summary"]["total_orders"] == 0, empty_context

    print("stage 1E verification ok")
    print("GET /api/v1/stats/sales: total_orders=3 total_sales_amount=916000.00")
    print("GET /api/v1/dashboard/summary: product/order/inquiry/sales counts ok")
    print("dashboard latest_sync_logs <= 5 and recent_orders <= 5: ok")
    print("risk_flags: FAILED_SYNC_LOG and OPEN_CUSTOMER_INQUIRIES generated")
    print("GET /api/v1/ai/daily-context: structured context ok, no model call")
    print("UTF-8: ECCO 골프화 / 中文运营测试, 한글 실패 로그, 检查未处理客服咨询")
    print("security: no plaintext credentials, no full buyer phones")


if __name__ == "__main__":
    main()
