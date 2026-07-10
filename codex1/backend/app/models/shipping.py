from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class LogisticsInventoryMapping(Base):
    __tablename__ = "logistics_inventory_mappings"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "platform",
            "normalized_product_name",
            "normalized_option_name",
            name="uq_logistics_mapping_product_option",
        ),
        Index("ix_logistics_mappings_store_platform", "store_id", "platform"),
        Index(
            "ix_logistics_mappings_match_key",
            "store_id",
            "platform",
            "normalized_product_name",
            "normalized_option_name",
        ),
        Index("ix_logistics_mappings_inventory_code", "logistics_inventory_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    match_product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    match_option_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    normalized_product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_option_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    platform_product_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    platform_option_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    internal_sku: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logistics_inventory_code: Mapped[str] = mapped_column(String(120), nullable=False)
    logistics_provider_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    match_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    mapping_version: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="shipping_mapping_v1",
        server_default="shipping_mapping_v1",
    )
    created_by_actor_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_by_actor_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="logistics_inventory_mappings")


class LogisticsInventoryItem(Base):
    __tablename__ = "logistics_inventory_items"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "platform",
            "logistics_inventory_code",
            name="uq_logistics_inventory_item_code",
        ),
        Index("ix_logistics_inventory_items_store_platform", "store_id", "platform"),
        Index("ix_logistics_inventory_items_code", "logistics_inventory_code"),
        Index("ix_logistics_inventory_items_status", "store_id", "platform", "stock_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    logistics_inventory_code: Mapped[str] = mapped_column(String(120), nullable=False)
    logistics_provider_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    current_stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stock_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="available",
        server_default="available",
    )
    last_manual_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_manual_updated_by_actor_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="logistics_inventory_items")


class ShippingExportBatch(Base):
    __tablename__ = "shipping_export_batches"
    __table_args__ = (
        Index("ix_shipping_export_batches_store_platform_created", "store_id", "platform", "created_at"),
        Index("ix_shipping_export_batches_file_type_status", "file_type", "export_status"),
        Index("ix_shipping_export_batches_audit_correlation", "audit_correlation_id"),
        Index("ix_shipping_export_batches_file_sha256", "file_sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    file_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_format: Mapped[str] = mapped_column(String(30), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matched_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unmatched_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    actor_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    audit_correlation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    export_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="generated",
        server_default="generated",
    )
    include_receiver_privacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    file_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    file_persisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    raw_response_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    secrets_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    privacy_fields_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    mapping_version: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="shipping_export_v1",
        server_default="shipping_export_v1",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="shipping_export_batches")
    rows = relationship(
        "ShippingExportBatchRow",
        back_populates="export_batch",
        cascade="all, delete-orphan",
    )


class ShippingExportBatchRow(Base):
    __tablename__ = "shipping_export_batch_rows"
    __table_args__ = (
        Index("ix_shipping_export_rows_batch", "export_batch_id"),
        Index("ix_shipping_export_rows_store_platform", "store_id", "platform"),
        Index("ix_shipping_export_rows_inventory_code", "logistics_inventory_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    export_batch_id: Mapped[int] = mapped_column(ForeignKey("shipping_export_batches.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    order_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    option_name: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    logistics_inventory_code: Mapped[str] = mapped_column(String(120), nullable=False)
    logistics_provider_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    internal_sku: Mapped[str | None] = mapped_column(String(120), nullable=True)
    platform_product_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    platform_option_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    row_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ready",
        server_default="ready",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    export_batch = relationship("ShippingExportBatch", back_populates="rows")
    store = relationship("Store")


class ShippingTrackingImportBatch(Base):
    __tablename__ = "shipping_tracking_import_batches"
    __table_args__ = (
        Index("ix_shipping_tracking_batches_store_platform_created", "store_id", "platform", "created_at"),
        Index("ix_shipping_tracking_batches_status", "store_id", "platform", "import_status"),
        Index("ix_shipping_tracking_batches_audit_correlation", "audit_correlation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    file_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_format: Mapped[str] = mapped_column(String(30), nullable=False)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ready_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duplicate_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    blocked_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    actor_id_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    audit_correlation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    import_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="recorded",
        server_default="recorded",
    )
    parser_contract_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    tracking_number_import_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    shipment_writeback_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    orders_updated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    raw_response_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    secrets_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    privacy_fields_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    mapping_version: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="shipping_tracking_import_v1",
        server_default="shipping_tracking_import_v1",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="shipping_tracking_import_batches")
    rows = relationship(
        "ShippingTrackingImportRow",
        back_populates="import_batch",
        cascade="all, delete-orphan",
    )


class ShippingTrackingImportRow(Base):
    __tablename__ = "shipping_tracking_import_rows"
    __table_args__ = (
        Index("ix_shipping_tracking_rows_batch", "import_batch_id"),
        Index("ix_shipping_tracking_rows_store_platform", "store_id", "platform"),
        Index("ix_shipping_tracking_rows_order_reference", "order_reference"),
        Index("ix_shipping_tracking_rows_tracking_number", "tracking_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("shipping_tracking_import_batches.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    order_reference: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    product_order_reference: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    logistics_inventory_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    carrier: Mapped[str] = mapped_column(String(120), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(120), nullable=False)
    shipped_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    row_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="ready_for_future_review",
        server_default="ready_for_future_review",
    )
    operator_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    future_write_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    import_batch = relationship("ShippingTrackingImportBatch", back_populates="rows")
    store = relationship("Store")
