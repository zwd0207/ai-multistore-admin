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
SUMMARY_SEMANTIC_NOTICE = (
    "docs-only/manual/mock/sandbox records do not mean real platform connection or real sync success. "
    "tested_success is a record status only, and real_readonly is reserved for a future explicit read-only test stage."
)


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


def _new_platform_summary(platform: str) -> dict:
    return {
        "platform": platform,
        "total_capabilities": 0,
        "docs_only_count": 0,
        "manual_count": 0,
        "tested_success_count": 0,
        "not_tested_count": 0,
        "permission_required_count": 0,
        "unavailable_count": 0,
        "first_phase_candidate_count": 0,
        "real_readonly_count": 0,
        "last_checked_at": None,
    }


def _new_store_summary(store_id: int, platform: str) -> dict:
    return {
        "store_id": store_id,
        "platform": platform,
        "total_results": 0,
        "credential_bound_results": 0,
        "docs_only_count": 0,
        "manual_count": 0,
        "mock_count": 0,
        "sandbox_count": 0,
        "tested_success_count": 0,
        "tested_failed_count": 0,
        "permission_required_count": 0,
        "unavailable_count": 0,
        "not_tested_count": 0,
        "latest_tested_at": None,
        "missing_first_phase_candidates": [],
    }


def _latest_datetime(*values):
    candidates = [value for value in values if value is not None]
    return max(candidates, key=lambda value: value.isoformat()) if candidates else None


def _update_latest_iso(summary: dict, key: str, candidate) -> None:
    if candidate is None:
        return
    current = summary.get(key)
    candidate_iso = candidate.isoformat()
    if current is None or candidate_iso > current:
        summary[key] = candidate_iso


def _capability_summary_item(item: ApiCapabilityCheck) -> dict:
    return {
        "capability_id": item.id,
        "platform": item.platform,
        "capability_key": item.capability_key,
        "capability_name": item.capability_name,
        "api_category": item.api_category,
    }


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


def get_api_capability_summary(
    db: Session,
    store_id: int | None = None,
    platform: str | None = None,
) -> dict:
    normalized_platform = normalize_platform(platform) if platform is not None else None
    if store_id is not None:
        ensure_store_exists(db, store_id)

    capability_statement = select(ApiCapabilityCheck).order_by(
        ApiCapabilityCheck.platform.asc(),
        ApiCapabilityCheck.capability_key.asc(),
    )
    if normalized_platform is not None:
        capability_statement = capability_statement.where(ApiCapabilityCheck.platform == normalized_platform)
    capabilities = db.scalars(capability_statement).all()

    platform_summaries: dict[str, dict] = {}
    for capability in capabilities:
        summary = platform_summaries.setdefault(capability.platform, _new_platform_summary(capability.platform))
        summary["total_capabilities"] += 1
        if capability.test_mode == "docs_only":
            summary["docs_only_count"] += 1
        if capability.test_mode == "manual":
            summary["manual_count"] += 1
        if capability.test_mode == "real_readonly":
            summary["real_readonly_count"] += 1
        if capability.test_status == "tested_success":
            summary["tested_success_count"] += 1
        if capability.test_status == "not_tested":
            summary["not_tested_count"] += 1
        if capability.test_status == "permission_required":
            summary["permission_required_count"] += 1
        if capability.test_status == "unavailable":
            summary["unavailable_count"] += 1
        if capability.first_phase_candidate:
            summary["first_phase_candidate_count"] += 1
        _update_latest_iso(
            summary,
            "last_checked_at",
            _latest_datetime(capability.last_checked_at, capability.doc_checked_at, capability.updated_at),
        )

    store_result_summary: list[dict] = []
    attention_items: list[dict] = []
    if store_id is not None:
        result_statement = select(ApiCapabilityTestResult).join(ApiCapabilityCheck).where(
            ApiCapabilityTestResult.store_id == store_id,
        )
        if normalized_platform is not None:
            result_statement = result_statement.where(ApiCapabilityCheck.platform == normalized_platform)
        results = db.scalars(result_statement).all()

        store_summaries: dict[str, dict] = {}
        covered_capability_ids: set[int] = set()
        for result in results:
            result_platform = result.capability.platform
            summary = store_summaries.setdefault(result_platform, _new_store_summary(store_id, result_platform))
            covered_capability_ids.add(result.capability_id)
            summary["total_results"] += 1
            if result.credential_id is not None:
                summary["credential_bound_results"] += 1
            if result.test_mode == "docs_only":
                summary["docs_only_count"] += 1
            if result.test_mode == "manual":
                summary["manual_count"] += 1
            if result.test_mode == "mock":
                summary["mock_count"] += 1
            if result.test_mode == "sandbox":
                summary["sandbox_count"] += 1
            if result.test_status == "tested_success":
                summary["tested_success_count"] += 1
            if result.test_status == "tested_failed":
                summary["tested_failed_count"] += 1
            if result.test_status == "permission_required":
                summary["permission_required_count"] += 1
            if result.test_status == "unavailable":
                summary["unavailable_count"] += 1
            if result.test_status == "not_tested":
                summary["not_tested_count"] += 1
            _update_latest_iso(summary, "latest_tested_at", result.tested_at or result.created_at)

        for capability in capabilities:
            store_summaries.setdefault(capability.platform, _new_store_summary(store_id, capability.platform))
            if capability.first_phase_candidate and capability.id not in covered_capability_ids:
                store_summaries[capability.platform]["missing_first_phase_candidates"].append(
                    _capability_summary_item(capability),
                )

        store_result_summary = [store_summaries[key] for key in sorted(store_summaries)]
        for summary in store_result_summary:
            if summary["permission_required_count"]:
                attention_items.append({
                    "code": "API_CAPABILITY_PERMISSION_REQUIRED",
                    "level": "warning",
                    "platform": summary["platform"],
                    "store_id": store_id,
                    "count": summary["permission_required_count"],
                    "message": "API capability records include permission-required items; this is a local record, not a real platform validation.",
                })
            if summary["unavailable_count"]:
                attention_items.append({
                    "code": "API_CAPABILITY_UNAVAILABLE",
                    "level": "info",
                    "platform": summary["platform"],
                    "store_id": store_id,
                    "count": summary["unavailable_count"],
                    "message": "API capability records include unavailable items; this is a local record, not a real sync result.",
                })
            if summary["missing_first_phase_candidates"]:
                attention_items.append({
                    "code": "API_CAPABILITY_FIRST_PHASE_UNCONFIRMED",
                    "level": "info",
                    "platform": summary["platform"],
                    "store_id": store_id,
                    "count": len(summary["missing_first_phase_candidates"]),
                    "message": "First-phase API capability candidates do not all have store-level records yet.",
                })

    return {
        "semantic_notice": SUMMARY_SEMANTIC_NOTICE,
        "platform_summary": [platform_summaries[key] for key in sorted(platform_summaries)],
        "store_result_summary": store_result_summary,
        "attention_items": attention_items,
    }


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
