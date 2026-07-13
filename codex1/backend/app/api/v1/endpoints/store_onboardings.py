from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.schemas.store_onboarding import HistoricalBackfillCreate, StoreOnboardingCreate
from app.services import store_onboarding_service
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_any_store_permission, require_store_permission


router = APIRouter(prefix="/store-onboardings", tags=["store-onboardings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_store_onboarding(
    payload: StoreOnboardingCreate,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    require_any_store_permission(db, identity=identity, permission_key="store_membership.assign")
    onboarding = store_onboarding_service.submit_onboarding(db, payload=payload, creator_user_id=identity.user_id)
    return success_response(data=onboarding, message="onboarding submitted")


@router.get("/{onboarding_id}")
def get_store_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    if onboarding.store_id is None:
        require_any_store_permission(db, identity=identity, permission_key="store_membership.assign")
    else:
        require_store_permission(db, identity=identity, store_id=onboarding.store_id, permission_key="store_membership.assign")
    return success_response(data=store_onboarding_service.serialize_onboarding(onboarding))


@router.post("/{onboarding_id}/resume")
def resume_store_onboarding(
    onboarding_id: int,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    if onboarding.store_id is None:
        require_any_store_permission(db, identity=identity, permission_key="store_membership.assign")
    else:
        require_store_permission(db, identity=identity, store_id=onboarding.store_id, permission_key="store_membership.assign")
    result = store_onboarding_service.resume_onboarding(db, onboarding_id=onboarding_id)
    return success_response(data=result, message="onboarding resumed")


@router.post("/{onboarding_id}/historical-backfill")
def historical_order_backfill(
    onboarding_id: int,
    payload: HistoricalBackfillCreate,
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    onboarding = store_onboarding_service._get_onboarding(db, onboarding_id)
    if onboarding.store_id is None:
        require_any_store_permission(db, identity=identity, permission_key="store_membership.assign")
    else:
        require_store_permission(db, identity=identity, store_id=onboarding.store_id, permission_key="store_membership.assign")
    result = store_onboarding_service.run_historical_order_backfill(db, onboarding_id=onboarding_id, payload=payload)
    return success_response(data=result, message="historical order backfill completed")
