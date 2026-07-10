from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.core.exceptions import ApiError


def get_fernet() -> Fernet:
    key = get_settings().credential_encryption_key
    if not key:
        raise ApiError(
            message="缺少 CREDENTIAL_ENCRYPTION_KEY，请先生成并配置凭证加密密钥",
            error_code="ENCRYPTION_KEY_MISSING",
            status_code=500,
        )

    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise ApiError(
            message="CREDENTIAL_ENCRYPTION_KEY 格式无效，请使用 scripts/generate_key.py 生成 Fernet key",
            error_code="ENCRYPTION_KEY_INVALID",
            status_code=500,
        ) from exc


def encrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ApiError(
            message="凭证解密失败，请检查 CREDENTIAL_ENCRYPTION_KEY 是否匹配",
            error_code="CREDENTIAL_DECRYPT_FAILED",
            status_code=500,
        ) from exc


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}****{value[-4:]}"
