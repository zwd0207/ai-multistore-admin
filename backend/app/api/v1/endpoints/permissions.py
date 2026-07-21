from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.permission import (
    PermissionMockCheckRequest,
    SensitiveActionPermissionMockCheckRequest,
    StoreMembershipReadonlyCheckRequest,
    UserInvitationApprovalAuditLinkageReadonlyCheckRequest,
    UserInvitationApprovalChecklistReadonlyCheckRequest,
    UserInvitationReadonlyCheckRequest,
)
from app.services.invitation_audit_linkage_service import (
    evaluate_real_user_invitation_approval_audit_linkage_readonly_api_local,
)
from app.services.permission_service import (
    VERIFICATION_SCOPE,
    evaluate_real_user_invitation_approval_checklist_readonly_api_local,
    evaluate_real_user_invitation_mock_gate,
    evaluate_sensitive_action_approval_mock_gate,
    evaluate_store_membership_assignment_runtime_mock_gate,
    evaluate_store_scoped_access_mock_gate,
    role_permission_inventory,
)


router = APIRouter(prefix="/permissions", tags=["permissions"])


def _public_mock_safety_flags() -> dict:
    return {
        "mock_permission_api": True,
        "public_endpoint_enabled": True,
        "real_auth_session_created": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }


@router.get("/role-inventory")
def get_role_permission_inventory() -> dict:
    return success_response(data={
        "phase": "ERP-Auth-1F",
        "status": "role_inventory_ready",
        "business_message": "当前仅开放本地角色权限模型预览，用于页面展示和后续审批设计；正式登录权限系统尚未开放。",
        "roles": role_permission_inventory(),
        **_public_mock_safety_flags(),
    })


@router.post("/mock-check")
def check_permission_mock_gate(payload: PermissionMockCheckRequest) -> dict:
    result = evaluate_store_scoped_access_mock_gate(
        actor_context=payload.actor_context,
        requested_store_id=payload.store_id,
        operation_key=payload.operation_key,
        verification_scope=VERIFICATION_SCOPE,
    )
    if result.get("status") == "access_allowed":
        business_message = "当前角色可查看该店铺的对应功能。"
    elif result.get("skip_reason") == "store_scope_mismatch":
        business_message = "当前角色未被分配到该店铺，不能访问该店铺数据。"
    elif result.get("skip_reason") == "permission_denied":
        business_message = "当前角色没有该操作权限，请联系管理员处理。"
    else:
        business_message = "当前权限检查未通过，请检查角色、店铺范围或操作类型。"
    return success_response(data={
        **result,
        "phase": "ERP-Auth-1F",
        "business_message": business_message,
        **_public_mock_safety_flags(),
    })


@router.post("/sensitive-action/mock-check")
def check_sensitive_action_permission_mock_gate(payload: SensitiveActionPermissionMockCheckRequest) -> dict:
    result = evaluate_sensitive_action_approval_mock_gate(
        actor_context=payload.actor_context,
        requested_store_id=payload.store_id,
        action_key=payload.action_key,
        manual_approval=payload.manual_approval,
        verification_scope=VERIFICATION_SCOPE,
    )
    if result.get("status") == "approval_allowed_mock":
        business_message = "管理员审批条件在 mock gate 中通过；真实写入仍需要单独阶段执行。"
    elif result.get("skip_reason") == "manual_approval_required":
        business_message = "该操作属于敏感操作，需要管理员人工批准后才能进入后续执行阶段。"
    elif result.get("skip_reason") in {"permission_denied", "approval_role_required"}:
        business_message = "当前角色不能批准该敏感操作，请由管理员或负责人审批。"
    else:
        business_message = "当前敏感操作审批检查未通过，不能进入写入阶段。"
    return success_response(data={
        **result,
        "phase": "ERP-Auth-1F",
        "business_message": business_message,
        **_public_mock_safety_flags(),
    })


