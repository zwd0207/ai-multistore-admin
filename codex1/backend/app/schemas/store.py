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

    @field_validator("name", "platform", "country", "language", "status", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    country: str | None = Field(default=None, min_length=2, max_length=10)
    language: str | None = Field(default=None, min_length=2, max_length=20)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    owner_name: str | None = Field(default=None, max_length=100)
    remark: str | None = None

    @field_validator("name", "platform", "country", "language", "status", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value


class StoreRead(StoreBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
