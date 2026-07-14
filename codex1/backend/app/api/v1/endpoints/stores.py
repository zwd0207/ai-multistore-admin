from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.models.store import Store
from app.models.auth import ErpRole, ErpStoreMembership
from app.models.device_environment import DeviceEnvironment
from app.schemas.store import StoreCreate, StoreRead, StoreUpdate
from app.schemas.sync import AutomaticReadRecoveryRequest
from app.services import automatic_read_sync_service, platform_login_service, store_service
from app.services.encryption import decrypt_value
from app.services.operator_access_service import (
    OperatorIdentity,
    get_operator_identity,
    require_any_store_permission,
    require_operator_recent_auth,
    require_store_permission,
)


router = APIRouter(prefix="/stores", tags=["stores"])


def _user_has_store_permission(
    db: Session,
    *,
    user_id: int | None,
    store_id: int,
    permission_key: str,
) -> bool:
    if user_id is None:
        return False
    try:
        require_store_permission(
            db,
            identity=OperatorIdentity(user_id=user_id, user_key_hash="store-serializer"),
            store_id=store_id,
            permission_key=permission_key,
        )
    except ApiError:
        return False
    return True


def _user_has_any_store_permission(
    db: Session,
    *,
    user_id: int | None,
    permission_key: str | tuple[str, ...],
) -> bool:
    if user_id is None:
        return False
    permission_keys = (permission_key,) if isinstance(permission_key, str) else permission_key
    identity = OperatorIdentity(user_id=user_id, user_key_hash="store-serializer")
    return any(
        _can_require_any_store_permission(db, identity=identity, permission_key=key)
        for key in permission_keys
    )


def _can_require_any_store_permission(
    db: Session,
    *,
    identity: OperatorIdentity,
    permission_key: str,
) -> bool:
    try:
        require_any_store_permission(db, identity=identity, permission_key=permission_key)
    except ApiError:
        return False
    return True


def _serialize_network(
    db: Session,
    *,
    store: Store,
    user_id: int | None,
) -> dict:
    environment = db.scalar(select(DeviceEnvironment).where(
        DeviceEnvironment.store_id == store.id,
        DeviceEnvironment.source_provider == "ziniao",
    ).order_by(DeviceEnvironment.id.asc()))
    if environment is None:
        return {
            "ip_address": None,
            "country": None,
            "region": None,
            "city": None,
            "status": "not_configured",
            "updated_at": None,
        }
    ip_address = environment.masked_ip_address
    if _user_has_store_permission(
        db,
        user_id=user_id,
        store_id=store.id,
        permission_key="platform.browser.open",
    ) and environment.encrypted_ip_address:
        try:
            ip_address = decrypt_value(environment.encrypted_ip_address)
        except ApiError:
            ip_address = environment.masked_ip_address
    return {
        "ip_address": ip_address,
        "country": environment.network_country,
        "region": environment.network_region,
        "city": environment.network_city,
        "status": environment.network_status,
        "updated_at": environment.updated_at.isoformat() if environment.updated_at else None,
    }


