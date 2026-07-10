from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportantEmailCreate(BaseModel):
    store_id: int
    email_account_id: int | None = None
    platform: str = Field(..., min_length=1, max_length=50)
    mail_type: str = Field(..., min_length=1, max_length=50)
    sender: str | None = Field(default=None, max_length=255)
    subject: str = Field(..., min_length=1, max_length=300)
    snippet: str | None = Field(default=None, max_length=500)
    body_text: str | None = None
    received_at: datetime
    status: str = Field(default="unread", min_length=1, max_length=30)
    priority: str = Field(default="normal", min_length=1, max_length=30)
    related_case_id: int | None = None
    raw_data: dict[str, Any] | None = None


class ImportantEmailUpdate(BaseModel):
    store_id: int | None = None
    email_account_id: int | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    mail_type: str | None = Field(default=None, min_length=1, max_length=50)
    sender: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    snippet: str | None = Field(default=None, max_length=500)
    body_text: str | None = None
    received_at: datetime | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)
    priority: str | None = Field(default=None, min_length=1, max_length=30)
    related_case_id: int | None = None
    raw_data: dict[str, Any] | None = None


class ImportantEmailRead(ImportantEmailCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
