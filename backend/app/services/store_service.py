from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.store import Store


SUPPORTED_PLATFORMS = {"naver", "coupang"}


def normalize_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized not in SUPPORTED_PLATFORMS:
        raise ApiError(
            message="暂不支持该平台",
            error_code="PLATFORM_NOT_SUPPORTED",
            status_code=400,
            detail={"platform": platform, "supported_platforms": sorted(SUPPORTED_PLATFORMS)},
        )
    return normalized


def ensure_store_exists(db: Session, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise ApiError(
            message="店铺不存在",
            error_code="STORE_NOT_FOUND",
            status_code=404,
            detail={"store_id": store_id},
        )
    return store
