from datetime import date

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
