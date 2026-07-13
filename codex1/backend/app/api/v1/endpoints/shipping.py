from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.models.shipping import WarehouseShippingBatch
from app.schemas.shipping import (
    ShippingExcelExportRequest,
    ShippingMappingWriteGateRequest,
    ShippingMappingWriteRequest,
    ShippingShipmentWritebackBoundaryRequest,
    ShippingShipmentWritebackDryRunGateRequest,
    ShippingShipmentWritebackExecutionMockGateRequest,
    ShippingTrackingImportMockParseRequest,
    ShippingTrackingImportWriteGateRequest,
    ShippingTrackingImportWriteRequest,
    ShippingTrackingImportXlsxParseRequest,
    ShippingTrackingOrderMatchReadonlyRequest,
    ShippingTrackingOrderStatusLocalUpdateGateRequest,
    ShippingTrackingOrderStatusLocalUpdateRequest,
    WarehouseShippingBatchCreateRequest,
    WarehouseShippingConfirmRequest,
    WarehouseShippingManifestRequest,
    WarehouseShippingTrackingImportRequest,
    WarehouseShippingWritebackRequest,
    WarehouseShippingRemoveRowRequest,
    WarehouseShippingApprovalRequest,
)
from app.services import shipping_service
from app.services import warehouse_shipping_service
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_operator_recent_auth, require_store_permission


router = APIRouter(prefix="/shipping", tags=["shipping"])


@router.get("/warehouse-batches")
def list_warehouse_shipping_batches(
    store_id: int = Query(..., ge=1),
    platform: str = Query(default="naver", min_length=1, max_length=50),
    include_rows: bool = Query(default=False),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="shipping.batch.manage")
    return success_response(
        data=warehouse_shipping_service.list_warehouse_batches(
            db, store_id=store_id, platform=platform, include_rows=include_rows,
        ),
        message="warehouse shipping batches listed",
    )


@router.get("/warehouse-batches/{batch_id}/tracking-details")
def get_warehouse_shipping_tracking_details(
    batch_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="shipping.batch.manage")
    return success_response(
        data=warehouse_shipping_service.get_warehouse_batch_tracking_details(db, batch_id=batch_id),
        message="warehouse shipping tracking details listed",
    )


@router.post("/warehouse-batches")
def create_warehouse_shipping_batch(payload: WarehouseShippingBatchCreateRequest, db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity)) -> dict:
    require_store_permission(db, identity=identity, store_id=payload.store_id, permission_key="shipping.batch.manage")
    return success_response(
        data=warehouse_shipping_service.create_warehouse_batch(
            db, store_id=payload.store_id, platform=payload.platform, order_ids=payload.order_ids,
            manual_approval=payload.manual_approval, actor_context={"role": "operator", "actor_id": identity.user_key_hash},
        ),
        message="warehouse shipping batch created",
    )


@router.post("/warehouse-batches/{batch_id}/manifest")
def download_warehouse_shipping_manifest(
    batch_id: int, payload: WarehouseShippingManifestRequest, db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="recipient_pii.export")
    require_operator_recent_auth(identity)
    if not payload.approval_token or not warehouse_shipping_service.consume_approval_grant(db, batch_id=batch_id, user_id=identity.user_id, grant_scope="manifest", token=payload.approval_token):
        return success_response(data={"status": "blocked", "skip_reason": "shipping_approval_token_invalid"})
    return success_response(
        data=warehouse_shipping_service.download_warehouse_manifest(
            db, batch_id=batch_id, manual_approval=payload.manual_approval,
            privacy_access_acknowledged=payload.privacy_access_acknowledged, actor_context={"role": "operator", "actor_id": identity.user_key_hash},
        ),
        message="warehouse shipping manifest prepared",
    )


@router.post("/warehouse-batches/{batch_id}/tracking-import")
def import_warehouse_shipping_tracking(
    batch_id: int, payload: WarehouseShippingTrackingImportRequest, db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="shipping.batch.manage")
    return success_response(
        data=warehouse_shipping_service.import_warehouse_tracking_xlsx(
            db, batch_id=batch_id, source_file_name=payload.source_file_name,
            file_content_base64=payload.file_content_base64, manual_approval=payload.manual_approval,
            actor_context={"role": "operator", "actor_id": identity.user_key_hash},
        ),
        message="warehouse tracking import completed",
    )


