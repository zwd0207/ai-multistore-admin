from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate, StoreOnboardingCredentialUpdate
from app.services import store_onboarding_service
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_any_store_permission


router = APIRouter(prefix="/store-onboardings", tags=["store-onboardings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_store_onboarding(
    payload: StoreOnboardingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_any_store_permission(db, identity=identity, permission_key="store_membership.assign")
    onboarding = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=identity.user_id)
    if onboarding["status"] in {"validating", "provisioning", "backfilling"}:
        background_tasks.add_task(store_onboarding_service.run_onboarding_worker, onboarding["id"])
    return success_response(data=onboarding, message="onboarding submitted")


@router.get("/{onboarding_id}")
def get_store_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    store_onboarding_service.require_onboarding_access(db, onboarding=onboarding, user_id=identity.user_id)
    return success_response(data=store_onboarding_service.serialize_onboarding(onboarding))


@router.post("/{onboarding_id}/resume")
def resume_store_onboarding(
    onboarding_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    store_onboarding_service.require_onboarding_access(db, onboarding=onboarding, user_id=identity.user_id)
    result = store_onboarding_service.request_onboarding_resume(db, onboarding_id=onboarding_id)
    if result["status"] not in {"partially_synced", "active_incremental", "cancelled"}:
        background_tasks.add_task(store_onboarding_service.run_onboarding_worker, onboarding_id)
    return success_response(data=result, message="onboarding resumed")


@router.patch("/{onboarding_id}")
def update_store_onboarding_credentials(
    onboarding_id: int,
    payload: StoreOnboardingCredentialUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    store_onboarding_service.require_onboarding_access(db, onboarding=onboarding, user_id=identity.user_id)
    result = store_onboarding_service.update_onboarding_credentials(db, onboarding_id=onboarding_id, payload=payload)
    background_tasks.add_task(store_onboarding_service.run_onboarding_worker, onboarding_id)
    return success_response(data=result, message="onboarding credentials updated")


@router.post("/{onboarding_id}/historical-backfill")
def historical_order_backfill(
    onboarding_id: int,
    payload: HistoricalBackfillCreate,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    store_onboarding_service.require_onboarding_access(db, onboarding=onboarding, user_id=identity.user_id)
    result = store_onboarding_service.run_historical_order_backfill(db, onboarding_id=onboarding_id, payload=payload)
    return success_response(data=result, message="historical order backfill completed")
