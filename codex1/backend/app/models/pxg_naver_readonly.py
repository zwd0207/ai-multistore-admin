from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.store import utc_now


class PxgNaverReadonlyRecordState(Base):
    """Freshness and idempotency metadata for approved PXG/Naver local records.

    This table deliberately contains only identifiers, hashes, timestamps, and flags.
    It never stores source payloads, request details, credentials, or recipient data.
    """

    __tablename__ = "pxg_naver_readonly_record_states"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "platform",
            "resource_type",
            "source_key_hash",
            name="uq_pxg_naver_readonly_state_source",
        ),
        Index(
            "ix_pxg_naver_readonly_state_store_resource",
            "store_id",
            "platform",
            "resource_type",
            "is_stale",
        ),
        Index("ix_pxg_naver_readonly_state_expiry", "expires_at", "is_stale"),
        CheckConstraint("platform = 'naver'", name="ck_pxg_naver_readonly_state_platform"),
        CheckConstraint(
            "resource_type IN ('product', 'order', 'recipient', 'logistics', 'customer_inquiry')",
            name="ck_pxg_naver_readonly_state_resource",
        ),
        CheckConstraint("is_stale IN (FALSE, TRUE)", name="ck_pxg_naver_readonly_state_stale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    local_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PxgNaverOrderRecipientSecureRecord(Base):
    """Encrypted recipient contract for PXG/Naver orders.

    Full recipient data is intentionally isolated from the generic orders table and
    can only be decrypted from the authorised warehouse fulfillment service.
    """

    __tablename__ = "pxg_naver_order_recipient_secure_records"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_pxg_naver_recipient_order"),
        Index("ix_pxg_naver_recipient_store_order", "store_id", "order_id"),
        Index("ix_pxg_naver_recipient_expiry", "expires_at", "is_stale"),
        CheckConstraint("platform = 'naver'", name="ck_pxg_naver_recipient_platform"),
        CheckConstraint("is_stale IN (FALSE, TRUE)", name="ck_pxg_naver_recipient_stale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    encrypted_recipient_payload: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminal_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PxgNaverReadonlyLogisticsRecord(Base):
    __tablename__ = "pxg_naver_readonly_logistics_records"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_pxg_naver_logistics_order"),
        Index("ix_pxg_naver_logistics_store_status", "store_id", "platform", "is_stale"),
        Index("ix_pxg_naver_logistics_expiry", "expires_at", "is_stale"),
        CheckConstraint("platform = 'naver'", name="ck_pxg_naver_logistics_platform"),
        CheckConstraint("is_stale IN (FALSE, TRUE)", name="ck_pxg_naver_logistics_stale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    carrier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_tracking_number: Mapped[str] = mapped_column(Text, nullable=False)
    tracking_number_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tracking_number_masked: Mapped[str] = mapped_column(String(120), nullable=False)
    shipment_status: Mapped[str] = mapped_column(String(60), nullable=False, default="observed")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PxgNaverReadonlyCustomerInquiry(Base):
    """Naver readonly inquiry storage (legacy PXG table name retained for compatibility)."""

    __tablename__ = "pxg_naver_readonly_customer_inquiries"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "platform",
            "external_inquiry_id_hash",
            name="uq_pxg_naver_readonly_inquiry",
        ),
        Index("ix_pxg_naver_readonly_inquiry_store_status", "store_id", "platform", "status"),
        Index("ix_pxg_naver_readonly_inquiry_expiry", "expires_at", "is_stale"),
        CheckConstraint("platform = 'naver'", name="ck_pxg_naver_readonly_inquiry_platform"),
        CheckConstraint("is_stale IN (FALSE, TRUE)", name="ck_pxg_naver_readonly_inquiry_stale"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    external_inquiry_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    related_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    inquiry_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_display_masked: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subject_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    encrypted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PxgNaverReadonlyCleanupStatus(Base):
    """PII-free health state for the PXG/Naver readonly retention job."""

    __tablename__ = "pxg_naver_readonly_cleanup_statuses"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", name="uq_pxg_naver_readonly_cleanup_store"),
        CheckConstraint("platform = 'naver'", name="ck_pxg_naver_readonly_cleanup_platform"),
        CheckConstraint(
            "status IN ('healthy', 'manual_review_required', 'failed')",
            name="ck_pxg_naver_readonly_cleanup_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="healthy", server_default="healthy")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manual_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PxgNaverReadonlySyncControl(Base):
    __tablename__ = "pxg_naver_readonly_sync_controls"
    __table_args__ = (UniqueConstraint("store_id", "platform", name="uq_pxg_naver_readonly_sync_control"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    write_and_refresh_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    backup_retention_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class PxgNaverReadonlySyncBatch(Base):
    __tablename__ = "pxg_naver_readonly_sync_batches"
    __table_args__ = (
        UniqueConstraint("batch_no", name="uq_pxg_naver_readonly_sync_batch_no"),
        Index("ix_pxg_naver_readonly_sync_batch_store_status", "store_id", "platform", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="prepared")
    actor_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mutation_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_record_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PxgNaverReadonlySyncBackup(Base):
    __tablename__ = "pxg_naver_readonly_sync_backups"
    __table_args__ = (UniqueConstraint("backup_ref", name="uq_pxg_naver_readonly_sync_backup_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("pxg_naver_readonly_sync_batches.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="naver")
    backup_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    encrypted_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    restore_drill_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
