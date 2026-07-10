from __future__ import annotations

import hashlib
import json
import re
from typing import Any


VERIFICATION_SCOPE = "verify_all_temp_db"

ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "owner": {
        "label": "owner",
        "store_scope": "all",
        "permissions": {"*"},
        "sensitive_approval_actions": {"*"},
    },
    "admin": {
        "label": "admin",
        "store_scope": "assigned",
        "permissions": {
            "dashboard.read",
            "products.read",
            "products.preview",
            "products.batch_sync_write",
            "orders.read",
            "orders.preview",
            "orders.local_write",
            "orders.batch_sync_write",
            "orders.refresh_batch_write",
            "audit.read",
            "backup.read",
            "backup.create",
            "store_membership.assign",
            "recipient_pii.view",
            "recipient_pii.export",
            "recipient_pii.cs_reveal",
            "shipping.batch.manage",
            "shipping.writeback.approve",
            "recipient_pii.audit.read",
        },
        "sensitive_approval_actions": {
            "products.batch_sync_write",
            "orders.batch_sync_write",
            "orders.local_write",
            "orders.refresh_batch_write",
            "backup.create",
            "store_membership.assign",
            "shipping.writeback.approve",
        },
    },
    "operator": {
        "label": "operator",
        "store_scope": "assigned",
        "permissions": {
            "dashboard.read",
            "products.read",
            "products.preview",
            "orders.read",
            "orders.preview",
            "audit.read",
            "backup.read",
        },
        "sensitive_approval_actions": set(),
    },
    "auditor": {
        "label": "auditor",
        "store_scope": "assigned",
        "permissions": {
            "dashboard.read",
            "orders.read",
            "products.read",
            "audit.read",
            "backup.read",
        },
        "sensitive_approval_actions": set(),
    },
    "viewer": {
        "label": "viewer",
        "store_scope": "assigned",
        "permissions": {
            "dashboard.read",
            "orders.read",
            "products.read",
        },
        "sensitive_approval_actions": set(),
    },
    "shipping_operator": {
        "label": "shipping_operator",
        "store_scope": "assigned",
        "permissions": {"orders.read", "recipient_pii.view", "recipient_pii.export", "shipping.batch.manage"},
        "sensitive_approval_actions": set(),
    },
}

SENSITIVE_ACTIONS = {
    "products.batch_sync_write",
    "orders.batch_sync_write",
    "orders.local_write",
    "orders.refresh_batch_write",
    "backup.create",
    "store_membership.assign",
    "database.restore",
    "credentials.update",
    "schema.migrate",
    "formal_sync.open",
    "shipping.writeback.approve",
}

SENSITIVE_KEY_MARKERS = (
    "authorization",
    "bcrypt",
    "client_secret",
    "headers",
    "raw_response",
    "raw response",
    "secret",
    "signature",
    "token",
)

SENSITIVE_VALUE_MARKERS = (
    "authorization:",
    "bearer ",
    "bcrypt",
    "client_secret",
    "raw response",
    "signature",
)

PHONE_PATTERN = re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b")
SAFE_OPERATION_PATTERN = re.compile(r"^[a-z0-9_.:-]{1,120}$")
SAFE_USER_HASH_PATTERN = re.compile(r"^user-hash-[a-f0-9]{8,64}$")
SAFE_LOGIN_HASH_PATTERN = re.compile(r"^login-hash-[a-f0-9]{8,64}$")
SAFE_MASKED_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9*@._+\-\s]{3,160}$")


def _actor_hash(actor_id: object) -> str | None:
    if not actor_id:
        return None
    digest = hashlib.sha256(str(actor_id).encode("utf-8")).hexdigest()[:10]
    return f"actor-hash-{digest}"


def _normalize_role(role: object) -> str | None:
    if not isinstance(role, str):
        return None
    normalized = role.strip().lower()
    return normalized if normalized in ROLE_DEFINITIONS else None


def _safe_operation_key(operation_key: object) -> str | None:
    if not isinstance(operation_key, str):
        return None
    normalized = operation_key.strip().lower()
    return normalized if SAFE_OPERATION_PATTERN.fullmatch(normalized) else None


def _store_ids(actor_context: dict[str, Any]) -> set[int]:
    raw_store_ids = actor_context.get("store_ids")
    if raw_store_ids == "all":
        return {-1}
    if not isinstance(raw_store_ids, (list, tuple, set)):
        return set()
    safe_ids: set[int] = set()
    for value in raw_store_ids:
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            continue
        if int_value > 0:
            safe_ids.add(int_value)
    return safe_ids


