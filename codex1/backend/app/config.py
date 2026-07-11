from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "AI Multi-Store Operations API"
    app_env: str = "development"
    database_url: str = "sqlite:///./codex1.db"
    api_prefix: str = ""
    app_timezone: str = "Asia/Seoul"
    cors_allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
    ]
    credential_encryption_key: str | None = None
    real_api_test_enabled: bool = False
    real_api_write_enabled: bool = False
    operator_trial_enabled: bool = False
    operator_trial_artificial_data_only: bool = True
    operator_trial_real_read_enabled: bool = False
    pxg_naver_local_read_persistence_enabled: bool = False
    pxg_naver_local_read_stale_after_hours: int = 24
    pxg_naver_local_read_retention_days: int = 90
    pxg_naver_local_read_retention_cleanup_enabled: bool = False
    ai_automatic_operations_enabled: bool = False
    platform_product_write_enabled: bool = False
    platform_inventory_write_enabled: bool = False
    platform_order_write_enabled: bool = False
    customer_platform_write_enabled: bool = False
    shipping_platform_write_enabled: bool = False
    allow_dev_auth: bool = False
    session_token_pepper: str | None = None
    session_cookie_name: str = "__Host-erp_session"
    session_cookie_secure: bool = True
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    session_mfa_pending_minutes: int = 5
    session_recent_auth_minutes: int = 15
    coupang_vendor_id: str | None = None
    coupang_access_key: str | None = None
    coupang_secret_key: str | None = None
    naver_client_id: str | None = None
    naver_client_secret: str | None = None
    naver_api_base: str = "https://api.commerce.naver.com/external"
    naver_channel_no: str | None = None
    naver_access_token: str | None = None
    naver_refresh_token: str | None = None
    naver_token_expires_at: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
