from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class PlatformLoginCredential(Base):
    __tablename__ = "platform_login_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    login_label: Mapped[str] = mapped_column(String(120), nullable=False)
    login_account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_login_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_account_id: Mapped[int | None] = mapped_column(ForeignKey("email_accounts.id"), nullable=True, index=True)
    device_environment_id: Mapped[int | None] = mapped_column(ForeignKey("device_environments.id"), nullable=True, index=True)
    login_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown", index=True)
    last_login_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="platform_login_credentials")
    email_account = relationship("EmailAccount")
    device_environment = relationship("DeviceEnvironment")
