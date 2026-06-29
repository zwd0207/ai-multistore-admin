from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.api_credential import ApiCredential
from app.schemas.credential import CredentialCreate, CredentialUpdate, DecryptedCredential
from app.services.encryption import decrypt_value, encrypt_value
from app.services.store_service import ensure_store_exists


def _serialize_credential(credential: ApiCredential) -> dict:
    return {
        "id": credential.id,
        "store_id": credential.store_id,
        "platform": credential.platform,
        "credential_name": credential.credential_name,
        "extra_config": credential.extra_config,
        "status": credential.status,
        "has_access_key": bool(credential.encrypted_access_key),
        "has_secret_key": bool(credential.encrypted_secret_key),
        "created_at": credential.created_at,
        "updated_at": credential.updated_at,
    }


def create_credential(db: Session, payload: CredentialCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    credential = ApiCredential(
        store_id=payload.store_id,
        platform=payload.platform,
        credential_name=payload.credential_name,
        encrypted_access_key=encrypt_value(payload.access_key),
        encrypted_secret_key=encrypt_value(payload.secret_key),
        extra_config=payload.extra_config,
        status=payload.status,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return _serialize_credential(credential)


def list_credentials(db: Session, store_id: int | None = None) -> list[dict]:
    statement = select(ApiCredential).order_by(ApiCredential.id.asc())
    if store_id is not None:
        ensure_store_exists(db, store_id)
        statement = statement.where(ApiCredential.store_id == store_id)

    return [_serialize_credential(item) for item in db.scalars(statement).all()]


def get_credential(db: Session, credential_id: int) -> dict:
    credential = db.get(ApiCredential, credential_id)
    if credential is None:
        raise ApiError(
            message="平台凭证不存在",
            error_code="CREDENTIAL_NOT_FOUND",
            status_code=404,
            detail={"credential_id": credential_id},
        )
    return _serialize_credential(credential)


def _get_credential_model(db: Session, credential_id: int) -> ApiCredential:
    credential = db.get(ApiCredential, credential_id)
    if credential is None:
        raise ApiError(
            message="平台凭证不存在",
            error_code="CREDENTIAL_NOT_FOUND",
            status_code=404,
            detail={"credential_id": credential_id},
        )
    return credential


def update_credential(db: Session, credential_id: int, payload: CredentialUpdate) -> dict:
    credential = _get_credential_model(db, credential_id)
    updates = payload.model_dump(exclude_unset=True)

    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
        credential.store_id = updates["store_id"]
    if "platform" in updates and updates["platform"] is not None:
        credential.platform = updates["platform"]
    if "credential_name" in updates and updates["credential_name"] is not None:
        credential.credential_name = updates["credential_name"]
    if "access_key" in updates and updates["access_key"] is not None:
        credential.encrypted_access_key = encrypt_value(updates["access_key"])
    if "secret_key" in updates and updates["secret_key"] is not None:
        credential.encrypted_secret_key = encrypt_value(updates["secret_key"])
    if "extra_config" in updates:
        credential.extra_config = updates["extra_config"]
    if "status" in updates and updates["status"] is not None:
        credential.status = updates["status"]

    db.commit()
    db.refresh(credential)
    return _serialize_credential(credential)


def delete_credential(db: Session, credential_id: int) -> dict:
    credential = _get_credential_model(db, credential_id)
    serialized = _serialize_credential(credential)
    db.delete(credential)
    db.commit()
    return serialized


def get_decrypted_credential_for_internal_use(db: Session, credential_id: int) -> DecryptedCredential:
    credential = _get_credential_model(db, credential_id)
    return DecryptedCredential(
        id=credential.id,
        store_id=credential.store_id,
        platform=credential.platform,
        credential_name=credential.credential_name,
        access_key=decrypt_value(credential.encrypted_access_key),
        secret_key=decrypt_value(credential.encrypted_secret_key),
        extra_config=credential.extra_config,
        status=credential.status,
    )


def get_decrypted_credential_by_store_and_platform(
    db: Session,
    store_id: int,
    platform: str,
) -> DecryptedCredential:
    ensure_store_exists(db, store_id)
    credential = db.scalar(
        select(ApiCredential).where(
            ApiCredential.store_id == store_id,
            ApiCredential.platform == platform,
        ).order_by(ApiCredential.id.desc())
    )
    if credential is None:
        raise ApiError(
            message="该店铺缺少平台凭证",
            error_code="CREDENTIAL_NOT_FOUND",
            status_code=404,
            detail={"store_id": store_id, "platform": platform},
        )
    return DecryptedCredential(
        id=credential.id,
        store_id=credential.store_id,
        platform=credential.platform,
        credential_name=credential.credential_name,
        access_key=decrypt_value(credential.encrypted_access_key),
        secret_key=decrypt_value(credential.encrypted_secret_key),
        extra_config=credential.extra_config,
        status=credential.status,
    )