def serialize_store(store: Store, *, db: Session | None = None, user_id: int | None = None) -> dict:
    data = StoreRead.model_validate(store).model_dump(mode="json")
    directory_status = str(store.ziniao_directory_status or "unmanaged")
    has_directory_id = bool(store.ziniao_external_id_encrypted and store.ziniao_external_id_hash)
    configured = bool(
        store.browser_provider == "ziniao"
        and store.browser_profile_name
        and (has_directory_id or str(store.platform or "").lower() == "naver")
    )
    data["browser_open_capability"] = {
        "provider": store.browser_provider,
        "configured": configured,
        "runtime_enabled": bool(get_settings().ziniao_browser_open_enabled),
        "supported": directory_status != "removed" and (
            has_directory_id or str(store.platform or "").lower() == "naver"
        ),
        "directory_status": directory_status,
    }
    data.update({
        "ziniao_directory_status": directory_status,
        "source_platform": store.ziniao_source_platform,
        "source_site": store.ziniao_source_site,
        "last_seen_at": store.ziniao_last_seen_at.isoformat() if store.ziniao_last_seen_at else None,
        "directory_checked_at": (
            store.ziniao_directory_checked_at.isoformat()
            if store.ziniao_directory_checked_at else None
        ),
        "ziniao_auto_managed": bool(store.ziniao_auto_managed),
        "operational_mode": str(store.ziniao_operational_mode or "business"),
        "network": _serialize_network(db, store=store, user_id=user_id) if db is not None else {
            "ip_address": None,
            "country": None,
            "region": None,
            "city": None,
            "status": "not_configured",
            "updated_at": None,
        },
    })
    return data


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
    values = payload.model_dump()
    provider, profile_name = store_service.normalize_browser_binding(
        values.get("browser_provider"), values.get("browser_profile_name"),
    )
    values.update(browser_provider=provider, browser_profile_name=profile_name)
    store = Store(**values)
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
    return success_response(data=serialize_store(store, db=db), message="created")


@router.get("")
def list_stores(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    offset = (page - 1) * page_size
    query = select(Store)
    user_id = getattr(request.state, "authenticated_user_id", None)
    if include_archived and not _user_has_any_store_permission(
        db,
        user_id=user_id,
        permission_key=("store_membership.assign", "store.manage"),
    ):
        raise ApiError(
            "archived stores require administrator permission",
            "store_membership_assign_forbidden",
            status.HTTP_403_FORBIDDEN,
        )
    if not include_archived:
        query = query.where(Store.ziniao_directory_status != "removed")
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
            "items": [serialize_store(store, db=db, user_id=user_id) for store in stores],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@router.get("/{store_id}")
def get_store(store_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    return success_response(data=serialize_store(
        store,
        db=db,
        user_id=getattr(request.state, "authenticated_user_id", None),
    ))


@router.post("/{store_id}/automatic-read/recover")
def recover_store_automatic_read(
    store_id: int,
    payload: AutomaticReadRecoveryRequest,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    del payload
    require_operator_recent_auth(identity)
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="credentials.manage")
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="platform.sync")
    try:
        result = automatic_read_sync_service.recover_automatic_read(db, store_id=store_id, actor_id=identity.user_key_hash)
    except ValueError as exc:
        raise ApiError("automatic read recovery is not available", str(exc), status.HTTP_409_CONFLICT) from exc
    return success_response(data=result, message="automatic read recovery restored")


@router.post("/{store_id}/open-backend")
def open_store_backend(
    store_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="platform.browser.open")
    result = platform_login_service.open_store_backend(
        db,
        store_id=store_id,
        actor_id=identity.user_key_hash,
    )
    return success_response(data=result, message="ziniao store browser opened")


@router.put("/{store_id}")
def update_store(store_id: int, payload: StoreUpdate, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return success_response(data=serialize_store(store, db=db), message="no changes")

    provider, profile_name = store_service.normalize_browser_binding(
        updates.get("browser_provider", store.browser_provider),
        updates.get("browser_profile_name", store.browser_profile_name),
    )
    if "browser_provider" in updates or "browser_profile_name" in updates:
        updates["browser_provider"] = provider
        updates["browser_profile_name"] = profile_name
    if "name" in updates and updates["name"] != store.name and store.ziniao_auto_managed:
        store.ziniao_name_managed = False

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
    return success_response(data=serialize_store(store, db=db), message="updated")


@router.delete("/{store_id}")
def delete_store(store_id: int, db: Session = Depends(get_db)) -> dict:
    store = get_store_or_404(db, store_id)
    if store.ziniao_auto_managed:
        raise ApiError(
            "Ziniao directory stores are archived instead of deleted",
            "ZINIAO_DIRECTORY_STORE_DELETE_FORBIDDEN",
            status.HTTP_409_CONFLICT,
        )
    deleted = serialize_store(store, db=db)
    db.delete(store)
    db.commit()
    return success_response(data=deleted, message="deleted")
