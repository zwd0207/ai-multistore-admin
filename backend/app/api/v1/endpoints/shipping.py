from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.shipping import (
    ShippingExcelExportRequest,
    ShippingMappingWriteGateRequest,
    ShippingMappingWriteRequest,
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
