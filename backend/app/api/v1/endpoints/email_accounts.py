from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.email_account import EmailAccountCreate, EmailAccountUpdate
from app.services import email_account_service


router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


@router.get("")
def list_email_accounts(
    store_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=email_account_service.list_email_accounts(db, store_id, page, page_size))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_email_account(payload: EmailAccountCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=email_account_service.create_email_account(db, payload), message="created")


@router.get("/{email_account_id}")
def get_email_account(email_account_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=email_account_service.get_email_account(db, email_account_id))


@router.put("/{email_account_id}")
def update_email_account(
    email_account_id: int,
    payload: EmailAccountUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=email_account_service.update_email_account(db, email_account_id, payload), message="updated")


@router.delete("/{email_account_id}")
def delete_email_account(email_account_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=email_account_service.delete_email_account(db, email_account_id), message="deleted")
