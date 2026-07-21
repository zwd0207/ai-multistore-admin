from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CustomerInquiryRead(BaseModel):
    id: int
    store_id: int
    platform: str
    external_inquiry_id: str
    inquiry_type: str
    customer_name: str | None
    title: str
    content: str
    status: str
    received_at: datetime
    answered_at: datetime | None
    raw_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
