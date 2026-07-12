from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.config import get_settings
from app.schemas.sync import (
    CoupangOrderPreviewRequest,
    CoupangOrderSyncRequest,
    CoupangProductSyncRequest,
    CoupangSalesPreviewRequest,
    CoupangSettlementPreviewRequest,
    ManualAllStoresSyncRequest,
    ManualBatchSyncRequest,
    NaverCustomerInquiryReplyRequest,
    NaverCustomerInquirySyncRequest,
    NaverOrderManualRefreshRequest,
    NaverOrderPreviewRequest,
    NaverOrderSingleRefreshRequest,
    NaverProductPreviewRequest,
)
from app.services import sync_service
from app.services.operator_trial_service import assert_legacy_naver_customer_inquiry_sync_closed


router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/manual-batch")
def manual_batch_sync(
    payload: ManualBatchSyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.manual_batch_sync(
        db,
        store_id=payload.store_id,
        platforms=payload.platforms,
        include_products=payload.include_products,
        include_orders=payload.include_orders,
        include_customer_inquiries=payload.include_customer_inquiries,
        replace_policy=payload.replace_policy,
    )
    return success_response(data=result, message="manual batch sync completed")


@router.post("/manual-batch/all")
def manual_batch_sync_all_stores(
    payload: ManualAllStoresSyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.manual_batch_sync_all_stores(
        db,
        platforms=payload.platforms,
        include_products=payload.include_products,
        include_orders=payload.include_orders,
        include_customer_inquiries=payload.include_customer_inquiries,
        include_inactive=payload.include_inactive,
        replace_policy=payload.replace_policy,
    )
    return success_response(data=result, message="manual batch sync for all stores completed")


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
        manual_approval=payload.manual_approval,
        backup_path=payload.backup_path,
        backup_sha256=payload.backup_sha256,
        actor_context=payload.actor_context,
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
        complete_field_preview=payload.complete_field_preview,
        real_sync=payload.real_sync,
    )
    return success_response(data=result, message="naver readonly order micro preview completed")


@router.post("/orders/naver/manual-refresh")
def manual_refresh_naver_orders(
    payload: NaverOrderManualRefreshRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.manual_refresh_naver_orders(
        db,
        store_id=payload.store_id,
        max_count=payload.max_count,
        hours=payload.hours,
    )
    return success_response(data=result, message="naver order local manual refresh completed")


@router.post("/orders/naver/refresh-one")
def refresh_single_naver_order_detail(
    payload: NaverOrderSingleRefreshRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.refresh_single_naver_order_detail(
        db,
        store_id=payload.store_id,
        order_id=payload.order_id,
    )
    return success_response(data=result, message="naver single order detail refreshed")


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


@router.post("/customer-inquiries/naver")
def sync_naver_customer_inquiries(
    payload: NaverCustomerInquirySyncRequest,
    db: Session = Depends(get_db),
) -> dict:
    assert_legacy_naver_customer_inquiry_sync_closed(get_settings())
    result = sync_service.sync_naver_customer_inquiries(
        db,
        store_id=payload.store_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        answered=payload.answered,
        page=payload.page,
        size=payload.size,
    )
    return success_response(data=result, message="naver customer inquiries synced")


@router.post("/customer-inquiries/naver/reply")
def reply_naver_customer_inquiry(
    payload: NaverCustomerInquiryReplyRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = sync_service.reply_naver_customer_inquiry(
        db,
        store_id=payload.store_id,
        inquiry_id=payload.inquiry_id,
        external_inquiry_id=payload.external_inquiry_id,
        answer_comment=payload.answer_comment,
        answer_template_id=payload.answer_template_id,
        manual_approval=payload.manual_approval,
        final_operator_confirmation=payload.final_operator_confirmation,
        actor_context=payload.actor_context,
    )
    return success_response(data=result, message="naver customer inquiry reply completed")
