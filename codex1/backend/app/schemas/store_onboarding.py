from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StoreOnboardingCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    store_name: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=120)
    client_secret: str = Field(min_length=1, max_length=1000)
    channel_no: str | None = Field(default=None, max_length=120)

    @field_validator("idempotency_key", "store_name", "client_id", "client_secret", "channel_no", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class HistoricalBackfillCreate(BaseModel):
    start_at: datetime
    end_at: datetime


class StoreOnboardingCredentialUpdate(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=120)
    client_secret: str | None = Field(default=None, min_length=1, max_length=1000)
    channel_no: str | None = Field(default=None, max_length=120)

    @field_validator("client_id", "client_secret", "channel_no", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_change(self) -> "StoreOnboardingCredentialUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one credential field must be supplied")
        return self


class StoreOnboardingRead(BaseModel):
    id: int
    idempotency_key: str
    requested_store_name: str
    store_id: int | None
    credential_id: int | None
    status: Literal[
        "validating", "blocked", "provisioning", "backfilling", "partially_synced",
        "active_incremental", "retry_wait", "cancelled",
    ]
    snapshot_end_at: datetime | None
    initial_window_start_at: datetime | None
    retry_count: int
    configuration_version: int
    next_retry_at: datetime | None
    last_error_code: str | None
    validation_summary: dict[str, Any] | None
    progress_summary: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
