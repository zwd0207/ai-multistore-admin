from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogisticsMappingInput(BaseModel):
    match_product_name: str = Field(..., min_length=1, max_length=300)
    match_option_name: str = Field(default="", max_length=300)
    platform_product_id_hash: str | None = Field(default=None, max_length=160)
    platform_option_id_hash: str | None = Field(default=None, max_length=160)
    internal_sku: str | None = Field(default=None, max_length=120)
    logistics_inventory_code: str = Field(..., min_length=1, max_length=120)
    logistics_provider_name: str | None = Field(default=None, max_length=160)
    current_stock_quantity: int = Field(default=0, ge=0, le=1_000_000)
    stock_status: str | None = Field(default=None, max_length=30)
    match_priority: int = Field(default=100, ge=0, le=10_000)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    model_config = ConfigDict(extra="allow")


class ShippingMappingWriteGateRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    platform: str = Field(default="naver", min_length=1, max_length=50)
    mappings: list[LogisticsMappingInput] = Field(default_factory=list, max_length=50)
    manual_approval: bool = False
    actor_context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ShippingMappingWriteRequest(ShippingMappingWriteGateRequest):
    pass


class ShippingExcelExportRowInput(BaseModel):
    order_reference: str = Field(..., min_length=1, max_length=160)
    product_name: str = Field(..., min_length=1, max_length=300)
    option_name: str = Field(default="", max_length=300)
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    logistics_inventory_code: str = Field(..., min_length=1, max_length=120)
    logistics_provider_name: str | None = Field(default=None, max_length=160)
    logistics_current_stock: int = Field(default=0, ge=0, le=1_000_000)
    platform_product_id_hash: str | None = Field(default=None, max_length=160)
    platform_option_id_hash: str | None = Field(default=None, max_length=160)
    internal_sku: str | None = Field(default=None, max_length=120)

    model_config = ConfigDict(extra="allow")


class ShippingExcelExportRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    platform: str = Field(default="naver", min_length=1, max_length=50)
    export_rows: list[ShippingExcelExportRowInput] = Field(default_factory=list, max_length=100)
    manual_approval: bool = False
    include_receiver_privacy: bool = False
    actor_context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class LogisticsInventoryMappingRead(BaseModel):
    id: int
    store_id: int
    platform: str
    match_product_name: str
    match_option_name: str
    normalized_product_name: str
    normalized_option_name: str
    platform_product_id_hash: str | None
    platform_option_id_hash: str | None
    internal_sku: str | None
    logistics_inventory_code: str
    logistics_provider_name: str | None
    match_priority: int
    is_active: bool
    mapping_version: str
    current_stock_quantity: int
    stock_status: str
    last_manual_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
