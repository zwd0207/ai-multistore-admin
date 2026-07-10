from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.services import order_service
from app.services.store_service import normalize_platform
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_store_permission
from app.services.warehouse_shipping_service import write_recipient_view_audit


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("")
def list_orders(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    normalized_platform = normalize_platform(platform) if platform else None
    items = order_service.list_orders(
        db,
        store_id=store_id,
        platform=normalized_platform,
        include_test_orders=include_test_orders,
    )
    return success_response(data={
        "items": items,
        "total": len(items),
        "include_test_orders": include_test_orders,
        "test_orders_excluded": 0 if include_test_orders else order_service.count_test_orders(
            db,
            store_id=store_id,
            platform=normalized_platform,
        ),
    })


@router.get("/operations")
def list_operations_orders(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    include_test_orders: bool = Query(default=False),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
) -> dict:
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
