from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.appeal_case import AppealCaseCreate, AppealCaseUpdate
from app.services import appeal_case_service


router = APIRouter(prefix="/appeal-cases", tags=["appeal-cases"])


@router.get("")
def list_appeal_cases(
    store_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=appeal_case_service.list_appeal_cases(db, store_id, page, page_size))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_appeal_case(payload: AppealCaseCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=appeal_case_service.create_appeal_case(db, payload), message="created")


@router.get("/{case_id}")
def get_appeal_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=appeal_case_service.get_appeal_case(db, case_id))


@router.put("/{case_id}")
def update_appeal_case(
    case_id: int,
    payload: AppealCaseUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=appeal_case_service.update_appeal_case(db, case_id, payload), message="updated")


@router.delete("/{case_id}")
def delete_appeal_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=appeal_case_service.delete_appeal_case(db, case_id), message="deleted")
