from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StoreBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(..., min_length=1, max_length=50)
    country: str = Field(default="KR", min_length=2, max_length=10)
    language: str = Field(default="ko-KR", min_length=2, max_length=20)
    status: str = Field(default="active", min_length=1, max_length=30)
    owner_name: str | None = Field(default=None, max_length=100)
    remark: str | None = None
    browser_provider: str | None = Field(default=None, max_length=30)
    browser_profile_name: str | None = Field(default=None, max_length=200)

    @field_validator("name", "platform", "country", "language", "status", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("browser_provider", "browser_profile_name", mode="before")
    @classmethod
    def strip_browser_binding(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("browser_provider")
    @classmethod
    def validate_browser_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if normalized != "ziniao":
            raise ValueError("browser_provider must be ziniao")
        return normalized

    @field_validator("browser_profile_name")
    @classmethod
    def validate_browser_profile_name(cls, value: str | None) -> str | None:
        if value and any(ord(char) < 32 for char in value):
            raise ValueError("browser_profile_name contains control characters")
        return value


class StoreCreate(StoreBase):
    tenant_id: int | None = Field(default=None, ge=1)


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    country: str | None = Field(default=None, min_length=2, max_length=10)
    language: str | None = Field(default=None, min_length=2, max_length=20)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    owner_name: str | None = Field(default=None, max_length=100)
    remark: str | None = None
    browser_provider: str | None = Field(default=None, max_length=30)
    browser_profile_name: str | None = Field(default=None, max_length=200)

    @field_validator("name", "platform", "country", "language", "status", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("browser_provider", "browser_profile_name", mode="before")
    @classmethod
    def strip_optional_browser_binding(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("browser_provider")
    @classmethod
    def validate_optional_browser_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if normalized != "ziniao":
            raise ValueError("browser_provider must be ziniao")
        return normalized

    @field_validator("browser_profile_name")
    @classmethod
    def validate_optional_browser_profile_name(cls, value: str | None) -> str | None:
        if value and any(ord(char) < 32 for char in value):
            raise ValueError("browser_profile_name contains control characters")
        return value


class StoreRead(StoreBase):
    id: int
    tenant_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
