from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import customer_inquiry_service
from app.services.store_service import normalize_platform


router = APIRouter(prefix="/customer-inquiries", tags=["customer-inquiries"])


@router.get("")
def list_customer_inquiries(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    normalized_platform = normalize_platform(platform) if platform else None
    items = customer_inquiry_service.list_customer_inquiries(
        db,
        store_id=store_id,
        platform=normalized_platform,
    )
    return success_response(data={"items": items, "total": len(items)})
