from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.sync import (
    CoupangOrderPreviewRequest,
    CoupangOrderSyncRequest,
    CoupangProductSyncRequest,
    CoupangSalesPreviewRequest,
    CoupangSettlementPreviewRequest,
    NaverOrderPreviewRequest,
    NaverProductPreviewRequest,
)
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


@router.post("/products/naver/preview")
def preview_naver_products(
    payload: NaverProductPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_naver_products(
        db,
        store_id=payload.store_id,
        credential_id=payload.credential_id,
        page=payload.page,
        size=payload.size,
        status=payload.status,
        keyword=payload.keyword,
        seller_product_id=payload.seller_product_id,
        real_preview=payload.real_preview,
        real_sync=payload.real_sync,
    )
    return success_response(data=result, message="naver product preview scaffold completed")


@router.post("/sales/coupang/preview")
def preview_coupang_sales(
    payload: CoupangSalesPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_coupang_sales(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly sales preview completed")


@router.post("/sales/coupang")
def sync_coupang_sales(
    payload: CoupangSalesPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_coupang_sales(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_pages=payload.max_pages,
    )
    return success_response(data=result, message="coupang readonly sales sync completed")


@router.post("/settlements/coupang/preview")
def preview_coupang_settlements(
    payload: CoupangSettlementPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_coupang_settlements(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return success_response(data=result, message="coupang readonly settlement preview completed")


@router.post("/settlements/coupang")
def sync_coupang_settlements(
    payload: CoupangSettlementPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.sync_coupang_settlements(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return success_response(data=result, message="coupang readonly settlement sync completed")


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


@router.post("/orders/naver/preview")
def preview_naver_orders(
    payload: NaverOrderPreviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.preview_naver_orders(
        db,
        store_id=payload.store_id,
        credential_id=payload.credential_id,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        order_status=payload.order_status,
        page=payload.page,
        size=payload.size,
        real_preview=payload.real_preview,
        include_detail=payload.include_detail,
    )
    return success_response(data=result, message="naver readonly order micro preview completed")


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
