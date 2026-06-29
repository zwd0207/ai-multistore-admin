from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import stats_service


router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/daily-context")
def get_daily_context(
    store_id: int | None = Query(default=None),
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    result = stats_service.get_daily_context(
        db,
        store_id=store_id,
        context_date=stats_service.parse_date(date, "date"),
    )
    return success_response(data=result)
