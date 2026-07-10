from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.models.api_credential import ApiCredential
from app.schemas.credential import CredentialCreate, CredentialUpdate, DecryptedCredential
from app.services.encryption import decrypt_value, encrypt_value
from app.services.store_service import ensure_store_exists

NAVER_DEFAULT_API_BASE = "https://api.commerce.naver.com/external"


def _serialize_credential(credential: ApiCredential) -> dict:
    return {
        "id": credential.id,
        "store_id": credential.store_id,
        "platform": credential.platform,
        "credential_name": credential.credential_name,
        "vendor_id": credential.vendor_id,
        "client_id": credential.client_id,
        "token_expires_at": credential.token_expires_at,
        "market": credential.market,
        "auth_status": credential.auth_status,
        "last_tested_at": credential.last_tested_at,
        "api_remark": credential.api_remark,
        "extra_config": credential.extra_config,
        "status": credential.status,
        "has_access_key": bool(credential.encrypted_access_key),
        "has_secret_key": bool(credential.encrypted_secret_key),
        "has_access_token": bool(credential.encrypted_access_token),
        "has_refresh_token": bool(credential.encrypted_refresh_token),
        "created_at": credential.created_at,
        "updated_at": credential.updated_at,
    }


def _normalize_naver_extra_config(
    extra_config: dict | None,
    existing_extra_config: dict | None = None,
) -> dict:
    merged: dict = dict(existing_extra_config or {})
    if extra_config:
        merged.update(extra_config)

    api_base = merged.get("api_base")
    if isinstance(api_base, str) and api_base.strip():
        merged["api_base"] = api_base.strip()
    else:
        merged["api_base"] = NAVER_DEFAULT_API_BASE

    channel_no = merged.get("channel_no")
    if isinstance(channel_no, str):
        channel_no = channel_no.strip()
        if channel_no:
            merged["channel_no"] = channel_no
        else:
            merged.pop("channel_no", None)

    return merged


def _normalize_extra_config(
    platform: str,
    extra_config: dict | None,
    existing_extra_config: dict | None = None,
) -> dict | None:
    if platform == "naver":
        return _normalize_naver_extra_config(extra_config, existing_extra_config=existing_extra_config)
    return extra_config


def _validate_platform_specific_credential_fields(
    *,
    platform: str,
    client_id: str | None,
    access_key_present: bool,
    secret_key_present: bool,
) -> None:
    if platform == "coupang":
        missing_fields: list[str] = []
        if not access_key_present:
            missing_fields.append("access_key")
        if not secret_key_present:
            missing_fields.append("secret_key")
        if missing_fields:
            raise ApiError(
                message="Coupang credentials require access_key and secret_key",
                error_code="INVALID_CREDENTIAL_FIELDS",
                status_code=400,
                detail={"platform": platform, "missing_fields": missing_fields},
            )
        return

    if platform == "naver":
        missing_fields: list[str] = []
        if not client_id:
            missing_fields.append("client_id")
        if not secret_key_present:
            missing_fields.append("secret_key")
        if missing_fields:
            raise ApiError(
                message="Naver credentials require client_id and secret_key",
                error_code="INVALID_CREDENTIAL_FIELDS",
                status_code=400,
                detail={"platform": platform, "missing_fields": missing_fields},
            )


