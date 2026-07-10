from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
from datetime import timedelta
from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timezone import get_utc_now
from app.models.order import Order
from app.models.shipping import (
    LogisticsInventoryMapping,
    ShippingTrackingImportBatch,
    ShippingTrackingImportRow,
    WarehouseShippingBatch,
    WarehouseShippingBatchOrder,
    WarehouseShippingApprovalGrant,
)
from app.services import shipping_service
from app.services.store_service import ensure_store_exists


ACTIVE_BATCH_STATUSES = {"created", "warehouse_sent", "warehouse_returned", "ready_to_writeback", "writeback_partial"}
TERMINAL_ORDER_STATUSES = shipping_service.SHIPPING_ORDER_STATUS_TERMINAL_STATUSES
UPDATABLE_ORDER_STATUSES = shipping_service.SHIPPING_ORDER_STATUS_UPDATABLE_STATUSES
PRIVACY_ROLES = {"admin", "operator", "shipping_operator"}


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
        "failure_reason": row.failure_reason,
        "operator_note": row.operator_note,
        "is_active": row.is_active,
    }


def issue_approval_grant(db: Session, *, batch_id: int, user_id: int, grant_scope: str) -> dict[str, Any]:
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None:
        return {"status": "blocked", "skip_reason": "shipping_batch_not_found"}
    rows = [row.id for row in batch.rows if row.row_status in {"pending_export", "ready_for_writeback"}]
    candidate_hash = hashlib.sha256(",".join(map(str, sorted(rows))).encode("utf-8")).hexdigest()
    token = secrets.token_urlsafe(32)
    now = get_utc_now()
    db.add(WarehouseShippingApprovalGrant(
        batch_id=batch.id, user_id=user_id, grant_scope=grant_scope,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(), batch_version=batch.version,
        candidate_hash=candidate_hash, expires_at=now + timedelta(minutes=10),
    ))
    db.commit()
    return {"status": "approval_granted", "approval_token": token, "expires_at": now + timedelta(minutes=10), "batch_version": batch.version}


def consume_approval_grant(db: Session, *, batch_id: int, user_id: int, grant_scope: str, token: str) -> bool:
    grant = db.scalar(select(WarehouseShippingApprovalGrant).where(
        WarehouseShippingApprovalGrant.batch_id == batch_id,
        WarehouseShippingApprovalGrant.user_id == user_id,
        WarehouseShippingApprovalGrant.grant_scope == grant_scope,
        WarehouseShippingApprovalGrant.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest(),
        WarehouseShippingApprovalGrant.used_at.is_(None),
    ))
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    expires_at = grant.expires_at.replace(tzinfo=timezone.utc) if grant is not None and grant.expires_at.tzinfo is None else (grant.expires_at if grant is not None else None)
    if grant is None or batch is None or expires_at < get_utc_now() or grant.batch_version != batch.version:
        return False
    grant.used_at = get_utc_now()
    db.commit()
    return True


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
        current_status = str(order.order_status or "").upper()
        if current_status in TERMINAL_ORDER_STATUSES or current_status not in UPDATABLE_ORDER_STATUSES:
            row_status, reason = "blocked", "order_status_not_shippable"
        elif mapping is None:
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
    return {"status": "ready", "items": [_serialize_batch(batch, include_rows=include_rows) for batch in batches], "real_api_called": False}


