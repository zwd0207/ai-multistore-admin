from fastapi import APIRouter

from app.core.responses import success_response
from app.schemas.api_credential_readiness import ApiCredentialSmokeTestRequest
from app.services.api_credential_readiness_service import (
    get_api_credential_readiness,
    run_api_credential_smoke_test,
)


router = APIRouter(prefix="/api-credentials", tags=["api-credentials"])


@router.get("/readiness")
def read_api_credential_readiness() -> dict:
    return success_response(data=get_api_credential_readiness())


@router.post("/smoke-test")
def run_readonly_smoke_test(payload: ApiCredentialSmokeTestRequest) -> dict:
    return success_response(data=run_api_credential_smoke_test(
        platform=payload.platform,
        mode=payload.mode,
    ))
