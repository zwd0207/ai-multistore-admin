from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailAccountCreate(BaseModel):
    store_id: int
    email_address: str = Field(..., min_length=3, max_length=255)
    provider: str = Field(..., min_length=1, max_length=50)
    account_label: str | None = Field(default=None, max_length=200)
    password_or_token: str | None = Field(default=None, min_length=1)
    status: str = Field(default="active", min_length=1, max_length=30)
    last_checked_at: datetime | None = None
    remark: str | None = None


class EmailAccountUpdate(BaseModel):
    store_id: int | None = None
    email_address: str | None = Field(default=None, min_length=3, max_length=255)
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    account_label: str | None = Field(default=None, max_length=200)
    password_or_token: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    last_checked_at: datetime | None = None
    remark: str | None = None


class EmailAccountRead(BaseModel):
    id: int
    store_id: int
    email_address: str
    provider: str
    account_label: str | None
    status: str
    last_checked_at: datetime | None
    remark: str | None
    has_password_or_token: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
