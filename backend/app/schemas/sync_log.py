from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SyncLogRead(BaseModel):
    id: int
    store_id: int
    platform: str
    sync_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    message: str | None
    error_detail: str | None
    raw_summary: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class SyncLogCreate(BaseModel):
    store_id: int
    platform: str = Field(..., min_length=1, max_length=50)
    sync_type: str = Field(..., min_length=1, max_length=50)
    message: str | None = None
    raw_summary: dict[str, Any] | None = None
