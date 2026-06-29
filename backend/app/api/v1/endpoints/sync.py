from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
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


@router.post("/orders/mock")
def sync_orders_mock(
    store_id: int = Query(...),
    platform: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_orders_mock(db, store_id=store_id, platform=platform)
    return success_response(data=result, message="mock sync completed")


@router.post("/customer-inquiries/mock")
def sync_customer_inquiries_mock(
    store_id: int = Query(...),
    platform: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_customer_inquiries_mock(db, store_id=store_id, platform=platform)
    return success_response(data=result, message="mock sync completed")
