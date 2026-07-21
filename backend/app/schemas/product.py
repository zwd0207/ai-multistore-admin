from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    id: int
    store_id: int
    platform: str
    external_product_id: str
    name: str
    sku: str | None
    brand: str | None
    category: str | None
    status: str
    price: Decimal
    currency: str
    stock_quantity: int
    source_type: str
    last_synced_at: datetime | None
    raw_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