@router.post("/warehouse-batches/{batch_id}/confirm")
def confirm_warehouse_shipping_batch(
    batch_id: int, payload: WarehouseShippingConfirmRequest, db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="shipping.batch.manage")
    return success_response(
        data=warehouse_shipping_service.confirm_warehouse_batch(
            db, batch_id=batch_id, confirmed_row_ids=payload.confirmed_row_ids,
            manual_approval=payload.manual_approval, actor_context={"role": "operator", "actor_id": identity.user_key_hash},
        ),
        message="warehouse shipping batch confirmed",
    )


@router.post("/warehouse-batches/{batch_id}/rows/{row_id}/remove")
def remove_warehouse_shipping_batch_row(
    batch_id: int, row_id: int, payload: WarehouseShippingRemoveRowRequest,
    db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="shipping.batch.manage")
    if not payload.manual_approval:
        return success_response(data={"status": "blocked", "skip_reason": "manual_approval_required"})
    return success_response(data=warehouse_shipping_service.remove_warehouse_batch_row(
        db, batch_id=batch_id, row_id=row_id, reason_code=payload.reason_code,
        warehouse_stopped_shipping=payload.warehouse_stopped_shipping,
        actor_context={"role": "operator", "actor_id": identity.user_key_hash},
    ))


@router.post("/warehouse-batches/{batch_id}/writeback")
def execute_warehouse_shipping_writeback(
    batch_id: int, payload: WarehouseShippingWritebackRequest, db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key="shipping.writeback.approve")
    require_operator_recent_auth(identity)
    return success_response(
        data=warehouse_shipping_service.execute_warehouse_batch_writeback(
            db, batch_id=batch_id, manual_approval=payload.manual_approval,
            final_operator_confirmation=payload.final_operator_confirmation,
            real_api_call_requested=payload.real_api_call_requested, actor_context={"role": "operator", "actor_id": identity.user_key_hash},
            action=payload.action,
            approval_token=payload.approval_token,
            user_id=identity.user_id,
            t18_pilot_execution=True,
        ),
        message="warehouse shipping platform writeback completed",
    )