@router.post("/store-membership/readonly-check")
def check_store_membership_readonly_gate(
    payload: StoreMembershipReadonlyCheckRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = evaluate_store_membership_assignment_runtime_mock_gate(
        db,
        actor_context=payload.actor_context,
        target_user_key_hash=payload.target_user_key_hash,
        target_store_id=payload.target_store_id,
        target_role=payload.target_role,
        manual_approval=payload.manual_approval,
        assignment_reason=payload.assignment_reason,
    )
    if result.get("status") == "membership_assignment_runtime_mock_ready":
        business_message = "店铺成员分配只读检查已通过。当前不会创建用户或店铺成员关系。"
    elif result.get("skip_reason") == "duplicate_active_membership":
        business_message = "该用户已经拥有相同店铺角色，不需要重复分配。"
    elif result.get("skip_reason") == "target_user_not_found":
        business_message = "目标用户尚不存在，当前不能分配店铺权限。"
    else:
        business_message = "店铺成员分配只读检查未通过，请管理员查看折叠详情。"
    return success_response(data={
        **result,
        "phase": "ERP-Multistore-1G",
        "store_membership_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "public_endpoint_enabled": True,
        "business_message": business_message,
        "membership_written": False,
        "real_database_written": False,
        "real_auth_session_created": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    })


@router.post("/user-invitation/readonly-check")
def check_user_invitation_readonly_gate(payload: UserInvitationReadonlyCheckRequest) -> dict:
    result = evaluate_real_user_invitation_mock_gate(
        actor_context=payload.actor_context,
        target_user_key_hash=payload.target_user_key_hash,
        login_identifier_hash=payload.login_identifier_hash,
        login_identifier_masked=payload.login_identifier_masked,
        target_store_ids=payload.target_store_ids,
        target_role=payload.target_role,
        manual_approval=payload.manual_approval,
        invitation_reason=payload.invitation_reason,
        backup_evidence_planned=payload.backup_evidence_planned,
        audit_evidence_planned=payload.audit_evidence_planned,
        membership_assignment_plan_ready=payload.membership_assignment_plan_ready,
        existing_user_hashes=payload.existing_user_hashes,
        verification_scope=VERIFICATION_SCOPE,
    )
    if result.get("status") == "user_invitation_mock_ready":
        business_message = "用户邀请只读检查已通过。当前不会创建用户、发送邀请或分配店铺成员。"
    elif result.get("skip_reason") == "target_user_already_exists":
        business_message = "目标用户已存在，当前不会重复创建邀请。"
    elif result.get("skip_reason") in {"login_identifier_must_be_masked", "login_identifier_masked_invalid"}:
        business_message = "登录标识必须脱敏后才能展示。"
    elif result.get("skip_reason") == "manual_approval_required":
        business_message = "用户邀请属于敏感操作，需要管理员人工批准后才能继续。"
    elif result.get("skip_reason") in {"permission_denied", "approval_role_required"}:
        business_message = "当前角色不能批准用户邀请，请由管理员或负责人审批。"
    else:
        business_message = "用户邀请只读检查未通过，请管理员查看折叠详情。"
    return success_response(data={
        **result,
        "phase": "ERP-Multistore-1P",
        "user_invitation_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "public_endpoint_enabled": True,
        "business_message": business_message,
        "invitation_sent": False,
        "users_written": False,
        "membership_written": False,
        "role_assignment_written": False,
        "real_auth_session_created": False,
        "real_database_written": False,
        "orders_written": False,
        "products_written": False,
        "sync_log_written": False,
        "capability_tested_success_written": False,
        "operation_audit_rows_written": False,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
    })


@router.post("/user-invitation/approval-checklist/readonly-check")
def check_user_invitation_approval_checklist_readonly_gate(
    payload: UserInvitationApprovalChecklistReadonlyCheckRequest,
) -> dict:
    result = evaluate_real_user_invitation_approval_checklist_readonly_api_local(
        actor_context=payload.actor_context,
        target_user_key_hash=payload.target_user_key_hash,
        login_identifier_hash=payload.login_identifier_hash,
        login_identifier_masked=payload.login_identifier_masked,
        target_store_ids=payload.target_store_ids,
        target_role=payload.target_role,
        manual_approval=payload.manual_approval,
        invitation_reason=payload.invitation_reason,
        approval_checklist=payload.approval_checklist,
        readonly_api_context=payload.readonly_api_context,
        existing_user_hashes=payload.existing_user_hashes,
    )
    return success_response(
        data=result,
        message="user invitation approval checklist readonly checked",
    )


@router.post("/user-invitation/approval-audit-linkage/readonly-check")
def check_user_invitation_approval_audit_linkage_readonly_gate(
    payload: UserInvitationApprovalAuditLinkageReadonlyCheckRequest,
) -> dict:
    result = evaluate_real_user_invitation_approval_audit_linkage_readonly_api_local(
        invitation_approval=payload.invitation_approval,
        audit_linkage_context=payload.audit_linkage_context,
        readonly_api_context=payload.readonly_api_context,
    )
    return success_response(
        data=result,
        message="user invitation approval audit linkage readonly checked",
    )
