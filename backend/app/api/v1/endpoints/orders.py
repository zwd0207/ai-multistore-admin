from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import order_service
from app.services.store_service import normalize_platform


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
def list_orders(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    normalized_platform = normalize_platform(platform) if platform else None
    items = order_service.list_orders(
        db,
        store_id=store_id,
        platform=normalized_platform,
        include_test_orders=include_test_orders,
    )
    return success_response(data={
        "items": items,
        "total": len(items),
        "include_test_orders": include_test_orders,
        "test_orders_excluded": 0 if include_test_orders else order_service.count_test_orders(
            db,
            store_id=store_id,
            platform=normalized_platform,
        ),
    })