def _warehouse_xlsx(rows: list[dict[str, Any]]) -> bytes:
    headers = [
        ("batch_no", "发货批次"), ("platform", "平台"), ("order_reference", "订单号"),
        ("product_order_reference", "商品订单号"), ("internal_sku", "内部货号"),
        ("logistics_inventory_code", "仓库货号"), ("product_name", "商品"), ("quantity", "数量"),
        ("receiver_name", "收件人"), ("receiver_phone", "联系电话"), ("zip_code", "邮编"),
        ("receiver_address", "地址"), ("delivery_memo", "配送备注"), ("carrier", "快递公司"),
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
    rows: list[dict[str, Any]] = []
    for item in batch.rows:
        if item.row_status != "pending_export":
            continue
        order = item.order
        rows.append({
            "batch_no": batch.batch_no, "platform": batch.platform, "order_reference": item.order_reference,
            "product_order_reference": item.product_order_reference or "", "internal_sku": item.internal_sku or "",
            "logistics_inventory_code": item.logistics_inventory_code or "", "product_name": item.product_name,
            "quantity": item.quantity, "receiver_name": order.receiver_name or "", "receiver_phone": order.receiver_phone or "",
            "zip_code": order.zip_code or "", "receiver_address": order.receiver_address or "",
            "delivery_memo": _delivery_memo(order), "carrier": "", "tracking_number": "", "warehouse_note": "",
        })
        item.row_status = "warehouse_sent"
    if not rows:
        return {"status": "blocked", "skip_reason": "no_exportable_batch_rows"}
    batch.status = "warehouse_sent"
    batch.warehouse_sent_at = get_utc_now()
    db.commit()
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
    batch_rows_by_ref = {row.order_reference: row for row in batch.rows}
    batch_rows_by_product_ref = {row.product_order_reference: row for row in batch.rows if row.product_order_reference}
    seen_tracking: set[str] = set()
    normal = needs_confirmation = blocked = 0
    for row in normalized:
        item = batch_rows_by_ref.get(row["order_reference"]) or batch_rows_by_product_ref.get(row["product_order_reference"])
        tracking_hash = shipping_service._safe_hash_identifier(row["tracking_number"])
        status, reason = "ready_for_confirmation", None
        if item is None:
            status, reason = "blocked", "order_not_in_shipping_batch"
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
    import_rows = db.scalars(select(ShippingTrackingImportRow).where(
        ShippingTrackingImportRow.import_batch_id == batch.tracking_import_batch_id,
    )).all()
    ready_references = {row.order_reference for row in batch.rows if row.row_status == "ready_for_writeback"}
    local_update = shipping_service.write_tracking_order_status_local_update(
        db,
        store_id=batch.store_id,
        platform=batch.platform,
        tracking_rows=[
            {
                "order_reference": row.order_reference,
                "product_order_reference": row.product_order_reference,
                "carrier": row.carrier,
                "tracking_number": row.tracking_number,
                "shipped_at": row.shipped_at,
            }
            for row in import_rows if row.order_reference in ready_references
        ],
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
    db.refresh(batch)
    return {"status": "ready_to_writeback", "batch": _serialize_batch(batch), "local_update": local_update, "real_api_called": False}


def execute_warehouse_batch_writeback(
    db: Session, *, batch_id: int, manual_approval: bool, final_operator_confirmation: bool,
    real_api_call_requested: bool, actor_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not manual_approval or not final_operator_confirmation or not real_api_call_requested:
        return {"status": "blocked", "skip_reason": "final_operator_confirmation_and_real_api_request_required", "real_api_called": False}
    if not _role_allowed(actor_context):
        return {"status": "blocked", "skip_reason": "operator_role_required", "real_api_called": False}
    batch = db.scalar(select(WarehouseShippingBatch).where(WarehouseShippingBatch.id == batch_id))
    if batch is None or batch.status not in {"ready_to_writeback", "writeback_partial"}:
        return {"status": "blocked", "skip_reason": "batch_not_ready_for_writeback", "real_api_called": False}
    if batch.platform != "naver" or not batch.tracking_import_batch_id:
        return {"status": "blocked", "skip_reason": "naver_tracking_import_required", "real_api_called": False}
    import_rows = db.scalars(select(ShippingTrackingImportRow).where(
        ShippingTrackingImportRow.import_batch_id == batch.tracking_import_batch_id,
    )).all()
    ready_refs = {row.order_reference for row in batch.rows if row.row_status == "ready_for_writeback"}
    tracking_rows = [
        {
            "order_reference": row.order_reference,
            "product_order_reference": row.product_order_reference,
            "carrier": row.carrier,
            "tracking_number": row.tracking_number,
            "shipped_at": row.shipped_at,
        }
        for row in import_rows if row.order_reference in ready_refs
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
    db.refresh(batch)
    return {"status": result.get("status"), "writeback": result, "batch": _serialize_batch(batch), "real_api_called": bool(result.get("real_api_called"))}
