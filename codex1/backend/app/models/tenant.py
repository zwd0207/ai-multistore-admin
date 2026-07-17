from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        Index("uq_tenants_tenant_key", "tenant_key", unique=True),
        Index("ix_tenants_status", "status"),
        CheckConstraint("status IN ('active', 'suspended', 'archived')", name="ck_tenants_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False,
    )

    users = relationship("ErpUser", back_populates="tenant")
    stores = relationship("Store", back_populates="tenant")


class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"
    __table_args__ = (
        Index("uq_tenant_invitations_token_hash", "token_hash", unique=True),
        Index("uq_tenant_invitations_enrollment_hash", "mfa_enrollment_token_hash", unique=True),
        Index("ix_tenant_invitations_email_status", "email_hash", "status"),
        Index(
            "uq_tenant_invitations_active_email_hash",
            "email_hash",
            unique=True,
            sqlite_where=text("status IN ('pending', 'pending_mfa')"),
            postgresql_where=text("status IN ('pending', 'pending_mfa')"),
        ),
        CheckConstraint(
            "status IN ('pending', 'pending_mfa', 'accepted', 'revoked', 'expired')",
            name="ck_tenant_invitations_status",
        ),
        CheckConstraint(
            "invited_platform_role IN ('tenant_owner', 'platform_admin')",
            name="ck_tenant_invitations_platform_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    email_masked: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_name: Mapped[str] = mapped_column(String(160), nullable=False)
    target_tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    invited_platform_role: Mapped[str] = mapped_column(
        String(30), nullable=False, default="tenant_owner", server_default="tenant_owner",
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    invited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("erp_users.id"), nullable=True)
    accepted_user_id: Mapped[int | None] = mapped_column(ForeignKey("erp_users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_enrollment_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enrollment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False,
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("uq_password_reset_tokens_hash", "token_hash", unique=True),
        Index("ix_password_reset_tokens_user_active", "user_id", "used_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("erp_users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ErpMfaRecoveryCode(Base):
    __tablename__ = "erp_mfa_recovery_codes"
    __table_args__ = (
        Index("uq_erp_mfa_recovery_code_hash", "code_hash", unique=True),
        Index("ix_erp_mfa_recovery_codes_user_unused", "user_id", "used_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("erp_users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
