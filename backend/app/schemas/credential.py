from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CredentialCreate(BaseModel):
    store_id: int
    platform: str = Field(..., min_length=1, max_length=50)
    credential_name: str = Field(..., min_length=1, max_length=120)
    access_key: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)
    extra_config: dict[str, Any] | None = None
    status: str = Field(default="active", min_length=1, max_length=30)

    @field_validator("platform", "credential_name", "access_key", "secret_key", "status", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
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


class CredentialUpdate(BaseModel):
    store_id: int | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    credential_name: str | None = Field(default=None, min_length=1, max_length=120)
    access_key: str | None = Field(default=None, min_length=1)
    secret_key: str | None = Field(default=None, min_length=1)
    extra_config: dict[str, Any] | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("platform", "credential_name", "access_key", "secret_key", "status", mode="before")
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


class CredentialRead(BaseModel):
    id: int
    store_id: int
    platform: str
    credential_name: str
    extra_config: dict[str, Any] | None
    status: str
    has_access_key: bool
    has_secret_key: bool
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
    extra_config: dict[str, Any] | None
    status: str