def _contains_sensitive_material(payload: object) -> bool:
    def walk(value: object) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(key).lower().replace("-", "_")
                if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                    return True
                if walk(item):
                    return True
        elif isinstance(value, (list, tuple, set)):
            return any(walk(item) for item in value)
        elif isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in SENSITIVE_VALUE_MARKERS):
                return True
            if PHONE_PATTERN.search(value):
                return True
        return False

    return walk(payload)


def _base_result(*, phase: str, actor_context: dict[str, Any] | None, requested_store_id: int | None, operation_key: str | None) -> dict[str, Any]:
    role = _normalize_role((actor_context or {}).get("role")) if isinstance(actor_context, dict) else None
    return {
        "phase": phase,
        "status": "blocked",
        "skip_reason": None,
        "actor_role": role,
        "actor_id_hash": _actor_hash((actor_context or {}).get("actor_id")) if isinstance(actor_context, dict) else None,
        "requested_store_id": requested_store_id,
        "operation_key": operation_key,
        "store_scope_verified": False,
        "permission_verified": False,
        "sensitive_action": bool(operation_key in SENSITIVE_ACTIONS),
        "manual_approval": False,
        "approval_role_verified": False,
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


def evaluate_store_scoped_access_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    requested_store_id: int | None,
    operation_key: str | None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for the future role/store permission layer."""

    safe_operation = _safe_operation_key(operation_key)
    result = _base_result(
        phase="ERP-Auth-1B",
        actor_context=actor_context,
        requested_store_id=requested_store_id,
        operation_key=safe_operation,
    )
    if verification_scope != VERIFICATION_SCOPE:
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(actor_context, dict):
        result["skip_reason"] = "actor_context_missing"
        return result
    if _contains_sensitive_material(actor_context):
        result["skip_reason"] = "actor_context_sensitive_material_blocked"
        return result
    role = _normalize_role(actor_context.get("role"))
    if role is None:
        result["skip_reason"] = "role_not_allowed"
        return result
    if not isinstance(requested_store_id, int) or requested_store_id <= 0:
        result["skip_reason"] = "requested_store_invalid"
        return result
    if safe_operation is None:
        result["skip_reason"] = "operation_key_invalid"
        return result

    role_definition = ROLE_DEFINITIONS[role]
    assigned_store_ids = _store_ids(actor_context)
    if role_definition["store_scope"] == "all" or -1 in assigned_store_ids or requested_store_id in assigned_store_ids:
        result["store_scope_verified"] = True
    else:
        result["skip_reason"] = "store_scope_mismatch"
        return result

    permissions = role_definition["permissions"]
    if "*" in permissions or safe_operation in permissions:
        result["permission_verified"] = True
    else:
        result["skip_reason"] = "permission_denied"
        return result

    result.update({
        "status": "access_allowed",
        "business_message": "Actor may access the requested store operation in the mock permission gate.",
    })
    return result


def evaluate_sensitive_action_approval_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    requested_store_id: int | None,
    action_key: str | None,
    manual_approval: bool,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for sensitive local ERP actions that need approval."""

    safe_action = _safe_operation_key(action_key)
    access_gate = evaluate_store_scoped_access_mock_gate(
        actor_context=actor_context,
        requested_store_id=requested_store_id,
        operation_key=safe_action,
        verification_scope=verification_scope,
    )
    result = {
        **access_gate,
        "phase": "ERP-Auth-1C",
        "sensitive_action_approval_gate": True,
        "manual_approval": bool(manual_approval),
        "approval_role_verified": False,
        "approval_status": "blocked",
    }
    if access_gate["status"] != "access_allowed":
        result["approval_status"] = "blocked"
        return result
    if safe_action not in SENSITIVE_ACTIONS:
        result.update({
            "status": "approval_not_required",
            "approval_status": "not_required",
            "business_message": "This action is not classified as sensitive in the mock permission gate.",
        })
        return result
    if not manual_approval:
        result.update({
            "status": "approval_blocked",
            "approval_status": "blocked",
            "skip_reason": "manual_approval_required",
        })
        return result

    role = result["actor_role"]
    role_definition = ROLE_DEFINITIONS.get(str(role), {})
    approval_actions = role_definition.get("sensitive_approval_actions", set())
    if "*" not in approval_actions and safe_action not in approval_actions:
        result.update({
            "status": "approval_blocked",
            "approval_status": "blocked",
            "skip_reason": "approval_role_required",
        })
        return result

    result.update({
        "status": "approval_allowed_mock",
        "approval_status": "approved_in_mock_gate",
        "approval_role_verified": True,
        "business_message": "Sensitive action approval passed in the private mock gate only.",
        "formal_sync_open": False,
        "platform_writes_enabled": False,
    })
    return result


def role_permission_inventory() -> dict[str, Any]:
    """Safe role inventory for documentation and frontend planning."""

    return {
        role: {
            "store_scope": definition["store_scope"],
            "permissions": sorted(definition["permissions"]),
            "sensitive_approval_actions": sorted(definition["sensitive_approval_actions"]),
        }
        for role, definition in ROLE_DEFINITIONS.items()
    }


def evaluate_store_membership_assignment_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    target_store_id: int | None,
    target_role: str | None,
    existing_memberships: list[dict[str, Any]] | None = None,
    manual_approval: bool = False,
    assignment_reason: str | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for future store membership assignment; never writes rows."""

    normalized_role = _normalize_role(target_role)
    result = {
        "phase": "ERP-Multistore-1C",
        "store_membership_assignment_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "target_user_key_hash": target_user_key_hash if isinstance(target_user_key_hash, str) else None,
        "target_store_id": target_store_id,
        "target_role": normalized_role,
        "manual_approval": bool(manual_approval),
        "assignment_reason_present": bool(assignment_reason),
        "duplicate_active_membership": False,
        "membership_would_create": False,
        "membership_written": False,
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
    if verification_scope != VERIFICATION_SCOPE:
        result["skip_reason"] = "verification_scope_required"
        return result
    if not isinstance(target_user_key_hash, str) or not SAFE_USER_HASH_PATTERN.fullmatch(target_user_key_hash):
        result["skip_reason"] = "target_user_hash_invalid"
        return result
    if not isinstance(target_store_id, int) or target_store_id <= 0:
        result["skip_reason"] = "target_store_invalid"
        return result
    if normalized_role is None:
        result["skip_reason"] = "target_role_not_allowed"
        return result
    if not isinstance(assignment_reason, str) or not assignment_reason.strip():
        result["skip_reason"] = "assignment_reason_required"
        return result
    if _contains_sensitive_material({
        "actor_context": actor_context,
        "target_user_key_hash": target_user_key_hash,
        "assignment_reason": assignment_reason,
        "existing_memberships": existing_memberships or [],
    }):
        result["skip_reason"] = "membership_assignment_sensitive_material_blocked"
        return result

    approval_gate = evaluate_sensitive_action_approval_mock_gate(
        actor_context=actor_context,
        requested_store_id=target_store_id,
        action_key="store_membership.assign",
        manual_approval=manual_approval,
        verification_scope=verification_scope,
    )
    result["approval_gate"] = {
        "status": approval_gate.get("status"),
        "skip_reason": approval_gate.get("skip_reason"),
        "actor_role": approval_gate.get("actor_role"),
        "actor_id_hash": approval_gate.get("actor_id_hash"),
        "store_scope_verified": approval_gate.get("store_scope_verified"),
        "permission_verified": approval_gate.get("permission_verified"),
        "approval_role_verified": approval_gate.get("approval_role_verified"),
    }
    if approval_gate.get("status") != "approval_allowed_mock":
        result["skip_reason"] = approval_gate.get("skip_reason") or "membership_assignment_approval_blocked"
        return result

    if not isinstance(existing_memberships, list):
        existing_memberships = []
    for membership in existing_memberships:
        if not isinstance(membership, dict):
            result["skip_reason"] = "existing_membership_shape_invalid"
            return result
        if _contains_sensitive_material(membership):
            result["skip_reason"] = "existing_membership_sensitive_material_blocked"
            return result
        is_duplicate = (
            membership.get("user_key_hash") == target_user_key_hash
            and int(membership.get("store_id") or 0) == target_store_id
            and str(membership.get("role") or "").strip().lower() == normalized_role
            and str(membership.get("membership_status") or "active").strip().lower() == "active"
        )
        if is_duplicate:
            result.update({
                "duplicate_active_membership": True,
                "skip_reason": "duplicate_active_membership",
            })
            return result

    result.update({
        "status": "membership_assignment_mock_ready",
        "membership_would_create": True,
        "business_message": "Store membership assignment passed the private mock gate only; no user or membership row was written.",
    })
    return result


def evaluate_store_membership_assignment_runtime_mock_gate(
    db: Any,
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    target_store_id: int | None,
    target_role: str | None,
    manual_approval: bool = False,
    assignment_reason: str | None = None,
) -> dict[str, Any]:
    """Read real auth tables for a future assignment, but never write membership rows."""

    from sqlalchemy import select

    from app.models.auth import ErpRole, ErpStoreMembership, ErpUser

    normalized_role = _normalize_role(target_role)
    result = {
        "phase": "ERP-Multistore-1E",
        "store_membership_assignment_runtime_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "target_user_key_hash": target_user_key_hash if isinstance(target_user_key_hash, str) else None,
        "target_store_id": target_store_id,
        "target_role": normalized_role,
        "manual_approval": bool(manual_approval),
        "assignment_reason_present": bool(assignment_reason),
        "target_user_exists": False,
        "target_role_exists": False,
        "existing_active_membership_count": 0,
        "duplicate_active_membership": False,
        "membership_would_create": False,
        "membership_written": False,
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
    if db is None:
        result["skip_reason"] = "db_session_required"
        return result
    if not isinstance(target_user_key_hash, str) or not SAFE_USER_HASH_PATTERN.fullmatch(target_user_key_hash):
        result["skip_reason"] = "target_user_hash_invalid"
        return result
    if not isinstance(target_store_id, int) or target_store_id <= 0:
        result["skip_reason"] = "target_store_invalid"
        return result
    if normalized_role is None:
        result["skip_reason"] = "target_role_not_allowed"
        return result
    if not isinstance(assignment_reason, str) or not assignment_reason.strip():
        result["skip_reason"] = "assignment_reason_required"
        return result
    if _contains_sensitive_material({
        "actor_context": actor_context,
        "target_user_key_hash": target_user_key_hash,
        "assignment_reason": assignment_reason,
    }):
        result["skip_reason"] = "membership_assignment_sensitive_material_blocked"
        return result

    user = db.scalar(select(ErpUser).where(ErpUser.user_key_hash == target_user_key_hash))
    if user is None:
        result["skip_reason"] = "target_user_not_found"
        return result
    if str(user.status).lower() not in {"active", "invited"}:
        result["skip_reason"] = "target_user_status_not_assignable"
        return result
    result["target_user_exists"] = True

    role = db.scalar(select(ErpRole).where(ErpRole.role_key == normalized_role, ErpRole.status == "active"))
    if role is None:
        result["skip_reason"] = "target_role_not_found"
        return result
    result["target_role_exists"] = True

    active_memberships = db.scalars(
        select(ErpStoreMembership).where(
            ErpStoreMembership.store_id == target_store_id,
            ErpStoreMembership.membership_status == "active",
        )
    ).all()
    existing_memberships: list[dict[str, Any]] = []
    for membership in active_memberships:
        existing_user = getattr(membership, "user", None)
        existing_role = getattr(membership, "role", None)
        existing_memberships.append({
            "user_key_hash": getattr(existing_user, "user_key_hash", None),
            "store_id": membership.store_id,
            "role": getattr(existing_role, "role_key", None),
            "membership_status": membership.membership_status,
        })
    result["existing_active_membership_count"] = len(existing_memberships)

    gate = evaluate_store_membership_assignment_mock_gate(
        actor_context=actor_context,
        target_user_key_hash=target_user_key_hash,
        target_store_id=target_store_id,
        target_role=normalized_role,
        existing_memberships=existing_memberships,
        manual_approval=manual_approval,
        assignment_reason=assignment_reason,
        verification_scope=VERIFICATION_SCOPE,
    )
    result["approval_gate"] = gate.get("approval_gate")
    result["duplicate_active_membership"] = bool(gate.get("duplicate_active_membership"))
    if gate.get("status") != "membership_assignment_mock_ready":
        result["skip_reason"] = gate.get("skip_reason") or "membership_assignment_runtime_gate_blocked"
        return result

    result.update({
        "status": "membership_assignment_runtime_mock_ready",
        "membership_would_create": True,
        "business_message": "Store membership assignment passed runtime mock checks. No user or membership row was written.",
    })
    return result


def evaluate_real_user_invitation_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    login_identifier_hash: str | None,
    login_identifier_masked: str | None,
    target_store_ids: list[int] | tuple[int, ...] | set[int] | None,
    target_role: str | None,
    manual_approval: bool = False,
    invitation_reason: str | None = None,
    backup_evidence_planned: bool = False,
    audit_evidence_planned: bool = False,
    membership_assignment_plan_ready: bool = False,
    existing_user_hashes: list[str] | tuple[str, ...] | set[str] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Private mock gate for future user invitation planning; never creates users or sends invites."""

    normalized_role = _normalize_role(target_role)
    safe_masked_identifier = (
        login_identifier_masked
        if (
            isinstance(login_identifier_masked, str)
            and SAFE_MASKED_IDENTIFIER_PATTERN.fullmatch(login_identifier_masked)
            and ("@" not in login_identifier_masked or "*" in login_identifier_masked)
            and not PHONE_PATTERN.search(login_identifier_masked)
        )
        else None
    )
    result = {
        "phase": "ERP-Multistore-1M",
        "real_user_invitation_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "target_user_key_hash": target_user_key_hash if isinstance(target_user_key_hash, str) else None,
        "login_identifier_hash": login_identifier_hash if isinstance(login_identifier_hash, str) else None,
        "login_identifier_masked": safe_masked_identifier,
        "target_store_ids": [],
        "target_role": normalized_role,
        "manual_approval": bool(manual_approval),
        "invitation_reason_present": bool(invitation_reason),
        "backup_evidence_planned": bool(backup_evidence_planned),
        "audit_evidence_planned": bool(audit_evidence_planned),
        "membership_assignment_plan_ready": bool(membership_assignment_plan_ready),
        "invitation_would_create_user": False,
        "invitation_would_send": False,
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
    if not isinstance(target_user_key_hash, str) or not SAFE_USER_HASH_PATTERN.fullmatch(target_user_key_hash):
        result["skip_reason"] = "target_user_hash_invalid"
        return result
    if not isinstance(login_identifier_hash, str) or not SAFE_LOGIN_HASH_PATTERN.fullmatch(login_identifier_hash):
        result["skip_reason"] = "login_identifier_hash_invalid"
        return result
    if not isinstance(login_identifier_masked, str) or not SAFE_MASKED_IDENTIFIER_PATTERN.fullmatch(login_identifier_masked):
        result["skip_reason"] = "login_identifier_masked_invalid"
        return result
    if "@" in login_identifier_masked and "*" not in login_identifier_masked:
        result["skip_reason"] = "login_identifier_must_be_masked"
        return result
    if PHONE_PATTERN.search(login_identifier_masked):
        result["skip_reason"] = "login_identifier_phone_not_allowed"
        return result
    if normalized_role is None:
        result["skip_reason"] = "target_role_not_allowed"
        return result
    if not isinstance(invitation_reason, str) or not invitation_reason.strip():
        result["skip_reason"] = "invitation_reason_required"
        return result
    if _contains_sensitive_material({
        "actor_context": actor_context,
        "target_user_key_hash": target_user_key_hash,
        "login_identifier_hash": login_identifier_hash,
        "login_identifier_masked": login_identifier_masked,
        "invitation_reason": invitation_reason,
        "existing_user_hashes": list(existing_user_hashes or []),
    }):
        result["skip_reason"] = "user_invitation_sensitive_material_blocked"
        return result

    if not isinstance(target_store_ids, (list, tuple, set)) or not target_store_ids:
        result["skip_reason"] = "target_store_ids_required"
        return result
    safe_store_ids: list[int] = []
    for store_id in target_store_ids:
        try:
            safe_store_id = int(store_id)
        except (TypeError, ValueError):
            result["skip_reason"] = "target_store_id_invalid"
            return result
        if safe_store_id <= 0:
            result["skip_reason"] = "target_store_id_invalid"
            return result
        safe_store_ids.append(safe_store_id)
    safe_store_ids = sorted(set(safe_store_ids))
    result["target_store_ids"] = safe_store_ids
    if len(safe_store_ids) > 5:
        result["skip_reason"] = "target_store_limit_exceeded"
        return result

    if not backup_evidence_planned:
        result["skip_reason"] = "backup_evidence_plan_required"
        return result
    if not audit_evidence_planned:
        result["skip_reason"] = "audit_evidence_plan_required"
        return result
    if not membership_assignment_plan_ready:
        result["skip_reason"] = "membership_assignment_plan_required"
        return result

    if existing_user_hashes is None:
        existing_user_hashes = []
    if not isinstance(existing_user_hashes, (list, tuple, set)):
        result["skip_reason"] = "existing_user_hashes_invalid"
        return result
    for existing_hash in existing_user_hashes:
        if not isinstance(existing_hash, str) or not SAFE_USER_HASH_PATTERN.fullmatch(existing_hash):
            result["skip_reason"] = "existing_user_hash_invalid"
            return result
    if target_user_key_hash in set(existing_user_hashes):
        result["skip_reason"] = "target_user_already_exists"
        return result

    approval_results: list[dict[str, Any]] = []
    for store_id in safe_store_ids:
        approval_gate = evaluate_sensitive_action_approval_mock_gate(
            actor_context=actor_context,
            requested_store_id=store_id,
            action_key="store_membership.assign",
            manual_approval=manual_approval,
            verification_scope=verification_scope,
        )
        approval_results.append({
            "store_id": store_id,
            "status": approval_gate.get("status"),
            "skip_reason": approval_gate.get("skip_reason"),
            "actor_role": approval_gate.get("actor_role"),
            "actor_id_hash": approval_gate.get("actor_id_hash"),
            "store_scope_verified": approval_gate.get("store_scope_verified"),
            "permission_verified": approval_gate.get("permission_verified"),
            "approval_role_verified": approval_gate.get("approval_role_verified"),
        })
        if approval_gate.get("status") != "approval_allowed_mock":
            result["approval_results"] = approval_results
            result["skip_reason"] = approval_gate.get("skip_reason") or "user_invitation_approval_blocked"
            return result

    result.update({
        "status": "user_invitation_mock_ready",
        "approval_results": approval_results,
        "invitation_would_create_user": True,
        "invitation_would_send": True,
        "business_message": "User invitation passed the private mock gate only; no user, session, role, or membership row was written.",
        "next_action": "Plan a separate readonly API and later real invitation approval phase.",
    })
    return result


def evaluate_real_user_invitation_approval_checklist_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    login_identifier_hash: str | None,
    login_identifier_masked: str | None,
    target_store_ids: list[int] | tuple[int, ...] | set[int] | None,
    target_role: str | None,
    manual_approval: bool = False,
    invitation_reason: str | None = None,
    approval_checklist: dict[str, Any] | None = None,
    existing_user_hashes: list[str] | tuple[str, ...] | set[str] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Mock gate for a real-user invitation approval checklist; never sends invites."""

    safe_masked_identifier = (
        login_identifier_masked
        if (
            isinstance(login_identifier_masked, str)
            and SAFE_MASKED_IDENTIFIER_PATTERN.fullmatch(login_identifier_masked)
            and ("@" not in login_identifier_masked or "*" in login_identifier_masked)
            and not PHONE_PATTERN.search(login_identifier_masked)
        )
        else None
    )
    required_checklist_flags = [
        "backup_evidence_ready",
        "audit_evidence_plan_ready",
        "membership_assignment_plan_ready",
        "invite_expiry_configured",
        "one_time_invite_configured",
        "post_create_readback_required",
        "disable_user_rollback_ready",
        "privacy_display_verified",
        "formal_login_boundary_acknowledged",
    ]
    result: dict[str, Any] = {
        "phase": "ERP-Multistore-2C",
        "real_user_invitation_approval_checklist_mock_gate": True,
        "status": "blocked",
        "skip_reason": None,
        "required_checklist_flags": required_checklist_flags,
        "missing_checklist_flags": [],
        "checklist_ready": False,
        "approval_role_verified": False,
        "target_user_key_hash": target_user_key_hash if isinstance(target_user_key_hash, str) else None,
        "login_identifier_hash": login_identifier_hash if isinstance(login_identifier_hash, str) else None,
        "login_identifier_masked": safe_masked_identifier,
        "target_store_ids": [],
        "target_role": _normalize_role(target_role),
        "manual_approval": bool(manual_approval),
        "real_invitation_open": False,
        "invitation_would_create_user": False,
        "invitation_would_send": False,
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
    if not isinstance(approval_checklist, dict):
        result["skip_reason"] = "approval_checklist_required"
        return result
    if _contains_sensitive_material({
        "actor_context": actor_context,
        "target_user_key_hash": target_user_key_hash,
        "login_identifier_hash": login_identifier_hash,
        "login_identifier_masked": login_identifier_masked,
        "invitation_reason": invitation_reason,
        "approval_checklist": approval_checklist,
        "existing_user_hashes": list(existing_user_hashes or []),
    }):
        result["skip_reason"] = "user_invitation_checklist_sensitive_material_blocked"
        return result

    missing_flags = [
        flag for flag in required_checklist_flags
        if approval_checklist.get(flag) is not True
    ]
    result["missing_checklist_flags"] = missing_flags
    if missing_flags:
        result["skip_reason"] = "approval_checklist_incomplete"
        return result
    if approval_checklist.get("invitation_sent") is True:
        result["skip_reason"] = "real_invitation_not_allowed_in_mock_gate"
        return result
    if approval_checklist.get("users_written") is True or approval_checklist.get("membership_written") is True:
        result["skip_reason"] = "user_or_membership_write_not_allowed_in_mock_gate"
        return result
    if approval_checklist.get("real_auth_session_created") is True:
        result["skip_reason"] = "auth_session_not_allowed_in_mock_gate"
        return result

    base_gate = evaluate_real_user_invitation_mock_gate(
        actor_context=actor_context,
        target_user_key_hash=target_user_key_hash,
        login_identifier_hash=login_identifier_hash,
        login_identifier_masked=login_identifier_masked,
        target_store_ids=target_store_ids,
        target_role=target_role,
        manual_approval=manual_approval,
        invitation_reason=invitation_reason,
        backup_evidence_planned=True,
        audit_evidence_planned=True,
        membership_assignment_plan_ready=True,
        existing_user_hashes=existing_user_hashes,
        verification_scope=verification_scope,
    )
    result.update({
        "target_user_key_hash": base_gate.get("target_user_key_hash"),
        "login_identifier_hash": base_gate.get("login_identifier_hash"),
        "login_identifier_masked": base_gate.get("login_identifier_masked"),
        "target_store_ids": base_gate.get("target_store_ids") or [],
        "target_role": base_gate.get("target_role"),
        "approval_results": base_gate.get("approval_results") or [],
        "backup_evidence_ready": True,
        "audit_evidence_plan_ready": True,
        "membership_assignment_plan_ready": True,
        "invite_expiry_configured": True,
        "one_time_invite_configured": True,
        "post_create_readback_required": True,
        "disable_user_rollback_ready": True,
        "privacy_display_verified": True,
        "formal_login_boundary_acknowledged": True,
    })
    if base_gate.get("status") != "user_invitation_mock_ready":
        result["skip_reason"] = base_gate.get("skip_reason") or "user_invitation_base_gate_blocked"
        return result

    result.update({
        "status": "user_invitation_approval_checklist_mock_ready",
        "checklist_ready": True,
        "approval_role_verified": all(
            item.get("approval_role_verified") is True
            for item in result.get("approval_results", [])
        ),
        "future_invitation_allowed_after_separate_approval": True,
        "business_message": (
            "真实用户邀请审批清单 mock 门禁已通过；当前只表示材料可进入人工审批，不会创建用户、发送邀请或分配店铺权限。"
        ),
        "next_action": (
            "继续规划只读页面展示和后续真实邀请审批；真实邀请必须另开阶段并再次备份、审计和回读。"
        ),
    })
    return result


def evaluate_real_user_invitation_approval_checklist_readonly_api_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    login_identifier_hash: str | None,
    login_identifier_masked: str | None,
    target_store_ids: list[int] | tuple[int, ...] | set[int] | None,
    target_role: str | None,
    manual_approval: bool = False,
    invitation_reason: str | None = None,
    approval_checklist: dict[str, Any] | None = None,
    readonly_api_context: dict[str, Any] | None = None,
    existing_user_hashes: list[str] | tuple[str, ...] | set[str] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Mock gate for a future invitation checklist readonly API; no route is exposed."""

    result = evaluate_real_user_invitation_approval_checklist_mock_gate(
        actor_context=actor_context,
        target_user_key_hash=target_user_key_hash,
        login_identifier_hash=login_identifier_hash,
        login_identifier_masked=login_identifier_masked,
        target_store_ids=target_store_ids,
        target_role=target_role,
        manual_approval=manual_approval,
        invitation_reason=invitation_reason,
        approval_checklist=approval_checklist,
        existing_user_hashes=existing_user_hashes,
        verification_scope=verification_scope,
    )
    required_api_flags = [
        "readonly_api_contract_planned",
        "business_wording_required",
        "technical_details_folded",
        "send_invitation_button_excluded",
        "write_endpoint_excluded",
        "masked_identifier_required",
        "route_requires_separate_implementation",
        "real_invitation_remains_closed",
    ]
    result.update({
        "phase": "ERP-Multistore-2G",
        "user_invitation_approval_checklist_readonly_api_mock_gate": True,
        "readonly_api_mock_gate": True,
        "required_api_flags": required_api_flags,
        "missing_api_flags": [],
        "route_path_planned": "/api/v1/permissions/user-invitation/approval-checklist/readonly-check",
        "http_method_planned": "POST",
        "public_endpoint_enabled": False,
        "backend_route_implemented": False,
        "real_invitation_open": False,
        "invitation_would_send": False,
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
    if result.get("status") != "user_invitation_approval_checklist_mock_ready":
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
        result["skip_reason"] = "invitation_checklist_readonly_api_sensitive_material_blocked"
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
        result["skip_reason"] = "real_invitation_not_allowed_in_mock_gate"
        return result

    result.update({
        "status": "user_invitation_approval_checklist_readonly_api_mock_ready",
        "checklist_ready": True,
        "business_message": (
            "真实用户邀请审批清单只读 API mock gate 已通过；当前只规划只读审查接口，不会发送邀请或创建用户。"
        ),
        "next_action": (
            "后续可单独规划本地只读 API 实现；真实邀请仍必须另开审批和写入阶段。"
        ),
    })
    return result


def evaluate_real_user_invitation_approval_checklist_readonly_api_local_route_mock_gate(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    login_identifier_hash: str | None,
    login_identifier_masked: str | None,
    target_store_ids: list[int] | tuple[int, ...] | set[int] | None,
    target_role: str | None,
    manual_approval: bool = False,
    invitation_reason: str | None = None,
    approval_checklist: dict[str, Any] | None = None,
    readonly_api_context: dict[str, Any] | None = None,
    existing_user_hashes: list[str] | tuple[str, ...] | set[str] | None = None,
    verification_scope: str | None = None,
) -> dict[str, Any]:
    """Mock gate for exposing the invitation approval checklist as a local readonly route."""

    result = evaluate_real_user_invitation_approval_checklist_readonly_api_mock_gate(
        actor_context=actor_context,
        target_user_key_hash=target_user_key_hash,
        login_identifier_hash=login_identifier_hash,
        login_identifier_masked=login_identifier_masked,
        target_store_ids=target_store_ids,
        target_role=target_role,
        manual_approval=manual_approval,
        invitation_reason=invitation_reason,
        approval_checklist=approval_checklist,
        readonly_api_context=readonly_api_context,
        existing_user_hashes=existing_user_hashes,
        verification_scope=verification_scope,
    )
    result.update({
        "phase": "ERP-Multistore-2I",
        "user_invitation_approval_checklist_readonly_api_local_route_mock_gate": True,
        "route_path_planned": "/api/v1/permissions/user-invitation/approval-checklist/readonly-check",
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
    if result.get("status") == "user_invitation_approval_checklist_readonly_api_mock_ready":
        result["status"] = "user_invitation_approval_checklist_readonly_route_mock_ready"
        result["business_message"] = (
            "用户邀请审批清单只读路由 mock gate 已通过。当前只允许展示审批材料，不会创建用户、发送邀请或分配店铺权限。"
        )
        result["next_action"] = (
            "后续可进入本地只读 API 实现；真实邀请仍必须单独审批并经过审计、备份和回读校验。"
        )
    return result


def evaluate_real_user_invitation_approval_checklist_readonly_api_local(
    *,
    actor_context: dict[str, Any] | None,
    target_user_key_hash: str | None,
    login_identifier_hash: str | None,
    login_identifier_masked: str | None,
    target_store_ids: list[int] | tuple[int, ...] | set[int] | None,
    target_role: str | None,
    manual_approval: bool = False,
    invitation_reason: str | None = None,
    approval_checklist: dict[str, Any] | None = None,
    readonly_api_context: dict[str, Any] | None = None,
    existing_user_hashes: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Local readonly invitation approval checklist route helper; never sends invitations."""

    result = evaluate_real_user_invitation_approval_checklist_readonly_api_local_route_mock_gate(
        actor_context=actor_context,
        target_user_key_hash=target_user_key_hash,
        login_identifier_hash=login_identifier_hash,
        login_identifier_masked=login_identifier_masked,
        target_store_ids=target_store_ids,
        target_role=target_role,
        manual_approval=manual_approval,
        invitation_reason=invitation_reason,
        approval_checklist=approval_checklist,
        readonly_api_context=readonly_api_context,
        existing_user_hashes=existing_user_hashes,
        verification_scope=VERIFICATION_SCOPE,
    )
    result.update({
        "phase": "ERP-Multistore-2J",
        "user_invitation_approval_checklist_readonly_api_local": True,
        "route_path": "/api/v1/permissions/user-invitation/approval-checklist/readonly-check",
        "http_method": "POST",
        "public_endpoint_enabled": True,
        "backend_route_implemented": True,
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
    if result.get("status") == "user_invitation_approval_checklist_readonly_route_mock_ready":
        result["status"] = "user_invitation_approval_checklist_readonly_api_ready"
        result["business_message"] = (
            "用户邀请审批清单只读检查已可用于本地后台查看。当前不会创建用户、发送邀请或分配店铺权限。"
        )
        result["next_action"] = (
            "如需真实邀请，必须另开审批阶段，并保留权限、审计、备份、回读和撤销证据。"
        )
    return result
