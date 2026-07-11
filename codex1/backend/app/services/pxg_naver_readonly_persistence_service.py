"""Default-closed local persistence for the approved PXG/Naver readonly trial.

The service accepts only normalized candidates from a server-side Naver
readonly adapter. It does not accept HTTP request payloads, persist raw
platform responses, or invoke any platform write operation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.order import Order
from app.models.product import Product
from app.models.pxg_naver_readonly import (
    PxgNaverOrderRecipientSecureRecord,
    PxgNaverReadonlyCleanupStatus,
    PxgNaverReadonlyCustomerInquiry,
    PxgNaverReadonlyLogisticsRecord,
    PxgNaverReadonlyRecordState,
)
from app.models.shipping import WarehouseShippingBatch, WarehouseShippingBatchOrder
from app.schemas.pxg_naver_readonly import (
    PxgNaverReadonlyAdapterBatch,
    PxgNaverReadonlyInquiryCandidate,
    PxgNaverReadonlyLogisticsCandidate,
    PxgNaverReadonlyOrderCandidate,
    PxgNaverReadonlyProductCandidate,
)
from app.services.encryption import decrypt_value, encrypt_value
from app.services.operation_audit_service import LOCAL_WRITER_SCOPE, write_operation_audit_log_local
from app.services.operator_trial_service import assert_trial_runtime_closed, resolve_trial_store


PXG_NAVER_READONLY_LOCAL_SOURCE = "pxg_naver_readonly_local_v1"
RESOURCE_TYPES = {"product", "order", "recipient", "logistics", "customer_inquiry"}
RECIPIENT_TERMINAL_RETENTION_DAYS = 7
RECIPIENT_MAX_RETENTION_DAYS = 30
TRACKING_RETENTION_DAYS = 30
METADATA_RETENTION_DAYS = 90
TERMINAL_ORDER_STATUSES = {"DELIVERED", "DELIVERY_COMPLETED", "CANCELLED", "CANCELED", "RETURNED"}
RECIPIENT_FIELDS = (
    "receiver_name",
    "receiver_phone",
    "receiver_phone_secondary",
    "zip_code",
    "receiver_address_line1",
    "receiver_address_line2",
    "receiver_address_full",
    "delivery_memo",
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _masked_tracking_number(value: str) -> str:
    text = str(value).strip()
    if len(text) <= 4:
        return "*" * len(text)
    return f"{'*' * max(4, len(text) - 4)}{text[-4:]}"


def _empty_recipient_contract() -> dict[str, str]:
    return {field: "" for field in RECIPIENT_FIELDS}


def _resource_expiry(settings: Settings, resource_type: str, observed_at: datetime) -> datetime:
    if resource_type in {"order", "recipient"}:
        return observed_at + timedelta(minutes=max(1, settings.pxg_naver_local_read_order_stale_after_minutes))
    if resource_type == "customer_inquiry":
        return observed_at + timedelta(minutes=max(1, settings.pxg_naver_local_read_inquiry_stale_after_minutes))
    if resource_type == "logistics":
        return observed_at + timedelta(minutes=max(1, settings.pxg_naver_local_read_logistics_stale_after_minutes))
    if resource_type == "product":
        return observed_at + timedelta(hours=max(1, settings.pxg_naver_local_read_product_stale_after_hours))
    raise ValueError(f"unsupported readonly resource type: {resource_type}")


def _recipient_payload(candidate: PxgNaverReadonlyOrderCandidate) -> dict[str, str] | None:
    if candidate.recipient is None:
        return None
    payload = {
        field: str(getattr(candidate.recipient, field) or "").strip()
        for field in RECIPIENT_FIELDS
    }
    return payload if any(payload.values()) else None


def _assert_persistence_enabled(
    db: Session,
    settings: Settings,
    batch: PxgNaverReadonlyAdapterBatch,
    *,
    manual_approval: bool,
) -> None:
    assert_trial_runtime_closed(settings)
    if batch.source_mode == "real_readonly":
        assert_pxg_naver_cleanup_healthy(db, store_id=batch.store_id, settings=settings)
    if not settings.pxg_naver_local_read_persistence_enabled:
        raise ApiError(
            "PXG/Naver readonly local persistence is disabled",
            "readonly_local_persistence_disabled",
            403,
        )
    if not manual_approval:
        raise ApiError(
            "local readonly persistence requires explicit approval",
            "readonly_local_persistence_approval_required",
            403,
        )
    if batch.source_mode == "real_readonly":
        if not settings.operator_trial_real_read_enabled:
            raise ApiError(
                "real readonly local persistence is not enabled",
                "readonly_real_source_disabled",
                403,
            )
        from app.services.pxg_naver_readonly_activation_service import assert_real_persistence_activation_ready

        assert_real_persistence_activation_ready(db, settings=settings, batch=batch)
        return
    if settings.app_env not in {"development", "test"}:
        raise ApiError(
            "fictional readonly candidates are limited to development and test environments",
            "readonly_fictional_source_forbidden",
            403,
        )


def _resolve_selected_store(db: Session, batch: PxgNaverReadonlyAdapterBatch):
    store = resolve_trial_store(db)
    if batch.platform != "naver" or batch.store_id != store.id:
        raise ApiError(
            "readonly local persistence is limited to the selected PXG/Naver store",
            "readonly_persistence_store_mismatch",
            403,
        )
    return store


def _state_for(
    db: Session,
    *,
    store_id: int,
    resource_type: str,
    source_key_hash: str,
) -> PxgNaverReadonlyRecordState | None:
    return db.scalar(select(PxgNaverReadonlyRecordState).where(
        PxgNaverReadonlyRecordState.store_id == store_id,
        PxgNaverReadonlyRecordState.platform == "naver",
        PxgNaverReadonlyRecordState.resource_type == resource_type,
        PxgNaverReadonlyRecordState.source_key_hash == source_key_hash,
    ))


def _state_decision(
    state: PxgNaverReadonlyRecordState | None,
    *,
    source_updated_at: datetime,
    content_fingerprint: str,
) -> str:
    if state is None:
        return "apply"
    incoming = _utc(source_updated_at)
    current = _utc(state.source_updated_at)
    if incoming < current:
        return "older_source"
    if incoming == current:
        return "unchanged" if state.content_fingerprint == content_fingerprint else "same_version_conflict"
    return "apply"


def _refresh_state(
    db: Session,
    *,
    state: PxgNaverReadonlyRecordState | None,
    store_id: int,
    resource_type: str,
    source_key_hash: str,
    local_record_id: int,
    source_updated_at: datetime,
    content_fingerprint: str,
    observed_at: datetime,
    settings: Settings,
) -> PxgNaverReadonlyRecordState:
    if resource_type not in RESOURCE_TYPES:
        raise ValueError(f"unsupported readonly resource type: {resource_type}")
    expires_at = _resource_expiry(settings, resource_type, observed_at)
    retention_review_at = observed_at + timedelta(days=max(1, settings.pxg_naver_local_read_retention_days))
    if state is None:
        state = PxgNaverReadonlyRecordState(
            store_id=store_id,
            platform="naver",
            resource_type=resource_type,
            source_key_hash=source_key_hash,
            local_record_id=local_record_id,
            content_fingerprint=content_fingerprint,
            source_updated_at=_utc(source_updated_at),
            source_observed_at=observed_at,
            expires_at=expires_at,
            retention_review_at=retention_review_at,
            is_stale=False,
        )
        db.add(state)
        return state
    state.local_record_id = local_record_id
    state.content_fingerprint = content_fingerprint
    state.source_updated_at = _utc(source_updated_at)
    state.source_observed_at = observed_at
    state.expires_at = expires_at
    state.retention_review_at = retention_review_at
    state.is_stale = False
    return state


def _refresh_existing_state(
    state: PxgNaverReadonlyRecordState,
    *,
    observed_at: datetime,
    settings: Settings,
) -> None:
    state.source_observed_at = observed_at
    state.expires_at = _resource_expiry(settings, state.resource_type, observed_at)
    state.retention_review_at = observed_at + timedelta(days=max(1, settings.pxg_naver_local_read_retention_days))
    state.is_stale = False


def _safe_order_metadata() -> dict[str, bool]:
    return {
        "readonly_local": True,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
        "recipient_data_isolated": True,
    }


def _safe_product_metadata() -> dict[str, bool]:
    return {
        "readonly_local": True,
        "raw_response_saved": False,
        "privacy_fields_redacted": True,
    }


def _product_outcome(
    db: Session,
    *,
    store_id: int,
    candidate: PxgNaverReadonlyProductCandidate,
    observed_at: datetime,
    settings: Settings,
) -> str:
    source_key_hash = _hash(f"product:{candidate.external_product_id}")
    payload = candidate.model_dump(mode="json", exclude={"source_updated_at"})
    fingerprint = _fingerprint(payload)
    state = _state_for(db, store_id=store_id, resource_type="product", source_key_hash=source_key_hash)
    decision = _state_decision(state, source_updated_at=candidate.source_updated_at, content_fingerprint=fingerprint)
    if decision == "older_source" or decision == "same_version_conflict":
        return decision
    if decision == "unchanged":
        _refresh_existing_state(state, observed_at=observed_at, settings=settings)
        return decision

    product = db.scalar(select(Product).where(
        Product.store_id == store_id,
        Product.platform == "naver",
        Product.external_product_id == candidate.external_product_id,
    ))
    if product is not None and product.source_type != PXG_NAVER_READONLY_LOCAL_SOURCE:
        return "legacy_record_protected"
    is_new = product is None
    if product is None:
        product = Product(
            store_id=store_id,
            platform="naver",
            external_product_id=candidate.external_product_id,
            name=candidate.name,
            sku=candidate.sku,
            brand=candidate.brand,
            category=candidate.category,
            status=candidate.status,
            price=candidate.price,
            currency=candidate.currency,
            stock_quantity=candidate.stock_quantity,
            source_type=PXG_NAVER_READONLY_LOCAL_SOURCE,
            last_synced_at=observed_at,
            raw_data=_safe_product_metadata(),
        )
        db.add(product)
    else:
        product.name = candidate.name
        product.sku = candidate.sku
        product.brand = candidate.brand
        product.category = candidate.category
        product.status = candidate.status
        product.price = candidate.price
        product.currency = candidate.currency
        product.stock_quantity = candidate.stock_quantity
        product.last_synced_at = observed_at
        product.raw_data = _safe_product_metadata()
    db.flush()
    _refresh_state(
        db,
        state=state,
        store_id=store_id,
        resource_type="product",
        source_key_hash=source_key_hash,
        local_record_id=product.id,
        source_updated_at=candidate.source_updated_at,
        content_fingerprint=fingerprint,
        observed_at=observed_at,
        settings=settings,
    )
    return "created" if is_new else "updated"


def _order_outcome(
    db: Session,
    *,
    store_id: int,
    candidate: PxgNaverReadonlyOrderCandidate,
    observed_at: datetime,
    settings: Settings,
) -> tuple[str, Order | None]:
    source_key_hash = _hash(f"order:{candidate.external_product_order_id}")
    recipient = _recipient_payload(candidate)
    payload = candidate.model_dump(mode="json", exclude={"source_updated_at", "recipient"})
    payload["recipient_fingerprint"] = _fingerprint(recipient) if recipient else None
    fingerprint = _fingerprint(payload)
    state = _state_for(db, store_id=store_id, resource_type="order", source_key_hash=source_key_hash)
    decision = _state_decision(state, source_updated_at=candidate.source_updated_at, content_fingerprint=fingerprint)
    if decision == "older_source" or decision == "same_version_conflict":
        return decision, None

    statement = select(Order).where(
        Order.store_id == store_id,
        Order.platform == "naver",
        Order.external_product_order_id == candidate.external_product_order_id,
    )
    matches = db.scalars(statement).all()
    if len(matches) > 1:
        return "order_not_unique", None
    order = matches[0] if matches else None
    if order is not None and order.source_type != PXG_NAVER_READONLY_LOCAL_SOURCE:
        return "legacy_record_protected", None
    if decision == "unchanged":
        if state is not None:
            _refresh_existing_state(state, observed_at=observed_at, settings=settings)
        if order is not None:
            _upsert_secure_recipient(
                db,
                store_id=store_id,
                order=order,
                recipient=recipient,
                source_updated_at=candidate.source_updated_at,
                observed_at=observed_at,
                settings=settings,
            )
        return decision, order

    is_new = order is None
    if order is None:
        order = Order(
            store_id=store_id,
            platform="naver",
            external_order_id=candidate.external_order_id,
            external_product_order_id=candidate.external_product_order_id,
            buyer_name=None,
            buyer_phone=None,
            buyer_masked_phone=None,
            receiver_name=None,
            receiver_phone=None,
            receiver_address=None,
            zip_code=None,
            product_name=candidate.product_name,
            quantity=candidate.quantity,
            order_amount=candidate.order_amount,
            currency=candidate.currency,
            order_status=candidate.order_status,
            paid_at=_utc(candidate.paid_at) if candidate.paid_at else None,
            ordered_at=_utc(candidate.ordered_at),
            source_type=PXG_NAVER_READONLY_LOCAL_SOURCE,
            last_synced_at=observed_at,
            raw_data=_safe_order_metadata(),
        )
        db.add(order)
    else:
        order.external_product_order_id = candidate.external_product_order_id
        order.product_name = candidate.product_name
        order.quantity = candidate.quantity
        order.order_amount = candidate.order_amount
        order.currency = candidate.currency
        order.order_status = candidate.order_status
        order.paid_at = _utc(candidate.paid_at) if candidate.paid_at else None
        order.ordered_at = _utc(candidate.ordered_at)
        order.last_synced_at = observed_at
        order.raw_data = _safe_order_metadata()
        # Do not let a readonly candidate repopulate legacy plaintext recipient columns.
        order.buyer_name = None
        order.buyer_phone = None
        order.buyer_masked_phone = None
        order.receiver_name = None
        order.receiver_phone = None
        order.receiver_address = None
        order.zip_code = None
    db.flush()
    _refresh_state(
        db,
        state=state,
        store_id=store_id,
        resource_type="order",
        source_key_hash=source_key_hash,
        local_record_id=order.id,
        source_updated_at=candidate.source_updated_at,
        content_fingerprint=fingerprint,
        observed_at=observed_at,
        settings=settings,
    )
    _upsert_secure_recipient(
        db,
        store_id=store_id,
        order=order,
        recipient=recipient,
        source_updated_at=candidate.source_updated_at,
        observed_at=observed_at,
        settings=settings,
    )
    return ("created" if is_new else "updated"), order


def _upsert_secure_recipient(
    db: Session,
    *,
    store_id: int,
    order: Order,
    recipient: dict[str, str] | None,
    source_updated_at: datetime,
    observed_at: datetime,
    settings: Settings,
) -> str:
    if recipient is None:
        return "not_present"
    source_key_hash = _hash(f"recipient:{order.id}")
    recipient_hash = _fingerprint(recipient)
    state = _state_for(db, store_id=store_id, resource_type="recipient", source_key_hash=source_key_hash)
    decision = _state_decision(state, source_updated_at=source_updated_at, content_fingerprint=recipient_hash)
    if decision in {"older_source", "same_version_conflict"}:
        return decision
    secure = db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(
        PxgNaverOrderRecipientSecureRecord.order_id == order.id,
        PxgNaverOrderRecipientSecureRecord.store_id == store_id,
        PxgNaverOrderRecipientSecureRecord.platform == "naver",
    ))
    if decision == "unchanged":
        if state is not None:
            _refresh_existing_state(state, observed_at=observed_at, settings=settings)
        if secure is not None:
            secure.is_stale = False
            secure.source_observed_at = observed_at
            secure.expires_at = _resource_expiry(settings, "recipient", observed_at)
        return decision

    encrypted = encrypt_value(json.dumps(recipient, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    expires_at = _resource_expiry(settings, "recipient", observed_at)
    is_new = secure is None
    if secure is None:
        secure = PxgNaverOrderRecipientSecureRecord(
            order_id=order.id,
            store_id=store_id,
            platform="naver",
            encrypted_recipient_payload=encrypted or "",
            recipient_payload_hash=recipient_hash,
            source_updated_at=_utc(source_updated_at),
            source_observed_at=observed_at,
            expires_at=expires_at,
            is_stale=False,
        )
        db.add(secure)
    else:
        secure.encrypted_recipient_payload = encrypted or ""
        secure.recipient_payload_hash = recipient_hash
        secure.source_updated_at = _utc(source_updated_at)
        secure.source_observed_at = observed_at
        secure.expires_at = expires_at
        secure.is_stale = False
    db.flush()
    _refresh_state(
        db,
        state=state,
        store_id=store_id,
        resource_type="recipient",
        source_key_hash=source_key_hash,
        local_record_id=secure.id,
        source_updated_at=source_updated_at,
        content_fingerprint=recipient_hash,
        observed_at=observed_at,
        settings=settings,
    )
    return "created" if is_new else "updated"


def _resolve_local_order(
    db: Session,
    *,
    store_id: int,
    external_order_id: str,
    external_product_order_id: str | None,
) -> Order | None:
    statement = select(Order).where(
        Order.store_id == store_id,
        Order.platform == "naver",
        Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
    )
    if external_product_order_id:
        matches = db.scalars(statement.where(Order.external_product_order_id == external_product_order_id)).all()
    else:
        matches = db.scalars(statement.where(Order.external_order_id == external_order_id)).all()
    return matches[0] if len(matches) == 1 else None


def _logistics_outcome(
    db: Session,
    *,
    store_id: int,
    candidate: PxgNaverReadonlyLogisticsCandidate,
    observed_at: datetime,
    settings: Settings,
) -> str:
    order = _resolve_local_order(
        db,
        store_id=store_id,
        external_order_id=candidate.external_order_id,
        external_product_order_id=candidate.external_product_order_id,
    )
    if order is None:
        return "order_not_found_or_ambiguous"
    source_key_hash = _hash(f"logistics:{order.id}")
    payload = candidate.model_dump(mode="json", exclude={"source_updated_at", "tracking_number"})
    payload["tracking_number_hash"] = _hash(candidate.tracking_number)
    fingerprint = _fingerprint(payload)
    state = _state_for(db, store_id=store_id, resource_type="logistics", source_key_hash=source_key_hash)
    decision = _state_decision(state, source_updated_at=candidate.source_updated_at, content_fingerprint=fingerprint)
    if decision in {"older_source", "same_version_conflict"}:
        return decision
    record = db.scalar(select(PxgNaverReadonlyLogisticsRecord).where(
        PxgNaverReadonlyLogisticsRecord.order_id == order.id,
        PxgNaverReadonlyLogisticsRecord.store_id == store_id,
        PxgNaverReadonlyLogisticsRecord.platform == "naver",
    ))
    if decision == "unchanged":
        if state is not None:
            _refresh_existing_state(state, observed_at=observed_at, settings=settings)
        if record is not None:
            record.is_stale = False
            record.source_observed_at = observed_at
            record.expires_at = _resource_expiry(settings, "logistics", observed_at)
        return decision

    expires_at = _resource_expiry(settings, "logistics", observed_at)
    encrypted_tracking = encrypt_value(candidate.tracking_number)
    if record is None:
        record = PxgNaverReadonlyLogisticsRecord(
            order_id=order.id,
            store_id=store_id,
            platform="naver",
            encrypted_tracking_number=encrypted_tracking or "",
            tracking_number_hash=_hash(candidate.tracking_number),
            tracking_number_masked=_masked_tracking_number(candidate.tracking_number),
            carrier=candidate.carrier,
            shipment_status=candidate.shipment_status,
            shipped_at=_utc(candidate.shipped_at) if candidate.shipped_at else None,
            source_updated_at=_utc(candidate.source_updated_at),
            source_observed_at=observed_at,
            expires_at=expires_at,
            is_stale=False,
        )
        db.add(record)
        outcome = "created"
    else:
        record.encrypted_tracking_number = encrypted_tracking or ""
        record.tracking_number_hash = _hash(candidate.tracking_number)
        record.tracking_number_masked = _masked_tracking_number(candidate.tracking_number)
        record.carrier = candidate.carrier
        record.shipment_status = candidate.shipment_status
        record.shipped_at = _utc(candidate.shipped_at) if candidate.shipped_at else None
        record.source_updated_at = _utc(candidate.source_updated_at)
        record.source_observed_at = observed_at
        record.expires_at = expires_at
        record.is_stale = False
        outcome = "updated"
    db.flush()
    _refresh_state(
        db,
        state=state,
        store_id=store_id,
        resource_type="logistics",
        source_key_hash=source_key_hash,
        local_record_id=record.id,
        source_updated_at=candidate.source_updated_at,
        content_fingerprint=fingerprint,
        observed_at=observed_at,
        settings=settings,
    )
    return outcome


def _inquiry_outcome(
    db: Session,
    *,
    store_id: int,
    candidate: PxgNaverReadonlyInquiryCandidate,
    observed_at: datetime,
    settings: Settings,
) -> str:
    inquiry_hash = _hash(f"customer-inquiry:{candidate.external_inquiry_id}")
    payload = candidate.model_dump(mode="json", exclude={"source_updated_at", "external_inquiry_id"})
    payload["external_inquiry_id_hash"] = inquiry_hash
    fingerprint = _fingerprint(payload)
    state = _state_for(db, store_id=store_id, resource_type="customer_inquiry", source_key_hash=inquiry_hash)
    decision = _state_decision(state, source_updated_at=candidate.source_updated_at, content_fingerprint=fingerprint)
    if decision in {"older_source", "same_version_conflict"}:
        return decision
    record = db.scalar(select(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store_id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
        PxgNaverReadonlyCustomerInquiry.external_inquiry_id_hash == inquiry_hash,
    ))
    if decision == "unchanged":
        if state is not None:
            _refresh_existing_state(state, observed_at=observed_at, settings=settings)
        if record is not None:
            record.is_stale = False
            record.source_observed_at = observed_at
            record.expires_at = _resource_expiry(settings, "customer_inquiry", observed_at)
        return decision

    related_order = None
    if candidate.related_external_order_id or candidate.related_external_product_order_id:
        related_order = _resolve_local_order(
            db,
            store_id=store_id,
            external_order_id=candidate.related_external_order_id or "",
            external_product_order_id=candidate.related_external_product_order_id,
        )
    expires_at = _resource_expiry(settings, "customer_inquiry", observed_at)
    if record is None:
        record = PxgNaverReadonlyCustomerInquiry(
            store_id=store_id,
            platform="naver",
            external_inquiry_id_hash=inquiry_hash,
            related_order_id=related_order.id if related_order else None,
            inquiry_type=candidate.inquiry_type,
            status=candidate.status,
            customer_display_masked=candidate.customer_display_masked,
            subject_category=candidate.subject_category,
            content_available=candidate.content_available,
            received_at=_utc(candidate.received_at) if candidate.received_at else None,
            answered_at=_utc(candidate.answered_at) if candidate.answered_at else None,
            source_updated_at=_utc(candidate.source_updated_at),
            source_observed_at=observed_at,
            expires_at=expires_at,
            is_stale=False,
        )
        db.add(record)
        outcome = "created"
    else:
        record.related_order_id = related_order.id if related_order else None
        record.inquiry_type = candidate.inquiry_type
        record.status = candidate.status
        record.customer_display_masked = candidate.customer_display_masked
        record.subject_category = candidate.subject_category
        record.content_available = candidate.content_available
        record.received_at = _utc(candidate.received_at) if candidate.received_at else None
        record.answered_at = _utc(candidate.answered_at) if candidate.answered_at else None
        record.source_updated_at = _utc(candidate.source_updated_at)
        record.source_observed_at = observed_at
        record.expires_at = expires_at
        record.is_stale = False
        outcome = "updated"
    db.flush()
    _refresh_state(
        db,
        state=state,
        store_id=store_id,
        resource_type="customer_inquiry",
        source_key_hash=inquiry_hash,
        local_record_id=record.id,
        source_updated_at=candidate.source_updated_at,
        content_fingerprint=fingerprint,
        observed_at=observed_at,
        settings=settings,
    )
    return outcome


def _count_outcome(counts: dict[str, dict[str, int]], resource: str, outcome: str) -> None:
    counts[resource][outcome] = counts[resource].get(outcome, 0) + 1


def _audit_local_ingestion(
    db: Session,
    *,
    store_id: int,
    actor_id: str | None,
    counts: dict[str, dict[str, int]],
    source_mode: str,
    observed_at: datetime,
) -> None:
    audit = write_operation_audit_log_local(
        db,
        {
            "created_at": observed_at,
            "updated_at": observed_at,
            "store_id": store_id,
            "platform": "naver",
            "environment": "local",
            "actor_type": "human",
            "actor_id": _hash(actor_id or "authorized-operator")[:64],
            "actor_label": "Authorized operator",
            "actor_role": "operator",
            "action": "pxg_naver_readonly_local_ingested",
            "operation_phase": "PXG-NAVER-READONLY-LOCAL",
            "correlation_id": f"pxg-readonly-{store_id}-{observed_at:%Y%m%d%H%M%S%f}",
            "request_id": None,
            "status": "success",
            "reason_code": f"{source_mode}_metadata_only",
            "target_type": "sync_gate",
            "target_id": None,
            "target_hash": _hash(f"pxg-naver-store:{store_id}"),
            "target_label": "PXG Naver readonly local persistence",
            "changed_field_names": ["local_readonly_records"],
            "before_summary": {},
            "after_summary": {"metadata_only": True},
            "counts_summary": {
                "product_created": counts["products"].get("created", 0),
                "product_updated": counts["products"].get("updated", 0),
                "order_created": counts["orders"].get("created", 0),
                "order_updated": counts["orders"].get("updated", 0),
                "logistics_created": counts["logistics"].get("created", 0),
                "inquiry_created": counts["customer_inquiries"].get("created", 0),
            },
            "safety_flags": {
                "platform_write": False,
                "customer_send": False,
                "ai_automatic_operation": False,
                "source_payload_saved": False,
                "privacy_fields_redacted": True,
            },
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Approved local readonly metadata only.",
        },
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )
    if audit.get("status") != "audit_row_written":
        raise ApiError(
            "readonly local persistence audit was rejected",
            "readonly_persistence_audit_blocked",
            500,
        )


def persist_pxg_naver_readonly_adapter_batch(
    db: Session,
    *,
    settings: Settings,
    batch: PxgNaverReadonlyAdapterBatch,
    actor_id: str | None,
    manual_approval: bool,
) -> dict[str, Any]:
    """Persist a server-generated readonly adapter batch without platform writes."""

    if not isinstance(batch, PxgNaverReadonlyAdapterBatch):
        raise ApiError("readonly adapter batch is required", "readonly_adapter_batch_required", 400)
    _assert_persistence_enabled(db, settings, batch, manual_approval=manual_approval)
    store = _resolve_selected_store(db, batch)
    observed_at = get_utc_now()
    counts: dict[str, dict[str, int]] = {
        "products": {},
        "orders": {},
        "logistics": {},
        "customer_inquiries": {},
    }
    try:
        mark_pxg_naver_readonly_stale(db, store_id=store.id, settings=settings, now=observed_at)
        for candidate in batch.products:
            _count_outcome(counts, "products", _product_outcome(
                db, store_id=store.id, candidate=candidate, observed_at=observed_at, settings=settings,
            ))
        for candidate in batch.orders:
            outcome, _order = _order_outcome(
                db, store_id=store.id, candidate=candidate, observed_at=observed_at, settings=settings,
            )
            _count_outcome(counts, "orders", outcome)
        for candidate in batch.logistics:
            _count_outcome(counts, "logistics", _logistics_outcome(
                db, store_id=store.id, candidate=candidate, observed_at=observed_at, settings=settings,
            ))
        for candidate in batch.customer_inquiries:
            _count_outcome(counts, "customer_inquiries", _inquiry_outcome(
                db, store_id=store.id, candidate=candidate, observed_at=observed_at, settings=settings,
            ))
        _audit_local_ingestion(
            db,
            store_id=store.id,
            actor_id=actor_id,
            counts=counts,
            source_mode=batch.source_mode,
            observed_at=observed_at,
        )
        # The audit writer commits the audited business mutation. Commit again
        # explicitly so this contract remains durable if the audit implementation
        # changes to use a flush-only transaction in the future.
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "status": "completed",
        "store_id": store.id,
        "platform": "naver",
        "source_mode": batch.source_mode,
        "counts": counts,
        "privacy": {
            "recipient_data_encrypted": True,
            "ordinary_data_redacted": True,
            "raw_platform_response_saved": False,
            "credentials_saved": False,
            "headers_saved": False,
        },
        "writes": {
            "platform_write": False,
            "customer_send": False,
            "ai_automatic_operation": False,
        },
    }


def mark_pxg_naver_readonly_stale(
    db: Session,
    *,
    store_id: int,
    settings: Settings,
    now: datetime | None = None,
) -> int:
    """Mark expired records stale without deleting them or calling any platform."""

    now = _utc(now or get_utc_now())
    states = db.scalars(select(PxgNaverReadonlyRecordState).where(
        PxgNaverReadonlyRecordState.store_id == store_id,
        PxgNaverReadonlyRecordState.platform == "naver",
        PxgNaverReadonlyRecordState.is_stale.is_(False),
        PxgNaverReadonlyRecordState.expires_at <= now,
    )).all()
    for state in states:
        state.is_stale = True
        if state.resource_type == "recipient" and state.local_record_id:
            record = db.get(PxgNaverOrderRecipientSecureRecord, state.local_record_id)
            if record is not None:
                record.is_stale = True
        elif state.resource_type == "logistics" and state.local_record_id:
            record = db.get(PxgNaverReadonlyLogisticsRecord, state.local_record_id)
            if record is not None:
                record.is_stale = True
        elif state.resource_type == "customer_inquiry" and state.local_record_id:
            record = db.get(PxgNaverReadonlyCustomerInquiry, state.local_record_id)
            if record is not None:
                record.is_stale = True
    return len(states)


def _cleanup_status(db: Session, *, store_id: int, create: bool = True) -> PxgNaverReadonlyCleanupStatus | None:
    status = db.scalar(select(PxgNaverReadonlyCleanupStatus).where(
        PxgNaverReadonlyCleanupStatus.store_id == store_id,
        PxgNaverReadonlyCleanupStatus.platform == "naver",
    ))
    if status is None and create:
        status = PxgNaverReadonlyCleanupStatus(store_id=store_id, platform="naver", status="healthy")
        db.add(status)
        db.flush()
    return status


def assert_pxg_naver_cleanup_healthy(
    db: Session,
    *,
    store_id: int,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> None:
    """Require a current, successful retention run before data may be used."""

    settings = settings or get_settings()
    if not settings.pxg_naver_local_read_retention_cleanup_enabled:
        raise ApiError(
            "PXG/Naver retention cleanup is disabled; data use is blocked",
            "readonly_retention_cleanup_disabled",
            409,
            {"alert_status": "retention_cleanup_disabled"},
        )
    status = _cleanup_status(db, store_id=store_id, create=False)
    if status is None or status.last_success_at is None:
        raise ApiError(
            "PXG/Naver retention cleanup has no successful run; data use is blocked",
            "readonly_retention_cleanup_no_successful_run",
            409,
            {"alert_status": "retention_cleanup_no_successful_run"},
        )
    if status.status == "manual_review_required":
        raise ApiError(
            "PXG/Naver retention cleanup requires manual warehouse review; data use is blocked",
            "readonly_retention_cleanup_manual_review_required",
            409,
            {"alert_status": "retention_cleanup_manual_review_required"},
        )
    if status.status == "failed":
        raise ApiError(
            "PXG/Naver readonly retention cleanup failed; data use is blocked",
            "readonly_retention_cleanup_failed",
            409,
            {"alert_status": "retention_cleanup_failed"},
        )
    current = _utc(now or get_utc_now())
    if _utc(status.last_success_at) < current - timedelta(hours=24):
        raise ApiError(
            "PXG/Naver retention cleanup is overdue; data use is blocked",
            "readonly_retention_cleanup_overdue",
            409,
            {"alert_status": "retention_cleanup_overdue"},
        )


def _has_unfinished_warehouse_batch(db: Session, *, order_id: int) -> bool:
    return db.scalar(select(WarehouseShippingBatchOrder.id).join(WarehouseShippingBatch).where(
        WarehouseShippingBatchOrder.local_order_id == order_id,
        WarehouseShippingBatchOrder.is_active.is_(True),
        WarehouseShippingBatch.status != "completed",
    ).limit(1)) is not None


def _cleanup_audit(
    db: Session,
    *,
    store_id: int,
    actor_id: str | None,
    status: str,
    reason_code: str,
    counts: dict[str, int],
) -> None:
    now = get_utc_now()
    write_operation_audit_log_local(
        db,
        {
            "created_at": now,
            "updated_at": now,
            "store_id": store_id,
            "platform": "naver",
            "environment": "local",
            "actor_type": "human",
            "actor_id": _hash(actor_id or "authorized-operator"),
            "actor_label": "Authorized operator",
            "actor_role": "operator",
            "action": "pxg_naver_readonly_retention_cleanup",
            "operation_phase": "T09-R1-RETENTION",
            "correlation_id": f"pxg-retention-{store_id}-{now:%Y%m%d%H%M%S%f}",
            "request_id": None,
            "status": status,
            "reason_code": reason_code,
            "target_type": "readonly_retention",
            "target_id": None,
            "target_hash": _hash(f"pxg-naver-store:{store_id}"),
            "target_label": "PXG Naver readonly retention cleanup",
            "changed_field_names": ["retention_cleanup"],
            "before_summary": None,
            "after_summary": None,
            "counts_summary": counts,
            "backup_sha256": None,
            "restore_source_sha256": None,
            "safety_flags": {
                "platform_write": False,
                "customer_send": False,
                "ai_automatic_operation": False,
                "privacy_fields_redacted": True,
            },
            "sensitive_scan_passed": True,
            "raw_response_saved": False,
            "secrets_saved": False,
            "privacy_fields_redacted": True,
            "notes": "Retention lifecycle counters only; no recipient or tracking values retained.",
        },
        write_enabled=True,
        manual_approval=True,
        local_write_scope=LOCAL_WRITER_SCOPE,
    )


def _terminal_order_for_recipient(order: Order) -> bool:
    return str(order.order_status or "").strip().upper() in TERMINAL_ORDER_STATUSES


def _recipient_due(secure: PxgNaverOrderRecipientSecureRecord, order: Order, *, now: datetime) -> bool:
    observed_at = _utc(secure.source_observed_at)
    if observed_at <= now - timedelta(days=RECIPIENT_MAX_RETENTION_DAYS):
        return True
    return _terminal_order_for_recipient(order) and _utc(order.updated_at) <= now - timedelta(days=RECIPIENT_TERMINAL_RETENTION_DAYS)


def _metadata_state_due(state: PxgNaverReadonlyRecordState, *, now: datetime) -> bool:
    return _utc(state.source_observed_at) <= now - timedelta(days=METADATA_RETENTION_DAYS)


def _clear_state_for_local_record(db: Session, *, store_id: int, resource_type: str, local_record_id: int) -> int | None:
    state = db.scalar(select(PxgNaverReadonlyRecordState).where(
        PxgNaverReadonlyRecordState.store_id == store_id,
        PxgNaverReadonlyRecordState.platform == "naver",
        PxgNaverReadonlyRecordState.resource_type == resource_type,
        PxgNaverReadonlyRecordState.local_record_id == local_record_id,
    ))
    if state is not None:
        db.delete(state)
        return state.id
    return None


def _anonymize_expired_order(order: Order) -> None:
    """Retain only a non-identifying reference when dependent records remain."""

    order.external_order_id = f"retired-{_hash(order.external_order_id)}"
    order.external_product_order_id = f"retired-{_hash(order.external_product_order_id or order.id)}"
    order.buyer_name = None
    order.buyer_phone = None
    order.buyer_masked_phone = None
    order.receiver_name = None
    order.receiver_phone = None
    order.receiver_address = None
    order.zip_code = None
    order.product_name = "Expired PXG readonly order"
    order.order_status = "expired_metadata"
    order.raw_data = None
    order.last_synced_at = None


def _state_order_id(db: Session, state: PxgNaverReadonlyRecordState) -> int | None:
    if state.resource_type == "order":
        return state.local_record_id
    if state.resource_type == "recipient" and state.local_record_id:
        record = db.get(PxgNaverOrderRecipientSecureRecord, state.local_record_id)
        return record.order_id if record is not None else None
    if state.resource_type == "logistics" and state.local_record_id:
        record = db.get(PxgNaverReadonlyLogisticsRecord, state.local_record_id)
        return record.order_id if record is not None else None
    if state.resource_type == "customer_inquiry" and state.local_record_id:
        record = db.get(PxgNaverReadonlyCustomerInquiry, state.local_record_id)
        return record.related_order_id if record is not None else None
    return None


def run_pxg_naver_readonly_retention_cleanup(
    db: Session,
    *,
    settings: Settings,
    preview: bool,
    manual_confirmation: bool,
    actor_id: str | None,
    now: datetime | None = None,
    force_failure_for_test: bool = False,
) -> dict[str, Any]:
    """Preview or execute the fixed PXG/Naver retention lifecycle.

    The operation is constrained to the readonly source and never calls a platform.
    A cleanup error stores an alert state which blocks later display, fulfillment,
    export, and activation until a successful formal cleanup clears it.
    """

    store = resolve_trial_store(db)
    current = _utc(now or get_utc_now())
    if not preview:
        if not settings.pxg_naver_local_read_retention_cleanup_enabled:
            raise ApiError("PXG/Naver retention cleanup is disabled", "readonly_retention_cleanup_disabled", 403)
        if not manual_confirmation:
            raise ApiError("PXG/Naver retention cleanup requires manual confirmation", "readonly_retention_cleanup_confirmation_required", 403)

    counts = {
        "recipient_cleanup_count": 0,
        "tracking_cleanup_count": 0,
        "metadata_cleanup_count": 0,
        "manual_review_frozen_count": 0,
    }
    recipients = db.execute(select(PxgNaverOrderRecipientSecureRecord, Order).join(
        Order, Order.id == PxgNaverOrderRecipientSecureRecord.order_id,
    ).where(
        PxgNaverOrderRecipientSecureRecord.store_id == store.id,
        PxgNaverOrderRecipientSecureRecord.platform == "naver",
        Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
    )).all()
    logistics = db.scalars(select(PxgNaverReadonlyLogisticsRecord).join(Order).where(
        PxgNaverReadonlyLogisticsRecord.store_id == store.id,
        PxgNaverReadonlyLogisticsRecord.platform == "naver",
        Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
    )).all()
    states = db.scalars(select(PxgNaverReadonlyRecordState).where(
        PxgNaverReadonlyRecordState.store_id == store.id,
        PxgNaverReadonlyRecordState.platform == "naver",
    )).all()

    recipient_ids: list[int] = []
    frozen_order_ids: set[int] = set()

    def freeze_for_manual_review(order_id: int) -> None:
        if order_id not in frozen_order_ids:
            frozen_order_ids.add(order_id)
            counts["manual_review_frozen_count"] += 1

    for secure, order in recipients:
        if not _recipient_due(secure, order, now=current):
            continue
        if _has_unfinished_warehouse_batch(db, order_id=order.id):
            freeze_for_manual_review(order.id)
        else:
            recipient_ids.append(secure.id)
    tracking_ids = [
        record.id for record in logistics
        if str(record.shipment_status or "").strip().upper() in {"DELIVERED", "DELIVERY_COMPLETED"}
        and _utc(record.source_updated_at) <= current - timedelta(days=TRACKING_RETENTION_DAYS)
    ]
    metadata_states = [state for state in states if _metadata_state_due(state, now=current)]
    counts["recipient_cleanup_count"] = len(recipient_ids)
    counts["tracking_cleanup_count"] = len(tracking_ids)
    counts["metadata_cleanup_count"] = len(metadata_states)

    if preview:
        return {"status": "preview", "store_id": store.id, "platform": "naver", **counts, "platform_write": False}

    cleanup_status = _cleanup_status(db, store_id=store.id)
    try:
        with db.begin_nested():
            if force_failure_for_test:
                raise RuntimeError("forced_cleanup_failure")
            removed_state_ids: set[int] = set()
            for secure_id in recipient_ids:
                secure = db.get(PxgNaverOrderRecipientSecureRecord, secure_id)
                if secure is not None:
                    state_id = _clear_state_for_local_record(db, store_id=store.id, resource_type="recipient", local_record_id=secure.id)
                    if state_id is not None:
                        removed_state_ids.add(state_id)
                    db.delete(secure)
            for record_id in tracking_ids:
                record = db.get(PxgNaverReadonlyLogisticsRecord, record_id)
                if record is not None:
                    record.encrypted_tracking_number = ""
                    record.is_stale = True
            for state in metadata_states:
                if state.id in removed_state_ids:
                    continue
                associated_order_id = _state_order_id(db, state)
                if associated_order_id and _has_unfinished_warehouse_batch(db, order_id=associated_order_id):
                    freeze_for_manual_review(associated_order_id)
                    continue
                if state.resource_type == "product" and state.local_record_id:
                    record = db.get(Product, state.local_record_id)
                    if record is not None and record.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE:
                        db.delete(record)
                elif state.resource_type == "customer_inquiry" and state.local_record_id:
                    record = db.get(PxgNaverReadonlyCustomerInquiry, state.local_record_id)
                    if record is not None:
                        db.delete(record)
                elif state.resource_type == "logistics" and state.local_record_id:
                    record = db.get(PxgNaverReadonlyLogisticsRecord, state.local_record_id)
                    if record is not None:
                        db.delete(record)
                elif state.resource_type == "order" and state.local_record_id:
                    order = db.get(Order, state.local_record_id)
                    if order is not None and order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE:
                        if _has_unfinished_warehouse_batch(db, order_id=order.id):
                            freeze_for_manual_review(order.id)
                            continue
                        for secure in db.scalars(select(PxgNaverOrderRecipientSecureRecord).where(
                            PxgNaverOrderRecipientSecureRecord.order_id == order.id,
                        )).all():
                            state_id = _clear_state_for_local_record(db, store_id=store.id, resource_type="recipient", local_record_id=secure.id)
                            if state_id is not None:
                                removed_state_ids.add(state_id)
                            db.delete(secure)
                        for record in db.scalars(select(PxgNaverReadonlyLogisticsRecord).where(
                            PxgNaverReadonlyLogisticsRecord.order_id == order.id,
                        )).all():
                            state_id = _clear_state_for_local_record(db, store_id=store.id, resource_type="logistics", local_record_id=record.id)
                            if state_id is not None:
                                removed_state_ids.add(state_id)
                            db.delete(record)
                        has_retained_dependency = db.scalar(select(WarehouseShippingBatchOrder.id).where(
                            WarehouseShippingBatchOrder.local_order_id == order.id,
                        ).limit(1)) is not None or db.scalar(select(PxgNaverReadonlyCustomerInquiry.id).where(
                            PxgNaverReadonlyCustomerInquiry.related_order_id == order.id,
                        ).limit(1)) is not None
                        if has_retained_dependency:
                            _anonymize_expired_order(order)
                        else:
                            db.delete(order)
                db.delete(state)
            cleanup_status.status = "manual_review_required" if counts["manual_review_frozen_count"] else "healthy"
            cleanup_status.last_run_at = current
            cleanup_status.last_success_at = current
            cleanup_status.last_failure_at = None
            cleanup_status.last_failure_code = None
            cleanup_status.manual_review_count = counts["manual_review_frozen_count"]
        _cleanup_audit(db, store_id=store.id, actor_id=actor_id, status="success", reason_code="retention_cleanup_completed", counts=counts)
        return {"status": "completed", "store_id": store.id, "platform": "naver", **counts, "platform_write": False}
    except Exception:
        cleanup_status.status = "failed"
        cleanup_status.last_run_at = current
        cleanup_status.last_failure_at = current
        cleanup_status.last_failure_code = "retention_cleanup_failed"
        cleanup_status.manual_review_count = 0
        _cleanup_audit(db, store_id=store.id, actor_id=actor_id, status="failed", reason_code="retention_cleanup_failed", counts=counts)
        return {"status": "failed", "store_id": store.id, "platform": "naver", **counts, "platform_write": False}


def _state_lookup_for_records(
    db: Session,
    *,
    store_id: int,
    resource_type: str,
) -> dict[int, PxgNaverReadonlyRecordState]:
    states = db.scalars(select(PxgNaverReadonlyRecordState).where(
        PxgNaverReadonlyRecordState.store_id == store_id,
        PxgNaverReadonlyRecordState.platform == "naver",
        PxgNaverReadonlyRecordState.resource_type == resource_type,
    )).all()
    return {state.local_record_id: state for state in states if state.local_record_id is not None}


def readonly_local_summary(db: Session, *, store_id: int, settings: Settings) -> dict[str, Any]:
    """Return only operationally useful redacted data for ordinary pages."""

    store = resolve_trial_store(db)
    if store.id != store_id:
        raise ApiError(
            "readonly local records are limited to the selected PXG/Naver store",
            "readonly_persistence_store_mismatch",
            403,
        )
    assert_pxg_naver_cleanup_healthy(db, store_id=store.id, settings=settings)
    now = _utc(get_utc_now())
    product_states = _state_lookup_for_records(db, store_id=store.id, resource_type="product")
    order_states = _state_lookup_for_records(db, store_id=store.id, resource_type="order")
    products = db.scalars(select(Product).where(
        Product.store_id == store.id,
        Product.platform == "naver",
        Product.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
    ).order_by(Product.id.asc())).all()
    orders = db.scalars(select(Order).where(
        Order.store_id == store.id,
        Order.platform == "naver",
        Order.source_type == PXG_NAVER_READONLY_LOCAL_SOURCE,
    ).order_by(Order.id.asc())).all()
    logistics = db.scalars(select(PxgNaverReadonlyLogisticsRecord).where(
        PxgNaverReadonlyLogisticsRecord.store_id == store.id,
        PxgNaverReadonlyLogisticsRecord.platform == "naver",
    ).order_by(PxgNaverReadonlyLogisticsRecord.id.asc())).all()
    inquiries = db.scalars(select(PxgNaverReadonlyCustomerInquiry).where(
        PxgNaverReadonlyCustomerInquiry.store_id == store.id,
        PxgNaverReadonlyCustomerInquiry.platform == "naver",
    ).order_by(PxgNaverReadonlyCustomerInquiry.id.asc())).all()

    def stale(state: PxgNaverReadonlyRecordState | None) -> bool:
        return bool(state and (state.is_stale or _utc(state.expires_at) <= now))

    def state_freshness(state: PxgNaverReadonlyRecordState | None) -> dict[str, Any]:
        return {
            "source_updated_at": state.source_updated_at if state else None,
            "source_observed_at": state.source_observed_at if state else None,
            "expires_at": state.expires_at if state else None,
            "is_stale": stale(state),
        }

    stale_warning_count = sum(
        1
        for state in db.scalars(select(PxgNaverReadonlyRecordState).where(
            PxgNaverReadonlyRecordState.store_id == store.id,
            PxgNaverReadonlyRecordState.platform == "naver",
        )).all()
        if state.is_stale or _utc(state.expires_at) <= now
    )

    return {
        "status": "ready",
        "store_id": store.id,
        "platform": "naver",
        "products": [{
            "id": item.id,
            "external_product_id": item.external_product_id,
            "name": item.name,
            "sku": item.sku,
            "status": item.status,
            "price": str(item.price),
            "currency": item.currency,
            "stock_quantity": item.stock_quantity,
            "last_synced_at": item.last_synced_at,
            **state_freshness(product_states.get(item.id)),
        } for item in products],
        "orders": [{
            "id": item.id,
            "external_order_id": item.external_order_id,
            "external_product_order_id": item.external_product_order_id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "order_amount": str(item.order_amount),
            "currency": item.currency,
            "order_status": item.order_status,
            "ordered_at": item.ordered_at,
            "last_synced_at": item.last_synced_at,
            **state_freshness(order_states.get(item.id)),
        } for item in orders],
        "logistics": [{
            "order_id": item.order_id,
            "carrier": item.carrier,
            "tracking_number_masked": item.tracking_number_masked,
            "shipment_status": item.shipment_status,
            "shipped_at": item.shipped_at,
            "source_updated_at": item.source_updated_at,
            "source_observed_at": item.source_observed_at,
            "expires_at": item.expires_at,
            "is_stale": bool(item.is_stale or _utc(item.expires_at) <= now),
        } for item in logistics],
        "customer_inquiries": [{
            "id": item.id,
            "related_order_id": item.related_order_id,
            "inquiry_type": item.inquiry_type,
            "status": item.status,
            "customer_display_masked": item.customer_display_masked,
            "subject_category": item.subject_category,
            "content_available": item.content_available,
            "received_at": item.received_at,
            "answered_at": item.answered_at,
            "source_updated_at": item.source_updated_at,
            "source_observed_at": item.source_observed_at,
            "expires_at": item.expires_at,
            "is_stale": bool(item.is_stale or _utc(item.expires_at) <= now),
        } for item in inquiries],
        "freshness": {
            "resource_expiry_minutes": {
                "orders": settings.pxg_naver_local_read_order_stale_after_minutes,
                "customer_inquiries": settings.pxg_naver_local_read_inquiry_stale_after_minutes,
                "logistics": settings.pxg_naver_local_read_logistics_stale_after_minutes,
                "products": settings.pxg_naver_local_read_product_stale_after_hours * 60,
            },
            "retention_review_days": settings.pxg_naver_local_read_retention_days,
            "stale_warning_count": stale_warning_count,
            "automatic_cleanup_enabled": False,
            "automatic_cleanup_approved": False,
        },
        "privacy": {
            "recipient_data_returned": False,
            "tracking_number_full_returned": False,
            "customer_content_returned": False,
            "raw_platform_response_returned": False,
        },
    }


def recipient_contract_for_authorized_warehouse(db: Session, *, order: Order) -> dict[str, str] | None:
    """Decrypt a recipient contract only for the existing authorised warehouse path."""

    if order.source_type != PXG_NAVER_READONLY_LOCAL_SOURCE:
        return None
    assert_pxg_naver_cleanup_healthy(db, store_id=order.store_id, settings=get_settings())
    secure = db.scalar(select(PxgNaverOrderRecipientSecureRecord).where(
        PxgNaverOrderRecipientSecureRecord.order_id == order.id,
        PxgNaverOrderRecipientSecureRecord.store_id == order.store_id,
        PxgNaverOrderRecipientSecureRecord.platform == order.platform,
    ))
    if secure is None:
        return _empty_recipient_contract()
    expires_at = _utc(secure.expires_at)
    if secure.is_stale or expires_at <= _utc(get_utc_now()):
        raise ApiError(
            "recipient data is stale and cannot be used for warehouse fulfillment",
            "readonly_recipient_data_stale",
            409,
        )
    try:
        decoded = json.loads(decrypt_value(secure.encrypted_recipient_payload) or "{}")
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "encrypted recipient data cannot be read",
            "readonly_recipient_data_invalid",
            500,
        ) from exc
    if not isinstance(decoded, dict):
        raise ApiError(
            "encrypted recipient data is invalid",
            "readonly_recipient_data_invalid",
            500,
        )
    return {
        field: str(decoded.get(field) or "").strip()
        for field in RECIPIENT_FIELDS
    }


def retention_cleanup_status(settings: Settings) -> dict[str, Any]:
    """Expose fixed policy without exposing privacy-bearing cleanup details."""

    return {
        "automatic_cleanup_enabled": bool(settings.pxg_naver_local_read_retention_cleanup_enabled),
        "configured_cleanup_switch": bool(settings.pxg_naver_local_read_retention_cleanup_enabled),
        "requires_manual_confirmation": True,
        "recipient_terminal_days": RECIPIENT_TERMINAL_RETENTION_DAYS,
        "recipient_max_days": RECIPIENT_MAX_RETENTION_DAYS,
        "tracking_delivery_days": TRACKING_RETENTION_DAYS,
        "metadata_days": METADATA_RETENTION_DAYS,
    }


def retention_cleanup_runtime_status(db: Session, *, store_id: int, settings: Settings) -> dict[str, Any]:
    status = _cleanup_status(db, store_id=store_id, create=False)
    alert_status = None
    try:
        assert_pxg_naver_cleanup_healthy(db, store_id=store_id, settings=settings)
    except ApiError as exc:
        alert_status = str(exc.detail.get("alert_status")) if isinstance(exc.detail, dict) else exc.error_code
    return {
        **retention_cleanup_status(settings),
        "alert_status": alert_status,
        "manual_review_required": bool(status is not None and status.status == "manual_review_required"),
        "last_run_at": status.last_run_at if status is not None else None,
        "last_success_at": status.last_success_at if status is not None else None,
    }
