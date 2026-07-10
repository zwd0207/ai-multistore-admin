from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class ErpUser(Base):
    __tablename__ = "erp_users"
    __table_args__ = (
        Index("ix_erp_users_status", "status"),
        CheckConstraint("status IN ('invited', 'active', 'inactive', 'locked')", name="ck_erp_users_status"),
        CheckConstraint(
            "auth_provider IN ('local_pending', 'password', 'sso', 'api_operator')",
            name="ck_erp_users_auth_provider",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_key_hash: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    login_identifier_hash: Mapped[str | None] = mapped_column(String(120), nullable=True)
    login_identifier_masked: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="invited", server_default="invited")
    auth_provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="local_pending",
        server_default="local_pending",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    store_memberships = relationship(
        "ErpStoreMembership",
        foreign_keys="ErpStoreMembership.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    assigned_store_memberships = relationship(
        "ErpStoreMembership",
        foreign_keys="ErpStoreMembership.assigned_by_user_id",
        back_populates="assigned_by_user",
    )


class ErpRole(Base):
    __tablename__ = "erp_roles"
    __table_args__ = (
        Index("ix_erp_roles_status", "status"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_erp_roles_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    role_label_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    role_label_en: Mapped[str] = mapped_column(String(120), nullable=False)
    system_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    role_permissions = relationship("ErpRolePermission", back_populates="role", cascade="all, delete-orphan")
    store_memberships = relationship("ErpStoreMembership", back_populates="role", cascade="all, delete-orphan")


class ErpPermission(Base):
    __tablename__ = "erp_permissions"
    __table_args__ = (
        Index("ix_erp_permissions_group", "permission_group"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_erp_permissions_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    permission_group: Mapped[str] = mapped_column(String(80), nullable=False)
    permission_label_zh: Mapped[str] = mapped_column(String(160), nullable=False)
    sensitive_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    role_permissions = relationship("ErpRolePermission", back_populates="permission", cascade="all, delete-orphan")


class ErpRolePermission(Base):
    __tablename__ = "erp_role_permissions"
    __table_args__ = (
        Index("ix_erp_role_permissions_role", "role_id"),
        Index("uq_erp_role_permissions_role_permission", "role_id", "permission_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("erp_roles.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(ForeignKey("erp_permissions.id"), nullable=False)
    can_approve_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    role = relationship("ErpRole", back_populates="role_permissions")
    permission = relationship("ErpPermission", back_populates="role_permissions")


class ErpStoreMembership(Base):
    __tablename__ = "erp_store_memberships"
    __table_args__ = (
        Index("ix_erp_store_memberships_store_status", "store_id", "membership_status"),
        Index("ix_erp_store_memberships_user_status", "user_id", "membership_status"),
        Index("uq_erp_store_memberships_user_store_role", "user_id", "store_id", "role_id", unique=True),
        CheckConstraint("store_id > 0", name="ck_erp_store_memberships_store_positive"),
        CheckConstraint("scope_type IN ('all', 'assigned')", name="ck_erp_store_memberships_scope_type"),
        CheckConstraint(
            "membership_status IN ('active', 'inactive', 'revoked')",
            name="ck_erp_store_memberships_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("erp_users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("erp_roles.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, default="assigned", server_default="assigned")
    membership_status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("erp_users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user = relationship("ErpUser", foreign_keys=[user_id], back_populates="store_memberships")
    assigned_by_user = relationship(
        "ErpUser",
        foreign_keys=[assigned_by_user_id],
        back_populates="assigned_store_memberships",
    )
    role = relationship("ErpRole", back_populates="store_memberships")
    store = relationship("Store", back_populates="erp_store_memberships")
