from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="KR")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="ko-KR")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

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
