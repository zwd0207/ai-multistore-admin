from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.email_account import EmailAccount
from app.schemas.email_account import EmailAccountCreate, EmailAccountUpdate
from app.services.encryption import encrypt_value
from app.services.store_service import ensure_store_exists


def _serialize(item: EmailAccount) -> dict:
    return {
        "id": item.id,
        "store_id": item.store_id,
        "email_address": item.email_address,
        "provider": item.provider,
        "account_label": item.account_label,
        "status": item.status,
        "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        "remark": item.remark,
        "has_password_or_token": bool(item.encrypted_password_or_token),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _get_model(db: Session, email_account_id: int) -> EmailAccount:
    item = db.get(EmailAccount, email_account_id)
    if item is None:
        raise ApiError("邮箱账户不存在", "EMAIL_ACCOUNT_NOT_FOUND", 404, {"email_account_id": email_account_id})
    return item


def create_email_account(db: Session, payload: EmailAccountCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    data = payload.model_dump(exclude={"password_or_token"})
    data["encrypted_password_or_token"] = encrypt_value(payload.password_or_token)
    item = EmailAccount(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_email_accounts(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = select(EmailAccount).where(EmailAccount.store_id == store_id).order_by(EmailAccount.id.asc())
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(EmailAccount).where(EmailAccount.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_email_account(db: Session, email_account_id: int) -> dict:
    return _serialize(_get_model(db, email_account_id))


def update_email_account(db: Session, email_account_id: int, payload: EmailAccountUpdate) -> dict:
    item = _get_model(db, email_account_id)
    updates = payload.model_dump(exclude_unset=True)
    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
    if "password_or_token" in updates:
        item.encrypted_password_or_token = encrypt_value(updates.pop("password_or_token"))
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def delete_email_account(db: Session, email_account_id: int) -> dict:
    item = _get_model(db, email_account_id)
    serialized = _serialize(item)
    db.delete(item)
    db.commit()
    return serialized
