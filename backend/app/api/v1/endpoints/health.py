from fastapi import APIRouter

from app.config import get_settings
from app.core.responses import success_response


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict:
    settings = get_settings()
    operation_flags = {
        "naver_shipment_dispatch": settings.shipping_platform_write_enabled,
        "naver_customer_inquiry_reply": settings.customer_platform_write_enabled,
        "naver_price_update": settings.platform_product_write_enabled,
        "naver_stock_update": settings.platform_inventory_write_enabled,
        "naver_order_update": settings.platform_order_write_enabled,
    }
    approved_operations = sorted(name for name, enabled in operation_flags.items() if enabled)
    blocked_operations = sorted(name for name, enabled in operation_flags.items() if not enabled)
    controlled_writes_enabled = settings.real_api_write_enabled and bool(approved_operations) and not settings.operator_trial_enabled
    all_platform_writes_closed = not settings.real_api_write_enabled and not approved_operations
    return success_response(
        data={
            "status": "ok",
            "environment": settings.app_env,
            "api_version": "v1",
            "real_api_test_enabled": settings.real_api_test_enabled,
            "real_api_write_enabled": settings.real_api_write_enabled,
            "platform_write_closed": all_platform_writes_closed,
            "generic_platform_write_closed": all_platform_writes_closed,
            "controlled_platform_writes_enabled": controlled_writes_enabled,
            "platform_write_mode": "operator_trial_closed" if settings.operator_trial_enabled else (
                "controlled_naver_official_writes" if controlled_writes_enabled else "closed"
            ),
            "approved_platform_write_operations": approved_operations if controlled_writes_enabled else [],
            "blocked_platform_write_operations": blocked_operations,
        }
    )
