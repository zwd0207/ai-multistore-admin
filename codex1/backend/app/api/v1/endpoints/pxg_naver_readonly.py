from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.database import get_db
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_store_permission
from app.services.pxg_naver_readonly_persistence_service import (
    persist_pxg_naver_readonly_adapter_batch,
    readonly_local_summary,
    retention_cleanup_status,
)
from app.services.pxg_naver_readonly_service import collect_pxg_naver_readonly_adapter_batch
from app.services.operator_trial_service import resolve_trial_store


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


@router.post("/refresh")
async def refresh_pxg_naver_readonly_local_records(
    request_http: Request,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    # The endpoint deliberately accepts no marketplace business data. It only
    # accepts an explicit confirmation before invoking the server-side adapter.
    try:
        payload: Any = await request_http.json()
    except ValueError as exc:
        raise ApiError("readonly refresh request is invalid", "readonly_refresh_payload_invalid", 400) from exc
    if not isinstance(payload, dict) or set(payload) != {"manual_approval"} or payload.get("manual_approval") is not True:
        raise ApiError("readonly refresh request is invalid", "readonly_refresh_payload_invalid", 400)
    store = resolve_trial_store(db)
    require_store_permission(
        db,
        identity=identity,
        store_id=store.id,
        permission_key="platform.readonly.persist",
    )
    batch = collect_pxg_naver_readonly_adapter_batch(db, get_settings())
    result = persist_pxg_naver_readonly_adapter_batch(
        db,
        settings=get_settings(),
        batch=batch,
        actor_id=identity.user_key_hash,
        manual_approval=True,
    )
    return success_response(data=result, message="PXG Naver readonly local records refreshed")
