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
