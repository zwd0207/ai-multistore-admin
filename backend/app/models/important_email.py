from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class ImportantEmail(Base):
    __tablename__ = "important_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    email_account_id: Mapped[int | None] = mapped_column(ForeignKey("email_accounts.id"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mail_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unread", index=True)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal", index=True)
    related_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="important_emails")
    email_account = relationship("EmailAccount", back_populates="important_emails")
