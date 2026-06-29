from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.schemas.order import OrderRead
from app.services.store_service import ensure_store_exists


def serialize_order(order: Order) -> dict:
    return OrderRead.model_validate(order).model_dump(mode="json")


def upsert_orders(db: Session, store_id: int, platform: str, items: list[dict]) -> dict:
    ensure_store_exists(db, store_id)
    created = 0
    updated = 0

    for item in items:
        external_order_id = item["external_order_id"]
        order = db.scalar(
            select(Order).where(
                Order.store_id == store_id,
                Order.platform == platform,
                Order.external_order_id == external_order_id,
            )
        )
        payload = {**item, "store_id": store_id, "platform": platform}
        if order is None:
            db.add(Order(**payload))
            created += 1
            continue

        for field, value in payload.items():
            setattr(order, field, value)
        updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(items)}


def list_orders(db: Session, store_id: int, platform: str | None = None) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(Order).where(Order.store_id == store_id).order_by(Order.id.asc())
    if platform:
        statement = statement.where(Order.platform == platform)

    return [serialize_order(item) for item in db.scalars(statement).all()]
