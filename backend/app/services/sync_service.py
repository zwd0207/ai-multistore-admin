from collections.abc import Callable

from sqlalchemy.orm import Session

from app.clients.coupang_client import CoupangClient
from app.clients.naver_client import NaverClient
from app.core.exceptions import ApiError
from app.services import credential_service, customer_inquiry_service, order_service, product_service, sync_log_service
from app.services.store_service import ensure_store_exists, normalize_platform


CLIENTS = {
    "naver": NaverClient,
    "coupang": CoupangClient,
}


def _build_client(db: Session, store_id: int, platform: str):
    platform = normalize_platform(platform)
    ensure_store_exists(db, store_id)
    credential = credential_service.get_decrypted_credential_by_store_and_platform(db, store_id, platform)
    client_class = CLIENTS.get(platform)
    if client_class is None:
        raise ApiError(
            message="暂不支持该平台",
            error_code="PLATFORM_NOT_SUPPORTED",
            status_code=400,
            detail={"platform": platform},
        )
    return client_class(credential)


def _run_mock_sync(
    db: Session,
    store_id: int,
    platform: str,
    sync_type: str,
    fetcher_name: str,
    writer: Callable[[Session, int, str, list[dict]], dict],
) -> dict:
    platform = normalize_platform(platform)
    sync_log = sync_log_service.create_sync_log(
        db,
        store_id=store_id,
        platform=platform,
        sync_type=sync_type,
        message=f"{sync_type} mock sync started",
        raw_summary={"stage": "started", "说明": "mock 同步开始", "한국어": "mock 동기화 시작"},
    )

    try:
        client = _build_client(db, store_id, platform)
        fetcher = getattr(client, fetcher_name)
        client_result = fetcher()
        items = client_result.get("data", {}).get("items", [])
        write_result = writer(db, store_id, platform, items)
        finished_log = sync_log_service.finish_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message=f"{sync_type} mock sync success",
            raw_summary={
                "platform": platform,
                "store_id": store_id,
                "sync_type": sync_type,
                "items": write_result,
                "中文": "同步成功",
                "한국어": "동기화 성공",
            },
        )
        return {
            "platform": platform,
            "store_id": store_id,
            "sync_type": sync_type,
            "write_result": write_result,
            "sync_log": finished_log,
        }
    except Exception as exc:
        sync_log_service.fail_sync_log(
            db,
            sync_log_id=sync_log["id"],
            message=f"{sync_type} mock sync failed",
            error_detail=str(exc),
            raw_summary={
                "platform": platform,
                "store_id": store_id,
                "sync_type": sync_type,
                "中文": "同步失败",
                "한국어": "동기화 실패",
            },
        )
        raise


def sync_products_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="products",
        fetcher_name="fetch_products_mock",
        writer=product_service.upsert_products,
    )


def sync_orders_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="orders",
        fetcher_name="fetch_orders_mock",
        writer=order_service.upsert_orders,
    )


def sync_customer_inquiries_mock(db: Session, store_id: int, platform: str) -> dict:
    return _run_mock_sync(
        db,
        store_id=store_id,
        platform=platform,
        sync_type="customer_inquiries",
        fetcher_name="fetch_customer_inquiries_mock",
        writer=customer_inquiry_service.upsert_customer_inquiries,
    )
