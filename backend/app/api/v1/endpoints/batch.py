from fastapi import APIRouter

from app.core.responses import success_response
from app.schemas.batch import BatchReadonlyEvidenceRequest
from app.services import sync_service


router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/readonly-evidence")
def normalize_batch_readonly_evidence(payload: BatchReadonlyEvidenceRequest) -> dict:
    result = sync_service.evaluate_batch_readonly_evidence_api_local(
        evidence_items=payload.evidence_items,
        max_items=payload.max_items,
    )
    return success_response(
        data=result,
        message="batch readonly evidence normalized",
    )
