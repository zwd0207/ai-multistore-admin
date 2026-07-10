from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.services import credential_service


router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_credential(payload: CredentialCreate, db: Session = Depends(get_db)) -> dict:
    credential = credential_service.create_credential(db, payload)
    return success_response(data=credential, message="created")


@router.get("")
def list_credentials(
    store_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    credentials = credential_service.list_credentials(db, store_id=store_id)
    return success_response(data={"items": credentials, "total": len(credentials)})


@router.get("/{credential_id}")
def get_credential(credential_id: int, db: Session = Depends(get_db)) -> dict:
    credential = credential_service.get_credential(db, credential_id)
    return success_response(data=credential)


@router.put("/{credential_id}")
def update_credential(
    credential_id: int,
    payload: CredentialUpdate,
    db: Session = Depends(get_db),
) -> dict:
    credential = credential_service.update_credential(db, credential_id, payload)
    return success_response(data=credential, message="updated")


@router.delete("/{credential_id}")
def delete_credential(credential_id: int, db: Session = Depends(get_db)) -> dict:
    credential = credential_service.delete_credential(db, credential_id)
    return success_response(data=credential, message="deleted")
