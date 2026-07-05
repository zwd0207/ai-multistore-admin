from fastapi import APIRouter

from app.core.responses import success_response
from app.schemas.batch import (
    BatchApprovalAuditEvidenceRequest,
    BatchApprovalDecisionAuditLinkageReadonlyCheckRequest,
    BatchApprovalDecisionReadonlyCheckRequest,
    BatchReadonlyEvidenceRequest,
    NaverProductRollbackReadonlyReportRequest,
)
from app.services import sync_service


router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/readonly-evidence")
def normalize_batch_readonly_evidence(payload: BatchReadonlyEvidenceRequest) -> dict:
    result = sync_service.evaluate_batch_readonly_evidence_api_local(
        evidence_items=payload.evidence_items,
        max_items=payload.max_items,
    )
    return success_response(
        data=result,
        message="batch readonly evidence normalized",
    )


@router.post("/approval-audit-evidence")
def check_batch_approval_audit_evidence(payload: BatchApprovalAuditEvidenceRequest) -> dict:
    result = sync_service.evaluate_batch_approval_audit_evidence_readonly_route_local(
        readonly_evidence=payload.readonly_evidence,
        approval_context=payload.approval_context,
        audit_evidence_plan=payload.audit_evidence_plan,
    )
    return success_response(
        data=result,
        message="batch approval audit evidence checked",
    )


@router.post("/approval-decision/readonly-check")
def check_batch_approval_decision_readonly(payload: BatchApprovalDecisionReadonlyCheckRequest) -> dict:
    result = sync_service.evaluate_formal_batch_approval_decision_readonly_api_local(
        readonly_evidence=payload.readonly_evidence,
        approval_audit_evidence=payload.approval_audit_evidence,
        decision_context=payload.decision_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="batch approval decision readonly check completed",
    )


@router.post("/approval-decision/audit-linkage/readonly-check")
def check_batch_approval_decision_audit_linkage_readonly(
    payload: BatchApprovalDecisionAuditLinkageReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_local(
        approval_decision=payload.approval_decision,
        audit_linkage_context=payload.audit_linkage_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="batch approval decision audit linkage readonly check completed",
    )


@router.post("/naver/products/rollback-readonly-report")
def check_naver_product_rollback_readonly_report(
    payload: NaverProductRollbackReadonlyReportRequest,
) -> dict:
    result = sync_service.evaluate_naver_product_rollback_readonly_report_route_local(
        rollback_drill_gate=payload.rollback_drill_gate,
    )
    return success_response(
        data=result,
        message="naver product rollback readonly report checked",
    )
