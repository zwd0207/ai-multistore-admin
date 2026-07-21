from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services.operation_audit_service import (
    ALLOWED_AUDIT_READ_FILTERS,
    list_operation_audit_logs_readonly_local,
    summarize_operation_audit_logs_readonly_local,
)


router = APIRouter(prefix="/operation-audit-logs", tags=["operation-audit-logs"])


def _collect_filters(request: Request, **known_filters) -> dict:
    query_keys = set(request.query_params.keys())
    unsupported = sorted(query_keys - ALLOWED_AUDIT_READ_FILTERS)
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_audit_log_filter",
                "unsupported_filter_count": len(unsupported),
                "business_message": "审计记录筛选条件不支持，请使用页面提供的筛选项。",
            },
        )
    return {
        key: value
        for key, value in known_filters.items()
        if value is not None
    }


def _raise_if_blocked(result: dict) -> None:
    if result.get("status") != "audit_read_blocked":
        return
    raise HTTPException(
        status_code=400,
        detail={
            "error_code": result.get("skip_reason", "audit_log_filter_invalid"),
            "business_message": "审计记录筛选条件无效，请调整筛选范围后重试。",
        },
    )


@router.get("")
def list_operation_audit_logs(
    request: Request,
    store_id: int | None = Query(default=None),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    include_advanced: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    filters = _collect_filters(
        request,
        store_id=store_id,
        platform=platform,
        status=status,
        target_type=target_type,
        action=action,
        actor_type=actor_type,
        date_from=date_from,
        date_to=date_to,
        correlation_id=correlation_id,
        limit=limit,
        offset=offset,
        include_advanced=include_advanced,
    )
    result = list_operation_audit_logs_readonly_local(db, filters=filters)
    _raise_if_blocked(result)
    return success_response(data=result)


@router.get("/summary")
def summarize_operation_audit_logs(
    request: Request,
    store_id: int | None = Query(default=None),
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    include_advanced: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    filters = _collect_filters(
        request,
        store_id=store_id,
        platform=platform,
        status=status,
        target_type=target_type,
        action=action,
        actor_type=actor_type,
        date_from=date_from,
        date_to=date_to,
        correlation_id=correlation_id,
        limit=limit,
        offset=offset,
        include_advanced=include_advanced,
    )
    result = summarize_operation_audit_logs_readonly_local(db, filters=filters)
    _raise_if_blocked(result)
    return success_response(data=result)
