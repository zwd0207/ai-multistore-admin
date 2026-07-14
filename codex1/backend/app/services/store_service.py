from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.store import Store


SUPPORTED_PLATFORMS = {"naver", "coupang"}
SUPPORTED_BROWSER_PROVIDERS = {"ziniao"}


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


def normalize_browser_binding(provider: str | None, profile_name: str | None) -> tuple[str | None, str | None]:
    normalized_provider = str(provider or "").strip().lower() or None
    normalized_name = str(profile_name or "").strip() or None
    if bool(normalized_provider) != bool(normalized_name):
        raise ApiError(
            message="紫鸟店铺绑定资料不完整",
            error_code="ZINIAO_BINDING_INCOMPLETE",
            status_code=400,
            detail=None,
        )
    if normalized_provider and normalized_provider not in SUPPORTED_BROWSER_PROVIDERS:
        raise ApiError(
            message="暂不支持该浏览器服务",
            error_code="BROWSER_PROVIDER_NOT_SUPPORTED",
            status_code=400,
            detail=None,
        )
    if normalized_name and (normalized_name.startswith("-") or any(ord(char) < 32 for char in normalized_name)):
        raise ApiError(
            message="紫鸟店铺名称格式不正确",
            error_code="ZINIAO_PROFILE_NAME_INVALID",
            status_code=400,
            detail=None,
        )
    return normalized_provider, normalized_name
