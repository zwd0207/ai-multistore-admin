from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.database import get_db
from app.core.exceptions import ApiError
from app.models.product import Product
from app.services import product_service
from app.services.operator_access_service import OperatorIdentity, get_operator_identity, require_store_permission
from app.services.product_thumbnail_service import thumbnail_response
from app.services.store_service import normalize_platform


router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(
    store_id: int = Query(...),
    platform: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    normalized_platform = normalize_platform(platform) if platform else None
    items = product_service.list_products(db, store_id=store_id, platform=normalized_platform)
    return success_response(data={"items": items, "total": len(items)})


@router.get("/{product_id}/thumbnail")
def get_product_thumbnail(
    product_id: int,
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    identity: OperatorIdentity = Depends(get_operator_identity),
):
    require_store_permission(db, identity=identity, store_id=store_id, permission_key="products.read")
    product = db.get(Product, product_id)
    if product is None or product.store_id != store_id:
        raise ApiError("product thumbnail is not found", "product_thumbnail_unavailable", 404)
    return thumbnail_response(product=product)
