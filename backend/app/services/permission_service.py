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
            "orders.read",
            "orders.preview",
            "orders.local_write",
            "orders.refresh_batch_write",
            "audit.read",
            "backup.read",
            "backup.create",
        },
        "sensitive_approval_actions": {
            "orders.local_write",
            "orders.refresh_batch_write",
            "backup.create",
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
}

SENSITIVE_ACTIONS = {
    "orders.local_write",
    "orders.refresh_batch_write",
    "backup.create",
    "database.restore",
    "credentials.update",
    "schema.migrate",
    "formal_sync.open",
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
