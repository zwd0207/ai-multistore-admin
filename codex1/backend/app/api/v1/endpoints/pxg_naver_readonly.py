from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.responses import success_response
from app.database import get_db
from app.schemas.pxg_naver_readonly import parse_pxg_naver_readonly_persistence_request
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_store_permission
from app.services.pxg_naver_readonly_persistence_service import (
    persist_pxg_naver_readonly_candidates,
    readonly_local_summary,
    retention_cleanup_status,
)


router = APIRouter(prefix="/pxg-naver-readonly", tags=["pxg-naver-readonly"])


@router.get("/local-summary")
def get_pxg_naver_readonly_local_summary(
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="orders.read")
    settings = get_settings()
    result = readonly_local_summary(db, store_id=store_id, settings=settings)
    result["retention"] = retention_cleanup_status(settings)
    return success_response(data=result, message="PXG Naver readonly local summary listed")


@router.post("/persist")
async def persist_pxg_naver_readonly_local_candidates(
    request_http: Request,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    # Parse and validate manually so malformed input cannot be echoed by FastAPI with PII.
    try:
        payload: Any = await request_http.json()
    except ValueError as exc:
        from app.core.exceptions import ApiError

        raise ApiError("readonly local persistence request is invalid", "readonly_persistence_payload_invalid", 400) from exc
    request = parse_pxg_naver_readonly_persistence_request(payload)
    require_store_permission(
        db,
        identity=identity,
        store_id=request.store_id,
        permission_key="platform.readonly.persist",
    )
    result = persist_pxg_naver_readonly_candidates(
        db,
        settings=get_settings(),
        request=request,
        actor_id=identity.user_key_hash,
    )
    return success_response(data=result, message="PXG Naver readonly local candidates persisted")
