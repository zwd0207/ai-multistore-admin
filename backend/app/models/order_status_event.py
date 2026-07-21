from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from app.models.store import utc_now


FORBIDDEN_SAFE_METADATA_FRAGMENTS = {
    "authorization",
    "bcrypt",
    "buyer",
    "clientsecret",
    "client_secret",
    "completefield",
    "complete_field",
    "header",
    "phone",
    "rawdata",
    "rawresponse",
    "raw_data",
    "raw_response",
    "receiver",
    "secret",
    "signature",
    "token",
    "zipcode",
    "zip_code",
}

ALLOWED_SAFE_METADATA_NAMES = {
    "addresssaved",
    "address_saved",
    "privacyfieldsredacted",
    "privacy_fields_redacted",
    "rawresponsesaved",
    "raw_response_saved",
}


def _metadata_field_names(payload: object) -> list[str]:
    if isinstance(payload, dict):
        names: list[str] = []
        for key, value in payload.items():
            names.append(str(key))
            names.extend(_metadata_field_names(value))
        return names
    if isinstance(payload, list):
        names: list[str] = []
        for item in payload:
            names.extend(_metadata_field_names(item))
        return names
    return []


def validate_safe_metadata(value: dict | None) -> dict | None:
    if value is None:
        return value
    field_names = _metadata_field_names(value)
    normalized = {
        name.replace("-", "").replace("_", "").replace(" ", "").lower()
        for name in field_names
    } - ALLOWED_SAFE_METADATA_NAMES
    forbidden = sorted(
        name
        for name in normalized
        if any(fragment in name for fragment in FORBIDDEN_SAFE_METADATA_FRAGMENTS)
    )
    if forbidden:
        raise ValueError(f"safe_metadata contains forbidden field names: {forbidden}")
    return value


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"
    __table_args__ = (
        Index("uq_order_status_event_dedupe", "store_id", "platform", "dedupe_key", unique=True),
        Index("ix_order_status_events_store_platform_observed", "store_id", "platform", "observed_at"),
        Index("ix_order_status_events_order_observed", "order_id", "observed_at"),
        Index("ix_order_status_events_store_event_type", "store_id", "platform", "event_type"),
        Index("ix_order_status_events_product_order_hash", "external_product_order_id_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_order_id_hash: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_product_order_id_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status_label_zh: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_status_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payment_status_label_zh: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_status_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    delivery_status_label_zh: Mapped[str | None] = mapped_column(String(120), nullable=True)
    claim_status_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    claim_status_label_zh: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_phase: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(320), nullable=False)
    raw_response_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    privacy_fields_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    address_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store = relationship("Store", back_populates="order_status_events")
    order = relationship("Order", back_populates="status_events")

    @validates("safe_metadata")
    def _validate_safe_metadata(self, _key: str, value: dict | None) -> dict | None:
        return validate_safe_metadata(value)
