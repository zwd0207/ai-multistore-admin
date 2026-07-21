from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.platform_login import PlatformLoginCreate, PlatformLoginUpdate
from app.services import platform_login_service


router = APIRouter(prefix="/platform-logins", tags=["platform-logins"])


@router.get("")
def list_platform_logins(
    store_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=platform_login_service.list_platform_logins(db, store_id, page, page_size))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_platform_login(payload: PlatformLoginCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=platform_login_service.create_platform_login(db, payload), message="created")


@router.get("/{login_id}")
def get_platform_login(login_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=platform_login_service.get_platform_login(db, login_id))


@router.put("/{login_id}")
def update_platform_login(
    login_id: int,
    payload: PlatformLoginUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=platform_login_service.update_platform_login(db, login_id, payload), message="updated")
