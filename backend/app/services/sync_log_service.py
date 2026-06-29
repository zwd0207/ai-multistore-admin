from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.store import Store, utc_now
from app.models.sync_log import SyncLog
from app.schemas.sync_log import SyncLogRead


def _ensure_store_exists(db: Session, store_id: int) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise ApiError(
            message="店铺不存在，无法记录同步日志",
            error_code="STORE_NOT_FOUND",
            status_code=404,
            detail={"store_id": store_id},
        )
    return store


def _serialize_sync_log(sync_log: SyncLog) -> dict:
    return SyncLogRead.model_validate(sync_log).model_dump(mode="json")


def create_sync_log(
    db: Session,
    store_id: int,
    platform: str,
    sync_type: str,
    message: str | None = None,
    raw_summary: dict | None = None,
) -> dict:
    _ensure_store_exists(db, store_id)
    sync_log = SyncLog(
        store_id=store_id,
        platform=platform,
        sync_type=sync_type,
        status="running",
        message=message,
        raw_summary=raw_summary,
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)
    return _serialize_sync_log(sync_log)


def _get_sync_log_model(db: Session, sync_log_id: int) -> SyncLog:
    sync_log = db.get(SyncLog, sync_log_id)
    if sync_log is None:
        raise ApiError(
            message="同步日志不存在",
            error_code="SYNC_LOG_NOT_FOUND",
            status_code=404,
            detail={"sync_log_id": sync_log_id},
        )
    return sync_log


def finish_sync_log(
    db: Session,
    sync_log_id: int,
    message: str | None = None,
    raw_summary: dict | None = None,
) -> dict:
    sync_log = _get_sync_log_model(db, sync_log_id)
    sync_log.status = "success"
    sync_log.finished_at = utc_now()
    if message is not None:
        sync_log.message = message
    if raw_summary is not None:
        sync_log.raw_summary = raw_summary
    db.commit()
    db.refresh(sync_log)
    return _serialize_sync_log(sync_log)


def fail_sync_log(
    db: Session,
    sync_log_id: int,
    message: str | None = None,
    error_detail: str | None = None,
    raw_summary: dict | None = None,
) -> dict:
    sync_log = _get_sync_log_model(db, sync_log_id)
    sync_log.status = "failed"
    sync_log.finished_at = utc_now()
    if message is not None:
        sync_log.message = message
    if error_detail is not None:
        sync_log.error_detail = error_detail
    if raw_summary is not None:
        sync_log.raw_summary = raw_summary
    db.commit()
    db.refresh(sync_log)
    return _serialize_sync_log(sync_log)


def list_sync_logs(db: Session, store_id: int | None = None) -> list[dict]:
    statement = select(SyncLog).order_by(SyncLog.id.desc())
    if store_id is not None:
        statement = statement.where(SyncLog.store_id == store_id)

    return [_serialize_sync_log(item) for item in db.scalars(statement).all()]
