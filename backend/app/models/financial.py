from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from app.models.store import utc_now


FORBIDDEN_OBSERVED_FIELDS = {
    "bankaccountholder",
    "bankname",
    "bankaccount",
    "accesskey",
    "secretkey",
    "access_key",
    "secret_key",
    "header",
    "signature",
    "token",
    "authorization",
}


def validate_observed_fields(value: list[str] | None) -> list[str] | None:
    if value is None:
        return value
    lowered = {str(item).replace("_", "").lower() for item in value}
    forbidden = sorted(lowered & FORBIDDEN_OBSERVED_FIELDS)
    if forbidden:
        raise ValueError(f"observed_fields contains forbidden field names: {forbidden}")
    return value


class PlatformSalesDetail(Base):
    __tablename__ = "platform_sales_details"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", "external_sales_id", name="uq_platform_sales_external_id"),
        Index("ix_platform_sales_store_platform_date", "store_id", "platform", "recognition_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    external_sales_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    recognition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    order_sheet_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    shipment_box_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    vendor_item_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    sale_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KRW")
    sale_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_sale: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discount_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    refund_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    commission_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fee_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    settlement_target_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    settlement_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    observed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="platform_sales_details")

    @validates("observed_fields")
    def _validate_observed_fields(self, _key: str, value: list[str] | None) -> list[str] | None:
        return validate_observed_fields(value)


class PlatformSettlementDetail(Base):
    __tablename__ = "platform_settlement_details"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", "external_settlement_id", name="uq_platform_settlement_external_id"),
        Index(
            "ix_platform_settlement_store_platform_month",
            "store_id",
            "platform",
            "revenue_recognition_year_month",
        ),
        Index("ix_platform_settlement_store_platform_date", "store_id", "platform", "settlement_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    external_settlement_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    revenue_recognition_year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    settlement_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    revenue_recognition_date_from: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    revenue_recognition_date_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KRW")
    total_sale: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    service_fee: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    settlement_target_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    settlement_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pending_released_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    dedicated_delivery_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    seller_service_fee: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    courantee_fee: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deduction_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    final_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    observed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="platform_settlement_details")

    @validates("observed_fields")
    def _validate_observed_fields(self, _key: str, value: list[str] | None) -> list[str] | None:
        return validate_observed_fields(value)
