from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.email_account import EmailAccount
from app.models.important_email import ImportantEmail
from app.schemas.important_email import ImportantEmailCreate, ImportantEmailRead, ImportantEmailUpdate
from app.services.store_service import ensure_store_exists, normalize_platform


def _serialize(item: ImportantEmail) -> dict:
    return ImportantEmailRead.model_validate(item).model_dump(mode="json")


def _get_model(db: Session, email_id: int) -> ImportantEmail:
    item = db.get(ImportantEmail, email_id)
    if item is None:
        raise ApiError("重点邮件不存在", "IMPORTANT_EMAIL_NOT_FOUND", 404, {"email_id": email_id})
    return item


def _validate_email_account(db: Session, store_id: int, email_account_id: int | None) -> None:
    if email_account_id is None:
        return
    account = db.get(EmailAccount, email_account_id)
    if account is None or account.store_id != store_id:
        raise ApiError("邮箱账户不存在或不属于该店铺", "EMAIL_ACCOUNT_NOT_FOUND", 404, {"email_account_id": email_account_id})


def create_important_email(db: Session, payload: ImportantEmailCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    _validate_email_account(db, payload.store_id, payload.email_account_id)
    data = payload.model_dump()
    data["platform"] = normalize_platform(data["platform"])
    item = ImportantEmail(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def list_important_emails(db: Session, store_id: int, page: int = 1, page_size: int = 20) -> dict:
    ensure_store_exists(db, store_id)
    statement = select(ImportantEmail).where(ImportantEmail.store_id == store_id).order_by(ImportantEmail.received_at.desc(), ImportantEmail.id.desc())
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total = len(db.scalars(select(ImportantEmail).where(ImportantEmail.store_id == store_id)).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


def get_important_email(db: Session, email_id: int) -> dict:
    return _serialize(_get_model(db, email_id))


def update_important_email(db: Session, email_id: int, payload: ImportantEmailUpdate) -> dict:
    item = _get_model(db, email_id)
    updates = payload.model_dump(exclude_unset=True)
    target_store_id = updates.get("store_id", item.store_id)
    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
    if "email_account_id" in updates:
        _validate_email_account(db, target_store_id, updates["email_account_id"])
    if "platform" in updates and updates["platform"] is not None:
        updates["platform"] = normalize_platform(updates["platform"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize(item)


def delete_important_email(db: Session, email_id: int) -> dict:
    item = _get_model(db, email_id)
    serialized = _serialize(item)
    db.delete(item)
    db.commit()
    return serialized