@router.post("/warehouse-batches/{batch_id}/approval/{grant_scope}")
def issue_warehouse_shipping_approval(
    batch_id: int, grant_scope: str, payload: WarehouseShippingApprovalRequest,
    db: Session = Depends(get_db), identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    if grant_scope not in {"manifest", "writeback"} or not payload.confirmation:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_approval_confirmation_required"})
    batch = db.get(__import__("app.models.shipping", fromlist=["WarehouseShippingBatch"]).WarehouseShippingBatch, batch_id)
    if batch is None:
        return success_response(data={"status": "blocked", "skip_reason": "shipping_batch_not_found"})
    permission = "recipient_pii.export" if grant_scope == "manifest" else "shipping.writeback.approve"
    require_store_permission(db, identity=identity, store_id=batch.store_id, permission_key=permission)
    if grant_scope in {"manifest", "writeback"}:
        require_operator_recent_auth(identity)
    return success_response(data=warehouse_shipping_service.issue_approval_grant(
        db,
        batch_id=batch_id,
        user_id=identity.user_id,
        grant_scope=grant_scope,
        t18_pilot_execution=grant_scope == "writeback",
    ))


@router.get("/logistics-mappings")
def list_logistics_inventory_mappings(
    store_id: int = Query(..., ge=1),
    platform: str = Query(default="naver", min_length=1, max_length=50),
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.list_logistics_inventory_mappings(
        db,
        store_id=store_id,
        platform=platform,
    )
    return success_response(data=result, message="shipping logistics mappings listed")


@router.get("/export-history")
def list_shipping_export_history(
    store_id: int = Query(..., ge=1),
    platform: str = Query(default="naver", min_length=1, max_length=50),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_rows: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.list_shipping_export_history(
        db,
        store_id=store_id,
        platform=platform,
        limit=limit,
        offset=offset,
        include_rows=include_rows,
    )
    return success_response(data=result, message="shipping export history listed")


@router.get("/tracking-import-history")
def list_shipping_tracking_import_history(
    store_id: int = Query(..., ge=1),
    platform: str = Query(default="naver", min_length=1, max_length=50),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_rows: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.list_shipping_tracking_import_history(
        db,
        store_id=store_id,
        platform=platform,
        limit=limit,
        offset=offset,
        include_rows=include_rows,
    )
    return success_response(data=result, message="shipping tracking import history listed")


@router.post("/tracking-order-match/readonly-check")
def check_tracking_order_match_readonly(
    payload: ShippingTrackingOrderMatchReadonlyRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_tracking_order_match_readonly(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        import_batch_id=payload.import_batch_id,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        matching_contract_acknowledged=payload.matching_contract_acknowledged,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping tracking order match readonly checked")


@router.post("/tracking-order-status/local-update-gate")
def check_tracking_order_status_local_update_gate(
    payload: ShippingTrackingOrderStatusLocalUpdateGateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_tracking_order_status_local_update_gate(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        import_batch_id=payload.import_batch_id,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        matching_contract_acknowledged=payload.matching_contract_acknowledged,
        backup_evidence_acknowledged=payload.backup_evidence_acknowledged,
        audit_evidence_acknowledged=payload.audit_evidence_acknowledged,
        operator_checklist_acknowledged=payload.operator_checklist_acknowledged,
        target_order_status=payload.target_order_status,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping tracking order status local update gate checked")


@router.post("/tracking-order-status/local-update")
def write_tracking_order_status_local_update(
    payload: ShippingTrackingOrderStatusLocalUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.write_tracking_order_status_local_update(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        import_batch_id=payload.import_batch_id,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        matching_contract_acknowledged=payload.matching_contract_acknowledged,
        backup_evidence_acknowledged=payload.backup_evidence_acknowledged,
        audit_evidence_acknowledged=payload.audit_evidence_acknowledged,
        operator_checklist_acknowledged=payload.operator_checklist_acknowledged,
        target_order_status=payload.target_order_status,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping tracking order status local update completed")


@router.post("/shipment-writeback/approval-boundary")
def check_shipment_writeback_approval_boundary(
    payload: ShippingShipmentWritebackBoundaryRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_shipment_writeback_approval_boundary(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        manual_approval=payload.manual_approval,
        matched_order_count=payload.matched_order_count,
        total_tracking_rows=payload.total_tracking_rows,
        matching_evidence_acknowledged=payload.matching_evidence_acknowledged,
        backup_evidence_acknowledged=payload.backup_evidence_acknowledged,
        audit_evidence_acknowledged=payload.audit_evidence_acknowledged,
        naver_writeback_boundary_acknowledged=payload.naver_writeback_boundary_acknowledged,
        operator_checklist_acknowledged=payload.operator_checklist_acknowledged,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping shipment writeback boundary checked")


@router.post("/shipment-writeback/dry-run-gate")
def check_shipment_writeback_dry_run_gate(
    payload: ShippingShipmentWritebackDryRunGateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_shipment_writeback_dry_run_gate(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        import_batch_id=payload.import_batch_id,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        matching_contract_acknowledged=payload.matching_contract_acknowledged,
        backup_evidence_acknowledged=payload.backup_evidence_acknowledged,
        audit_evidence_acknowledged=payload.audit_evidence_acknowledged,
        local_status_evidence_acknowledged=payload.local_status_evidence_acknowledged,
        naver_writeback_boundary_acknowledged=payload.naver_writeback_boundary_acknowledged,
        operator_checklist_acknowledged=payload.operator_checklist_acknowledged,
        target_delivery_status=payload.target_delivery_status,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping shipment writeback dry run gate checked")


@router.post("/shipment-writeback/execution-mock-gate")
def check_shipment_writeback_execution_mock_gate(
    payload: ShippingShipmentWritebackExecutionMockGateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_shipment_writeback_execution_mock_gate(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        import_batch_id=payload.import_batch_id,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        matching_contract_acknowledged=payload.matching_contract_acknowledged,
        backup_evidence_acknowledged=payload.backup_evidence_acknowledged,
        audit_evidence_acknowledged=payload.audit_evidence_acknowledged,
        local_status_evidence_acknowledged=payload.local_status_evidence_acknowledged,
        naver_writeback_boundary_acknowledged=payload.naver_writeback_boundary_acknowledged,
        operator_checklist_acknowledged=payload.operator_checklist_acknowledged,
        target_delivery_status=payload.target_delivery_status,
        execution_approval=payload.execution_approval,
        dry_run_evidence_acknowledged=payload.dry_run_evidence_acknowledged,
        permission_evidence_acknowledged=payload.permission_evidence_acknowledged,
        final_operator_confirmation=payload.final_operator_confirmation,
        real_api_call_requested=payload.real_api_call_requested,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping shipment writeback execution mock gate checked")


@router.post("/logistics-mappings/write-gate")
def check_logistics_inventory_mapping_write_gate(
    payload: ShippingMappingWriteGateRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.evaluate_mapping_and_stock_write_gate(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        mappings=[item.model_dump() for item in payload.mappings],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping mapping write gate checked")


@router.post("/logistics-mappings")
def write_logistics_inventory_mappings(
    payload: ShippingMappingWriteRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.write_mapping_and_stock_local(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        mappings=[item.model_dump() for item in payload.mappings],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="shipping mapping local write completed")


@router.post("/export-excel")
def generate_shipping_excel_export(
    payload: ShippingExcelExportRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.generate_shipping_excel_local(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        export_rows=[item.model_dump() for item in payload.export_rows],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
        include_receiver_privacy=payload.include_receiver_privacy,
    )
    return success_response(data=result, message="shipping excel export checked")


@router.post("/tracking-import/mock-parse")
def check_tracking_number_import_mock_parse(
    payload: ShippingTrackingImportMockParseRequest,
) -> dict:
    result = shipping_service.evaluate_tracking_number_import_mock_gate(
        store_id=payload.store_id,
        platform=payload.platform,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
        file_type=payload.file_type,
        file_format=payload.file_format,
        parser_contract_acknowledged=payload.parser_contract_acknowledged,
    )
    return success_response(data=result, message="shipping tracking import mock parse checked")


@router.post("/tracking-import/parse-xlsx-mock")
def check_tracking_import_xlsx_parser_mock(
    payload: ShippingTrackingImportXlsxParseRequest,
) -> dict:
    result = shipping_service.evaluate_tracking_import_xlsx_parser_mock(
        store_id=payload.store_id,
        platform=payload.platform,
        file_name=payload.source_file_name,
        file_content_base64=payload.file_content_base64,
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
        file_type=payload.file_type,
        file_format=payload.file_format,
        parser_contract_acknowledged=payload.parser_contract_acknowledged,
    )
    return success_response(data=result, message="shipping tracking import xlsx parser checked")


@router.post("/tracking-import/write-gate")
def check_tracking_import_local_write_gate(
    payload: ShippingTrackingImportWriteGateRequest,
) -> dict:
    result = shipping_service.evaluate_tracking_import_local_write_gate(
        store_id=payload.store_id,
        platform=payload.platform,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
        file_type=payload.file_type,
        file_format=payload.file_format,
        parser_contract_acknowledged=payload.parser_contract_acknowledged,
        source_file_name=payload.source_file_name,
    )
    return success_response(data=result, message="shipping tracking import local write gate checked")


@router.post("/tracking-import")
def write_tracking_import_local(
    payload: ShippingTrackingImportWriteRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = shipping_service.write_tracking_import_local(
        db,
        store_id=payload.store_id,
        platform=payload.platform,
        tracking_rows=[item.model_dump() for item in payload.tracking_rows],
        manual_approval=payload.manual_approval,
        actor_context=payload.actor_context,
        file_type=payload.file_type,
        file_format=payload.file_format,
        parser_contract_acknowledged=payload.parser_contract_acknowledged,
        source_file_name=payload.source_file_name,
    )
    return success_response(data=result, message="shipping tracking import local write completed")
