import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from scripts.seed import SEED_STORES, seed_stores


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def assert_success(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["success"] is True, payload
    return payload


def main() -> None:
    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:
        health = assert_success(client.get("/api/v1/health"))
        assert health["data"]["status"] == "ok", health

        chinese_store = assert_success(
            client.post(
                "/api/v1/stores",
                json={
                    "name": "接口中文测试店",
                    "platform": "naver",
                    "country": "KR",
                    "language": "zh-KR",
                    "status": "active",
                    "owner_name": "测试负责人",
                    "remark": "中文备注：用于测试店铺 CRUD。",
                },
            ),
            expected_status=201,
        )
        assert chinese_store["data"]["name"] == "接口中文测试店", chinese_store

        korean_store = assert_success(
            client.post(
                "/api/v1/stores",
                json={
                    "name": "인터페이스서울테스트",
                    "platform": "naver",
                    "country": "KR",
                    "language": "ko-KR",
                    "status": "active",
                    "owner_name": "테스트 담당자",
                    "remark": "네이버 테스트 고객문의",
                },
            ),
            expected_status=201,
        )
        korean_id = korean_store["data"]["id"]
        assert korean_store["data"]["name"] == "인터페이스서울테스트", korean_store

        mixed_store = assert_success(
            client.post(
                "/api/v1/stores",
                json={
                    "name": "Interface Mixed Store",
                    "platform": "coupang",
                    "country": "KR",
                    "language": "mixed",
                    "status": "active",
                    "owner_name": "中韩测试负责人",
                    "remark": "Naver 正品申诉 / Coupang 订单 / 정품 소명 자료",
                },
            ),
            expected_status=201,
        )
        assert "정품 소명 자료" in mixed_store["data"]["remark"], mixed_store

        listing = assert_success(client.get("/api/v1/stores?page=1&page_size=10"))
        names = [item["name"] for item in listing["data"]["items"]]
        assert "接口中文测试店" in names, listing
        assert "인터페이스서울테스트" in names, listing
        assert listing["data"]["total"] == 3, listing

        single = assert_success(client.get(f"/api/v1/stores/{korean_id}"))
        assert single["data"]["name"] == "인터페이스서울테스트", single

        updated_remark = "수정된 한글 비고: 배송지연 고객문의 확인"
        updated = assert_success(
            client.put(
                f"/api/v1/stores/{korean_id}",
                json={"remark": updated_remark},
            )
        )
        assert updated["data"]["remark"] == updated_remark, updated

        deleted = assert_success(client.delete(f"/api/v1/stores/{korean_id}"))
        assert deleted["data"]["name"] == "인터페이스서울테스트", deleted

        missing = client.get(f"/api/v1/stores/{korean_id}")
        assert missing.status_code == 404, missing.text
        missing_payload = missing.json()
        assert missing_payload["success"] is False, missing_payload
        assert missing_payload["error_code"] == "STORE_NOT_FOUND", missing_payload

    seed_result = seed_stores()
    assert seed_result["created"] == 4, seed_result
    assert seed_result["skipped"] == 0, seed_result

    repeated_seed_result = seed_stores()
    assert repeated_seed_result["created"] == 0, repeated_seed_result
    assert repeated_seed_result["skipped"] == 4, repeated_seed_result

    with TestClient(app) as client:
        response = assert_success(client.get("/api/v1/stores?page=1&page_size=100"))
        stores = {item["name"]: item["remark"] for item in response["data"]["items"]}
        for item in SEED_STORES:
            assert stores[item["name"]] == item["remark"], item

    print("stage 1B verification ok")
    print("GET /api/v1/health: ok")
    print("POST /api/v1/stores Chinese: 接口中文测试店")
    print("POST /api/v1/stores Korean: 인터페이스서울테스트")
    print("POST /api/v1/stores mixed remark: Naver 正品申诉 / Coupang 订单 / 정품 소명 자료")
    print("PUT Korean remark: 수정된 한글 비고: 배송지연 고객문의 확인")
    print(f"seed created={seed_result['created']} skipped={seed_result['skipped']}")
    print(f"seed repeat created={repeated_seed_result['created']} skipped={repeated_seed_result['skipped']}")
    for item in SEED_STORES:
        print(f"{item['name']} => {item['remark']}")


if __name__ == "__main__":
    main()
