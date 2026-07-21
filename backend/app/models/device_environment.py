from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class DeviceEnvironment(Base):
    __tablename__ = "device_environments"
    __table_args__ = (
        Index("uq_device_environments_store_source", "store_id", "source_provider", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    environment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    os_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    browser_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    proxy_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    encrypted_ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    masked_ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    network_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    network_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    network_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    network_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_configured", server_default="not_configured", index=True,
    )
    network_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="device_environments")
