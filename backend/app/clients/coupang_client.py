from app.models.store import utc_now
from app.schemas.credential import DecryptedCredential


class CoupangClient:
    platform = "coupang"

    def __init__(self, credential: DecryptedCredential) -> None:
        self.credential = credential

    def _mock_response(self, message: str, data: dict | None = None) -> dict:
        return {
            "success": True,
            "platform": self.platform,
            "store_id": self.credential.store_id,
            "message": message,
            "data": data or {},
        }

    def test_connection(self) -> dict:
        return self._mock_response("mock connection ok")

    def fetch_products_mock(self) -> dict:
        return self._mock_response(
            "mock products fetch ok",
            {
                "items": [
                    {
                        "external_product_id": f"coupang-{self.credential.store_id}-product-cn",
                        "name": "SK-II 神仙水测试商品",
                        "sku": "COUPANG-SKII-CN",
                        "brand": "SK-II",
                        "category": "护肤品",
                        "status": "active",
                        "price": 128000,
                        "currency": "KRW",
                        "stock_quantity": 15,
                        "raw_data": {"source": "coupang mock", "说明": "中文商品摘要"},
                    },
                    {
                        "external_product_id": f"coupang-{self.credential.store_id}-product-ko",
                        "name": "타이틀리스트 캐디백 테스트",
                        "sku": "COUPANG-TITLEIST-KO",
                        "brand": "Titleist",
                        "category": "골프용품",
                        "status": "active",
                        "price": 345000,
                        "currency": "KRW",
                        "stock_quantity": 7,
                        "raw_data": {"source": "coupang mock", "요약": "한글 상품 데이터"},
                    },
                    {
                        "external_product_id": f"coupang-{self.credential.store_id}-product-mixed",
                        "name": "ECCO 골프화 / 中文运营测试",
                        "sku": "COUPANG-ECCO-MIX",
                        "brand": "ECCO",
                        "category": "스포츠화",
                        "status": "active",
                        "price": 215000,
                        "currency": "KRW",
                        "stock_quantity": 9,
                        "raw_data": {"source": "coupang mock", "中文": "运营测试", "한국어": "골프화"},
                    },
                ]
            },
        )

    def fetch_orders_mock(self) -> dict:
        now = utc_now()
        return self._mock_response(
            "mock orders fetch ok",
            {
                "items": [
                    {
                        "external_order_id": f"coupang-{self.credential.store_id}-order-cn",
                        "buyer_name": "中文测试买家",
                        "buyer_masked_phone": "010-****-1234",
                        "product_name": "SK-II 神仙水测试商品",
                        "quantity": 1,
                        "order_amount": 128000,
                        "currency": "KRW",
                        "order_status": "paid",
                        "paid_at": now,
                        "ordered_at": now,
                        "raw_data": {"source": "coupang mock", "说明": "中文订单摘要"},
                    },
                    {
                        "external_order_id": f"coupang-{self.credential.store_id}-order-ko",
                        "buyer_name": "홍길동",
                        "buyer_masked_phone": "010-****-5678",
                        "product_name": "타이틀리스트 캐디백 테스트",
                        "quantity": 1,
                        "order_amount": 345000,
                        "currency": "KRW",
                        "order_status": "paid",
                        "paid_at": now,
                        "ordered_at": now,
                        "raw_data": {"source": "coupang mock", "요약": "한글 주문 데이터"},
                    },
                    {
                        "external_order_id": f"coupang-{self.credential.store_id}-order-mixed",
                        "buyer_name": "중한테스트",
                        "buyer_masked_phone": "010-****-9012",
                        "product_name": "ECCO 골프화 / 中文运营测试",
                        "quantity": 2,
                        "order_amount": 430000,
                        "currency": "KRW",
                        "order_status": "paid",
                        "paid_at": now,
                        "ordered_at": now,
                        "raw_data": {"source": "coupang mock", "中文": "订单", "한국어": "주문"},
                    },
                ]
            },
        )

    def fetch_customer_inquiries_mock(self) -> dict:
        now = utc_now()
        return self._mock_response(
            "mock customer inquiries fetch ok",
            {
                "items": [
                    {
                        "external_inquiry_id": f"coupang-{self.credential.store_id}-inquiry-cn",
                        "inquiry_type": "authenticity",
                        "customer_name": "中文测试客户",
                        "title": "正品申诉资料咨询",
                        "content": "请确认是否可以提供小票和卡支付明细。",
                        "status": "open",
                        "received_at": now,
                        "answered_at": None,
                        "raw_data": {"source": "coupang mock", "说明": "中文咨询摘要"},
                    },
                    {
                        "external_inquiry_id": f"coupang-{self.credential.store_id}-inquiry-ko",
                        "inquiry_type": "delivery",
                        "customer_name": "홍길동",
                        "title": "배송지연 문의",
                        "content": "배송이 언제 시작되는지 확인 부탁드립니다.",
                        "status": "open",
                        "received_at": now,
                        "answered_at": None,
                        "raw_data": {"source": "coupang mock", "요약": "한글 문의 데이터"},
                    },
                    {
                        "external_inquiry_id": f"coupang-{self.credential.store_id}-inquiry-mixed",
                        "inquiry_type": "authenticity",
                        "customer_name": "중한테스트",
                        "title": "Naver 정품 소명 / 中文备注",
                        "content": "고객문의 처리 후 中文运营备注에 기록해야 합니다.",
                        "status": "open",
                        "received_at": now,
                        "answered_at": None,
                        "raw_data": {"source": "coupang mock", "中文": "客服咨询", "한국어": "정품 소명"},
                    },
                ]
            },
        )
