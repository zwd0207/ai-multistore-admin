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
    assert_pxg_naver_cleanup_healthy,
    retention_cleanup_runtime_status,
    retention_cleanup_status,
    run_pxg_naver_readonly_retention_cleanup,
)
from app.services.pxg_naver_readonly_activation_service import readonly_activation_precheck
from app.services.pxg_naver_readonly_service import collect_pxg_naver_readonly_adapter_batch
from app.services.operator_trial_service import resolve_trial_store


router = APIRouter(prefix="/pxg-naver-readonly", tags=["pxg-naver-readonly"])


@router.get("/activation-check")
def get_pxg_naver_readonly_activation_check(
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    store = resolve_trial_store(db)
    require_store_permission(db, identity=identity, store_id=store.id, permission_key="platform.readonly.persist")
    return success_response(
        data=readonly_activation_precheck(db, settings=get_settings()),
        message="PXG Naver readonly activation check listed",
    )


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


@router.get("/retention-status")
def get_pxg_naver_readonly_retention_status(
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    store = resolve_trial_store(db)
    require_store_permission(db, identity=identity, store_id=store.id, permission_key="orders.read")
    return success_response(
        data=retention_cleanup_runtime_status(db, store_id=store.id, settings=get_settings()),
        message="PXG Naver readonly retention status listed",
    )


@router.post("/retention-cleanup")
async def run_pxg_naver_readonly_retention_cleanup_endpoint(
    request_http: Request,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    try:
        payload: Any = await request_http.json()
    except ValueError as exc:
        raise ApiError("readonly retention cleanup request is invalid", "readonly_retention_cleanup_payload_invalid", 400) from exc
    if not isinstance(payload, dict) or set(payload) != {"preview", "manual_confirmation"}:
        raise ApiError("readonly retention cleanup request is invalid", "readonly_retention_cleanup_payload_invalid", 400)
    preview = payload.get("preview")
    manual_confirmation = payload.get("manual_confirmation")
    if not isinstance(preview, bool) or not isinstance(manual_confirmation, bool):
        raise ApiError("readonly retention cleanup request is invalid", "readonly_retention_cleanup_payload_invalid", 400)
    store = resolve_trial_store(db)
    require_store_permission(db, identity=identity, store_id=store.id, permission_key="platform.readonly.persist")
    result = run_pxg_naver_readonly_retention_cleanup(
        db,
        settings=get_settings(),
        preview=preview,
        manual_confirmation=manual_confirmation,
        actor_id=identity.user_key_hash,
    )
    return success_response(data=result, message="PXG Naver readonly retention cleanup processed")


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
    settings = get_settings()
    assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=settings)
    batch = collect_pxg_naver_readonly_adapter_batch(db, settings)
    result = persist_pxg_naver_readonly_adapter_batch(
        db,
        settings=settings,
        batch=batch,
        actor_id=identity.user_key_hash,
        manual_approval=True,
    )
    return success_response(data=result, message="PXG Naver readonly local records refreshed")
