from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class OrderRead(BaseModel):
    id: int
    store_id: int
    platform: str
    external_order_id: str
    external_product_order_id: str | None
    buyer_name: str | None
    buyer_phone: str | None
    buyer_masked_phone: str | None
    receiver_name: str | None
    receiver_phone: str | None
    receiver_address: str | None
    zip_code: str | None
    product_name: str
    platform_product_id: str | None = None
    option_name: str | None = None
    product_image_url: str | None = None
    product_url: str | None = None
    quantity: int
    order_amount: Decimal
    currency: str
    order_status: str
    paid_at: datetime | None
    ordered_at: datetime
    source_type: str
    last_synced_at: datetime | None
    raw_data: dict[str, Any] | None
    delivery_company: str | None = None
    delivery_company_code: str | None = None
    tracking_number: str | None = None
    logistics_trace_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
