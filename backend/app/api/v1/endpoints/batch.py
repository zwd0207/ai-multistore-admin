from fastapi import APIRouter

from app.core.responses import success_response
from app.schemas.batch import (
    BatchApprovalAuditEvidenceRequest,
    BatchApprovalDecisionAuditLinkageReadonlyCheckRequest,
    BatchApprovalDecisionReadonlyCheckRequest,
    BatchReadonlyEvidenceRequest,
    FormalBatchExecutionApprovalReadonlyCheckRequest,
    FormalBatchExecutionDryRunReadonlyCheckRequest,
    FormalBatchExecutionPreflightReadonlyCheckRequest,
    FormalBatchExecutionWriteBoundaryReadonlyCheckRequest,
    FormalBatchPreExecutionRefreshReadonlyCheckRequest,
    FormalBatchWriteExecutionReadonlyCheckRequest,
    NaverOrderBatchExecutionApprovalReadonlyCheckRequest,
    NaverProductBatchExecutionApprovalReadonlyCheckRequest,
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


@router.post("/execution-preflight/readonly-check")
def check_formal_batch_execution_preflight_readonly(
    payload: FormalBatchExecutionPreflightReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_execution_preflight_readonly_api_local(
        approval_decision=payload.approval_decision,
        approval_audit_linkage=payload.approval_audit_linkage,
        execution_approvals=payload.execution_approvals,
        preflight_context=payload.preflight_context,
    )
    return success_response(
        data=result,
        message="formal batch execution preflight readonly check completed",
    )


@router.post("/execution-dry-run/readonly-check")
def check_formal_batch_execution_dry_run_readonly(
    payload: FormalBatchExecutionDryRunReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_execution_dry_run_readonly_api_local(
        execution_preflight=payload.execution_preflight,
        dry_run_context=payload.dry_run_context,
        execution_plan=payload.execution_plan,
        candidate_summaries=payload.candidate_summaries,
    )
    return success_response(
        data=result,
        message="formal batch execution dry-run readonly check completed",
    )


@router.post("/execution-approval/readonly-check")
def check_formal_batch_execution_approval_readonly(
    payload: FormalBatchExecutionApprovalReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_execution_approval_readonly_api_local(
        execution_preflight=payload.execution_preflight,
        execution_dry_run=payload.execution_dry_run,
        final_approval_context=payload.final_approval_context,
    )
    return success_response(
        data=result,
        message="formal batch execution approval readonly check completed",
    )


@router.post("/execution-write-boundary/readonly-check")
def check_formal_batch_execution_write_boundary_readonly(
    payload: FormalBatchExecutionWriteBoundaryReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_execution_write_boundary_readonly_api_local(
        execution_approval=payload.execution_approval,
        write_boundary_context=payload.write_boundary_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="formal batch execution write boundary readonly check completed",
    )


@router.post("/pre-execution-refresh/readonly-check")
def check_formal_batch_pre_execution_refresh_readonly(
    payload: FormalBatchPreExecutionRefreshReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_pre_execution_refresh_readonly_api_local(
        write_boundary_review=payload.write_boundary_review,
        backup_refresh_evidence=payload.backup_refresh_evidence,
        audit_refresh_evidence=payload.audit_refresh_evidence,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="formal batch pre-execution refresh readonly check completed",
    )


@router.post("/write-execution/readonly-check")
def check_formal_batch_write_execution_readonly(
    payload: FormalBatchWriteExecutionReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_formal_batch_write_execution_readonly_api_local(
        pre_execution_refresh_review=payload.pre_execution_refresh_review,
        write_execution_context=payload.write_execution_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="formal batch write execution readonly check completed",
    )


@router.post("/naver/products/execution-approval/readonly-check")
def check_naver_product_batch_execution_approval_readonly(
    payload: NaverProductBatchExecutionApprovalReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_naver_product_batch_execution_approval_readonly_api_local(
        actor_context=payload.actor_context,
        store_ids=payload.store_ids,
        candidate_count=payload.candidate_count,
        batch_size=payload.batch_size,
        readonly_evidence=payload.readonly_evidence,
        backup_evidence=payload.backup_evidence,
        manual_approval=payload.manual_approval,
        execution_context=payload.execution_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="naver product batch execution approval readonly check completed",
    )


@router.post("/naver/orders/execution-approval/readonly-check")
def check_naver_order_batch_execution_approval_readonly(
    payload: NaverOrderBatchExecutionApprovalReadonlyCheckRequest,
) -> dict:
    result = sync_service.evaluate_naver_order_batch_execution_approval_readonly_api_local(
        actor_context=payload.actor_context,
        store_ids=payload.store_ids,
        candidate_count=payload.candidate_count,
        batch_size=payload.batch_size,
        readonly_evidence=payload.readonly_evidence,
        backup_evidence=payload.backup_evidence,
        manual_approval=payload.manual_approval,
        execution_context=payload.execution_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="naver order batch execution approval readonly check completed",
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
