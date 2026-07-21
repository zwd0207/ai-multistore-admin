from fastapi import APIRouter, HTTPException, Query, Request

from app.core.responses import success_response
from app.services.backup_service import (
    ALLOWED_BACKUP_REPORT_FILTERS,
    list_backup_report_readonly_local,
    summarize_backup_report_readonly_local,
)


router = APIRouter(prefix="/backups", tags=["backups"])


def _reject_unsupported_filters(request: Request) -> None:
    unsupported = sorted(set(request.query_params.keys()) - ALLOWED_BACKUP_REPORT_FILTERS)
    if not unsupported:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "error_code": "unsupported_backup_report_filter",
            "unsupported_filter_count": len(unsupported),
            "business_message": "备份报告筛选条件不支持，请使用页面提供的筛选项。",
        },
    )


def _raise_if_blocked(result: dict) -> None:
    if result.get("status") != "backup_report_blocked":
        return
    raise HTTPException(
        status_code=400,
        detail={
            "error_code": result.get("skip_reason", "backup_report_unavailable"),
            "business_message": result.get("business_message") or "本地备份报告暂不可用，请稍后重试。",
        },
    )


@router.get("/local-report")
def get_local_backup_report(
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> dict:
    _reject_unsupported_filters(request)
    result = list_backup_report_readonly_local(limit=limit)
    _raise_if_blocked(result)
    return success_response(data=result)


@router.get("/local-report/summary")
def get_local_backup_report_summary(
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> dict:
    _reject_unsupported_filters(request)
    result = summarize_backup_report_readonly_local(limit=limit)
    if result.get("status") == "backup_summary_blocked":
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "backup_report_unavailable",
                "business_message": result.get("business_message") or "本地备份摘要暂不可用，请稍后重试。",
            },
        )
    return success_response(data=result)
