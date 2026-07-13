from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.responses import success_response
from app.config import get_settings
from app.database import get_db
from app.services import order_service
from app.services.store_service import normalize_platform
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_store_permission
from app.services.warehouse_shipping_service import write_recipient_view_audit


router = APIRouter(prefix="/orders", tags=["orders"])


def _include_trial_orders(requested: bool) -> bool:
    settings = get_settings()
    return requested or (settings.operator_trial_enabled and settings.operator_trial_artificial_data_only)


@router.get("")
def list_orders(
    request: Request,
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    view: str = Query(default="current", pattern="^(current|historical)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    order_id: str | None = Query(default=None, max_length=120),
    product_order_id: str | None = Query(default=None, max_length=120),
    product_id: str | None = Query(default=None, max_length=120),
    product_name: str | None = Query(default=None, max_length=300),
    status: str | None = Query(default=None, max_length=30),
    buyer_name: str | None = Query(default=None, max_length=120),
    buyer_phone: str | None = Query(default=None, max_length=40),
    include_test_orders: bool = Query(default=False),
    x_erp_user_key: str | None = Header(default=None, alias="X-ERP-User-Key"),
    db: Session = Depends(get_db),
) -> dict:
    include_test_orders = _include_trial_orders(include_test_orders)
    normalized_platform = normalize_platform(platform) if platform else None
    if start_at and end_at and end_at < start_at:
        raise ApiError("end_at must not precede start_at", "invalid_order_date_range", 400)
    if buyer_name or buyer_phone:
        identity = get_operator_identity(request, x_erp_user_key, db)
        require_store_permission(db, identity=identity, store_id=store_id, permission_key="recipient_pii.view")
    result = order_service.query_orders(
        db,
        store_id=store_id,
        platform=normalized_platform,
        include_test_orders=include_test_orders,
        view=view,
        page=page,
        page_size=page_size,
        start_at=start_at,
        end_at=end_at,
        order_id=order_id,
        product_order_id=product_order_id,
        product_id=product_id,
        product_name=product_name,
        status=status,
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
    )
    return success_response(data={
        **result,
        "include_test_orders": include_test_orders,
        "test_orders_excluded": 0 if include_test_orders else order_service.count_test_orders(
            db,
            store_id=store_id,
            platform=normalized_platform,
        ),
        "workbench_eligible": view != "historical",
        "platform_actions": [],
        "customer_send_allowed": False,
    })


@router.get("/operations")
def list_operations_orders(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
    include_test_orders = _include_trial_orders(include_test_orders)
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="recipient_pii.view")
    items = order_service.list_operations_orders(db, store_id=store_id, platform=normalize_platform(platform) if platform else None, include_test_orders=include_test_orders)
    write_recipient_view_audit(db, store_id=store_id, platform=normalize_platform(platform) if platform else "all", user_key_hash=identity.user_key_hash, row_count=len(items))
    return success_response(data={"items": items})


@router.get("/{order_id}/logistics-trace")
def get_order_logistics_trace(
    order_id: int,
    store_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    result = order_service.get_order_logistics_timeline(db, store_id=store_id, order_id=order_id)
    return success_response(data=result, message="order logistics trace listed")
