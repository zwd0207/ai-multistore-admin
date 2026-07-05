from __future__ import annotations

from typing import Any

from app.services.permission_service import (
    SAFE_USER_HASH_PATTERN,
    VERIFICATION_SCOPE,
    _contains_sensitive_material,
    _normalize_role,
)


def _normalize_invitation_store_ids(store_ids: Any) -> list[int] | None:
    if not isinstance(store_ids, (list, tuple, set)) or not store_ids:
        return None
    normalized: list[int] = []
    for store_id in store_ids:
        try:
            safe_store_id = int(store_id)
        except (TypeError, ValueError):
            return None
        if safe_store_id <= 0:
            return None
        normalized.append(safe_store_id)
    return sorted(set(normalized))


def evaluate_real_user_invitation_approval_audit_linkage_mock_gate(
    *,
    invitation_approval: dict[str, Any] | None,
    audit_linkage_context: dict[str, Any] | None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Mock gate for linking a future real invitation approval to audit evidence."""

    required_linkage_flags = [
        "invitation_decision_id_planned",
        "target_user_hash_planned",
        "masked_login_identifier_planned",
        "store_scope_planned",
        "target_role_planned",
        "approval_actor_hash_planned",
        "permission_evidence_reference_planned",
        "backup_evidence_reference_planned",
        "invitation_expiry_policy_reference_planned",
        "readback_plan_reference_planned",
        "rollback_plan_reference_planned",
        "audit_correlation_id_planned",
        "append_only_audit_rows_planned",
        "real_invitation_remains_closed",
    ]
    result: dict[str, Any] = {
        "phase": "ERP-Multistore-2N",
        "real_user_invitation_approval_audit_linkage_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "audit_linkage_ready": False,
        "required_linkage_flags": required_linkage_flags,
        "missing_linkage_flags": [],
        "target_user_key_hash": None,
        "login_identifier_hash": None,
        "login_identifier_masked": None,
        "target_store_ids": [],
        "target_role": None,
        "approval_actor_hash_planned": False,
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
        "operation_audit_rows_planned": True,
        "operation_audit_rows_written": False,
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    }
    if verification_scope != VERIFICATION_SCOPE:
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(invitation_approval, dict):
        result["skip_reason"] = "invitation_approval_required"
        return result
    if not isinstance(audit_linkage_context, dict):
        result["skip_reason"] = "audit_linkage_context_required"
        return result
    invitation_scan_subset = {
        "status": invitation_approval.get("status"),
        "target_user_key_hash": invitation_approval.get("target_user_key_hash"),
        "login_identifier_hash": invitation_approval.get("login_identifier_hash"),
        "login_identifier_masked": invitation_approval.get("login_identifier_masked"),
        "target_store_ids": invitation_approval.get("target_store_ids"),
        "target_role": invitation_approval.get("target_role"),
    }
    if _contains_sensitive_material({
        "invitation_approval": invitation_scan_subset,
        "audit_linkage_context": audit_linkage_context,
    }):
        result["skip_reason"] = "invitation_approval_audit_linkage_sensitive_material_blocked"
        return result

    if invitation_approval.get("status") not in {
        "user_invitation_approval_checklist_mock_ready",
        "user_invitation_approval_checklist_readonly_api_mock_ready",
        "user_invitation_approval_checklist_readonly_route_mock_ready",
        "user_invitation_approval_checklist_readonly_api_ready",
    }:
        result["skip_reason"] = "invitation_approval_not_ready"
        return result
    if invitation_approval.get("invitation_sent") is True:
        result["skip_reason"] = "real_invitation_not_allowed_in_linkage_mock_gate"
        return result
    if invitation_approval.get("users_written") is True or invitation_approval.get("membership_written") is True:
        result["skip_reason"] = "user_or_membership_write_not_allowed_in_linkage_mock_gate"
        return result
    if invitation_approval.get("role_assignment_written") is True or invitation_approval.get("real_auth_session_created") is True:
        result["skip_reason"] = "auth_or_role_write_not_allowed_in_linkage_mock_gate"
        return result
    if invitation_approval.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "audit_write_not_allowed_in_linkage_mock_gate"
        return result
    if invitation_approval.get("privacy_fields_redacted") is not True:
        result["skip_reason"] = "privacy_redaction_required"
        return result

    missing_flags = [
        flag for flag in required_linkage_flags
        if audit_linkage_context.get(flag) is not True
    ]
    result["missing_linkage_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "invitation_approval_audit_linkage_incomplete"
        return result
    if audit_linkage_context.get("invitation_sent") is True or audit_linkage_context.get("users_written") is True:
        result["skip_reason"] = "real_invitation_not_allowed_in_linkage_mock_gate"
        return result
    if audit_linkage_context.get("membership_written") is True or audit_linkage_context.get("real_auth_session_created") is True:
        result["skip_reason"] = "user_or_membership_write_not_allowed_in_linkage_mock_gate"
        return result
    if audit_linkage_context.get("operation_audit_rows_written") is True:
        result["skip_reason"] = "audit_write_not_allowed_in_linkage_mock_gate"
        return result
    if audit_linkage_context.get("formal_sync_open") is True or audit_linkage_context.get("platform_writes_enabled") is True:
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    approval_store_ids = _normalize_invitation_store_ids(invitation_approval.get("target_store_ids"))
    linkage_store_ids = _normalize_invitation_store_ids(audit_linkage_context.get("target_store_ids"))
    if not approval_store_ids or not linkage_store_ids or not set(approval_store_ids).issubset(set(linkage_store_ids)):
        result["skip_reason"] = "invitation_audit_linkage_store_scope_mismatch"
        return result

    target_user_hash = invitation_approval.get("target_user_key_hash")
    if (
        not isinstance(target_user_hash, str)
        or not SAFE_USER_HASH_PATTERN.fullmatch(target_user_hash)
        or audit_linkage_context.get("target_user_key_hash") != target_user_hash
    ):
        result["skip_reason"] = "invitation_audit_linkage_user_scope_mismatch"
        return result

    target_role = _normalize_role(invitation_approval.get("target_role"))
    if target_role is None or _normalize_role(audit_linkage_context.get("target_role")) != target_role:
        result["skip_reason"] = "invitation_audit_linkage_role_scope_mismatch"
        return result

    result.update({
        "status": "user_invitation_approval_audit_linkage_mock_ready",
        "audit_linkage_ready": True,
        "target_user_key_hash": target_user_hash,
        "login_identifier_hash": invitation_approval.get("login_identifier_hash"),
        "login_identifier_masked": invitation_approval.get("login_identifier_masked"),
        "target_store_ids": approval_store_ids,
        "target_role": target_role,
        "approval_actor_hash_planned": True,
        "business_message": (
            "User invitation approval audit linkage mock gate passed. "
            "It plans evidence references only; no user, membership, session, invitation, or audit row is written."
        ),
        "next_action": (
            "Keep real invitation closed until a separate write phase re-checks approval, backup, audit, readback, and rollback evidence."
        ),
    })
    return result


def evaluate_real_user_invitation_approval_audit_linkage_readonly_api_mock_gate(
    *,
    invitation_approval: dict[str, Any] | None,
    audit_linkage_context: dict[str, Any] | None,
    readonly_api_context: dict[str, Any] | None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Mock gate for a future readonly API that reviews invitation audit linkage."""

    result = evaluate_real_user_invitation_approval_audit_linkage_mock_gate(
        invitation_approval=invitation_approval,
        audit_linkage_context=audit_linkage_context,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "send_invitation_button_excluded",
        "write_endpoint_excluded",
        "masked_identifier_required",
        "audit_row_write_excluded",
        "route_requires_separate_implementation",
        "real_invitation_remains_closed",
    ]
    result.update({
        "phase": "ERP-Multistore-2P",
        "real_user_invitation_approval_audit_linkage_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/permissions/user-invitation/approval-audit-linkage/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
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
        "raw_response_saved": False,
        "secrets_saved": False,
        "privacy_fields_redacted": True,
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    })
    if result.get("status") != "user_invitation_approval_audit_linkage_mock_ready":
        return result
    if verification_scope != VERIFICATION_SCOPE:
        result["status"] = "blocked"
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(readonly_api_context, dict):
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_required"
        return result
    if _contains_sensitive_material(readonly_api_context):
        result["status"] = "blocked"
        result["skip_reason"] = "invitation_approval_audit_linkage_readonly_api_sensitive_material_blocked"
        return result

    missing_api_flags = [
        flag for flag in required_api_flags
        if readonly_api_context.get(flag) is not True
    ]
    result["missing_api_flags"] = missing_api_flags
    if missing_api_flags:
        result["status"] = "blocked"
        result["skip_reason"] = "readonly_api_context_incomplete"
        return result
    if readonly_api_context.get("public_endpoint_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "public_endpoint_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("backend_route_implemented") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "backend_route_not_allowed_in_mock_gate"
        return result
    if readonly_api_context.get("invitation_sent") is True or readonly_api_context.get("users_written") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "real_invitation_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("membership_written") is True or readonly_api_context.get("operation_audit_rows_written") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "write_not_allowed_in_readonly_api_mock_gate"
        return result
    if readonly_api_context.get("formal_sync_open") is True or readonly_api_context.get("platform_writes_enabled") is True:
        result["status"] = "blocked"
        result["skip_reason"] = "formal_sync_already_open_not_allowed"
        return result

    result.update({
        "status": "user_invitation_approval_audit_linkage_readonly_api_mock_ready",
        "audit_linkage_ready": True,
        "business_message": (
            "User invitation approval audit linkage readonly API mock gate passed. "
            "It plans review-only display; no invitation, user, membership, session, or audit row is written."
        ),
        "next_action": (
            "Plan a local readonly route separately. Real invitation and membership writes remain closed."
        ),
    })
    return result
