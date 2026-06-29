from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class OrderRead(BaseModel):
    id: int
    store_id: int
    platform: str
    external_order_id: str
    buyer_name: str | None
    buyer_masked_phone: str | None
    product_name: str
    quantity: int
    order_amount: Decimal
    currency: str
    order_status: str
    paid_at: datetime | None
    ordered_at: datetime
    raw_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
