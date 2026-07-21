from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.appeal_case import AppealCase
from app.schemas.appeal_case import AppealCaseCreate, AppealCaseRead, AppealCaseUpdate
from app.services.store_service import ensure_store_exists, normalize_platform


def _serialize(item: AppealCase) -> dict:
    return AppealCaseRead.model_validate(item).model_dump(mode="json")


def _get_model(db: Session, case_id: int) -> AppealCase:
    item = db.get(AppealCase, case_id)
    if item is None:
        raise ApiError("申诉案件不存在", "APPEAL_CASE_NOT_FOUND", 404, {"case_id": case_id})
    return item


def create_appeal_case(db: Session, payload: AppealCaseCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    data = payload.model_dump()
    data["platform"] = normalize_platform(data["platform"])
    item = AppealCase(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_appeal_cases(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = select(AppealCase).where(AppealCase.store_id == store_id).order_by(AppealCase.id.desc())
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(AppealCase).where(AppealCase.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_appeal_case(db: Session, case_id: int) -> dict:
    return _serialize(_get_model(db, case_id))


def update_appeal_case(db: Session, case_id: int, payload: AppealCaseUpdate) -> dict:
    item = _get_model(db, case_id)
    updates = payload.model_dump(exclude_unset=True)
    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
    if "platform" in updates and updates["platform"] is not None:
        updates["platform"] = normalize_platform(updates["platform"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def delete_appeal_case(db: Session, case_id: int) -> dict:
    item = _get_model(db, case_id)
    serialized = _serialize(item)
    db.delete(item)
    db.commit()
    return serialized
