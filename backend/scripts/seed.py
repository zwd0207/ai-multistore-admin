from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_db
from app.models.store import Store


SEED_STORES = [
    {
        "name": "东方优选测试店",
        "platform": "naver",
        "country": "KR",
        "language": "zh-KR",
        "status": "active",
        "owner_name": "测试负责人",
        "remark": "中文备注：用于测试店铺管理、订单管理、申诉资料。",
    },
    {
        "name": "서울뷰티테스트",
        "platform": "naver",
        "country": "KR",
        "language": "ko-KR",
        "status": "active",
        "owner_name": "테스트 담당자",
        "remark": "네이버 스마트스토어 테스트 / 정품 소명 자료 / 배송지연 고객문의",
    },
    {
        "name": "강남스포츠테스트",
        "platform": "coupang",
        "country": "KR",
        "language": "ko-KR",
        "status": "active",
        "owner_name": "테스트 담당자",
        "remark": "쿠팡 고객문의 / 반품 요청 / 주문 동기화 테스트",
    },
    {
        "name": "Global Korea Test Store",
        "platform": "naver",
        "country": "KR",
        "language": "mixed",
        "status": "active",
        "owner_name": "中韩测试负责人",
        "remark": "Naver 正品申诉 / Coupang 订单 / 中文运营备注 / 정품 소명 자료",
    },
]


def seed_stores() -> dict[str, int]:
    init_db()
    created = 0
    skipped = 0

    with SessionLocal() as db:
        for item in SEED_STORES:
            existing = db.query(Store).filter(Store.name == item["name"]).one_or_none()
            if existing:
                skipped += 1
                continue

            db.add(Store(**item))
            created += 1

        db.commit()

    return {"created": created, "skipped": skipped}


if __name__ == "__main__":
    result = seed_stores()
    print(f"Seed stores completed: created={result['created']}, skipped={result['skipped']}")
