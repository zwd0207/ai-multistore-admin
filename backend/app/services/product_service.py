from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductRead
from app.services.store_service import ensure_store_exists


def serialize_product(product: Product) -> dict:
    return ProductRead.model_validate(product).model_dump(mode="json")


def upsert_products(
    db: Session,
    store_id: int,
    platform: str,
    items: list[dict],
    *,
    commit: bool = True,
) -> dict:
    ensure_store_exists(db, store_id)
    created = 0
    updated = 0

    for item in items:
        external_product_id = item["external_product_id"]
        product = db.scalar(
            select(Product).where(
                Product.store_id == store_id,
                Product.platform == platform,
                Product.external_product_id == external_product_id,
            )
        )
        payload = {**item, "store_id": store_id, "platform": platform}
        if product is None:
            db.add(Product(**payload))
            created += 1
            continue

        for field, value in payload.items():
            setattr(product, field, value)
        updated += 1

    if commit:
        db.commit()
    return {"created": created, "updated": updated, "total": len(items)}


def list_products(db: Session, store_id: int, platform: str | None = None) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(Product).where(Product.store_id == store_id).order_by(Product.id.asc())
    if platform:
        statement = statement.where(Product.platform == platform)

    return [serialize_product(item) for item in db.scalars(statement).all()]
