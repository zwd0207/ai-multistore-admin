from fastapi import APIRouter

from app.core.responses import success_response
from app.services.api_credential_readiness_service import get_api_credential_readiness


router = APIRouter(prefix="/api-credentials", tags=["api-credentials"])


@router.get("/readiness")
def read_api_credential_readiness() -> dict:
    return success_response(data=get_api_credential_readiness())
