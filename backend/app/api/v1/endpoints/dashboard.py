from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import stats_service


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    store_id: int | None = Query(default=None),
    platform: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    result = stats_service.get_dashboard_summary(
        db,
        store_id=store_id,
        platform=platform,
        start_date=stats_service.parse_date(start_date, "start_date"),
        end_date=stats_service.parse_date(end_date, "end_date"),
        include_test_orders=include_test_orders,
    )
    return success_response(data=result)
