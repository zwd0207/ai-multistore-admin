from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.device_environment import DeviceEnvironment
from app.schemas.device_environment import DeviceEnvironmentCreate, DeviceEnvironmentRead, DeviceEnvironmentUpdate
from app.services.store_service import ensure_store_exists


def _serialize(item: DeviceEnvironment) -> dict:
    return DeviceEnvironmentRead.model_validate(item).model_dump(mode="json")


def _get_model(db: Session, environment_id: int) -> DeviceEnvironment:
    item = db.get(DeviceEnvironment, environment_id)
    if item is None:
        raise ApiError("设备环境不存在", "DEVICE_ENVIRONMENT_NOT_FOUND", 404, {"environment_id": environment_id})
    return item


def create_device_environment(db: Session, payload: DeviceEnvironmentCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    item = DeviceEnvironment(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_device_environments(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = select(DeviceEnvironment).where(DeviceEnvironment.store_id == store_id).order_by(DeviceEnvironment.id.asc())
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(DeviceEnvironment).where(DeviceEnvironment.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_device_environment(db: Session, environment_id: int) -> dict:
    return _serialize(_get_model(db, environment_id))


def update_device_environment(db: Session, environment_id: int, payload: DeviceEnvironmentUpdate) -> dict:
    item = _get_model(db, environment_id)
    updates = payload.model_dump(exclude_unset=True)
    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def delete_device_environment(db: Session, environment_id: int) -> dict:
    item = _get_model(db, environment_id)
    serialized = _serialize(item)
    db.delete(item)
    db.commit()
    return serialized
