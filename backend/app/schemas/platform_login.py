from datetime import datetime

from pydantic import BaseModel, Field, field_validator


LOGIN_STATUSES = {"active", "inactive", "unknown", "needs_check"}


class PlatformLoginCreate(BaseModel):
    store_id: int
    platform: str = Field(..., min_length=1, max_length=50)
    login_label: str = Field(..., min_length=1, max_length=120)
    login_account: str | None = Field(default=None, max_length=255)
    login_password: str | None = Field(default=None, min_length=1)
    email_account_id: int | None = None
    device_environment_id: int | None = None
    login_status: str = Field(default="unknown", min_length=1, max_length=30)
    last_login_check_at: datetime | None = None
    remark: str | None = None

    @field_validator("platform", "login_label", "login_account", "login_password", "login_status", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("login_status")
    @classmethod
    def validate_login_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in LOGIN_STATUSES:
            raise ValueError("login_status must be active, inactive, unknown, or needs_check")
        return normalized


class PlatformLoginUpdate(BaseModel):
    store_id: int | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    login_label: str | None = Field(default=None, min_length=1, max_length=120)
    login_account: str | None = Field(default=None, max_length=255)
    login_password: str | None = Field(default=None)
    email_account_id: int | None = None
    device_environment_id: int | None = None
    login_status: str | None = Field(default=None, min_length=1, max_length=30)
    last_login_check_at: datetime | None = None
    remark: str | None = None

    @field_validator("platform", "login_label", "login_account", "login_password", "login_status", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("login_status")
    @classmethod
    def validate_optional_login_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in LOGIN_STATUSES:
            raise ValueError("login_status must be active, inactive, unknown, or needs_check")
        return normalized
