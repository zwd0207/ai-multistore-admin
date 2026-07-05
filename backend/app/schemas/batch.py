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


class FormalBatchExecutionPreflightReadonlyCheckRequest(BaseModel):
    approval_decision: dict[str, Any] = Field(default_factory=dict)
    approval_audit_linkage: dict[str, Any] = Field(default_factory=dict)
    execution_approvals: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    preflight_context: dict[str, Any] = Field(default_factory=dict)


class FormalBatchExecutionDryRunReadonlyCheckRequest(BaseModel):
    execution_preflight: dict[str, Any] = Field(default_factory=dict)
    dry_run_context: dict[str, Any] = Field(default_factory=dict)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    candidate_summaries: list[dict[str, Any]] = Field(default_factory=list, max_length=10)


class FormalBatchExecutionApprovalReadonlyCheckRequest(BaseModel):
    execution_preflight: dict[str, Any] = Field(default_factory=dict)
    execution_dry_run: dict[str, Any] = Field(default_factory=dict)
    final_approval_context: dict[str, Any] = Field(default_factory=dict)


class FormalBatchExecutionWriteBoundaryReadonlyCheckRequest(BaseModel):
    execution_approval: dict[str, Any] = Field(default_factory=dict)
    write_boundary_context: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class FormalBatchPreExecutionRefreshReadonlyCheckRequest(BaseModel):
    write_boundary_review: dict[str, Any] = Field(default_factory=dict)
    backup_refresh_evidence: dict[str, Any] = Field(default_factory=dict)
    audit_refresh_evidence: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class NaverProductBatchExecutionApprovalReadonlyCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    store_ids: list[int] = Field(default_factory=list, max_length=10)
    candidate_count: int = Field(default=0, ge=0, le=1000)
    batch_size: int = Field(default=0, ge=0, le=1000)
    readonly_evidence: dict[str, Any] = Field(default_factory=dict)
    backup_evidence: dict[str, Any] = Field(default_factory=dict)
    manual_approval: bool = False
    execution_context: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class NaverOrderBatchExecutionApprovalReadonlyCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    store_ids: list[int] = Field(default_factory=list, max_length=10)
    candidate_count: int = Field(default=0, ge=0, le=1000)
    batch_size: int = Field(default=0, ge=0, le=1000)
    readonly_evidence: dict[str, Any] = Field(default_factory=dict)
    backup_evidence: dict[str, Any] = Field(default_factory=dict)
    manual_approval: bool = False
    execution_context: dict[str, Any] = Field(default_factory=dict)
    readonly_api_context: dict[str, Any] = Field(default_factory=dict)


class NaverProductRollbackReadonlyReportRequest(BaseModel):
    rollback_drill_gate: dict[str, Any] = Field(default_factory=dict)
