from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.api_credential_readiness import ApiCredentialSmokeTestRequest
from app.services.api_credential_readiness_service import (
    get_api_credential_readiness,
    run_api_credential_smoke_test,
)


router = APIRouter(prefix="/api-credentials", tags=["api-credentials"])


@router.get("/readiness")
def read_api_credential_readiness(
    store_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=get_api_credential_readiness(db=db, store_id=store_id))


@router.post("/smoke-test")
def run_readonly_smoke_test(
    payload: ApiCredentialSmokeTestRequest,
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=run_api_credential_smoke_test(
        db=db,
        platform=payload.platform,
        mode=payload.mode,
        store_id=payload.store_id,
        credential_id=payload.credential_id,
        capability_scope=payload.capability_scope,
    ))
