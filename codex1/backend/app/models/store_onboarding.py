from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


ONBOARDING_STATES = (
    "validating",
    "blocked",
    "provisioning",
    "backfilling",
    "partially_synced",
    "active_incremental",
    "retry_wait",
    "cancelled",
)


class StoreOnboarding(Base):
    __tablename__ = "store_onboardings"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_store_onboarding_idempotency_key"),
        CheckConstraint(
            "status IN ('validating', 'blocked', 'provisioning', 'backfilling', "
            "'partially_synced', 'active_incremental', 'retry_wait', 'cancelled')",
            name="ck_store_onboarding_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    requested_store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("erp_users.id"), nullable=False, index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True, unique=True, index=True)
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("api_credentials.id"), nullable=True, unique=True, index=True)
    encrypted_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_channel_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="validating", index=True)
    snapshot_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_window_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    validation_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    progress_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store = relationship("Store")
    credential = relationship("ApiCredential")
    creator = relationship("ErpUser")
