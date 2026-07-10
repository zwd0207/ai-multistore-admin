from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.store import utc_now


class ApiCapabilityCheck(Base):
    __tablename__ = "api_capability_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    capability_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    capability_name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    endpoint_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    required_credential_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinary_store_supported: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown", index=True)
    test_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_tested", index=True)
    test_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="docs_only", index=True)
    request_params_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_fields_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_codes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_usefulness: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown", index=True)
    first_phase_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sales_source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="not_applicable", index=True)
    official_doc_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    doc_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    test_results = relationship(
        "ApiCapabilityTestResult",
        back_populates="capability",
        cascade="all, delete-orphan",
    )


class ApiCapabilityTestResult(Base):
    __tablename__ = "api_capability_test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("api_credentials.id"), nullable=True, index=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("api_capability_checks.id"), nullable=False, index=True)
    test_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", index=True)
    test_status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    permission_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_fields_observed: Mapped[str | None] = mapped_column(Text, nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    capability = relationship("ApiCapabilityCheck", back_populates="test_results")
    credential = relationship("ApiCredential")
    store = relationship("Store")
