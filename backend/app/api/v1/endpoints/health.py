from fastapi import APIRouter

from app.config import get_settings
from app.core.responses import success_response


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict:
    settings = get_settings()
    return success_response(
        data={
            "status": "ok",
            "environment": settings.app_env,
            "api_version": "v1",
            "real_api_test_enabled": settings.real_api_test_enabled,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "platform_write_closed": settings.real_api_write_enabled is False,
            "generic_platform_write_closed": settings.real_api_write_enabled is False,
            "controlled_platform_writes_enabled": True,
            "platform_write_mode": "controlled_naver_official_writes",
            "approved_platform_write_operations": [
                "naver_shipment_dispatch",
                "naver_customer_inquiry_reply",
            ],
            "blocked_platform_write_operations": [
                "naver_price_update",
                "naver_stock_update",
                "naver_auto_reply",
                "coupang_shipment_writeback",
                "coupang_price_update",
                "coupang_stock_update",
            ],
        }
    )
