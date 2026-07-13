from functools import lru_cache

from pydantic import model_validator
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
    pxg_naver_local_read_order_stale_after_minutes: int = 15
    pxg_naver_local_read_inquiry_stale_after_minutes: int = 15
    pxg_naver_local_read_logistics_stale_after_minutes: int = 30
    pxg_naver_local_read_product_stale_after_hours: int = 6
    pxg_naver_local_read_retention_days: int = 90
    pxg_naver_local_read_retention_cleanup_enabled: bool = False
    pxg_naver_local_read_activation_enabled: bool = False
    pxg_naver_local_read_retention_approved: bool = False
    pxg_naver_local_read_backup_rollback_approved: bool = False
    pxg_naver_local_read_backup_encryption_key: str | None = None
    pxg_naver_local_read_backup_root: str | None = None
    local_product_thumbnail_root: str | None = None
    pxg_naver_local_read_thumbnail_generation_enabled: bool = False
    automatic_read_sync_enabled: bool = False
    automatic_read_sync_interval_seconds: int = 45
    lifecycle_schedulers_enabled: bool = True
    pxg_naver_local_read_first_sync_limit: int = 3
    ai_automatic_operations_enabled: bool = False
    platform_product_write_enabled: bool = False
    platform_inventory_write_enabled: bool = False
    platform_order_write_enabled: bool = False
    customer_platform_write_enabled: bool = False
    shipping_platform_write_enabled: bool = False
    pxg_naver_shipping_pilot_enabled: bool = False
    pxg_naver_shipping_pilot_max_rows: int = 1
    pxg_naver_shipping_pilot_max_attempts: int = 1
    allow_dev_auth: bool = False
    local_mfa_code_display_enabled: bool = False
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

    @model_validator(mode="after")
    def validate_local_mfa_code_display(self) -> "Settings":
        if self.local_mfa_code_display_enabled and self.app_env != "test":
            raise ValueError("LOCAL_MFA_CODE_DISPLAY_ENABLED requires APP_ENV=test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
