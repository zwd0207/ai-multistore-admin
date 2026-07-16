from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timezone import get_utc_now
from app.database import Base


def utc_now() -> datetime:
    return get_utc_now()


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        Index("uq_stores_tenant_name", "tenant_id", "name", unique=True),
        Index("uq_stores_tenant_ziniao_external_hash", "tenant_id", "ziniao_external_id_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="KR")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="ko-KR")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    browser_profile_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ziniao_external_id_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ziniao_external_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ziniao_source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ziniao_source_platform: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ziniao_source_site: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ziniao_auto_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    ziniao_name_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    ziniao_directory_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unmanaged", server_default="unmanaged", index=True,
    )
    ziniao_operational_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="business", server_default="business", index=True,
    )
    ziniao_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ziniao_directory_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ziniao_missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ziniao_missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="stores")

    api_credentials = relationship(
        "ApiCredential",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    platform_login_credentials = relationship(
        "PlatformLoginCredential",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    sync_logs = relationship(
        "SyncLog",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    sync_checkpoints = relationship(
        "SyncCheckpoint",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    products = relationship(
        "Product",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    orders = relationship(
        "Order",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    order_status_events = relationship(
        "OrderStatusEvent",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    operation_audit_logs = relationship(
        "OperationAuditLog",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    erp_store_memberships = relationship(
        "ErpStoreMembership",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    platform_sales_details = relationship(
        "PlatformSalesDetail",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    platform_settlement_details = relationship(
        "PlatformSettlementDetail",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    logistics_inventory_mappings = relationship(
        "LogisticsInventoryMapping",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    logistics_inventory_items = relationship(
        "LogisticsInventoryItem",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    shipping_export_batches = relationship(
        "ShippingExportBatch",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    shipping_tracking_import_batches = relationship(
        "ShippingTrackingImportBatch",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    customer_inquiries = relationship(
        "CustomerInquiry",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    device_environments = relationship(
        "DeviceEnvironment",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    email_accounts = relationship(
        "EmailAccount",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    important_emails = relationship(
        "ImportantEmail",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    appeal_cases = relationship(
        "AppealCase",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    api_capability_test_results = relationship(
        "ApiCapabilityTestResult",
        back_populates="store",
        cascade="all, delete-orphan",
    )
