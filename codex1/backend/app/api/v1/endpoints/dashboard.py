from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.models.auth import ErpUser
from app.services import stats_service
from app.services.operator_access_service import OperatorIdentity, require_any_store_permission, require_store_permission
from app.services.session_service import require_session


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    request: Request,
    store_id: int | None = Query(default=None),
    platform: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    if store_id is not None and get_settings().app_env != "development":
        user = db.get(ErpUser, getattr(request.state, "authenticated_user_id", None))
        if user is not None:
            require_store_permission(
                db,
                identity=OperatorIdentity(user_id=user.id, user_key_hash=user.user_key_hash),
                store_id=store_id,
                permission_key="dashboard.read",
            )
    result = stats_service.get_dashboard_summary(
        db,
        store_id=store_id,
        platform=platform,
        start_date=stats_service.parse_date(start_date, "start_date"),
        end_date=stats_service.parse_date(end_date, "end_date"),
        include_test_orders=include_test_orders,
    )
    return success_response(data=result)


@router.get("/store-overview")
def get_store_overview(
    request: Request,
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    principal = require_session(request, db)
    user = db.get(ErpUser, principal.user_id)
    if user is None:
        raise ApiError("login session is required", "session_required", 401)
    identity = OperatorIdentity(user_id=user.id, user_key_hash=user.user_key_hash)
    require_any_store_permission(db, identity=identity, permission_key="dashboard.read")
    result = stats_service.get_store_overview(
        db,
        include_inactive=include_inactive,
        operator_user_id=user.id,
    )
    return success_response(data=result)
