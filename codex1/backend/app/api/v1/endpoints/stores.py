from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.models.store import Store
from app.models.auth import ErpRole, ErpStoreMembership
from app.schemas.store import StoreCreate, StoreRead, StoreUpdate


router = APIRouter(prefix="/stores", tags=["stores"])


def serialize_store(store: Store) -> dict:
    return StoreRead.model_validate(store).model_dump(mode="json")


def get_store_or_404(db: Session, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise ApiError(
            message="店铺不存在",
            error_code="STORE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"store_id": store_id},
        )
    return store


@router.post("", status_code=status.HTTP_201_CREATED)
def create_store(payload: StoreCreate, db: Session = Depends(get_db)) -> dict:
    store = Store(**payload.model_dump())
    db.add(store)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            message="店铺名称已存在",
            error_code="STORE_NAME_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            detail={"name": payload.name},
        ) from exc

    db.refresh(store)
    return success_response(data=serialize_store(store), message="created")


@router.get("")
def list_stores(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    offset = (page - 1) * page_size
    query = select(Store)
    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id is not None:
        query = query.join(ErpStoreMembership, ErpStoreMembership.store_id == Store.id).join(
            ErpRole, ErpRole.id == ErpStoreMembership.role_id,
        ).where(
            ErpStoreMembership.user_id == user_id,
            ErpStoreMembership.membership_status == "active",
            ErpRole.status == "active",
            Store.status == "active",
        ).distinct()
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    stores = db.scalars(
        query
        .order_by(Store.id.asc())
        .offset(offset)
        .limit(page_size)
    ).all()

    return success_response(
        data={
            "items": [serialize_store(store) for store in stores],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@router.get("/{store_id}")
def get_store(store_id: int, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    return success_response(data=serialize_store(store))


@router.put("/{store_id}")
def update_store(store_id: int, payload: StoreUpdate, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return success_response(data=serialize_store(store), message="no changes")

    for field, value in updates.items():
        setattr(store, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            message="店铺名称已存在",
            error_code="STORE_NAME_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            detail={"name": updates.get("name")},
        ) from exc

    db.refresh(store)
    return success_response(data=serialize_store(store), message="updated")


@router.delete("/{store_id}")
def delete_store(store_id: int, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    deleted = serialize_store(store)
    db.delete(store)
    db.commit()
    return success_response(data=deleted, message="deleted")
