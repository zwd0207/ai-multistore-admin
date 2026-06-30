from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.api_capability import ApiCapabilityCheckCreate, ApiCapabilityCheckUpdate, ApiCapabilityTestResultCreate
from app.services import api_capability_service


router = APIRouter(prefix="", tags=["api-capabilities"])


@router.get("/api-capabilities")
def list_capabilities(
    platform: str | None = Query(default=None),
    api_category: str | None = Query(default=None),
    test_status: str | None = Query(default=None),
    test_mode: str | None = Query(default=None),
    first_phase_candidate: bool | None = Query(default=None),
    sales_source_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=api_capability_service.list_capabilities(
        db,
        platform=platform,
        api_category=api_category,
        test_status=test_status,
        test_mode=test_mode,
        first_phase_candidate=first_phase_candidate,
        sales_source_type=sales_source_type,
    ))


@router.post("/api-capabilities", status_code=status.HTTP_201_CREATED)
def create_capability(payload: ApiCapabilityCheckCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=api_capability_service.create_capability(db, payload), message="created")


@router.get("/api-capabilities/summary")
def get_capability_summary(
    store_id: int | None = Query(default=None),
    platform: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=api_capability_service.get_api_capability_summary(
        db,
        store_id=store_id,
        platform=platform,
    ))


@router.get("/api-capabilities/{capability_id}")
def get_capability(capability_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=api_capability_service.get_capability(db, capability_id))


@router.put("/api-capabilities/{capability_id}")
def update_capability(
    capability_id: int,
    payload: ApiCapabilityCheckUpdate,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=api_capability_service.update_capability(db, capability_id, payload), message="updated")


@router.get("/api-capability-results")
def list_test_results(
    store_id: int | None = Query(default=None),
    credential_id: int | None = Query(default=None),
    capability_id: int | None = Query(default=None),
    test_status: str | None = Query(default=None),
    test_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=api_capability_service.list_test_results(
        db,
        store_id=store_id,
        credential_id=credential_id,
        capability_id=capability_id,
        test_status=test_status,
        test_mode=test_mode,
    ))


@router.post("/api-capability-results", status_code=status.HTTP_201_CREATED)
def create_test_result(payload: ApiCapabilityTestResultCreate, db: Session = Depends(get_db)) -> dict:
    return success_response(data=api_capability_service.create_test_result(db, payload), message="created")


@router.get("/api-capability-results/{result_id}")
def get_test_result(result_id: int, db: Session = Depends(get_db)) -> dict:
    return success_response(data=api_capability_service.get_test_result(db, result_id))