def create_credential(db: Session, payload: CredentialCreate) -> dict:
    ensure_store_exists(db, payload.store_id)
    extra_config = _normalize_extra_config(payload.platform, payload.extra_config)
    _validate_platform_specific_credential_fields(
        platform=payload.platform,
        client_id=payload.client_id,
        access_key_present=bool(payload.access_key),
        secret_key_present=bool(payload.secret_key),
    )
    credential = ApiCredential(
        store_id=payload.store_id,
        platform=payload.platform,
        credential_name=payload.credential_name,
        vendor_id=payload.vendor_id,
        client_id=payload.client_id,
        encrypted_access_key=encrypt_value(payload.access_key),
        encrypted_secret_key=encrypt_value(payload.secret_key),
        encrypted_access_token=encrypt_value(payload.access_token),
        encrypted_refresh_token=encrypt_value(payload.refresh_token),
        token_expires_at=payload.token_expires_at,
        market=payload.market,
        auth_status=payload.auth_status,
        last_tested_at=payload.last_tested_at,
        api_remark=payload.api_remark,
        extra_config=extra_config,
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
    target_platform = updates.get("platform") or credential.platform
    target_client_id = updates["client_id"] if "client_id" in updates else credential.client_id
    target_access_key_present = (
        bool(updates.get("access_key"))
        if "access_key" in updates
        else bool(credential.encrypted_access_key)
    )
    target_secret_key_present = (
        bool(updates.get("secret_key"))
        if "secret_key" in updates
        else bool(credential.encrypted_secret_key)
    )

    _validate_platform_specific_credential_fields(
        platform=target_platform,
        client_id=target_client_id,
        access_key_present=target_access_key_present,
        secret_key_present=target_secret_key_present,
    )

    if "store_id" in updates and updates["store_id"] is not None:
        ensure_store_exists(db, updates["store_id"])
        credential.store_id = updates["store_id"]
    if "platform" in updates and updates["platform"] is not None:
        credential.platform = updates["platform"]
    if "credential_name" in updates and updates["credential_name"] is not None:
        credential.credential_name = updates["credential_name"]
    if "vendor_id" in updates:
        credential.vendor_id = updates["vendor_id"] or None
    if "client_id" in updates:
        credential.client_id = updates["client_id"] or None
    if "access_key" in updates and updates["access_key"] is not None:
        credential.encrypted_access_key = encrypt_value(updates["access_key"])
    if "secret_key" in updates and updates["secret_key"] is not None:
        credential.encrypted_secret_key = encrypt_value(updates["secret_key"])
    if "access_token" in updates and updates["access_token"] is not None:
        credential.encrypted_access_token = encrypt_value(updates["access_token"])
    if "refresh_token" in updates and updates["refresh_token"] is not None:
        credential.encrypted_refresh_token = encrypt_value(updates["refresh_token"])
    if "token_expires_at" in updates:
        credential.token_expires_at = updates["token_expires_at"]
    if "market" in updates:
        credential.market = updates["market"] or None
    if "auth_status" in updates and updates["auth_status"] is not None:
        credential.auth_status = updates["auth_status"]
    if "last_tested_at" in updates:
        credential.last_tested_at = updates["last_tested_at"]
    if "api_remark" in updates:
        credential.api_remark = updates["api_remark"] or None
    if "extra_config" in updates:
        credential.extra_config = _normalize_extra_config(
            target_platform,
            updates["extra_config"],
            existing_extra_config=credential.extra_config,
        )
    elif target_platform == "naver":
        credential.extra_config = _normalize_extra_config(
            target_platform,
            credential.extra_config,
        )
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
        access_token=decrypt_value(credential.encrypted_access_token),
        refresh_token=decrypt_value(credential.encrypted_refresh_token),
        vendor_id=credential.vendor_id,
        client_id=credential.client_id,
        token_expires_at=credential.token_expires_at,
        market=credential.market,
        auth_status=credential.auth_status,
        last_tested_at=credential.last_tested_at,
        api_remark=credential.api_remark,
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
        access_token=decrypt_value(credential.encrypted_access_token),
        refresh_token=decrypt_value(credential.encrypted_refresh_token),
        vendor_id=credential.vendor_id,
        client_id=credential.client_id,
        token_expires_at=credential.token_expires_at,
        market=credential.market,
        auth_status=credential.auth_status,
        last_tested_at=credential.last_tested_at,
        api_remark=credential.api_remark,
        extra_config=credential.extra_config,
        status=credential.status,
    )
