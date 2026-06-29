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
        }
    )
