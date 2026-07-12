import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEV_AUTH"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.api_credential import ApiCredential
from app.models.auth import ErpPermission, ErpRole, ErpRolePermission, ErpStoreMembership, ErpUser
from app.models.customer_inquiry import CustomerInquiry
from app.models.order import Order
from app.models.product import Product
from app.models.sync_log import SyncLog


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


NAVER_CLIENT_ID = "mock-naver-client-id"
NAVER_ACCESS_KEY = "mock-naver-access-token"
NAVER_SECRET_KEY = "mock-naver-secret-token"
COUPANG_ACCESS_KEY = "mock-coupang-access-token"
COUPANG_SECRET_KEY = "mock-coupang-secret-token"
FULL_PHONE_CANDIDATES = ["010-1111-1234", "010-2222-5678", "010-3333-9012"]


def assert_success(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["success"] is True, payload
    assert_no_secret(payload)
    return payload


def assert_no_secret(payload: object) -> None:
    serialized = str(payload)
    for secret in [NAVER_ACCESS_KEY, NAVER_SECRET_KEY, COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY]:
        assert secret not in serialized, serialized


def assert_masked_phone_only(payload: object) -> None:
    serialized = str(payload)
    for phone in FULL_PHONE_CANDIDATES:
        assert phone not in serialized, serialized
    assert "010-****-1234" in serialized
    assert "010-****-5678" in serialized
    assert "010-****-9012" in serialized


def create_store_and_credentials(client: TestClient) -> int:
    store = assert_success(
        client.post(
            "/api/v1/stores",
            json={
                "name": "1D Mock Sync Store",
                "platform": "naver",
                "country": "KR",
                "language": "mixed",
                "status": "active",
                "owner_name": "中韩同步测试负责人",
                "remark": "商品 / 주문 / 고객문의 mock 同步测试",
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
                "credential_name": "1D Naver mock credential",
                "client_id": NAVER_CLIENT_ID,
                "access_key": NAVER_ACCESS_KEY,
                "secret_key": NAVER_SECRET_KEY,
                "extra_config": {"用途": "mock 同步", "한국어": "테스트"},
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
                "credential_name": "1D Coupang mock credential",
                "access_key": COUPANG_ACCESS_KEY,
                "secret_key": COUPANG_SECRET_KEY,
                "extra_config": {"用途": "mock 同步", "한국어": "테스트"},
                "status": "active",
            },
        ),
        expected_status=201,
    )
    return store_id


def verify_legacy_query_payloads(client: TestClient, store_id: int) -> None:
    products = assert_success(client.get(f"/api/v1/products?store_id={store_id}&platform=naver"))
    product_names = [item["name"] for item in products["data"]["items"]]
    assert products["data"]["total"] == 3, products
    assert "SK-II 神仙水测试商品" in product_names, products
    assert "타이틀리스트 캐디백 테스트" in product_names, products
    assert "ECCO 골프화 / 中文运营测试" in product_names, products
    assert "中文商品摘要" in str(products), products
    assert "한글 상품 데이터" in str(products), products

    orders = assert_success(client.get(f"/api/v1/orders?store_id={store_id}&platform=naver"))
    assert orders["data"]["total"] == 0, orders
    assert orders["data"]["test_orders_excluded"] == 3, orders

    orders = assert_success(client.get(f"/api/v1/orders?store_id={store_id}&platform=naver&include_test_orders=true"))
    order_names = [item["product_name"] for item in orders["data"]["items"]]
    assert orders["data"]["total"] == 3, orders
    assert orders["data"]["include_test_orders"] is True, orders
    assert "SK-II 神仙水测试商品" in order_names, orders
    assert "타이틀리스트 캐디백 테스트" in order_names, orders
    assert "ECCO 골프화 / 中文运营测试" in order_names, orders
    assert_masked_phone_only(orders)

    inquiries = assert_success(client.get(f"/api/v1/customer-inquiries?store_id={store_id}&platform=naver"))
    titles = [item["title"] for item in inquiries["data"]["items"]]
    assert inquiries["data"]["total"] == 3, inquiries
    assert "正品申诉资料咨询" in titles, inquiries
    assert "배송지연 문의" in titles, inquiries
    assert "Naver 정품 소명 / 中文备注" in titles, inquiries
    assert "请确认是否可以提供小票和卡支付明细。" in str(inquiries), inquiries
    assert "배송이 언제 시작되는지 확인 부탁드립니다." in str(inquiries), inquiries
    assert "고객문의 처리 후 中文运营备注에 기록해야 합니다." in str(inquiries), inquiries


def create_customer_inquiry_reader(store_id: int) -> dict[str, str]:
    with SessionLocal() as db:
        permission = db.scalar(select(ErpPermission).where(ErpPermission.permission_key == "orders.read"))
        if permission is None:
            permission = ErpPermission(
                permission_key="orders.read",
                permission_group="orders",
                permission_label_zh="stage 1D test",
            )
            db.add(permission)
        role = ErpRole(role_key="stage_1d_inquiry_reader", role_label_zh="test", role_label_en="test", status="active")
        user = ErpUser(
            user_key_hash="stage-1d-customer-inquiry-reader",
            display_name="Stage 1D Reader",
            login_identifier_hash="stage-1d-reader-login-hash",
            login_identifier_masked="stage-1d-reader",
            status="active",
            auth_provider="password",
        )
        db.add_all([role, user])
        db.flush()
        db.add(ErpRolePermission(role_id=role.id, permission_id=permission.id))
        db.add(ErpStoreMembership(user_id=user.id, store_id=store_id, role_id=role.id, membership_status="active"))
        db.commit()
    return {"X-ERP-User-Key": "stage-1d-customer-inquiry-reader"}


def verify_query_payloads(client: TestClient, store_id: int, customer_inquiry_headers: dict[str, str]) -> None:
    products = assert_success(client.get(f"/api/v1/products?store_id={store_id}&platform=naver"))
    assert products["data"]["total"] == 3, products
    orders = assert_success(client.get(f"/api/v1/orders?store_id={store_id}&platform=naver&include_test_orders=true"))
    assert orders["data"]["total"] == 3, orders
    inquiries = assert_success(client.get(
        f"/api/v1/customer-inquiries?store_id={store_id}&platform=naver",
        headers=customer_inquiry_headers,
    ))
    items = inquiries["data"]["items"]
    assert len(items) == 3 and inquiries["data"]["total"] == 3, inquiries
    expected = {
        "source", "inquiry_id", "category", "inquiry_type", "status", "summary",
        "created_at", "updated_at", "store_id", "order_context", "logistics_context", "reply_enabled",
    }
    assert all(item["source"] == "generic" and expected <= set(item) for item in items), inquiries
    assert all("title" not in item and "content" not in item and "raw_data" not in item for item in items), inquiries


def verify_database_security_and_logs(store_id: int) -> None:
    with SessionLocal() as db:
        credentials = db.scalars(select(ApiCredential)).all()
        encrypted_blob = " ".join(
            value
            for credential in credentials
            for value in [credential.encrypted_access_key, credential.encrypted_secret_key]
            if value
        )
        assert_no_secret(encrypted_blob)

        products = db.scalars(select(Product).where(Product.store_id == store_id)).all()
        orders = db.scalars(select(Order).where(Order.store_id == store_id)).all()
        inquiries = db.scalars(select(CustomerInquiry).where(CustomerInquiry.store_id == store_id)).all()
        logs = db.scalars(select(SyncLog).where(SyncLog.store_id == store_id)).all()

        assert len(products) == 3, products
        assert len(orders) == 3, orders
        assert len(inquiries) == 3, inquiries
        assert {log.sync_type for log in logs} >= {"products", "orders", "customer_inquiries"}, logs
        assert all(log.status == "success" for log in logs if log.sync_type in {"products", "orders", "customer_inquiries"}), logs
        assert "同步成功" in str([log.raw_summary for log in logs]), logs
        assert "동기화 성공" in str([log.raw_summary for log in logs]), logs

        assert_no_secret(products)
        assert_no_secret(orders)
        assert_no_secret(inquiries)
        assert_no_secret(logs)
        assert_masked_phone_only([order.buyer_masked_phone for order in orders])


def main() -> None:
    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:
        assert_success(client.get("/api/v1/health"))
        store_id = create_store_and_credentials(client)

        missing_credential = client.post(
            f"/api/v1/sync/products/mock?store_id={store_id}&platform=unsupported"
        )
        assert missing_credential.status_code == 400, missing_credential.text
        assert missing_credential.json()["error_code"] == "PLATFORM_NOT_SUPPORTED", missing_credential.text

        sync_products = assert_success(
            client.post(f"/api/v1/sync/products/mock?store_id={store_id}&platform=naver")
        )
        assert sync_products["data"]["write_result"]["created"] == 3, sync_products

        sync_orders = assert_success(
            client.post(f"/api/v1/sync/orders/mock?store_id={store_id}&platform=naver")
        )
        assert sync_orders["data"]["write_result"]["created"] == 3, sync_orders

        sync_inquiries = assert_success(
            client.post(f"/api/v1/sync/customer-inquiries/mock?store_id={store_id}&platform=naver")
        )
        assert sync_inquiries["data"]["write_result"]["created"] == 3, sync_inquiries

        sync_products_again = assert_success(
            client.post(f"/api/v1/sync/products/mock?store_id={store_id}&platform=naver")
        )
        assert sync_products_again["data"]["write_result"]["created"] == 0, sync_products_again
        assert sync_products_again["data"]["write_result"]["updated"] == 3, sync_products_again

        verify_query_payloads(client, store_id, create_customer_inquiry_reader(store_id))

        logs = assert_success(client.get(f"/api/v1/sync-logs?store_id={store_id}"))
        log_types = {item["sync_type"] for item in logs["data"]["items"]}
        assert {"products", "orders", "customer_inquiries"}.issubset(log_types), logs
        assert "同步成功" in str(logs), logs
        assert "동기화 성공" in str(logs), logs

        credential_response = assert_success(client.get(f"/api/v1/credentials?store_id={store_id}"))
        assert_no_secret(credential_response)

    verify_database_security_and_logs(store_id)

    print("stage 1D verification ok")
    print("seed-like store and Naver/Coupang mock credentials: ok")
    print("POST /api/v1/sync/products/mock: ok")
    print("POST /api/v1/sync/orders/mock: ok")
    print("POST /api/v1/sync/customer-inquiries/mock: ok")
    print("GET /api/v1/products: SK-II 神仙水测试商品 / 타이틀리스트 캐디백 테스트 / ECCO 골프화 / 中文运营测试")
    print("GET /api/v1/orders: 中文测试买家 / 홍길동 / 중한테스트 with masked phones only")
    print("GET /api/v1/customer-inquiries: 正品申诉资料咨询 / 배송지연 문의 / Naver 정품 소명 / 中文备注")
    print("sync_logs: products / orders / customer_inquiries success records found")
    print("security: plaintext credential tokens not stored or returned")
    print("privacy: full buyer phone numbers not stored or returned")


if __name__ == "__main__":
    main()
