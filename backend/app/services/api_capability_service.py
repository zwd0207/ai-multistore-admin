from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.schemas.api_capability import (
    API_CATEGORIES,
    SALES_SOURCE_TYPES,
    TEST_MODES,
    TEST_STATUSES,
    ApiCapabilityCheckCreate,
    ApiCapabilityCheckRead,
    ApiCapabilityCheckUpdate,
    ApiCapabilityTestResultCreate,
    ApiCapabilityTestResultRead,
)
from app.services.store_service import ensure_store_exists, normalize_platform


RESULT_TEST_MODES = TEST_MODES - {"real_readonly"}


def _serialize_capability(item: ApiCapabilityCheck) -> dict:
    return ApiCapabilityCheckRead.model_validate(item).model_dump(mode="json")


def _serialize_result(item: ApiCapabilityTestResult) -> dict:
    return ApiCapabilityTestResultRead.model_validate(item).model_dump(mode="json")


def _get_capability_model(db: Session, capability_id: int) -> ApiCapabilityCheck:
    item = db.get(ApiCapabilityCheck, capability_id)
    if item is None:
        raise ApiError(
            message="API capability record not found",
            error_code="API_CAPABILITY_NOT_FOUND",
            status_code=404,
            detail={"capability_id": capability_id},
        )
    return item


def _get_result_model(db: Session, result_id: int) -> ApiCapabilityTestResult:
    item = db.get(ApiCapabilityTestResult, result_id)
    if item is None:
        raise ApiError(
            message="API capability test result not found",
            error_code="API_CAPABILITY_RESULT_NOT_FOUND",
            status_code=404,
            detail={"result_id": result_id},
        )
    return item


def _validate_choice(value: str | None, allowed: set[str], field_name: str) -> str | None:
    if value is None:
        return value
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ApiError(
            message=f"{field_name} is not supported",
            error_code="INVALID_API_CAPABILITY_FILTER",
            status_code=400,
            detail={"field": field_name, "value": value, "allowed": sorted(allowed)},
        )
    return normalized


def create_capability(db: Session, payload: ApiCapabilityCheckCreate) -> dict:
    item = ApiCapabilityCheck(**payload.model_dump())
    item.platform = normalize_platform(item.platform)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_capability(item)


def list_capabilities(
    db: Session,
    platform: str | None = None,
    api_category: str | None = None,
    test_status: str | None = None,
    test_mode: str | None = None,
    first_phase_candidate: bool | None = None,
    sales_source_type: str | None = None,
) -> dict:
    statement = select(ApiCapabilityCheck).order_by(ApiCapabilityCheck.platform.asc(), ApiCapabilityCheck.capability_key.asc())
    if platform is not None:
        statement = statement.where(ApiCapabilityCheck.platform == normalize_platform(platform))
    if api_category is not None:
        api_category = _validate_choice(api_category, API_CATEGORIES, "api_category")
        statement = statement.where(ApiCapabilityCheck.api_category == api_category)
    if test_status is not None:
        test_status = _validate_choice(test_status, TEST_STATUSES, "test_status")
        statement = statement.where(ApiCapabilityCheck.test_status == test_status)
    if test_mode is not None:
        test_mode = _validate_choice(test_mode, TEST_MODES, "test_mode")
        statement = statement.where(ApiCapabilityCheck.test_mode == test_mode)
    if first_phase_candidate is not None:
        statement = statement.where(ApiCapabilityCheck.first_phase_candidate == first_phase_candidate)
    if sales_source_type is not None:
        sales_source_type = _validate_choice(sales_source_type, SALES_SOURCE_TYPES, "sales_source_type")
        statement = statement.where(ApiCapabilityCheck.sales_source_type == sales_source_type)

    items = db.scalars(statement).all()
    return {"items": [_serialize_capability(item) for item in items], "total": len(items)}


def get_capability(db: Session, capability_id: int) -> dict:
    return _serialize_capability(_get_capability_model(db, capability_id))


def update_capability(db: Session, capability_id: int, payload: ApiCapabilityCheckUpdate) -> dict:
    item = _get_capability_model(db, capability_id)
    updates = payload.model_dump(exclude_unset=True)
    if "platform" in updates and updates["platform"] is not None:
        updates["platform"] = normalize_platform(updates["platform"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _serialize_capability(item)


def _validate_result_bindings(
    db: Session,
    store_id: int,
    capability_id: int,
    credential_id: int | None,
) -> tuple[ApiCapabilityCheck, ApiCredential | None]:
    ensure_store_exists(db, store_id)
    capability = _get_capability_model(db, capability_id)
    credential = None
    if credential_id is not None:
        credential = db.get(ApiCredential, credential_id)
        if credential is None:
            raise ApiError(
                message="API credential not found",
                error_code="CREDENTIAL_NOT_FOUND",
                status_code=404,
                detail={"credential_id": credential_id},
            )
        if credential.store_id != store_id:
            raise ApiError(
                message="API credential does not belong to the selected store",
                error_code="CREDENTIAL_STORE_MISMATCH",
                status_code=400,
                detail={"credential_id": credential_id, "store_id": store_id},
            )
        if credential.platform != capability.platform:
            raise ApiError(
                message="API credential platform does not match capability platform",
                error_code="CREDENTIAL_PLATFORM_MISMATCH",
                status_code=400,
                detail={
                    "credential_id": credential_id,
                    "credential_platform": credential.platform,
                    "capability_id": capability_id,
                    "capability_platform": capability.platform,
                },
            )
    return capability, credential


def create_test_result(db: Session, payload: ApiCapabilityTestResultCreate) -> dict:
    if payload.test_mode == "real_readonly":
        raise ApiError(
            message="real_readonly is reserved for future explicit read-only API tests",
            error_code="REAL_READONLY_TEST_RESERVED",
            status_code=400,
            detail={"test_mode": payload.test_mode},
        )
    _validate_result_bindings(db, payload.store_id, payload.capability_id, payload.credential_id)
    item = ApiCapabilityTestResult(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_result(item)


def list_test_results(
    db: Session,
    store_id: int | None = None,
    credential_id: int | None = None,
    capability_id: int | None = None,
    test_status: str | None = None,
    test_mode: str | None = None,
) -> dict:
    statement = select(ApiCapabilityTestResult).order_by(ApiCapabilityTestResult.id.desc())
    if store_id is not None:
        ensure_store_exists(db, store_id)
        statement = statement.where(ApiCapabilityTestResult.store_id == store_id)
    if credential_id is not None:
        statement = statement.where(ApiCapabilityTestResult.credential_id == credential_id)
    if capability_id is not None:
        _get_capability_model(db, capability_id)
        statement = statement.where(ApiCapabilityTestResult.capability_id == capability_id)
    if test_status is not None:
        test_status = _validate_choice(test_status, TEST_STATUSES, "test_status")
        statement = statement.where(ApiCapabilityTestResult.test_status == test_status)
    if test_mode is not None:
        test_mode = _validate_choice(test_mode, RESULT_TEST_MODES, "test_mode")
        statement = statement.where(ApiCapabilityTestResult.test_mode == test_mode)

    items = db.scalars(statement).all()
    return {"items": [_serialize_result(item) for item in items], "total": len(items)}


def get_test_result(db: Session, result_id: int) -> dict:
    return _serialize_result(_get_result_model(db, result_id))
