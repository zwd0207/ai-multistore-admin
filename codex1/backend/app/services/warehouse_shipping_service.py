from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from datetime import timedelta
from datetime import timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.order import Order
from app.models.order_status_event import OrderStatusEvent
from app.models.shipping import (
    LogisticsInventoryMapping,
    ShippingTrackingImportBatch,
    ShippingTrackingImportRow,
    WarehouseShippingBatch,
    WarehouseShippingBatchOrder,
    WarehouseShippingApprovalGrant,
)
from app.services import order_service, shipping_service
from app.services.store_service import ensure_store_exists
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local


ACTIVE_BATCH_STATUSES = {"created", "warehouse_sent", "warehouse_returned", "ready_to_writeback", "writeback_partial"}
TERMINAL_ORDER_STATUSES = shipping_service.SHIPPING_ORDER_STATUS_TERMINAL_STATUSES
UPDATABLE_ORDER_STATUSES = shipping_service.SHIPPING_ORDER_STATUS_UPDATABLE_STATUSES
PRIVACY_ROLES = {"admin", "operator", "shipping_operator"}
WAREHOUSE_STOP_CONFIRMATION_STATUSES = {"warehouse_sent", "warehouse_returned", "ready_to_writeback", "writeback_partial"}
WAREHOUSE_BATCH_REMOVE_REASON_CODES = {
    "address_issue",
    "customer_request",
    "order_cancelled",
    "sku_mapping_error",
    "stock_unavailable",
    "warehouse_exception",
}
T18_PILOT_SCOPE_PREFIX = shipping_service.T18_PILOT_SCOPE_PREFIX
T18_ALLOWED_PLATFORM_STATUSES = {"PAYED", "PLACE_PRODUCT_ORDER", "READY", "DELIVERY_READY"}
T18_RECONCILED_PLATFORM_STATUSES = {
    "DISPATCHED", "DELIVERING", "SHIPPING", "IN_DELIVERY", "DELIVERED",
    "DELIVERY_COMPLETION", "DELIVERY_COMPLETED", "DELIVERY_COMPLETE",
}
T18_NO_CLAIM_STATUSES = {"", "NONE", "NO_CLAIM", "NO_CLAIMS", "NOT_APPLIED", "NO"}
T18_PREPARED_ATTEMPT_STATUSES = {"prepared", "not_started"}
T18_RECONCILABLE_ATTEMPT_STATUSES = {"requesting", "pending", "unknown"}
T18_ATTEMPT_TERMINAL_STATUSES = {
    "success", "failed", "unknown", "reconciled", "reconciled_success", "reconciled_not_applied",
}

T18_ATTEMPT_OPERATOR_STATUS = {
    "prepared": "已审批，等待最终核对",
    "not_started": "已审批，等待最终核对",
    "requesting": "平台请求已发出，等待结果核对",
    "pending": "平台请求已发出，等待结果核对",
    "success": "平台回填已确认",
    "failed": "平台明确拒绝，需人工处理",
    "unknown": "平台结果不明确，必须先核对",
    "reconciled": "平台结果已核对",
    "reconciled_success": "平台已确认回填成功",
    "reconciled_not_applied": "平台确认未生效，需负责人重新批准",
}


def _role_allowed(actor_context: dict[str, Any] | None) -> bool:
    return str((actor_context or {}).get("role") or "").strip().lower() in PRIVACY_ROLES


def _safe_batch_row(row: WarehouseShippingBatchOrder) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.local_order_id,
        "order_reference": row.order_reference,
        "product_order_reference": row.product_order_reference,
        "product_name": row.product_name,
        "quantity": row.quantity,
        "internal_sku": row.internal_sku,
        "logistics_inventory_code": row.logistics_inventory_code,
        "row_status": row.row_status,
        "carrier": row.carrier,
        "tracking_number_hash": row.tracking_number_hash,
        "shipped_at": row.shipped_at,
        "failure_reason": row.failure_reason,
        "operator_note": row.operator_note,
        "is_active": row.is_active,
    }


def _match_tracking_import_row(
    import_rows: list[ShippingTrackingImportRow],
    batch_row: WarehouseShippingBatchOrder,
) -> tuple[ShippingTrackingImportRow | None, str | None]:
    product_reference = str(batch_row.product_order_reference or "").strip()
    if product_reference:
        matches = [item for item in import_rows if item.product_order_reference == product_reference]
        if len(matches) != 1:
            return None, "shipping_tracking_product_order_match_not_unique"
        return matches[0], None
    matches = [item for item in import_rows if item.order_reference == batch_row.order_reference]
    if len(matches) != 1:
        return None, "shipping_tracking_order_match_not_unique"
    return matches[0], None


