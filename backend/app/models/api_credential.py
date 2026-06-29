from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class ApiCredential(Base):
    __tablename__ = "api_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    credential_name: Mapped[str] = mapped_column(String(120), nullable=False)
    vendor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_access_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_secret_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market: Mapped[str | None] = mapped_column(String(30), nullable=True)
    auth_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_configured", index=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    api_remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="inactive", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="api_credentials")
