from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AppealCaseCreate(BaseModel):
    store_id: int
    platform: str = Field(..., min_length=1, max_length=50)
    case_type: str = Field(..., min_length=1, max_length=50)
    case_title: str = Field(..., min_length=1, max_length=300)
    case_status: str = Field(default="open", min_length=1, max_length=30)
    external_case_id: str | None = Field(default=None, max_length=120)
    related_order_id: int | None = None
    related_product_id: int | None = None
    deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    resolved_at: datetime | None = None
    summary: str | None = None
    action_required: str | None = None
    raw_data: dict[str, Any] | None = None


class AppealCaseUpdate(BaseModel):
    store_id: int | None = None
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    case_type: str | None = Field(default=None, min_length=1, max_length=50)
    case_title: str | None = Field(default=None, min_length=1, max_length=300)
    case_status: str | None = Field(default=None, min_length=1, max_length=30)
    external_case_id: str | None = Field(default=None, max_length=120)
    related_order_id: int | None = None
    related_product_id: int | None = None
    deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    resolved_at: datetime | None = None
    summary: str | None = None
    action_required: str | None = None
    raw_data: dict[str, Any] | None = None


class AppealCaseRead(AppealCaseCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