def _writeback_execution_candidates(
    db: Session,
    batch: WarehouseShippingBatch,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not batch.tracking_import_batch_id:
        return None, "tracking_import_required"
    import_rows = db.scalars(select(ShippingTrackingImportRow).where(
        ShippingTrackingImportRow.import_batch_id == batch.tracking_import_batch_id,
    )).all()
    candidates: list[dict[str, Any]] = []
    selected_tracking_ids: set[int] = set()
    ready_batch_rows = [row for row in batch.rows if row.is_active and row.row_status == "ready_for_writeback"]
    for batch_row in sorted(ready_batch_rows, key=lambda item: item.id):
        tracking_row, error = _match_tracking_import_row(import_rows, batch_row)
        if error or tracking_row is None or tracking_row.id in selected_tracking_ids:
            return None, error or "shipping_tracking_record_reused"
        candidates.append({
            "batch_row_id": batch_row.id,
            "tracking_record_id": tracking_row.id,
            "product_order_reference": tracking_row.product_order_reference,
            "order_reference": tracking_row.order_reference,
            "carrier": tracking_row.carrier,
            "tracking_number": tracking_row.tracking_number,
            "tracking_number_hash": shipping_service._safe_hash_identifier(tracking_row.tracking_number),
            "shipped_at": tracking_row.shipped_at,
        })
        selected_tracking_ids.add(tracking_row.id)
    if not candidates:
        return None, "no_confirmed_tracking_rows"
    return candidates, None


def _candidate_hash(db: Session, batch: WarehouseShippingBatch, grant_scope: str) -> str:
    if grant_scope == "writeback":
        execution_candidates, error = _writeback_execution_candidates(db, batch)
        candidates = [
            {
                "tracking_record_id": item["tracking_record_id"],
                "product_order_reference": item["product_order_reference"],
                "order_reference": item["order_reference"],
                "carrier": item["carrier"],
                "tracking_number_hash": item["tracking_number_hash"],
                "shipped_at": item["shipped_at"],
            }
            for item in (execution_candidates or [])
        ]
    else:
        error = None
        candidates = []
        for row in sorted(batch.rows, key=lambda item: item.id):
            if not row.is_active or row.row_status != "pending_export":
                continue
            candidates.append({
                "id": row.id,
                "order_id": row.local_order_id,
                "order_reference": row.order_reference,
                "product_order_reference": row.product_order_reference,
                "product_name": row.product_name,
                "quantity": row.quantity,
                "internal_sku": row.internal_sku,
                "logistics_inventory_code": row.logistics_inventory_code,
                "recipient": order_service.recipient_contract(
                    row.order,
                    db=db,
                    warehouse_authorized=True,
                ),
            })
    payload = {
        "batch_id": batch.id,
        "batch_version": batch.version,
        "grant_scope": grant_scope,
        "candidate_error": error,
        "candidates": candidates,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _as_utc(value: Any) -> Any:
    if value is None or not hasattr(value, "tzinfo"):
        return value
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _as_iso(value: Any) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None and hasattr(normalized, "isoformat") else None


def _t18_attempt_scope(store_id: int) -> str:
    return shipping_service._t18_attempt_scope(store_id)


def _t18_gate_skip_reason(settings: Any) -> str | None:
    if not settings.real_api_write_enabled:
        return "real_api_write_disabled"
    if not settings.shipping_platform_write_enabled:
        return "shipping_platform_write_disabled"
    if not settings.pxg_naver_shipping_pilot_enabled:
        return "pxg_naver_shipping_pilot_disabled"
    if bool(getattr(settings, "platform_order_write_enabled", False)):
        return "platform_order_write_must_remain_disabled"
    return None


def _t18_capability(
    *,
    settings: Any,
    status: str,
    candidate_count: int,
    operator_message: str,
    platform_checked_at: Any = None,
    approval_expires_at: Any = None,
    reconciliation_required: bool = False,
    allowed_action: str | None = None,
    attempt_status: str | None = None,
    store_name: str | None = None,
    product_order_reference: str | None = None,
    carrier: str | None = None,
    tracking_number_masked: str | None = None,
    platform_latest_status: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "pilot_enabled": bool(settings.pxg_naver_shipping_pilot_enabled),
        # This is deliberately a hard cap, not a tunable production multiplier.
        "max_rows": 1,
        "candidate_count": int(candidate_count),
        "operator_message": operator_message,
        "platform_checked_at": _as_iso(platform_checked_at),
        "approval_expires_at": _as_iso(approval_expires_at),
        "reconciliation_required": bool(reconciliation_required),
        "allowed_action": allowed_action,
        "attempt_status": attempt_status,
        "attempt_operator_status": T18_ATTEMPT_OPERATOR_STATUS.get(attempt_status or "", None),
        "store_name": store_name,
        "product_order_reference": product_order_reference,
        "carrier": carrier,
        "tracking_number_masked": tracking_number_masked,
        "platform_latest_status": platform_latest_status,
    }


def _t18_capability_details(
    *,
    batch: WarehouseShippingBatch,
    candidates: list[dict[str, Any]] | None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """Expose only the operator-safe fields frozen for the T18 capability contract."""

    candidate = candidates[0] if candidates is not None and len(candidates) == 1 else None
    product_order_reference = str((candidate or {}).get("product_order_reference") or "").strip() or None
    platform_latest_status = None
    if product_order_reference and preflight is not None:
        for state in preflight.get("states") or []:
            if str(state.get("product_order_id") or "").strip() == product_order_reference:
                platform_latest_status = _t18_status(state.get("order_status")) or None
                break
    return {
        "store_name": str(getattr(batch.store, "name", "") or "").strip() or None,
        "product_order_reference": product_order_reference,
        "carrier": str((candidate or {}).get("carrier") or "").strip() or None,
        "tracking_number_masked": order_service._mask_tracking_number((candidate or {}).get("tracking_number")),
        "platform_latest_status": platform_latest_status,
    }


def _t18_trial_store_matches(db: Session, batch: WarehouseShippingBatch) -> tuple[bool, str | None]:
    """Keep the pilot constrained to the uniquely configured PXG/Naver store."""

    from app.services.operator_trial_service import resolve_trial_store

    try:
        store = resolve_trial_store(db)
    except ApiError as exc:
        return False, str(exc.error_code or "pxg_naver_pilot_store_unavailable")
    if batch.platform != "naver" or batch.store_id != store.id:
        return False, "pxg_naver_pilot_store_required"
    return True, None


def _t18_candidates(
    db: Session,
    batch: WarehouseShippingBatch,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    candidates, candidate_error = _writeback_execution_candidates(db, batch)
    if candidate_error or candidates is None:
        return None, candidate_error or "no_confirmed_tracking_rows"
    if len(candidates) != 1:
        return candidates, "pxg_naver_pilot_single_row_required"
    candidate = candidates[0]
    if not str(candidate.get("product_order_reference") or "").strip():
        return None, "product_order_reference_required"
    if not shipping_service._normalize_naver_delivery_company_code(candidate.get("carrier")):
        return None, "unsupported_delivery_company"
    if not str(candidate.get("tracking_number") or "").strip():
        return None, "tracking_number_missing"
    return candidates, None


def _t18_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("raw") or value.get("status")
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _t18_platform_carrier_code(detail: dict[str, Any]) -> str | None:
    return shipping_service._normalize_naver_delivery_company_code(
        detail.get("delivery_company_code")
        or detail.get("delivery_company")
        or detail.get("carrier")
        or detail.get("deliveryCompanyCode")
        or detail.get("deliveryCompany")
    )


def _t18_platform_tracking_hash(detail: dict[str, Any]) -> str | None:
    tracking_number = (
        detail.get("tracking_number")
        or detail.get("trackingNumber")
        or detail.get("invoice_number")
        or detail.get("invoiceNo")
    )
    if not str(tracking_number or "").strip():
        return None
    return shipping_service._safe_hash_identifier(tracking_number)


def _t18_platform_writeback_state(detail: dict[str, Any]) -> str:
    return _t18_status(
        detail.get("writeback_status")
        or detail.get("dispatch_status")
        or detail.get("dispatchStatus")
        or detail.get("shipment_writeback_status")
    )


def _t18_platform_preflight(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Read only the current order states; never retain the response payload."""

    from app.models.api_credential import ApiCredential
    from app.services import automatic_read_sync_service, store_onboarding_service

    product_order_ids = [str(item["product_order_reference"]).strip() for item in candidates]
    try:
        context = automatic_read_sync_service._context(db, batch.store_id)
        details = store_onboarding_service.DefaultNaverReadAdapter().read_logistics(
            context,
            product_order_ids=product_order_ids,
        )
    except Exception as exc:
        error_code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
        return None, str(error_code or "naver_platform_preflight_failed")[:80]
    if not isinstance(details, list):
        return None, "naver_platform_preflight_invalid_response"

    by_product_order_id: dict[str, list[dict[str, Any]]] = {}
    for detail in details:
        if not isinstance(detail, dict):
            return None, "naver_platform_preflight_invalid_response"
        product_order_id = str(detail.get("external_product_order_id") or "").strip()
        if product_order_id:
            by_product_order_id.setdefault(product_order_id, []).append(detail)

    states: list[dict[str, str | None]] = []
    for product_order_id in product_order_ids:
        matches = by_product_order_id.get(product_order_id, [])
        if len(matches) != 1:
            return None, "naver_platform_preflight_product_order_not_unique"
        detail = matches[0]
        states.append({
            "product_order_id": product_order_id,
            "order_status": _t18_status(detail.get("order_status")),
            "claim_status": _t18_status(detail.get("claim_status")),
            "carrier_code": _t18_platform_carrier_code(detail),
            "tracking_number_hash": _t18_platform_tracking_hash(detail),
            "writeback_state": _t18_platform_writeback_state(detail),
        })
    checked_at = get_utc_now()
    credential = db.get(ApiCredential, context.credential_id)
    credential_marker = {
        "credential_id": context.credential_id,
        "client_id": context.client_id,
        "updated_at": _as_iso(credential.updated_at) if credential is not None else None,
    }
    return {
        "credential_id": context.credential_id,
        "credential_binding": hashlib.sha256(
            json.dumps(credential_marker, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "platform_checked_at": checked_at,
        "states": states,
    }, None


def _t18_preflight_eligible(preflight: dict[str, Any]) -> str | None:
    for state in preflight.get("states") or []:
        if state.get("order_status") not in T18_ALLOWED_PLATFORM_STATUSES:
            return "naver_platform_status_not_writeback_eligible"
        if state.get("claim_status") not in T18_NO_CLAIM_STATUSES:
            return "naver_platform_claim_present"
        if state.get("tracking_number_hash"):
            return "naver_platform_tracking_already_present"
        if _t18_status(state.get("writeback_state")) not in {"", "NOT_APPLIED"}:
            return "naver_platform_writeback_state_not_writeback_eligible"
    return None


def _t18_candidate_hash(
    *,
    batch: WarehouseShippingBatch,
    candidates: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> str:
    states = {
        str(item.get("product_order_id") or ""): {
            "order_status": item.get("order_status"),
            "claim_status": item.get("claim_status"),
            "carrier_code": item.get("carrier_code"),
            "tracking_number_hash": item.get("tracking_number_hash"),
            "writeback_state": item.get("writeback_state"),
        }
        for item in preflight.get("states") or []
    }
    payload = {
        "scope": T18_PILOT_SCOPE_PREFIX,
        "store_id": batch.store_id,
        "batch_id": batch.id,
        "batch_version": batch.version,
        "credential_binding": preflight.get("credential_binding"),
        "candidates": [
            {
                "product_order_id": str(item.get("product_order_reference") or ""),
                "carrier": str(item.get("carrier") or ""),
                "tracking_number_hash": item.get("tracking_number_hash"),
                "shipped_at": str(item.get("shipped_at") or "").strip(),
                "platform_state": states.get(str(item.get("product_order_reference") or "")),
            }
            for item in candidates
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _t18_attempt_limit_reached(db: Session, *, store_id: int) -> bool:
    count = db.scalar(
        select(func.count(WarehouseShippingApprovalGrant.id))
        .join(WarehouseShippingBatch, WarehouseShippingApprovalGrant.batch_id == WarehouseShippingBatch.id)
        .where(
            WarehouseShippingBatch.store_id == store_id,
            WarehouseShippingApprovalGrant.attempt_scope == _t18_attempt_scope(store_id),
            WarehouseShippingApprovalGrant.attempt_status.not_in(T18_PREPARED_ATTEMPT_STATUSES),
        )
    ) or 0
    return int(count) >= 1


def _write_workflow_audit(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    actor_context: dict[str, Any] | None,
    action: str,
    row_count: int,
    reason_code: str,
    real_api_called: bool = False,
    platform_request_count: int = 0,
) -> None:
    now = get_utc_now()
    correlation = f"warehouse-{action}-{batch.id}-{now:%Y%m%d%H%M%S%f}"
    write_operation_audit_log_local(db, {
        "created_at": now, "updated_at": now, "store_id": batch.store_id, "platform": batch.platform,
        "environment": "local", "actor_type": "human", "actor_id": shipping_service._actor_hash(actor_context) or "actor-hash-warehouse",
        "actor_label": "Operator", "actor_role": "operator", "action": action, "operation_phase": "Warehouse-R2",
        "correlation_id": correlation, "request_id": correlation, "status": "success", "reason_code": reason_code,
        "target_type": "shipping_batch", "target_id": str(batch.id), "target_hash": f"id-hash-{hashlib.sha256(batch.batch_no.encode()).hexdigest()[:16]}",
        "target_label": "Warehouse shipping batch", "changed_field_names": ["warehouse_shipping_batches"],
        "before_summary": {}, "after_summary": {"batch_id": batch.id, "row_count": row_count},
        "counts_summary": {
            "shipping_batch_rows": row_count,
            "platform_request_count": int(platform_request_count),
        },
        "safety_flags": {
            "privacy_fields_redacted": True,
            "real_api_called": bool(real_api_called),
            "platform_write": bool(real_api_called),
        }, "sensitive_scan_passed": True,
        "raw_response_saved": False, "secrets_saved": False, "privacy_fields_redacted": True,
        "notes": "No recipient fields, full tracking number, or platform response content recorded.",
    }, write_enabled=True, manual_approval=True, local_write_scope=LOCAL_WRITER_SCOPE)


def write_recipient_view_audit(db: Session, *, store_id: int, platform: str, user_key_hash: str, row_count: int) -> None:
    batch = WarehouseShippingBatch(batch_no="operations-view", store_id=store_id, platform=platform)
    _write_workflow_audit(db, batch=batch, actor_context={"actor_id": user_key_hash}, action="recipient_pii_viewed", row_count=row_count, reason_code="authorized_operations_view")


def _issue_t18_writeback_approval(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    user_id: int,
) -> dict[str, Any]:
    settings = get_settings()
    candidates, candidate_error = _t18_candidates(db, batch)
    candidate_count = len(candidates or [])
    capability_details = _t18_capability_details(batch=batch, candidates=candidates)
    gate_error = _t18_gate_skip_reason(settings)
    if gate_error:
        return {
            "status": "blocked",
            "skip_reason": gate_error,
            "token_request_count": 0,
            "http_request_count": 0,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="PXG/Naver pilot writeback is disabled by a required safety gate.",
                **capability_details,
            ),
        }
    store_matches, store_error = _t18_trial_store_matches(db, batch)
    if not store_matches:
        return {
            "status": "blocked",
            "skip_reason": store_error,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="This batch is outside the configured PXG/Naver pilot store.",
                **capability_details,
            ),
        }
    if candidate_error or candidates is None:
        return {
            "status": "blocked",
            "skip_reason": candidate_error or "no_confirmed_tracking_rows",
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="The pilot requires exactly one valid warehouse tracking row.",
                **capability_details,
            ),
        }
    if _t18_attempt_limit_reached(db, store_id=batch.store_id):
        return {
            "status": "blocked",
            "skip_reason": "pxg_naver_pilot_attempt_limit_reached",
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="The single allowed pilot attempt has already been claimed.",
                **capability_details,
            ),
        }
    preflight, preflight_error = _t18_platform_preflight(db, batch=batch, candidates=candidates)
    if preflight_error or preflight is None:
        return {
            "status": "blocked",
            "skip_reason": preflight_error or "naver_platform_preflight_failed",
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="The latest Naver order state could not be verified.",
                **capability_details,
            ),
        }
    capability_details = _t18_capability_details(batch=batch, candidates=candidates, preflight=preflight)
    eligibility_error = _t18_preflight_eligible(preflight)
    if eligibility_error:
        return {
            "status": "blocked",
            "skip_reason": eligibility_error,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="The latest Naver state is not eligible for shipment writeback.",
                platform_checked_at=preflight["platform_checked_at"],
                **capability_details,
            ),
        }

    now = get_utc_now()
    expires_at = now + timedelta(minutes=10)
    token = secrets.token_urlsafe(32)
    db.add(WarehouseShippingApprovalGrant(
        batch_id=batch.id,
        user_id=user_id,
        grant_scope="writeback",
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        batch_version=batch.version,
        candidate_hash=_t18_candidate_hash(batch=batch, candidates=candidates, preflight=preflight),
        expires_at=expires_at,
        attempt_scope=_t18_attempt_scope(batch.store_id),
        attempt_status="prepared",
    ))
    db.commit()
    return {
        "status": "approval_granted",
        "approval_token": token,
        "expires_at": expires_at,
        "batch_version": batch.version,
        "writeback_capability": _t18_capability(
            settings=settings,
            status="ready",
            candidate_count=candidate_count,
            operator_message="One pilot writeback row is ready for final operator confirmation.",
            platform_checked_at=preflight["platform_checked_at"],
            approval_expires_at=expires_at,
            allowed_action="execute",
            **capability_details,
        ),
    }


def issue_approval_grant(
    db: Session,
    *,
    batch_id: int,
    user_id: int,
    grant_scope: str,
    t18_pilot_execution: bool = False,
) -> dict[str, Any]:
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found"}
    if grant_scope not in {"manifest", "writeback"}:
        return {"status": "blocked", "skip_reason": "shipping_approval_scope_invalid"}
    if grant_scope == "writeback" and t18_pilot_execution:
        return _issue_t18_writeback_approval(db, batch=batch, user_id=user_id)
    if grant_scope == "writeback":
        _candidates, candidate_error = _writeback_execution_candidates(db, batch)
        if candidate_error:
            return {"status": "blocked", "skip_reason": candidate_error}
    try:
        candidate_hash = _candidate_hash(db, batch, grant_scope)
    except ApiError as exc:
        if exc.error_code == "readonly_recipient_data_stale":
            return {"status": "blocked", "skip_reason": "recipient_data_stale"}
        raise
    token = secrets.token_urlsafe(32)
    now = get_utc_now()
    db.add(WarehouseShippingApprovalGrant(
        batch_id=batch.id, user_id=user_id, grant_scope=grant_scope,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(), batch_version=batch.version,
        candidate_hash=candidate_hash, expires_at=now + timedelta(minutes=10),
    ))
    db.commit()
    return {"status": "approval_granted", "approval_token": token, "expires_at": now + timedelta(minutes=10), "batch_version": batch.version}


def _consume_approval_grant(
    db: Session, *, batch_id: int, user_id: int, grant_scope: str, token: str,
) -> str | None:
    grant = db.scalar(select(WarehouseShippingApprovalGrant).where(
        WarehouseShippingApprovalGrant.batch_id == batch_id,
        WarehouseShippingApprovalGrant.user_id == user_id,
        WarehouseShippingApprovalGrant.grant_scope == grant_scope,
        WarehouseShippingApprovalGrant.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest(),
        WarehouseShippingApprovalGrant.used_at.is_(None),
    ))
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    expires_at = grant.expires_at.replace(tzinfo=timezone.utc) if grant is not None and grant.expires_at.tzinfo is None else (grant.expires_at if grant is not None else None)
    try:
        candidate_hash = _candidate_hash(db, batch, grant_scope) if batch is not None else None
    except ApiError:
        return None
    if (
        grant is None
        or batch is None
        or expires_at < get_utc_now()
        or grant.batch_version != batch.version
        or grant.candidate_hash != candidate_hash
    ):
        return None
    grant.used_at = get_utc_now()
    db.commit()
    return grant.candidate_hash


def consume_approval_grant(db: Session, *, batch_id: int, user_id: int, grant_scope: str, token: str) -> bool:
    return _consume_approval_grant(
        db, batch_id=batch_id, user_id=user_id, grant_scope=grant_scope, token=token,
    ) is not None


def consume_approval_grant_with_candidate_hash(
    db: Session, *, batch_id: int, user_id: int, grant_scope: str, token: str,
) -> str | None:
    return _consume_approval_grant(
        db, batch_id=batch_id, user_id=user_id, grant_scope=grant_scope, token=token,
    )


def _serialize_batch(batch: WarehouseShippingBatch, *, include_rows: bool = True) -> dict[str, Any]:
    data = {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "store_id": batch.store_id,
        "platform": batch.platform,
        "status": batch.status,
        "export_batch_id": batch.export_batch_id,
        "tracking_import_batch_id": batch.tracking_import_batch_id,
        "warehouse_sent_at": batch.warehouse_sent_at,
        "warehouse_returned_at": batch.warehouse_returned_at,
        "operator_confirmed_at": batch.operator_confirmed_at,
        "completed_at": batch.completed_at,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }
    if include_rows:
        rows = [_safe_batch_row(row) for row in sorted(batch.rows, key=lambda item: item.id)]
        data["rows"] = rows
        data["counts"] = {
            "normal": sum(row["row_status"] in {"pending_export", "ready_for_confirmation", "ready_for_writeback", "platform_written"} for row in rows),
            "needs_confirmation": sum(row["row_status"] == "needs_confirmation" for row in rows),
            "blocked": sum(row["row_status"] == "blocked" for row in rows),
            "failed": sum(row["row_status"] == "platform_failed" for row in rows),
        }
    return data


def _t18_batch_capability_snapshot(db: Session, batch: WarehouseShippingBatch) -> dict[str, Any]:
    """Return local-only writeback readiness without exposing tracking or calling Naver."""

    settings = get_settings()
    candidates, candidate_error = _t18_candidates(db, batch)
    candidate_count = len(candidates or [])
    capability_details = _t18_capability_details(batch=batch, candidates=candidates)
    grant = db.scalar(
        select(WarehouseShippingApprovalGrant)
        .where(
            WarehouseShippingApprovalGrant.batch_id == batch.id,
            WarehouseShippingApprovalGrant.attempt_scope == _t18_attempt_scope(batch.store_id),
        )
        .order_by(WarehouseShippingApprovalGrant.id.desc())
    )
    attempt_status = grant.attempt_status if grant else None
    if attempt_status in T18_RECONCILABLE_ATTEMPT_STATUSES:
        return _t18_capability(
            settings=settings,
            status="reconciliation_required",
            candidate_count=candidate_count,
            operator_message="A previous platform request requires read-only reconciliation before any further action.",
            approval_expires_at=grant.expires_at,
            reconciliation_required=True,
            allowed_action="reconcile",
            attempt_status=attempt_status,
            **capability_details,
        )
    store_matches, _store_error = _t18_trial_store_matches(db, batch)
    if not store_matches:
        return _t18_capability(
            settings=settings,
            status="not_available",
            candidate_count=candidate_count,
            operator_message="This batch is outside the constrained PXG/Naver pilot scope.",
            attempt_status=attempt_status,
            **capability_details,
        )
    if candidate_error or candidates is None:
        return _t18_capability(
            settings=settings,
            status="blocked",
            candidate_count=candidate_count,
            operator_message="The batch does not contain exactly one confirmed pilot tracking record.",
            attempt_status=attempt_status,
            **capability_details,
        )
    gate_error = _t18_gate_skip_reason(settings)
    if gate_error:
        return _t18_capability(
            settings=settings,
            status="disabled",
            candidate_count=candidate_count,
            operator_message="The pilot write gates are closed.",
            attempt_status=attempt_status,
            **capability_details,
        )
    if _t18_attempt_limit_reached(db, store_id=batch.store_id):
        return _t18_capability(
            settings=settings,
            status="blocked",
            candidate_count=candidate_count,
            operator_message="The pilot request limit has already been consumed and requires owner review.",
            attempt_status=attempt_status,
            **capability_details,
        )
    return _t18_capability(
        settings=settings,
        status="approval_required",
        candidate_count=candidate_count,
        operator_message="A fresh final Naver preflight and operator approval are required before execution.",
        allowed_action="approve",
        attempt_status=attempt_status,
        **capability_details,
    )


def _find_mapping(db: Session, order: Order) -> LogisticsInventoryMapping | None:
    product_key = shipping_service._normalize_key_part(order.product_name)
    return db.scalar(
        select(LogisticsInventoryMapping)
        .where(
            LogisticsInventoryMapping.store_id == order.store_id,
            LogisticsInventoryMapping.platform == order.platform,
            LogisticsInventoryMapping.normalized_product_name == product_key,
            LogisticsInventoryMapping.is_active.is_(True),
        )
        .order_by(LogisticsInventoryMapping.match_priority.asc(), LogisticsInventoryMapping.id.asc())
    )


def _delivery_memo(order: Order) -> str:
    raw = order.raw_data if isinstance(order.raw_data, dict) else {}
    return shipping_service._clean_text(
        raw.get("delivery_memo") or raw.get("deliveryMemo") or raw.get("shippingMemo") or raw.get("memo"),
        max_length=300,
    )


def create_warehouse_batch(
    db: Session, *, store_id: int, platform: str, order_ids: list[int], manual_approval: bool, actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_platform = shipping_service._normalize_platform(platform)
    if not manual_approval:
        return {"status": "blocked", "skip_reason": "manual_approval_required"}
    if not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_role_required"}
    if normalized_platform is None:
        return {"status": "blocked", "skip_reason": "platform_not_supported"}
    ensure_store_exists(db, store_id)
    unique_ids = sorted(set(order_ids))
    orders = db.scalars(select(Order).where(Order.id.in_(unique_ids))).all()
    order_by_id = {order.id: order for order in orders}
    missing = [order_id for order_id in unique_ids if order_id not in order_by_id]
    invalid = [order.id for order in orders if order.store_id != store_id or order.platform != normalized_platform]
    if missing or invalid:
        return {"status": "blocked", "skip_reason": "orders_outside_selected_store_or_platform", "missing_order_ids": missing, "invalid_order_ids": invalid}

    active_rows = db.scalars(
        select(WarehouseShippingBatchOrder).join(WarehouseShippingBatch).where(
            WarehouseShippingBatchOrder.local_order_id.in_(unique_ids),
            WarehouseShippingBatchOrder.is_active.is_(True),
            WarehouseShippingBatch.status.in_(ACTIVE_BATCH_STATUSES),
        )
    ).all()
    if active_rows:
        return {
            "status": "blocked",
            "skip_reason": "orders_already_in_active_shipping_batch",
            "duplicate_order_ids": [row.local_order_id for row in active_rows],
            "existing_batch_ids": sorted({row.batch_id for row in active_rows}),
        }

    completed_rows = db.scalars(
        select(WarehouseShippingBatchOrder).where(
            WarehouseShippingBatchOrder.local_order_id.in_(unique_ids),
            WarehouseShippingBatchOrder.row_status == "platform_written",
        )
    ).all()
    non_shippable = [
        order.id
        for order in orders
        if str(order.order_status or "").upper() in TERMINAL_ORDER_STATUSES
        or str(order.order_status or "").upper() not in UPDATABLE_ORDER_STATUSES
    ]
    if completed_rows or non_shippable:
        return {
            "status": "blocked",
            "skip_reason": "orders_not_shippable_or_already_platform_written",
            "order_ids": sorted(set(non_shippable + [row.local_order_id for row in completed_rows])),
        }

    now = get_utc_now()
    batch_no = f"SHIP-{now.astimezone(timezone.utc):%Y%m%d%H%M%S%f}-{store_id:04d}"
    batch = WarehouseShippingBatch(
        batch_no=batch_no,
        store_id=store_id,
        platform=normalized_platform,
        status="created",
        created_by_actor_hash=shipping_service._actor_hash(actor_context),
    )
    db.add(batch)
    db.flush()
    for order in orders:
        mapping = _find_mapping(db, order)
        if mapping is None:
            row_status, reason = "needs_confirmation", "sku_mapping_missing"
        else:
            row_status, reason = "pending_export", None
        db.add(WarehouseShippingBatchOrder(
            batch_id=batch.id,
            local_order_id=order.id,
            store_id=store_id,
            platform=normalized_platform,
            order_reference=order.external_order_id,
            product_order_reference=order.external_product_order_id,
            product_name=order.product_name,
            quantity=order.quantity,
            internal_sku=mapping.internal_sku if mapping else None,
            logistics_inventory_code=mapping.logistics_inventory_code if mapping else None,
            pre_batch_order_status=order.order_status,
            row_status=row_status,
            failure_reason=reason,
            active_lock="active",
        ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "blocked", "skip_reason": "orders_already_in_active_shipping_batch"}
    db.refresh(batch)
    return {"status": "created", "batch": _serialize_batch(batch), "real_api_called": False, "privacy_fields_redacted": True}


def list_warehouse_batches(db: Session, *, store_id: int, platform: str, include_rows: bool = False) -> dict[str, Any]:
    normalized_platform = shipping_service._normalize_platform(platform)
    ensure_store_exists(db, store_id)
    batches = db.scalars(
        select(WarehouseShippingBatch).where(
            WarehouseShippingBatch.store_id == store_id,
            WarehouseShippingBatch.platform == normalized_platform,
        ).order_by(WarehouseShippingBatch.created_at.desc())
    ).unique().all()
    items: list[dict[str, Any]] = []
    for batch in batches:
        item = _serialize_batch(batch, include_rows=include_rows)
        item["writeback_capability"] = _t18_batch_capability_snapshot(db, batch)
        items.append(item)
    return {"status": "ready", "items": items, "real_api_called": False}


def get_warehouse_batch_tracking_details(db: Session, *, batch_id: int) -> dict[str, Any]:
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found"}
    if batch.status not in {"warehouse_returned", "ready_to_writeback", "writeback_partial"}:
        return {
            "status": "blocked",
            "skip_reason": "shipping_batch_status_not_supported_for_tracking_details",
            "batch_id": batch.id,
        }
    if not batch.tracking_import_batch_id:
        return {"status": "blocked", "skip_reason": "tracking_import_required", "batch_id": batch.id}
    import_rows = db.scalars(select(ShippingTrackingImportRow).where(
        ShippingTrackingImportRow.import_batch_id == batch.tracking_import_batch_id,
    ).order_by(ShippingTrackingImportRow.id.asc())).all()
    batch_rows = list(batch.rows)
    items: list[dict[str, Any]] = []

    if batch.status == "warehouse_returned":
        for tracking_row in import_rows:
            product_reference = str(tracking_row.product_order_reference or "").strip()
            if product_reference:
                matches = [row for row in batch_rows if row.product_order_reference == product_reference]
                match_error = "shipping_tracking_product_order_match_not_unique"
            else:
                matches = [row for row in batch_rows if row.order_reference == tracking_row.order_reference]
                match_error = "shipping_tracking_order_match_not_unique"
            batch_row = matches[0] if len(matches) == 1 else None
            items.append({
                "tracking_record_id": tracking_row.id,
                "batch_row_id": batch_row.id if batch_row else None,
                "product_order_reference": tracking_row.product_order_reference,
                "order_reference": tracking_row.order_reference,
                "product_name": batch_row.product_name if batch_row else None,
                "carrier": tracking_row.carrier,
                "tracking_number": tracking_row.tracking_number,
                "shipped_at": tracking_row.shipped_at,
                "validation_status": tracking_row.row_status if batch_row else "blocked",
                "exception_reason": tracking_row.operator_note or (None if batch_row else match_error),
            })
        detail_mode = "warehouse_import_review"
        source = "warehouse_tracking_import_records"
    else:
        strict_statuses = {"ready_for_writeback"} if batch.status == "ready_to_writeback" else {
            "ready_for_writeback", "platform_failed", "platform_written",
        }
        selected_tracking_ids: set[int] = set()
        for batch_row in sorted(
            (row for row in batch_rows if row.row_status in strict_statuses),
            key=lambda item: item.id,
        ):
            tracking_row, match_error = _match_tracking_import_row(import_rows, batch_row)
            if match_error or tracking_row is None or tracking_row.id in selected_tracking_ids:
                return {
                    "status": "blocked",
                    "skip_reason": match_error or "shipping_tracking_record_reused",
                    "batch_id": batch.id,
                }
            items.append({
                "tracking_record_id": tracking_row.id,
                "batch_row_id": batch_row.id,
                "product_order_reference": tracking_row.product_order_reference,
                "order_reference": tracking_row.order_reference,
                "product_name": batch_row.product_name,
                "carrier": tracking_row.carrier,
                "tracking_number": tracking_row.tracking_number,
                "shipped_at": tracking_row.shipped_at,
                "validation_status": batch_row.row_status,
                "exception_reason": batch_row.failure_reason or tracking_row.operator_note,
            })
            selected_tracking_ids.add(tracking_row.id)
        if not items:
            return {"status": "blocked", "skip_reason": "no_tracking_details_available", "batch_id": batch.id}
        detail_mode = "platform_writeback_review"
        source = "platform_writeback_tracking_records"
    return {
        "status": "ready",
        "batch_id": batch.id,
        "items": items,
        "privacy_fields_included": False,
        "source": source,
        "detail_mode": detail_mode,
    }


def _warehouse_xlsx(rows: list[dict[str, Any]]) -> bytes:
    headers = [
        ("batch_no", "发货批次"), ("platform", "平台"), ("order_reference", "订单号"),
        ("product_order_reference", "商品订单号"), ("internal_sku", "内部货号"),
        ("logistics_inventory_code", "仓库货号"), ("product_name", "商品"), ("quantity", "数量"),
        ("receiver_name", "收件人"), ("receiver_phone", "主联系电话"),
        ("receiver_phone_secondary", "备用联系电话"), ("zip_code", "邮编"),
        ("receiver_address_line1", "基础地址"), ("receiver_address_line2", "详细地址"),
        ("receiver_address_full", "完整地址"), ("delivery_memo", "配送备注"), ("carrier", "快递公司"),
        ("tracking_number", "物流单号"), ("warehouse_note", "仓库备注"),
    ]
    return shipping_service._build_xlsx_bytes(rows, headers=headers)


def download_warehouse_manifest(
    db: Session, *, batch_id: int, manual_approval: bool, privacy_access_acknowledged: bool, actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not manual_approval or not privacy_access_acknowledged:
        return {"status": "blocked", "skip_reason": "manual_privacy_approval_required"}
    if not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_role_required"}
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found"}
    if batch.status not in {"created", "warehouse_sent"}:
        return {"status": "blocked", "skip_reason": "batch_not_exportable"}
    prepared_rows: list[tuple[WarehouseShippingBatchOrder, dict[str, str]]] = []
    for item in batch.rows:
        if item.row_status != "pending_export":
            continue
        order = item.order
        try:
            recipient = order_service.recipient_contract(order, db=db, warehouse_authorized=True)
        except ApiError as exc:
            if exc.error_code == "readonly_recipient_data_stale":
                return {"status": "blocked", "skip_reason": "recipient_data_stale"}
            raise
        prepared_rows.append((item, recipient))
    if not prepared_rows:
        return {"status": "blocked", "skip_reason": "no_exportable_batch_rows"}

    rows: list[dict[str, Any]] = []
    for item, recipient in prepared_rows:
        rows.append({
            "batch_no": batch.batch_no, "platform": batch.platform, "order_reference": item.order_reference,
            "product_order_reference": item.product_order_reference or "", "internal_sku": item.internal_sku or "",
            "logistics_inventory_code": item.logistics_inventory_code or "", "product_name": item.product_name,
            "quantity": item.quantity, **recipient, "carrier": "", "tracking_number": "", "warehouse_note": "",
        })
        item.row_status = "warehouse_sent"
    batch.status = "warehouse_sent"
    batch.version += 1
    batch.warehouse_sent_at = get_utc_now()
    db.commit()
    _write_workflow_audit(db, batch=batch, actor_context=actor_context, action="recipient_pii_exported", row_count=len(rows), reason_code="warehouse_manifest_download")
    content = _warehouse_xlsx(rows)
    return {
        "status": "warehouse_manifest_ready", "batch_id": batch.id, "file_name": f"{batch.batch_no}-warehouse.xlsx",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "file_content_base64": base64.b64encode(content).decode("ascii"), "row_count": len(rows),
        "audit_payload_contains_pii": False, "privacy_fields_redacted": False, "real_api_called": False,
    }


def import_warehouse_tracking_xlsx(
    db: Session, *, batch_id: int, source_file_name: str, file_content_base64: str, manual_approval: bool, actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not manual_approval or not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_manual_approval_required"}
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None or batch.status not in {"warehouse_sent", "warehouse_returned"}:
        return {"status": "blocked", "skip_reason": "batch_not_waiting_for_warehouse_return"}
    try:
        content = base64.b64decode(file_content_base64, validate=True)
        table = shipping_service._parse_xlsx_rows(content)
    except (binascii.Error, ValueError, Exception) as exc:
        return {"status": "blocked", "skip_reason": "tracking_xlsx_parse_failed", "error_type": type(exc).__name__}
    if len(table) < 2:
        return {"status": "blocked", "skip_reason": "tracking_xlsx_data_rows_required"}
    header_map, _unknown = shipping_service._tracking_header_map(table[0])
    parsed = []
    for values in table[1:]:
        payload = {field: values[index] for index, field in header_map.items() if index < len(values)}
        if any(str(value or "").strip() for value in payload.values()):
            parsed.append(payload)
    normalized, error = shipping_service._validate_tracking_import_rows(parsed)
    if normalized is None:
        return {"status": "blocked", **error}

    now = get_utc_now()
    import_batch = ShippingTrackingImportBatch(
        store_id=batch.store_id, platform=batch.platform, file_type="tracking_upload", file_format="xlsx",
        source_file_name=shipping_service._clean_text(source_file_name, max_length=255), row_count=len(normalized),
        ready_row_count=0, duplicate_row_count=0, blocked_row_count=0,
        actor_id_hash=shipping_service._actor_hash(actor_context), audit_correlation_id=f"warehouse-import-{batch.id}-{now:%Y%m%d%H%M%S}",
        import_status="recorded", parser_contract_acknowledged=True, tracking_number_import_open=False,
        shipment_writeback_called=False, orders_updated=False, raw_response_saved=False, secrets_saved=False,
        privacy_fields_redacted=True, mapping_version="warehouse_tracking_import_v1",
    )
    db.add(import_batch)
    db.flush()
    batch_rows_by_ref: dict[str, list[WarehouseShippingBatchOrder]] = {}
    for batch_row in batch.rows:
        batch_rows_by_ref.setdefault(batch_row.order_reference, []).append(batch_row)
    batch_rows_by_product_ref = {row.product_order_reference: row for row in batch.rows if row.product_order_reference}
    seen_tracking: set[str] = set()
    normal = needs_confirmation = blocked = 0
    for row in normalized:
        product_order_reference = str(row.get("product_order_reference") or "").strip()
        order_reference_matches = batch_rows_by_ref.get(row["order_reference"], [])
        item = batch_rows_by_product_ref.get(product_order_reference) if product_order_reference else None
        tracking_hash = shipping_service._safe_hash_identifier(row["tracking_number"])
        status, reason = "ready_for_confirmation", None
        if item is None and product_order_reference:
            status, reason = "blocked", "product_order_not_in_shipping_batch"
        elif item is None and len(order_reference_matches) == 1:
            item = order_reference_matches[0]
        elif item is None and len(order_reference_matches) > 1:
            status, reason = "blocked", "product_order_reference_required_for_multi_item_order"
        elif item is None:
            status, reason = "blocked", "order_not_in_shipping_batch"
        if item is not None and status != "blocked":
            if item.order_reference != row["order_reference"]:
                status, reason = "blocked", "product_order_order_reference_mismatch"
            elif item.order.order_status.upper() in TERMINAL_ORDER_STATUSES:
                status, reason = "blocked", "order_status_not_shippable"
            elif tracking_hash in seen_tracking:
                status, reason = "needs_confirmation", "duplicate_tracking_number_in_upload"
            elif row.get("logistics_inventory_code") and item.logistics_inventory_code and row["logistics_inventory_code"] != item.logistics_inventory_code:
                status, reason = "needs_confirmation", "warehouse_sku_mismatch"
        seen_tracking.add(tracking_hash)
        if item is not None:
            item.carrier = row["carrier"]
            item.tracking_number_hash = tracking_hash
            item.shipped_at = row["shipped_at"]
            item.row_status = status
            item.failure_reason = reason
        if status == "ready_for_confirmation": normal += 1
        elif status == "needs_confirmation": needs_confirmation += 1
        else: blocked += 1
        db.add(ShippingTrackingImportRow(
            import_batch_id=import_batch.id, store_id=batch.store_id, platform=batch.platform,
            order_reference=row["order_reference"], product_order_reference=row["product_order_reference"],
            logistics_inventory_code=row["logistics_inventory_code"] or None, carrier=row["carrier"],
            tracking_number=row["tracking_number"], shipped_at=row["shipped_at"], row_status=status,
            operator_note=reason, future_write_allowed=False,
        ))
    import_batch.ready_row_count = normal
    import_batch.duplicate_row_count = needs_confirmation
    import_batch.blocked_row_count = blocked
    batch.tracking_import_batch_id = import_batch.id
    batch.version += 1
    batch.warehouse_returned_at = now
    batch.status = "warehouse_returned"
    db.commit()
    _write_workflow_audit(db, batch=batch, actor_context=actor_context, action="warehouse_tracking_imported", row_count=len(normalized), reason_code="warehouse_return_import")
    db.refresh(batch)
    return {"status": "warehouse_return_imported", "batch": _serialize_batch(batch), "normal_count": normal, "needs_confirmation_count": needs_confirmation, "blocked_count": blocked, "real_api_called": False}


def confirm_warehouse_batch(db: Session, *, batch_id: int, confirmed_row_ids: list[int], manual_approval: bool, actor_context: dict[str, Any] | None) -> dict[str, Any]:
    if not manual_approval or not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_manual_approval_required"}
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None or batch.status != "warehouse_returned":
        return {"status": "blocked", "skip_reason": "batch_not_ready_for_confirmation"}
    confirmed = set(confirmed_row_ids)
    for row in batch.rows:
        if row.row_status == "ready_for_confirmation" or (row.row_status == "needs_confirmation" and row.id in confirmed):
            row.row_status = "ready_for_writeback"
            row.failure_reason = None
        elif row.row_status == "needs_confirmation":
            row.failure_reason = row.failure_reason or "operator_confirmation_required"
    ready = sum(row.row_status == "ready_for_writeback" for row in batch.rows)
    if not ready:
        return {"status": "blocked", "skip_reason": "no_confirmed_tracking_rows"}
    if not batch.tracking_import_batch_id:
        return {"status": "blocked", "skip_reason": "tracking_import_required"}
    execution_candidates, candidate_error = _writeback_execution_candidates(db, batch)
    if candidate_error or execution_candidates is None:
        db.rollback()
        return {"status": "blocked", "skip_reason": candidate_error or "no_confirmed_tracking_rows"}
    local_update = shipping_service.write_tracking_order_status_local_update(
        db,
        store_id=batch.store_id,
        platform=batch.platform,
        tracking_rows=[
            {
                "order_reference": item["order_reference"],
                "product_order_reference": item["product_order_reference"],
                "carrier": item["carrier"],
                "tracking_number": item["tracking_number"],
                "shipped_at": item["shipped_at"],
            }
            for item in execution_candidates
        ],
        import_batch_id=batch.tracking_import_batch_id,
        manual_approval=True,
        matching_contract_acknowledged=True,
        backup_evidence_acknowledged=True,
        audit_evidence_acknowledged=True,
        operator_checklist_acknowledged=True,
        actor_context=actor_context,
    )
    if local_update.get("status") not in {"tracking_order_status_update_succeeded", "tracking_order_status_update_noop"}:
        db.rollback()
        return {"status": "blocked", "skip_reason": local_update.get("skip_reason") or "local_dispatch_update_failed", "local_update": local_update}
    batch.status = "ready_to_writeback"
    batch.version += 1
    batch.operator_confirmed_at = get_utc_now()
    db.commit()
    _write_workflow_audit(db, batch=batch, actor_context=actor_context, action="shipping_batch_confirmed", row_count=ready, reason_code="operator_confirmed_tracking")
    db.refresh(batch)
    return {"status": "ready_to_writeback", "batch": _serialize_batch(batch), "local_update": local_update, "real_api_called": False}


def _t18_attempt_response_hash(result: dict[str, Any] | None) -> str:
    safe_summary = {
        "status": (result or {}).get("status"),
        "skip_reason": (result or {}).get("skip_reason"),
        "error_code": (result or {}).get("error_code"),
        "http_status": (result or {}).get("http_status"),
        "success_count": (result or {}).get("success_count"),
        "failed_count": (result or {}).get("failed_count"),
        "real_api_called": bool((result or {}).get("real_api_called")),
    }
    return hashlib.sha256(
        json.dumps(safe_summary, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _t18_record_attempt(
    db: Session,
    *,
    grant_id: int,
    attempt_status: str,
    error_code: str | None = None,
    result: dict[str, Any] | None = None,
) -> WarehouseShippingApprovalGrant | None:
    grant = db.get(WarehouseShippingApprovalGrant, grant_id)
    if grant is None:
        return None
    grant.attempt_status = attempt_status
    grant.attempt_finished_at = get_utc_now()
    grant.attempt_error_code = str(error_code or "")[:80] or None
    grant.attempt_response_hash = _t18_attempt_response_hash(result)
    db.commit()
    return grant


def _t18_load_prepared_approval(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    user_id: int,
    approval_token: str | None,
) -> tuple[WarehouseShippingApprovalGrant | None, str | None]:
    if not approval_token:
        return None, "shipping_approval_token_invalid"
    token_hash = hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
    grant = db.scalar(select(WarehouseShippingApprovalGrant).where(
        WarehouseShippingApprovalGrant.batch_id == batch.id,
        WarehouseShippingApprovalGrant.user_id == user_id,
        WarehouseShippingApprovalGrant.grant_scope == "writeback",
        WarehouseShippingApprovalGrant.token_hash == token_hash,
    ))
    if grant is None or grant.attempt_scope != _t18_attempt_scope(batch.store_id):
        return None, "shipping_approval_token_invalid"
    now = get_utc_now()
    if _as_utc(grant.expires_at) < now or grant.batch_version != batch.version:
        return None, "shipping_approval_token_invalid"
    if grant.attempt_status not in T18_PREPARED_ATTEMPT_STATUSES or grant.used_at is not None:
        return grant, "shipping_approval_attempt_already_claimed"
    return grant, None


def _t18_claim_attempt(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    grant_id: int,
    user_id: int,
    candidate_hash: str,
) -> tuple[WarehouseShippingApprovalGrant | None, str | None, str | None]:
    """Atomically consume the sole pilot POST slot immediately before POST."""

    grant = db.get(WarehouseShippingApprovalGrant, grant_id)
    now = get_utc_now()
    if (
        grant is None
        or grant.batch_id != batch.id
        or grant.user_id != user_id
        or grant.grant_scope != "writeback"
        or grant.attempt_scope != _t18_attempt_scope(batch.store_id)
        or grant.batch_version != batch.version
        or _as_utc(grant.expires_at) < now
    ):
        return None, None, "shipping_approval_token_invalid"
    if grant.candidate_hash != candidate_hash:
        return grant, None, "shipping_approval_candidate_changed"
    if grant.attempt_status not in T18_PREPARED_ATTEMPT_STATUSES or grant.used_at is not None:
        return grant, None, "shipping_approval_attempt_already_claimed"
    if _t18_attempt_limit_reached(db, store_id=batch.store_id):
        return grant, None, "pxg_naver_pilot_attempt_limit_reached"

    attempt_nonce = secrets.token_urlsafe(32)
    claim_nonce_hash = hashlib.sha256(attempt_nonce.encode("utf-8")).hexdigest()
    try:
        claimed = db.execute(
            update(WarehouseShippingApprovalGrant)
            .where(
                WarehouseShippingApprovalGrant.id == grant.id,
                WarehouseShippingApprovalGrant.batch_id == batch.id,
                WarehouseShippingApprovalGrant.user_id == user_id,
                WarehouseShippingApprovalGrant.grant_scope == "writeback",
                WarehouseShippingApprovalGrant.attempt_scope == _t18_attempt_scope(batch.store_id),
                WarehouseShippingApprovalGrant.batch_version == batch.version,
                WarehouseShippingApprovalGrant.expires_at >= now,
                WarehouseShippingApprovalGrant.used_at.is_(None),
                WarehouseShippingApprovalGrant.attempt_status.in_(T18_PREPARED_ATTEMPT_STATUSES),
                WarehouseShippingApprovalGrant.candidate_hash == candidate_hash,
            )
            .values(
                used_at=now,
                attempt_status="requesting",
                attempt_token_hash=claim_nonce_hash,
                attempt_started_at=now,
                attempt_error_code=None,
                attempt_response_hash=None,
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return grant, None, "pxg_naver_pilot_attempt_limit_reached"
    if claimed.rowcount != 1:
        return grant, None, "shipping_approval_attempt_already_claimed"
    db.expire_all()
    return db.get(WarehouseShippingApprovalGrant, grant.id), attempt_nonce, None


def _t18_release_unposted_attempt(db: Session, *, grant_id: int, attempt_nonce: str) -> None:
    """Release a claimed slot only when the lower layer proves no POST began."""

    attempt_token_hash = hashlib.sha256(attempt_nonce.encode("utf-8")).hexdigest()
    db.execute(
        update(WarehouseShippingApprovalGrant)
        .where(
            WarehouseShippingApprovalGrant.id == grant_id,
            WarehouseShippingApprovalGrant.attempt_status == "requesting",
            WarehouseShippingApprovalGrant.attempt_token_hash == attempt_token_hash,
        )
        .values(
            used_at=None,
            attempt_status="prepared",
            attempt_token_hash=None,
            attempt_started_at=None,
            attempt_finished_at=None,
            attempt_error_code=None,
            attempt_response_hash=None,
        )
    )
    db.commit()


def _remove_full_tracking_from_order_metadata(order: Order) -> dict[str, Any]:
    return shipping_service._remove_full_tracking_metadata(dict(order.raw_data or {}))


def _mark_t18_batch_completed(batch: WarehouseShippingBatch, candidates: list[dict[str, Any]]) -> None:
    selected_row_ids = {int(item["batch_row_id"]) for item in candidates}
    for row in batch.rows:
        if row.id in selected_row_ids:
            row.row_status = "platform_written"
            row.is_active = False
            row.active_lock = None
            row.failure_reason = None
    batch.status = "completed"
    batch.completed_at = get_utc_now()


def _apply_t18_reconciled_local_state(
    db: Session,
    *,
    batch: WarehouseShippingBatch,
    candidates: list[dict[str, Any]],
) -> None:
    now = get_utc_now()
    candidate_by_row_id = {int(item["batch_row_id"]): item for item in candidates}
    for row in batch.rows:
        candidate = candidate_by_row_id.get(row.id)
        if candidate is None:
            continue
        order = row.order or db.get(Order, row.local_order_id)
        if order is None:
            raise ApiError("warehouse batch order is unavailable", "warehouse_batch_order_not_found", 409)
        previous_status = str(order.order_status or "").strip().upper()
        metadata = _remove_full_tracking_from_order_metadata(order)
        carrier_code = shipping_service._normalize_naver_delivery_company_code(candidate.get("carrier"))
        metadata.update({
            "naver_shipment_writeback": True,
            "naver_shipment_writeback_phase": "T18-reconciled",
            "shipping_status_previous_status": previous_status,
            "shipping_status_current_status": shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_TARGET_STATUS,
            "shipping_tracking_hash": candidate["tracking_number_hash"],
            "shipping_carrier_code": carrier_code,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
        })
        order.order_status = shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_TARGET_STATUS
        order.last_synced_at = now
        order.raw_data = metadata
        dedupe_key = (
            f"shipping-naver-t18-reconciled|{batch.store_id}|{order.id}|"
            f"{candidate['tracking_number_hash']}|DISPATCHED"
        )
        existing_event = db.scalar(select(OrderStatusEvent).where(
            OrderStatusEvent.store_id == batch.store_id,
            OrderStatusEvent.platform == batch.platform,
            OrderStatusEvent.dedupe_key == dedupe_key,
        ))
        if existing_event is None:
            db.add(OrderStatusEvent(
                store_id=batch.store_id,
                order_id=order.id,
                platform=batch.platform,
                external_order_id_hash=shipping_service._safe_hash_identifier(order.external_order_id),
                external_product_order_id_hash=shipping_service._safe_hash_identifier(candidate["product_order_reference"]),
                event_type="shipping_dispatched",
                status_raw=shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_TARGET_STATUS,
                status_label_zh=shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_LABEL_ZH,
                payment_status_raw=None,
                payment_status_label_zh=None,
                delivery_status_raw=shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_TARGET_STATUS,
                delivery_status_label_zh=shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_LABEL_ZH,
                claim_status_raw=None,
                claim_status_label_zh=None,
                observed_at=now,
                source_phase="T18",
                source_type="naver_shipment_writeback_reconcile",
                mapping_version="naver_shipment_writeback_t18_v1",
                dedupe_key=dedupe_key,
                raw_response_saved=False,
                privacy_fields_redacted=True,
                address_saved=False,
                safe_metadata={
                    "shipping_tracking_hash": candidate["tracking_number_hash"],
                    "shipping_carrier_code": carrier_code,
                    "source_phase": "T18",
                    "raw_response_saved": False,
                    "privacy_fields_redacted": True,
                },
            ))
    _mark_t18_batch_completed(batch, candidates)


def _t18_unknown_after_post(result: dict[str, Any]) -> bool:
    if not result.get("real_api_called"):
        return False
    http_status = result.get("http_status")
    if not http_status:
        return True
    try:
        if int(http_status) >= 500:
            return True
    except (TypeError, ValueError):
        return True
    return result.get("skip_reason") in {
        "shipment_writeback_failed",
        "no_successful_dispatch_items",
        "shipment_dispatch_invalid_response",
        "shipment_dispatch_exact_success_not_confirmed",
    } or result.get("status") not in {"success", "failed"}


def _t18_execute_writeback(
    db: Session,
    *,
    batch_id: int,
    user_id: int | None,
    approval_token: str | None,
    manual_approval: bool,
    final_operator_confirmation: bool,
    real_api_call_requested: bool,
    actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = get_settings()
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found", "real_api_called": False}
    candidates, candidate_error = _t18_candidates(db, batch)
    candidate_count = len(candidates or [])
    gate_error = _t18_gate_skip_reason(settings)
    if gate_error:
        return {
            "status": "blocked", "skip_reason": gate_error, "real_api_called": False,
            "token_request_count": 0, "http_request_count": 0,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="PXG/Naver pilot writeback is disabled by a required safety gate.",
            ),
        }
    store_matches, store_error = _t18_trial_store_matches(db, batch)
    if not store_matches:
        return {
            "status": "blocked", "skip_reason": store_error, "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="This batch is outside the configured PXG/Naver pilot store.",
            ),
        }
    if not manual_approval or not final_operator_confirmation or not real_api_call_requested:
        return {
            "status": "blocked", "skip_reason": "final_operator_confirmation_and_real_api_request_required", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="Final operator confirmation is required before a pilot writeback.",
            ),
        }
    if not _role_allowed(actor_context) or user_id is None:
        return {
            "status": "blocked", "skip_reason": "operator_role_required", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="An authorized operator is required for pilot writeback.",
            ),
        }
    if batch.status not in {"ready_to_writeback", "writeback_partial"} or not batch.tracking_import_batch_id:
        return {
            "status": "blocked", "skip_reason": "batch_not_ready_for_writeback", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="The warehouse batch is not ready for platform writeback.",
            ),
        }
    if candidate_error or candidates is None:
        return {
            "status": "blocked", "skip_reason": candidate_error or "no_confirmed_tracking_rows", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="The pilot requires exactly one valid warehouse tracking row.",
            ),
        }

    grant, approval_error = _t18_load_prepared_approval(
        db, batch=batch, user_id=user_id, approval_token=approval_token,
    )
    if approval_error or grant is None:
        reconciliation_required = bool(grant and grant.attempt_status in T18_RECONCILABLE_ATTEMPT_STATUSES)
        return {
            "status": "blocked", "skip_reason": approval_error or "shipping_approval_token_invalid", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="reconciliation_required" if reconciliation_required else "blocked",
                candidate_count=candidate_count,
                operator_message="The approval token is no longer available for a new platform attempt.",
                approval_expires_at=grant.expires_at if grant else None,
                reconciliation_required=reconciliation_required,
                allowed_action="reconcile" if reconciliation_required else None,
                attempt_status=grant.attempt_status if grant else None,
            ),
        }

    preflight, preflight_error = _t18_platform_preflight(db, batch=batch, candidates=candidates)
    eligibility_error = _t18_preflight_eligible(preflight) if preflight is not None else None
    if preflight_error or eligibility_error or preflight is None:
        error_code = preflight_error or eligibility_error or "naver_platform_preflight_failed"
        return {
            "status": "blocked", "skip_reason": error_code, "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="The final Naver preflight did not permit a platform writeback.",
                platform_checked_at=preflight.get("platform_checked_at") if preflight else None,
                approval_expires_at=grant.expires_at,
                attempt_status=grant.attempt_status,
            ),
        }
    current_candidate_hash = _t18_candidate_hash(batch=batch, candidates=candidates, preflight=preflight)
    if grant.candidate_hash != current_candidate_hash:
        return {
            "status": "blocked", "skip_reason": "shipping_approval_candidate_changed", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="Batch, tracking, credential, or platform state changed after approval.",
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at,
                attempt_status=grant.attempt_status,
            ),
        }

    tracking_rows = [{
        "order_reference": item["order_reference"],
        "product_order_reference": item["product_order_reference"],
        "carrier": item["carrier"],
        "tracking_number": item["tracking_number"],
        "shipped_at": item["shipped_at"],
    } for item in candidates]
    prepared_auth = shipping_service.prepare_t18_naver_shipment_writeback(
        db,
        store_id=batch.store_id,
        expected_credential_id=int(preflight["credential_id"]),
        grant_id=grant.id,
        batch_id=batch.id,
        candidate_hash=current_candidate_hash,
        user_id=user_id,
        approval_token=str(approval_token or ""),
        expected_credential_binding=str(preflight["credential_binding"]),
        t18_pilot_execution=True,
    )
    if prepared_auth.get("status") != "ready":
        return {
            "status": "blocked",
            "skip_reason": prepared_auth.get("skip_reason") or "naver_writeback_authentication_failed",
            "real_api_called": False,
            "token_request_count": int(prepared_auth.get("token_request_count") or 0),
            "http_request_count": 0,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="blocked",
                candidate_count=candidate_count,
                operator_message="Naver write authentication could not be completed before any platform request.",
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at,
                attempt_status=grant.attempt_status,
            ),
        }

    claimed_grant, attempt_nonce, claim_error = _t18_claim_attempt(
        db,
        batch=batch,
        grant_id=grant.id,
        user_id=user_id,
        candidate_hash=current_candidate_hash,
    )
    if claim_error or claimed_grant is None or attempt_nonce is None:
        reconciliation_required = bool(claimed_grant and claimed_grant.attempt_status in T18_RECONCILABLE_ATTEMPT_STATUSES)
        return {
            "status": "blocked", "skip_reason": claim_error or "shipping_approval_attempt_already_claimed", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="reconciliation_required" if reconciliation_required else "blocked",
                candidate_count=candidate_count,
                operator_message="The approval is no longer available for a new platform request.",
                approval_expires_at=claimed_grant.expires_at if claimed_grant else grant.expires_at,
                reconciliation_required=reconciliation_required,
                allowed_action="reconcile" if reconciliation_required else None,
                attempt_status=claimed_grant.attempt_status if claimed_grant else None,
            ),
        }

    grant = claimed_grant
    execution_proof = {
        "grant_id": grant.id,
        "batch_id": batch.id,
        "store_id": batch.store_id,
        "candidate_hash": current_candidate_hash,
        "attempt_nonce": attempt_nonce,
        "expected_credential_id": int(preflight["credential_id"]),
        "credential_binding": str(preflight["credential_binding"]),
        "dispatch_candidate_hash": shipping_service._t18_dispatch_candidate_hash(
            store_id=batch.store_id,
            tracking_rows=tracking_rows,
        ),
    }
    result = shipping_service.execute_naver_shipment_writeback(
        db,
        store_id=batch.store_id,
        platform=batch.platform,
        import_batch_id=None,
        tracking_rows=tracking_rows,
        manual_approval=True,
        matching_contract_acknowledged=True,
        backup_evidence_acknowledged=True,
        audit_evidence_acknowledged=True,
        local_status_evidence_acknowledged=True,
        naver_writeback_boundary_acknowledged=True,
        operator_checklist_acknowledged=True,
        execution_approval=True,
        dry_run_evidence_acknowledged=True,
        permission_evidence_acknowledged=True,
        final_operator_confirmation=True,
        real_api_call_requested=True,
        actor_context=actor_context,
        t18_pilot_execution=True,
        commit_local_changes=False,
        expected_credential_id=int(preflight["credential_id"]),
        t18_execution_proof=execution_proof,
        t18_prepared_auth=prepared_auth.get("auth_context"),
    )
    success = (
        result.get("status") == "success"
        and int(result.get("success_count") or 0) == 1
        and int(result.get("failed_count") or 0) == 0
        and int(result.get("dispatch_candidate_count") or 0) == 1
    )
    if not success:
        if not result.get("platform_write_attempted") and not result.get("real_api_called"):
            _t18_release_unposted_attempt(db, grant_id=grant.id, attempt_nonce=attempt_nonce)
            return {
                "status": "blocked",
                "skip_reason": str(result.get("skip_reason") or "t18_prepost_execution_blocked")[:80],
                "writeback": result,
                "real_api_called": False,
                "writeback_capability": _t18_capability(
                    settings=settings,
                    status="blocked",
                    candidate_count=candidate_count,
                    operator_message="The platform request did not start; the approval remains available after correction.",
                    platform_checked_at=preflight["platform_checked_at"],
                    approval_expires_at=grant.expires_at,
                    attempt_status="prepared",
                ),
            }
        attempt_status = (
            "failed"
            if result.get("skipped_candidates")
            else ("unknown" if _t18_unknown_after_post(result) else "failed")
        )
        error_code = str(result.get("skip_reason") or result.get("error_code") or "platform_writeback_failed")[:80]
        if result.get("real_api_called"):
            refreshed_batch = db.get(WarehouseShippingBatch, batch.id)
            if refreshed_batch is not None:
                _write_workflow_audit(
                    db,
                    batch=refreshed_batch,
                    actor_context=actor_context,
                    action="platform_writeback_attempt_recorded",
                    row_count=candidate_count,
                    reason_code=f"platform_writeback_{attempt_status}",
                    real_api_called=True,
                    platform_request_count=int(result.get("http_request_count") or 1),
                )
        grant = _t18_record_attempt(
            db, grant_id=grant.id, attempt_status=attempt_status, error_code=error_code, result=result,
        )
        return {
            "status": attempt_status,
            "skip_reason": error_code,
            "writeback": result,
            "real_api_called": bool(result.get("real_api_called")),
            "writeback_capability": _t18_capability(
                settings=settings,
                status="reconciliation_required" if attempt_status == "unknown" else "failed",
                candidate_count=candidate_count,
                operator_message=(
                    "Naver did not return a verifiable writeback result; reconcile before any further action."
                    if attempt_status == "unknown" else "Naver rejected the pilot writeback without a retryable result."
                ),
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at if grant else None,
                reconciliation_required=attempt_status == "unknown",
                allowed_action="reconcile" if attempt_status == "unknown" else None,
                attempt_status=attempt_status,
            ),
        }

    try:
        _mark_t18_batch_completed(batch, candidates)
        grant.attempt_status = "success"
        grant.attempt_finished_at = get_utc_now()
        grant.attempt_error_code = None
        grant.attempt_response_hash = _t18_attempt_response_hash(result)
        _write_workflow_audit(
            db,
            batch=batch,
            actor_context=actor_context,
            action="platform_writeback_recorded",
            row_count=candidate_count,
            reason_code="platform_writeback_success",
            real_api_called=True,
            platform_request_count=int(result.get("http_request_count") or 1),
        )
        db.commit()
    except Exception:
        db.rollback()
        try:
            grant = _t18_record_attempt(
                db,
                grant_id=grant.id,
                attempt_status="unknown",
                error_code="local_commit_after_platform_success_failed",
                result=result,
            )
        except Exception:
            # The durable pending claim still prohibits a resend when the
            # recovery record itself cannot be written.
            grant = None
        return {
            "status": "unknown",
            "skip_reason": "local_commit_after_platform_success_failed",
            "real_api_called": True,
            "writeback_capability": _t18_capability(
                settings=settings,
                status="reconciliation_required",
                candidate_count=candidate_count,
                operator_message="The platform may have accepted the writeback; reconciliation is required.",
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at if grant else None,
                reconciliation_required=True,
                allowed_action="reconcile",
                attempt_status="unknown",
            ),
        }
    db.refresh(batch)
    return {
        "status": "success",
        "writeback": result,
        "batch": _serialize_batch(batch),
        "real_api_called": True,
        "writeback_capability": _t18_capability(
            settings=settings,
            status="completed",
            candidate_count=candidate_count,
            operator_message="The single pilot writeback was confirmed by Naver and recorded locally.",
            platform_checked_at=preflight["platform_checked_at"],
            approval_expires_at=grant.expires_at,
            attempt_status="success",
        ),
    }


def _t18_reconcile_writeback(
    db: Session,
    *,
    batch_id: int,
    actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = get_settings()
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found", "real_api_called": False}
    candidates, candidate_error = _t18_candidates(db, batch)
    candidate_count = len(candidates or [])
    if not _role_allowed(actor_context):
        return {
            "status": "blocked", "skip_reason": "operator_role_required", "real_api_called": False,
            "token_request_count": 0, "http_request_count": 0,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="An authorized operator is required for read-only reconciliation.",
            ),
        }
    store_matches, store_error = _t18_trial_store_matches(db, batch)
    if not store_matches or candidate_error or candidates is None:
        return {
            "status": "blocked", "skip_reason": store_error or candidate_error or "no_confirmed_tracking_rows", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="The batch cannot be reconciled through the constrained pilot workflow.",
            ),
        }
    grant = db.scalar(select(WarehouseShippingApprovalGrant).where(
        WarehouseShippingApprovalGrant.batch_id == batch.id,
        WarehouseShippingApprovalGrant.attempt_scope == _t18_attempt_scope(batch.store_id),
        WarehouseShippingApprovalGrant.attempt_status.in_(T18_RECONCILABLE_ATTEMPT_STATUSES),
    ).order_by(WarehouseShippingApprovalGrant.id.desc()))
    if grant is None:
        return {
            "status": "blocked", "skip_reason": "shipping_reconciliation_not_required", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="blocked", candidate_count=candidate_count,
                operator_message="No ambiguous pilot writeback attempt is available for reconciliation.",
            ),
        }
    preflight, preflight_error = _t18_platform_preflight(db, batch=batch, candidates=candidates)
    if preflight_error or preflight is None:
        return {
            "status": "unknown", "skip_reason": preflight_error or "naver_platform_preflight_failed", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="reconciliation_required", candidate_count=candidate_count,
                operator_message="The latest Naver state could not be read for reconciliation.",
                approval_expires_at=grant.expires_at,
                reconciliation_required=True,
                allowed_action="reconcile",
            ),
        }
    state = (preflight.get("states") or [{}])[0]
    candidate = candidates[0]
    expected_product_order_id = str(candidate.get("product_order_reference") or "").strip()
    expected_carrier_code = shipping_service._normalize_naver_delivery_company_code(candidate.get("carrier"))
    expected_tracking_hash = str(candidate.get("tracking_number_hash") or "")
    exact_logistics_match = (
        state.get("product_order_id") == expected_product_order_id
        and state.get("carrier_code") == expected_carrier_code
        and state.get("tracking_number_hash") == expected_tracking_hash
    )
    reconciled = (
        state.get("order_status") in T18_RECONCILED_PLATFORM_STATUSES
        and state.get("claim_status") in T18_NO_CLAIM_STATUSES
        and exact_logistics_match
    )
    if not reconciled:
        if state.get("writeback_state") == "NOT_APPLIED":
            try:
                grant.attempt_status = "reconciled_not_applied"
                grant.attempt_finished_at = get_utc_now()
                grant.attempt_error_code = "naver_reconciliation_not_applied"
                grant.attempt_response_hash = _t18_attempt_response_hash({
                    "status": "reconciled_not_applied",
                    "skip_reason": "naver_reconciliation_not_applied",
                })
                _write_workflow_audit(
                    db,
                    batch=batch,
                    actor_context=actor_context,
                    action="platform_writeback_reconciled_not_applied",
                    row_count=candidate_count,
                    reason_code="platform_writeback_not_applied",
                    real_api_called=False,
                    platform_request_count=0,
                )
                db.commit()
            except Exception:
                db.rollback()
                return {
                    "status": "unknown", "skip_reason": "local_reconciliation_commit_failed", "real_api_called": False,
                    "writeback_capability": _t18_capability(
                        settings=settings, status="reconciliation_required", candidate_count=candidate_count,
                        operator_message="The platform state could not be safely recorded for reconciliation.",
                        platform_checked_at=preflight["platform_checked_at"],
                        approval_expires_at=grant.expires_at,
                        reconciliation_required=True,
                        allowed_action="reconcile",
                        attempt_status="unknown",
                    ),
                }
            return {
                "status": "reconciled_not_applied",
                "real_api_called": False,
                "writeback_capability": _t18_capability(
                    settings=settings, status="completed", candidate_count=candidate_count,
                    operator_message="Naver confirmed that the request was not applied. A new owner approval is required before any future attempt.",
                    platform_checked_at=preflight["platform_checked_at"],
                    approval_expires_at=grant.expires_at,
                    attempt_status="reconciled_not_applied",
                ),
            }
        return {
            "status": "unknown", "skip_reason": "naver_reconciliation_exact_logistics_not_confirmed", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="reconciliation_required", candidate_count=candidate_count,
                operator_message="Naver has not confirmed the exact product order, carrier, and tracking record; do not resend.",
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at,
                reconciliation_required=True,
                allowed_action="reconcile",
                attempt_status=grant.attempt_status,
            ),
        }
    try:
        _apply_t18_reconciled_local_state(db, batch=batch, candidates=candidates)
        grant.attempt_status = "reconciled_success"
        grant.attempt_finished_at = get_utc_now()
        grant.attempt_error_code = None
        grant.attempt_response_hash = _t18_attempt_response_hash({"status": "reconciled_success"})
        _write_workflow_audit(
            db,
            batch=batch,
            actor_context=actor_context,
            action="platform_writeback_reconciled",
            row_count=candidate_count,
            reason_code="platform_writeback_reconciled",
            real_api_called=False,
            platform_request_count=0,
        )
        db.commit()
    except Exception:
        db.rollback()
        return {
            "status": "unknown", "skip_reason": "local_reconciliation_commit_failed", "real_api_called": False,
            "writeback_capability": _t18_capability(
                settings=settings, status="reconciliation_required", candidate_count=candidate_count,
                operator_message="Naver appears dispatched, but the local reconciliation could not be recorded.",
                platform_checked_at=preflight["platform_checked_at"],
                approval_expires_at=grant.expires_at,
                reconciliation_required=True,
                allowed_action="reconcile",
            ),
        }
    db.refresh(batch)
    return {
        "status": "reconciled_success",
        "batch": _serialize_batch(batch),
        "real_api_called": False,
        "writeback_capability": _t18_capability(
            settings=settings, status="completed", candidate_count=candidate_count,
            operator_message="The ambiguous pilot attempt was confirmed from Naver's latest read-only state.",
            platform_checked_at=preflight["platform_checked_at"],
            approval_expires_at=grant.expires_at,
            attempt_status="reconciled_success",
        ),
    }


def execute_warehouse_batch_writeback(
    db: Session, *, batch_id: int, manual_approval: bool, final_operator_confirmation: bool,
    real_api_call_requested: bool, actor_context: dict[str, Any] | None,
    approved_candidate_hash: str | None = None,
    action: str = "execute",
    approval_token: str | None = None,
    user_id: int | None = None,
    t18_pilot_execution: bool = False,
) -> dict[str, Any]:
    if t18_pilot_execution:
        if action == "reconcile":
            return _t18_reconcile_writeback(db, batch_id=batch_id, actor_context=actor_context)
        return _t18_execute_writeback(
            db,
            batch_id=batch_id,
            user_id=user_id,
            approval_token=approval_token,
            manual_approval=manual_approval,
            final_operator_confirmation=final_operator_confirmation,
            real_api_call_requested=real_api_call_requested,
            actor_context=actor_context,
        )
    if not manual_approval or not final_operator_confirmation or not real_api_call_requested:
        return {"status": "blocked", "skip_reason": "final_operator_confirmation_and_real_api_request_required", "real_api_called": False}
    if not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_role_required", "real_api_called": False}
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None or batch.status not in {"ready_to_writeback", "writeback_partial"}:
        return {"status": "blocked", "skip_reason": "batch_not_ready_for_writeback", "real_api_called": False}
    if batch.platform != "naver" or not batch.tracking_import_batch_id:
        return {"status": "blocked", "skip_reason": "naver_tracking_import_required", "real_api_called": False}
    execution_candidates, candidate_error = _writeback_execution_candidates(db, batch)
    if candidate_error or execution_candidates is None:
        return {"status": "blocked", "skip_reason": candidate_error or "no_confirmed_tracking_rows", "real_api_called": False}
    current_candidate_hash = _candidate_hash(db, batch, "writeback")
    if not approved_candidate_hash or approved_candidate_hash != current_candidate_hash:
        return {"status": "blocked", "skip_reason": "shipping_approval_candidate_changed", "real_api_called": False}
    tracking_rows = [
        {
            "order_reference": item["order_reference"],
            "product_order_reference": item["product_order_reference"],
            "carrier": item["carrier"],
            "tracking_number": item["tracking_number"],
            "shipped_at": item["shipped_at"],
        }
        for item in execution_candidates
    ]
    if not tracking_rows:
        return {"status": "blocked", "skip_reason": "no_confirmed_tracking_rows", "real_api_called": False}
    result = shipping_service.execute_naver_shipment_writeback(
        db, store_id=batch.store_id, platform=batch.platform, import_batch_id=None,
        tracking_rows=tracking_rows, manual_approval=True, matching_contract_acknowledged=True,
        backup_evidence_acknowledged=True, audit_evidence_acknowledged=True, local_status_evidence_acknowledged=True,
        naver_writeback_boundary_acknowledged=True, operator_checklist_acknowledged=True,
        execution_approval=True, dry_run_evidence_acknowledged=True, permission_evidence_acknowledged=True,
        final_operator_confirmation=True, real_api_call_requested=True, actor_context=actor_context,
    )
    # The retired non-T18 path must not turn a rejected lower-level write into
    # a local failure transition or any other durable business-side effect.
    if result.get("status") == "blocked":
        return result
    if result.get("status") == "success":
        for row in batch.rows:
            if row.row_status == "ready_for_writeback":
                row.row_status = "platform_written"
                row.is_active = False
                row.active_lock = None
                row.failure_reason = None
        batch.status = "completed"
        batch.completed_at = get_utc_now()
    elif result.get("status") == "partial_success":
        batch.status = "writeback_partial"
        failed_hashes = {
            str(item.get("product_order_id_hash") or "")
            for item in (result.get("failed_items") or [])
            if isinstance(item, dict)
        }
        for row in batch.rows:
            if row.row_status == "ready_for_writeback":
                product_hash = shipping_service._safe_hash_identifier(row.product_order_reference or "")
                if product_hash and product_hash not in failed_hashes:
                    row.row_status = "platform_written"
                    row.is_active = False
                    row.active_lock = None
                    row.failure_reason = None
                else:
                    row.row_status = "platform_failed"
                    row.failure_reason = "platform_writeback_partial_or_failed"
    else:
        batch.status = "writeback_partial"
        for row in batch.rows:
            if row.row_status == "ready_for_writeback":
                row.failure_reason = result.get("skip_reason") or "platform_writeback_failed"
    db.commit()
    _write_workflow_audit(db, batch=batch, actor_context=actor_context, action="platform_writeback_recorded", row_count=len(execution_candidates), reason_code=str(result.get("status") or "failed"))
    db.refresh(batch)
    return {"status": result.get("status"), "writeback": result, "batch": _serialize_batch(batch), "real_api_called": bool(result.get("real_api_called"))}


def remove_warehouse_batch_row(
    db: Session,
    *,
    batch_id: int,
    row_id: int,
    reason_code: str,
    warehouse_stopped_shipping: bool,
    actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    row = db.scalar(select(WarehouseShippingBatchOrder).where(WarehouseShippingBatchOrder.id == row_id, WarehouseShippingBatchOrder.batch_id == batch_id))
    if batch is None or row is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_row_not_found"}
    if reason_code not in WAREHOUSE_BATCH_REMOVE_REASON_CODES:
        return {"status": "blocked", "skip_reason": "warehouse_batch_remove_reason_invalid"}
    if batch.status in {"completed", "cancelled"} or row.row_status == "platform_written":
        return {"status": "blocked", "skip_reason": "completed_batch_row_cannot_be_removed"}
    if batch.status in WAREHOUSE_STOP_CONFIRMATION_STATUSES and not warehouse_stopped_shipping:
        return {"status": "blocked", "skip_reason": "warehouse_stop_confirmation_required"}
    if not row.is_active:
        return {"status": "blocked", "skip_reason": "shipping_batch_row_not_active"}
    if not row.pre_batch_order_status:
        return {"status": "blocked", "skip_reason": "pre_batch_order_status_missing_manual_resolution_required"}

    tracking_import_batch_id = batch.tracking_import_batch_id
    if tracking_import_batch_id:
        import_batch = db.get(ShippingTrackingImportBatch, tracking_import_batch_id)
        if import_batch is not None:
            matched_import_row, match_error = _match_tracking_import_row(list(import_batch.rows), row)
            if match_error or matched_import_row is None:
                return {
                    "status": "blocked",
                    "skip_reason": "shipping_tracking_cleanup_ambiguous_manual_resolution_required",
                    "match_error": match_error,
                }
            db.delete(matched_import_row)
            db.flush()
            remaining_import_rows = db.scalars(select(ShippingTrackingImportRow).where(
                ShippingTrackingImportRow.import_batch_id == import_batch.id,
            )).all()
            if not remaining_import_rows:
                db.expire(import_batch, ["rows"])
                db.delete(import_batch)
                batch.tracking_import_batch_id = None
            else:
                import_batch.row_count = len(remaining_import_rows)
                import_batch.ready_row_count = sum(item.row_status == "ready_for_confirmation" for item in remaining_import_rows)
                import_batch.duplicate_row_count = sum(item.row_status == "needs_confirmation" for item in remaining_import_rows)
                import_batch.blocked_row_count = sum(item.row_status == "blocked" for item in remaining_import_rows)
    for status_event in db.scalars(select(OrderStatusEvent).where(
        OrderStatusEvent.order_id == row.local_order_id,
        OrderStatusEvent.platform == batch.platform,
        OrderStatusEvent.source_type == shipping_service.SHIPPING_ORDER_STATUS_LOCAL_UPDATE_SOURCE_TYPE,
    )).all():
        db.delete(status_event)
    safe_metadata = dict(row.order.raw_data or {})
    for key in (
        "shipping_status_update_source",
        "shipping_status_update_phase",
        "shipping_status_update_correlation_id",
        "shipping_status_previous_status",
        "shipping_status_current_status",
        "shipping_tracking_hash",
        "shipping_carrier_label",
        "shipping_tracking_import_batch_id",
    ):
        safe_metadata.pop(key, None)
    row.order.raw_data = safe_metadata or None
    row.order.order_status = row.pre_batch_order_status
    row.row_status = "removed"
    row.carrier = None
    row.tracking_number_hash = None
    row.shipped_at = None
    row.failure_reason = reason_code
    row.is_active = False
    row.active_lock = None
    batch.version += 1
    db.commit()
    _write_workflow_audit(db, batch=batch, actor_context=actor_context, action="shipping_batch_row_removed", row_count=1, reason_code=reason_code)
    db.refresh(batch)
    return {"status": "removed", "batch": _serialize_batch(batch), "real_api_called": False}
