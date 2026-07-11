from datetime import datetime
from decimal import Decimal
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SAFE_INQUIRY_LABEL_PATTERN = re.compile(r"^[\w.:-]{1,120}$", re.UNICODE)
PHONE_PATTERN = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")
SAFE_MASKED_CUSTOMER_PATTERN = re.compile(r"^[\w* .-]{1,120}$", re.UNICODE)


class _StrictReadonlyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("source_updated_at", check_fields=False)
    @classmethod
    def _source_time_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_updated_at must include a timezone")
        return value


class PxgNaverReadonlyRecipientCandidate(BaseModel):
    """The sole input contract that is encrypted before persistence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    receiver_name: str | None = Field(default=None, max_length=120)
    receiver_phone: str | None = Field(default=None, max_length=40)
    receiver_phone_secondary: str | None = Field(default=None, max_length=40)
    zip_code: str | None = Field(default=None, max_length=30)
    receiver_address_line1: str | None = Field(default=None, max_length=300)
    receiver_address_line2: str | None = Field(default=None, max_length=300)
    receiver_address_full: str | None = Field(default=None, max_length=600)
    delivery_memo: str | None = Field(default=None, max_length=300)


class PxgNaverReadonlyProductCandidate(_StrictReadonlyCandidate):
    external_product_id: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=300)
    sku: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    status: str = Field(default="active", min_length=1, max_length=30)
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KRW", min_length=1, max_length=10)
    stock_quantity: int = Field(default=0, ge=0)
    source_updated_at: datetime


class PxgNaverReadonlyOrderCandidate(_StrictReadonlyCandidate):
    external_order_id: str = Field(..., min_length=1, max_length=120)
    external_product_order_id: str = Field(..., min_length=1, max_length=120)
    product_name: str = Field(..., min_length=1, max_length=300)
    quantity: int = Field(default=1, ge=1)
    order_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KRW", min_length=1, max_length=10)
    order_status: str = Field(..., min_length=1, max_length=30)
    ordered_at: datetime
    paid_at: datetime | None = None
    source_updated_at: datetime
    recipient: PxgNaverReadonlyRecipientCandidate | None = None

    @field_validator("ordered_at", "paid_at")
    @classmethod
    def _business_time_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("business timestamps must include a timezone")
        return value


class PxgNaverReadonlyLogisticsCandidate(_StrictReadonlyCandidate):
    external_order_id: str = Field(..., min_length=1, max_length=120)
    external_product_order_id: str | None = Field(default=None, max_length=120)
    carrier: str | None = Field(default=None, max_length=120)
    tracking_number: str = Field(..., min_length=1, max_length=120)
    shipment_status: str = Field(default="observed", min_length=1, max_length=60)
    shipped_at: datetime | None = None
    source_updated_at: datetime

    @field_validator("shipped_at")
    @classmethod
    def _shipped_time_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("shipped_at must include a timezone")
        return value


class PxgNaverReadonlyInquiryCandidate(_StrictReadonlyCandidate):
    external_inquiry_id: str = Field(..., min_length=1, max_length=120)
    related_external_order_id: str | None = Field(default=None, max_length=120)
    related_external_product_order_id: str | None = Field(default=None, max_length=120)
    inquiry_type: str = Field(..., min_length=1, max_length=60)
    status: str = Field(..., min_length=1, max_length=40)
    customer_display_masked: str | None = Field(default=None, max_length=120)
    subject_category: str | None = Field(default=None, max_length=120)
    content_available: bool = False
    received_at: datetime | None = None
    answered_at: datetime | None = None
    source_updated_at: datetime

    @field_validator("received_at", "answered_at")
    @classmethod
    def _inquiry_time_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("inquiry timestamps must include a timezone")
        return value

    @field_validator("customer_display_masked")
    @classmethod
    def _customer_display_is_masked(cls, value: str | None) -> str | None:
        if value and (
            "*" not in value
            or PHONE_PATTERN.search(value)
            or not SAFE_MASKED_CUSTOMER_PATTERN.fullmatch(value)
        ):
            raise ValueError("customer_display_masked must be a safe masked label")
        return value

    @field_validator("inquiry_type", "status", "subject_category")
    @classmethod
    def _inquiry_metadata_is_safe_label(cls, value: str | None) -> str | None:
        if value is not None and not SAFE_INQUIRY_LABEL_PATTERN.fullmatch(value):
            raise ValueError("customer inquiry metadata must be a safe category label")
        return value


class PxgNaverReadonlyAdapterBatch(BaseModel):
    """Normalized candidates produced only by the server-side Naver adapter.

    This is intentionally not an HTTP request model. The public refresh endpoint
    accepts no product, order, logistics, inquiry, or recipient fields.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    store_id: int = Field(..., ge=1)
    platform: Literal["naver"] = "naver"
    source_mode: Literal["fictional_test", "real_readonly"]
    products: list[PxgNaverReadonlyProductCandidate] = Field(default_factory=list, max_length=50)
    orders: list[PxgNaverReadonlyOrderCandidate] = Field(default_factory=list, max_length=50)
    logistics: list[PxgNaverReadonlyLogisticsCandidate] = Field(default_factory=list, max_length=50)
    customer_inquiries: list[PxgNaverReadonlyInquiryCandidate] = Field(default_factory=list, max_length=50)
