from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.important_email import ImportantEmailCreate, ImportantEmailUpdate
from app.services import important_email_service


router = APIRouter(prefix="/important-emails", tags=["important-emails"])


@router.get("")
def list_important_emails(
    store_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=important_email_service.list_important_emails(db, store_id, page, page_size))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_important_email(payload: ImportantEmailCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=important_email_service.create_important_email(db, payload), message="created")


@router.get("/{email_id}")
def get_important_email(email_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=important_email_service.get_important_email(db, email_id))


@router.put("/{email_id}")
def update_important_email(
    email_id: int,
    payload: ImportantEmailUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=important_email_service.update_important_email(db, email_id, payload), message="updated")


@router.delete("/{email_id}")
def delete_important_email(email_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=important_email_service.delete_important_email(db, email_id), message="deleted")
