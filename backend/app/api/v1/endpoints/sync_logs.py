from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import sync_log_service


router = APIRouter(prefix="/sync-logs", tags=["sync-logs"])


@router.get("")
def list_sync_logs(
    store_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    logs = sync_log_service.list_sync_logs(db, store_id=store_id)
    return success_response(data={"items": logs, "total": len(logs)})
