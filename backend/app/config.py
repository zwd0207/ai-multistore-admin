from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, StrictInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "AI Multi-Store Operations API"
    app_env: Literal["development", "test", "production"] = "development"
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
    naver_readonly_inquiry_real_read_enabled: bool = False
    naver_readonly_inquiry_approved_store_id: int | None = Field(default=None, gt=0)
    naver_readonly_inquiry_approved_store_ids: list[StrictInt] = Field(default_factory=list)
    lifecycle_schedulers_enabled: bool = True
    pxg_naver_local_read_first_sync_limit: int = 3
    ai_automatic_operations_enabled: bool = False
    platform_product_write_enabled: bool = False
    platform_inventory_write_enabled: bool = False
    platform_order_write_enabled: bool = False
    customer_platform_write_enabled: bool = False
    shipping_platform_write_enabled: bool = False
    pxg_naver_shipping_pilot_enabled: bool = False
    allow_dev_auth: bool = False
    local_mfa_code_display_enabled: bool = False
    ziniao_browser_open_enabled: bool = False
    ziniao_cli_executable: str | None = None
    ziniao_cli_profile: str = "ziniao-sso-pilot"
    ziniao_cli_timeout_seconds: int = 30
    ziniao_directory_sync_enabled: bool = False
    ziniao_directory_sync_interval_seconds: int = 300
    ziniao_directory_geoip_timeout_seconds: int = 8
    session_token_pepper: str | None = None
    session_cookie_name: str = "__Host-erp_session"
    session_cookie_secure: bool = True
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    session_mfa_pending_minutes: int = 5
    session_recent_auth_minutes: int = 15
    public_app_url: str = "https://aiglxt.xyz"
    auth_invitation_hours: int = 24
    password_reset_minutes: int = 30
    email_delivery_enabled: bool = False
    auth_email_from_address: EmailStr | None = None
    auth_email_from_name: str = "AIGLXT"
    auth_email_smtp_host: str | None = None
    auth_email_smtp_port: int = Field(default=465, ge=1, le=65535)
    auth_email_smtp_username: str | None = None
    auth_email_smtp_password: SecretStr | None = None
    auth_email_smtp_security: Literal["ssl", "starttls"] = "ssl"
    auth_email_smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
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

    @model_validator(mode="after")
    def validate_naver_readonly_inquiry_real_read(self) -> "Settings":
        if any(type(store_id) is not int or store_id <= 0 for store_id in self.naver_readonly_inquiry_approved_store_ids):
            raise ValueError("NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS requires positive integer store IDs")
        if len(self.naver_readonly_inquiry_approved_store_ids) != len(
            set(self.naver_readonly_inquiry_approved_store_ids)
        ):
            raise ValueError("NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS cannot contain duplicate store IDs")
        if (
            self.naver_readonly_inquiry_approved_store_ids
            and self.naver_readonly_inquiry_approved_store_id is not None
            and self.naver_readonly_inquiry_approved_store_id
            not in self.naver_readonly_inquiry_approved_store_ids
        ):
            raise ValueError(
                "NAVER_READONLY_INQUIRY_APPROVED_STORE_ID must be unset or included in "
                "NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS"
            )
        if self.naver_readonly_inquiry_real_read_enabled and not self.naver_readonly_inquiry_approved_store_id_set:
            raise ValueError(
                "NAVER_READONLY_INQUIRY_REAL_READ_ENABLED requires "
                "NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS or "
                "NAVER_READONLY_INQUIRY_APPROVED_STORE_ID"
            )
        return self

    @property
    def naver_readonly_inquiry_approved_store_id_set(self) -> frozenset[int]:
        store_ids = set(self.naver_readonly_inquiry_approved_store_ids)
        if self.naver_readonly_inquiry_approved_store_id is not None:
            store_ids.add(self.naver_readonly_inquiry_approved_store_id)
        return frozenset(store_ids)

    @model_validator(mode="after")
    def validate_auth_email_delivery(self) -> "Settings":
        if not self.email_delivery_enabled:
            return self
        required_values = {
            "AUTH_EMAIL_FROM_ADDRESS": self.auth_email_from_address,
            "AUTH_EMAIL_SMTP_HOST": self.auth_email_smtp_host,
            "AUTH_EMAIL_SMTP_USERNAME": self.auth_email_smtp_username,
            "AUTH_EMAIL_SMTP_PASSWORD": (
                self.auth_email_smtp_password.get_secret_value()
                if self.auth_email_smtp_password is not None
                else None
            ),
        }
        missing = [name for name, value in required_values.items() if not value or not value.strip()]
        if missing:
            raise ValueError(
                "EMAIL_DELIVERY_ENABLED requires complete authentication email SMTP configuration"
            )
        if not self.public_app_url.startswith("https://"):
            raise ValueError("EMAIL_DELIVERY_ENABLED requires an HTTPS PUBLIC_APP_URL")
        header_values = (self.auth_email_from_address, self.auth_email_from_name)
        if any("\r" in value or "\n" in value for value in header_values if value):
            raise ValueError("authentication email sender fields cannot contain line breaks")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
