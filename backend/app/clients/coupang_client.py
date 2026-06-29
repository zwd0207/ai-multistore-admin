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
        return self._mock_response("mock products fetch ok", {"items": []})

    def fetch_orders_mock(self) -> dict:
        return self._mock_response("mock orders fetch ok", {"items": []})

    def fetch_customer_inquiries_mock(self) -> dict:
        return self._mock_response("mock customer inquiries fetch ok", {"items": []})
