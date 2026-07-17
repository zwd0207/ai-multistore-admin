from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import customer_inquiry_service
from app.services import naver_readonly_inquiry_service
from app.services.operator_access_service import (
    OperatorIdentity, get_operator_identity, require_operator_recent_auth, require_store_permission,
)
from app.services.store_service import normalize_platform


router = APIRouter(prefix="/customer-inquiries", tags=["customer-inquiries"])


@router.get("")
def list_customer_inquiries(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    normalized_platform = normalize_platform(platform) if platform else None
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="orders.read")
    customer_inquiry_service.assert_customer_inquiry_read_cleanup_healthy(
        db,
        store_id=store_id,
        platform=normalized_platform,
    )
    items = customer_inquiry_service.list_customer_inquiries(
        db,
        store_id=store_id,
        platform=normalized_platform,
    )
    return success_response(data={
        "items": items,
        "total": len(items),
        "classification_counts": customer_inquiry_service.summarize_classifications(items),
    })


@router.post("/naver/refresh")
def refresh_naver_customer_inquiries(
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_operator_recent_auth(identity)
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="platform.sync")
    result = naver_readonly_inquiry_service.refresh_naver_readonly_inquiries(
        db, store_id=store_id, actor_id=identity.user_key_hash,
    )
    return success_response(data=result, message="naver readonly inquiry refresh completed")


@router.get("/{readonly_id}")
def get_readonly_customer_inquiry(
    readonly_id: int,
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="customer.inquiries.content.read")
    detail = naver_readonly_inquiry_service.inquiry_detail(db, store_id=store_id, readonly_id=readonly_id)
    return success_response(data=detail)
