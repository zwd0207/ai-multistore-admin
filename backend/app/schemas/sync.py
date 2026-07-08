from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class CoupangOrderPreviewRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    start_date: date | None = None
    end_date: date | None = None
    max_pages: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def validate_date_range(self) -> "CoupangOrderPreviewRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class CoupangOrderSyncRequest(CoupangOrderPreviewRequest):
    pass


class CoupangProductSyncRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    status: str = Field(default="APPROVED")
    max_pages: int = Field(default=1, ge=1, le=3)


class NaverProductPreviewRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    credential_id: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=50)
    status: str | None = Field(default="ALL")
    keyword: str | None = Field(default=None, max_length=120)
    seller_product_id: str | None = Field(default=None, max_length=120)
    real_preview: bool = False
    real_sync: bool = False
    manual_approval: bool = False
    backup_path: str | None = Field(default=None, max_length=500)
    backup_sha256: str | None = Field(default=None, max_length=64)
    actor_context: dict = Field(default_factory=dict)


class NaverOrderPreviewRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    credential_id: int | None = Field(default=None, ge=1)
    start_datetime: datetime
    end_datetime: datetime
    order_status: str | None = Field(default="ALL")
    page: int = Field(default=1, ge=1, le=1)
    size: int = Field(default=1, ge=1, le=1)
    real_preview: bool = False
    include_detail: bool = False
    complete_field_preview: bool = False
    real_sync: bool = False

    @model_validator(mode="after")
    def validate_datetime_range(self) -> "NaverOrderPreviewRequest":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be greater than start_datetime")
        return self


class CoupangSalesPreviewRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    start_date: date | None = None
    end_date: date | None = None
    max_pages: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def validate_date_range(self) -> "CoupangSalesPreviewRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class CoupangSettlementPreviewRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "CoupangSettlementPreviewRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self


class ManualBatchSyncRequest(BaseModel):
    store_id: int = Field(..., ge=1)
    platforms: list[str] = Field(default_factory=lambda: ["naver", "coupang"])
    include_products: bool = True
    include_orders: bool = True
    include_customer_inquiries: bool = True
    replace_policy: str = "delete_absent_when_full_snapshot"


class ManualAllStoresSyncRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["naver", "coupang"])
    include_products: bool = True
    include_orders: bool = True
    include_customer_inquiries: bool = True
    include_inactive: bool = False
    replace_policy: str = "delete_absent_when_full_snapshot"
