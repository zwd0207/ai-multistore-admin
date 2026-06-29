from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.device_environment import DeviceEnvironment
from app.models.email_account import EmailAccount
from app.models.platform_login_credential import PlatformLoginCredential
from app.schemas.platform_login import PlatformLoginCreate, PlatformLoginUpdate
from app.services.encryption import encrypt_value
from app.services.store_service import ensure_store_exists, normalize_platform


def _serialize(item: PlatformLoginCredential) -> dict:
    return {
        "id": item.id,
        "store_id": item.store_id,
        "platform": item.platform,
        "login_label": item.login_label,
        "login_account": item.login_account,
        "email_account_id": item.email_account_id,
        "device_environment_id": item.device_environment_id,
        "login_status": item.login_status,
        "last_login_check_at": item.last_login_check_at.isoformat() if item.last_login_check_at else None,
        "remark": item.remark,
        "hasLoginPassword": bool(item.encrypted_login_password),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _get_model(db: Session, login_id: int) -> PlatformLoginCredential:
    item = db.get(PlatformLoginCredential, login_id)
    if item is None:
        raise ApiError(
            message="平台登录信息不存在",
            error_code="PLATFORM_LOGIN_NOT_FOUND",
            status_code=404,
            detail={"login_id": login_id},
        )
    return item


def _ensure_email_belongs_to_store(db: Session, email_account_id: int | None, store_id: int) -> None:
    if email_account_id is None:
        return
    item = db.get(EmailAccount, email_account_id)
    if item is None:
        raise ApiError(
            message="验证码邮箱不存在",
            error_code="EMAIL_ACCOUNT_NOT_FOUND",
            status_code=404,
            detail={"email_account_id": email_account_id},
        )
    if item.store_id != store_id:
        raise ApiError(
            message="验证码邮箱不属于当前店铺",
            error_code="EMAIL_ACCOUNT_STORE_MISMATCH",
            status_code=400,
            detail={"email_account_id": email_account_id, "store_id": store_id},
        )


def _ensure_device_belongs_to_store(db: Session, device_environment_id: int | None, store_id: int) -> None:
    if device_environment_id is None:
        return
    item = db.get(DeviceEnvironment, device_environment_id)
    if item is None:
        raise ApiError(
            message="设备环境不存在",
            error_code="DEVICE_ENVIRONMENT_NOT_FOUND",
            status_code=404,
            detail={"device_environment_id": device_environment_id},
        )
    if item.store_id != store_id:
        raise ApiError(
            message="设备环境不属于当前店铺",
            error_code="DEVICE_ENVIRONMENT_STORE_MISMATCH",
            status_code=400,
            detail={"device_environment_id": device_environment_id, "store_id": store_id},
        )


def _validate_bindings(
    db: Session,
    store_id: int,
    email_account_id: int | None,
    device_environment_id: int | None,
) -> None:
    ensure_store_exists(db, store_id)
    _ensure_email_belongs_to_store(db, email_account_id, store_id)
    _ensure_device_belongs_to_store(db, device_environment_id, store_id)


def create_platform_login(db: Session, payload: PlatformLoginCreate) -> dict:
    platform = normalize_platform(payload.platform)
    _validate_bindings(db, payload.store_id, payload.email_account_id, payload.device_environment_id)
    item = PlatformLoginCredential(
        store_id=payload.store_id,
        platform=platform,
        login_label=payload.login_label,
        login_account=payload.login_account or None,
        encrypted_login_password=encrypt_value(payload.login_password),
        email_account_id=payload.email_account_id,
        device_environment_id=payload.device_environment_id,
        login_status=payload.login_status,
        last_login_check_at=payload.last_login_check_at,
        remark=payload.remark,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_platform_logins(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = (
        select(PlatformLoginCredential)
        .where(PlatformLoginCredential.store_id == store_id)
        .order_by(PlatformLoginCredential.id.asc())
    )
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(PlatformLoginCredential).where(PlatformLoginCredential.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_platform_login(db: Session, login_id: int) -> dict:
    return _serialize(_get_model(db, login_id))


def update_platform_login(db: Session, login_id: int, payload: PlatformLoginUpdate) -> dict:
    item = _get_model(db, login_id)
    updates = payload.model_dump(exclude_unset=True)
    target_store_id = updates.get("store_id", item.store_id) or item.store_id
    target_email_id = updates.get("email_account_id", item.email_account_id)
    target_device_id = updates.get("device_environment_id", item.device_environment_id)
    _validate_bindings(db, target_store_id, target_email_id, target_device_id)

    if "store_id" in updates and updates["store_id"] is not None:
        item.store_id = updates["store_id"]
    if "platform" in updates and updates["platform"] is not None:
        item.platform = normalize_platform(updates["platform"])
    if "login_label" in updates and updates["login_label"] is not None:
        item.login_label = updates["login_label"]
    if "login_account" in updates:
        item.login_account = updates["login_account"] or None
    if "login_password" in updates:
        password = updates["login_password"]
        if password:
            item.encrypted_login_password = encrypt_value(password)
    if "email_account_id" in updates:
        item.email_account_id = updates["email_account_id"]
    if "device_environment_id" in updates:
        item.device_environment_id = updates["device_environment_id"]
    if "login_status" in updates and updates["login_status"] is not None:
        item.login_status = updates["login_status"]
    if "last_login_check_at" in updates:
        item.last_login_check_at = updates["last_login_check_at"]
    if "remark" in updates:
        item.remark = updates["remark"]

    db.commit()
    db.refresh(item)
    return _serialize(item)
