from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer_inquiry import CustomerInquiry
from app.schemas.customer_inquiry import CustomerInquiryRead
from app.services.store_service import ensure_store_exists


def serialize_customer_inquiry(inquiry: CustomerInquiry) -> dict:
    return CustomerInquiryRead.model_validate(inquiry).model_dump(mode="json")


def upsert_customer_inquiries(db: Session, store_id: int, platform: str, items: list[dict]) -> dict:
    ensure_store_exists(db, store_id)
    created = 0
    updated = 0

    for item in items:
        external_inquiry_id = item["external_inquiry_id"]
        inquiry = db.scalar(
            select(CustomerInquiry).where(
                CustomerInquiry.store_id == store_id,
                CustomerInquiry.platform == platform,
                CustomerInquiry.external_inquiry_id == external_inquiry_id,
            )
        )
        payload = {**item, "store_id": store_id, "platform": platform}
        if inquiry is None:
            db.add(CustomerInquiry(**payload))
            created += 1
            continue

        for field, value in payload.items():
            setattr(inquiry, field, value)
        updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(items)}


def list_customer_inquiries(db: Session, store_id: int, platform: str | None = None) -> list[dict]:
    ensure_store_exists(db, store_id)
    statement = select(CustomerInquiry).where(CustomerInquiry.store_id == store_id).order_by(CustomerInquiry.id.asc())
    if platform:
        statement = statement.where(CustomerInquiry.platform == platform)

    return [serialize_customer_inquiry(item) for item in db.scalars(statement).all()]
