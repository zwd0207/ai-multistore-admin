from typing import Any

from pydantic import BaseModel, Field


class BatchReadonlyEvidenceRequest(BaseModel):
    evidence_items: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    max_items: int = Field(default=10, ge=1, le=10)


class BatchApprovalAuditEvidenceRequest(BaseModel):
    readonly_evidence: dict[str, Any] = Field(default_factory=dict)
    approval_context: dict[str, Any] = Field(default_factory=dict)
    audit_evidence_plan: dict[str, Any] = Field(default_factory=dict)


class BatchApprovalDecisionReadonlyCheckRequest(BaseModel):
    readonly_evidence: dict[str, Any] = Field(default_factory=dict)
    approval_audit_evidence: dict[str, Any] = Field(default_factory=dict)
    decision_context: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class BatchApprovalDecisionAuditLinkageReadonlyCheckRequest(BaseModel):
    approval_decision: dict[str, Any] = Field(default_factory=dict)
    audit_linkage_context: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class NaverProductRollbackReadonlyReportRequest(BaseModel):
    rollback_drill_gate: dict[str, Any] = Field(default_factory=dict)
