from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


def _sha256_check(column_name: str) -> str:
    remainder = column_name
    for character in "0123456789abcdef":
        remainder = f"replace({remainder}, '{character}', '')"
    return f"{column_name} IS NULL OR (length({column_name}) = 64 AND length({remainder}) = 0)"


class OperationAuditLog(Base):
    __tablename__ = "operation_audit_logs"
    __table_args__ = (
        Index("ix_operation_audit_logs_created_at", "created_at"),
        Index("ix_operation_audit_logs_store_created_at", "store_id", "created_at"),
        Index("ix_operation_audit_logs_platform_created_at", "platform", "created_at"),
        Index("ix_operation_audit_logs_actor_created_at", "actor_type", "actor_id", "created_at"),
        Index("ix_operation_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_operation_audit_logs_status_reason", "status", "reason_code"),
        Index("ix_operation_audit_logs_target", "target_type", "target_id"),
        Index("ix_operation_audit_logs_target_hash", "target_hash"),
        Index("ix_operation_audit_logs_correlation_id", "correlation_id"),
        Index("ix_operation_audit_logs_request_id", "request_id"),
        CheckConstraint("length(trim(actor_type)) > 0", name="ck_operation_audit_logs_actor_type_not_empty"),
        CheckConstraint("length(trim(action)) > 0", name="ck_operation_audit_logs_action_not_empty"),
        CheckConstraint("length(trim(correlation_id)) > 0", name="ck_operation_audit_logs_correlation_id_not_empty"),
        CheckConstraint("length(trim(status)) > 0", name="ck_operation_audit_logs_status_not_empty"),
        CheckConstraint("raw_response_saved IN (FALSE, TRUE)", name="ck_operation_audit_logs_raw_response_saved_bool"),
        CheckConstraint("secrets_saved IN (FALSE, TRUE)", name="ck_operation_audit_logs_secrets_saved_bool"),
        CheckConstraint("privacy_fields_redacted IN (FALSE, TRUE)", name="ck_operation_audit_logs_privacy_fields_bool"),
        CheckConstraint(_sha256_check("backup_sha256"), name="ck_operation_audit_logs_backup_sha256"),
        CheckConstraint(_sha256_check("restore_source_sha256"), name="ck_operation_audit_logs_restore_sha256"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    environment: Mapped[str] = mapped_column(String(30), nullable=False, default="local", server_default="local")
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    operation_phase: Mapped[str | None] = mapped_column(String(120), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_field_names: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    before_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    counts_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safety_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    backup_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    backup_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    restore_source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    restore_source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sensitive_scan_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    raw_response_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    secrets_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    privacy_fields_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    store = relationship("Store", back_populates="operation_audit_logs")
