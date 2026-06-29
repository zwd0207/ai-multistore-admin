from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.device_environment import DeviceEnvironmentCreate, DeviceEnvironmentUpdate
from app.services import device_environment_service


router = APIRouter(prefix="/device-environments", tags=["device-environments"])


@router.get("")
def list_device_environments(
    store_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=device_environment_service.list_device_environments(db, store_id, page, page_size))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device_environment(payload: DeviceEnvironmentCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=device_environment_service.create_device_environment(db, payload), message="created")


@router.get("/{environment_id}")
def get_device_environment(environment_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=device_environment_service.get_device_environment(db, environment_id))


@router.put("/{environment_id}")
def update_device_environment(
    environment_id: int,
    payload: DeviceEnvironmentUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=device_environment_service.update_device_environment(db, environment_id, payload), message="updated")


@router.delete("/{environment_id}")
def delete_device_environment(environment_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=device_environment_service.delete_device_environment(db, environment_id), message="deleted")
