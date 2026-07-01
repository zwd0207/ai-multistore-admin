from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.sync import CoupangOrderPreviewRequest, CoupangOrderSyncRequest, CoupangProductSyncRequest
from app.services import sync_service


router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/products/mock")
def sync_products_mock(
    store_id: int = Query(...),
    platform: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_products_mock(db, store_id=store_id, platform=platform)
    return success_response(data=result, message="mock sync completed")


@router.post("/products/coupang/preview")
def preview_coupang_products(
    payload: CoupangProductSyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_coupang_products(
        db,
        store_id=payload.store_id,
        status=payload.status,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly product preview completed")


@router.post("/products/coupang")
def sync_coupang_products(
    payload: CoupangProductSyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_coupang_products(
        db,
        store_id=payload.store_id,
        status=payload.status,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly product sync completed")


@router.post("/orders/mock")
def sync_orders_mock(
    store_id: int = Query(...),
    platform: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_orders_mock(db, store_id=store_id, platform=platform)
    return success_response(data=result, message="mock sync completed")


@router.post("/orders/coupang/preview")
def preview_coupang_orders(
    payload: CoupangOrderPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_coupang_orders(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly preview completed")


@router.post("/orders/coupang")
def sync_coupang_orders(
    payload: CoupangOrderSyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_coupang_orders(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly order sync completed")


@router.post("/customer-inquiries/mock")
def sync_customer_inquiries_mock(
    store_id: int = Query(...),
    platform: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_customer_inquiries_mock(db, store_id=store_id, platform=platform)
    return success_response(data=result, message="mock sync completed")
