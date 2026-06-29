from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CredentialCreate(BaseModel):
    store_id: int
    platform: str = Field(..., min_length=1, max_length=50)
    credential_name: str = Field(..., min_length=1, max_length=120)
    vendor_id: str | None = Field(default=None, max_length=120)
    client_id: str | None = Field(default=None, max_length=120)
    access_key: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)
    access_token: str | None = Field(default=None, min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)
    token_expires_at: datetime | None = None
    market: str | None = Field(default=None, max_length=30)
    auth_status: str = Field(default="not_configured", min_length=1, max_length=30)
    last_tested_at: datetime | None = None
    api_remark: str | None = Field(default=None, max_length=500)
    extra_config: dict[str, Any] | None = None
    status: str = Field(default="active", min_length=1, max_length=30)

    @field_validator(
        "platform",
        "credential_name",
        "vendor_id",
        "client_id",
        "access_key",
        "secret_key",
        "access_token",
        "refresh_token",
        "market",
        "auth_status",
        "api_remark",
        "status",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"naver", "coupang"}:
            raise ValueError("platform must be naver or coupang")
        return normalized

    @field_validator("auth_status")
    @classmethod
    def validate_auth_status(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"not_configured", "configured", "needs_test", "test_failed", "test_passed"}:
            raise ValueError("auth_status must be not_configured, configured, needs_test, test_failed, or test_passed")
        return normalized


class CredentialUpdate(BaseModel):
    store_id: int | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    credential_name: str | None = Field(default=None, min_length=1, max_length=120)
    vendor_id: str | None = Field(default=None, max_length=120)
    client_id: str | None = Field(default=None, max_length=120)
    access_key: str | None = Field(default=None, min_length=1)
    secret_key: str | None = Field(default=None, min_length=1)
    access_token: str | None = Field(default=None, min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)
    token_expires_at: datetime | None = None
    market: str | None = Field(default=None, max_length=30)
    auth_status: str | None = Field(default=None, min_length=1, max_length=30)
    last_tested_at: datetime | None = None
    api_remark: str | None = Field(default=None, max_length=500)
    extra_config: dict[str, Any] | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator(
        "platform",
        "credential_name",
        "vendor_id",
        "client_id",
        "access_key",
        "secret_key",
        "access_token",
        "refresh_token",
        "market",
        "auth_status",
        "api_remark",
        "status",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in {"naver", "coupang"}:
            raise ValueError("platform must be naver or coupang")
        return normalized

    @field_validator("auth_status")
    @classmethod
    def validate_auth_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in {"not_configured", "configured", "needs_test", "test_failed", "test_passed"}:
            raise ValueError("auth_status must be not_configured, configured, needs_test, test_failed, or test_passed")
        return normalized


class CredentialRead(BaseModel):
    id: int
    store_id: int
    platform: str
    credential_name: str
    vendor_id: str | None
    client_id: str | None
    token_expires_at: datetime | None
    market: str | None
    auth_status: str
    last_tested_at: datetime | None
    api_remark: str | None
    extra_config: dict[str, Any] | None
    status: str
    has_access_key: bool
    has_secret_key: bool
    has_access_token: bool
    has_refresh_token: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecryptedCredential(BaseModel):
    id: int
    store_id: int
    platform: str
    credential_name: str
    access_key: str | None
    secret_key: str | None
    access_token: str | None = None
    refresh_token: str | None = None
    vendor_id: str | None = None
    client_id: str | None = None
    token_expires_at: datetime | None = None
    market: str | None = None
    auth_status: str | None = None
    last_tested_at: datetime | None = None
    api_remark: str | None = None
    extra_config: dict[str, Any] | None
    status: str
