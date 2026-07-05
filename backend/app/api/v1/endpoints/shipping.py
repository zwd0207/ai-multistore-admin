from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.shipping import (
    ShippingExcelExportRequest,
    ShippingMappingWriteGateRequest,
    ShippingMappingWriteRequest,
    ShippingShipmentWritebackBoundaryRequest,
    ShippingTrackingImportMockParseRequest,
    ShippingTrackingImportWriteGateRequest,
    ShippingTrackingImportWriteRequest,
    ShippingTrackingImportXlsxParseRequest,
    ShippingTrackingOrderMatchReadonlyRequest,
)
from app.services import shipping_service


router = APIRouter(prefix="/shipping", tags=["shipping"])


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
