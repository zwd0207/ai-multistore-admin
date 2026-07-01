import base64
import hashlib
import hmac
import re
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.core.timezone import get_utc_now
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.store import Store
from app.services.encryption import decrypt_value

NAVER_DEFAULT_API_BASE = "https://api.commerce.naver.com/external"
NAVER_SUPPORTED_GRANT_TYPES = {"SELF", "SELLER"}
NAVER_REAL_SELLER_ACCOUNT_ENDPOINT_CONFIRMED = True
NAVER_REAL_PRODUCT_READ_ENDPOINT_CONFIRMED = False
NAVER_REAL_ORDER_READ_ENDPOINT_CONFIRMED = False

SMOKE_STEPS = [
    "token_test",
    "seller_or_account_test",
    "product_read_test",
    "order_read_test",
    "sales_read_test",
    "settlement_read_test",
    "customer_inquiry_read_test",
    "shipping_delivery_read_test",
]
READINESS_NOTICE = (
    "Readiness only reports whether local environment variables are present. "
    "It does not return credential values, decrypt database credentials, call Naver or Coupang, "
    "refresh tokens, or execute sync."
)
STORE_BOUND_READINESS_NOTICE = (
    "Store-bound readiness is a local database and decryptability check only. "
    "It does not call Naver, fetch tokens, refresh tokens, or prove remote authorization."
)
ENV_FALLBACK_NOTICE = (
    "Environment readiness is kept as a smoke-test fallback for local debugging. "
    "It is not the final multi-store credential solution."
)
SMOKE_NOTICE = (
    "Smoke tests are readonly only. They never return credential values or raw signed requests, "
    "and they are disabled unless REAL_API_TEST_ENABLED is true."
)


def _is_configured(value: str | None) -> bool:
    return bool(value and value.strip())


def _field_status(value: str | None) -> str:
    return "configured" if _is_configured(value) else "missing"


def _platform_status(fields: dict[str, str]) -> str:
    return "configured" if all(value == "configured" for value in fields.values()) else "missing"


def _readiness_status(credential_status: str, real_api_test_enabled: bool) -> str:
    if not real_api_test_enabled:
        return "disabled"
    return credential_status


def _naver_api_base_from_extra_config(extra_config: dict | None) -> str:
    if isinstance(extra_config, dict):
        api_base = extra_config.get("api_base")
        if isinstance(api_base, str) and api_base.strip():
            return api_base.strip()
    return NAVER_DEFAULT_API_BASE


def _naver_channel_no_from_extra_config(extra_config: dict | None) -> str | None:
    if not isinstance(extra_config, dict):
        return None
    channel_no = extra_config.get("channel_no")
    if isinstance(channel_no, str) and channel_no.strip():
        return channel_no.strip()
    return None


def _naver_grant_type_from_extra_config(extra_config: dict | None) -> str:
    if not isinstance(extra_config, dict):
        return "SELF"
    raw = extra_config.get("grant_type")
    if isinstance(raw, str):
        normalized = raw.strip().upper()
        if normalized in NAVER_SUPPORTED_GRANT_TYPES:
            return normalized
    return "SELF"


def _naver_seller_account_id_from_extra_config(extra_config: dict | None) -> str | None:
    if not isinstance(extra_config, dict):
        return None
    value = extra_config.get("seller_account_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _safe_decrypt(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    try:
        return decrypt_value(value), True
    except ApiError as exc:
        if exc.error_code == "CREDENTIAL_DECRYPT_FAILED":
            return None, False
        raise


def _get_active_store_credential(db: Session, store_id: int, platform: str) -> ApiCredential | None:
    return db.scalar(
        select(ApiCredential)
        .where(
            ApiCredential.store_id == store_id,
            ApiCredential.platform == platform,
            ApiCredential.status == "active",
        )
        .order_by(ApiCredential.id.desc())
    )


def _get_store_bound_credential(
    db: Session,
    store_id: int,
    credential_id: int | None,
    platform: str,
) -> ApiCredential | None:
    if credential_id is None:
        return _get_active_store_credential(db, store_id, platform)

    credential = db.get(ApiCredential, credential_id)
    if credential is None:
        raise ApiError(
            message="Credential not found",
            error_code="CREDENTIAL_NOT_FOUND",
            status_code=404,
            detail={"credential_id": credential_id, "store_id": store_id, "platform": platform},
        )
    if credential.store_id != store_id:
        raise ApiError(
            message="Credential does not belong to the selected store",
            error_code="CREDENTIAL_STORE_MISMATCH",
            status_code=400,
            detail={"credential_id": credential_id, "store_id": store_id},
        )
    if credential.platform != platform:
        raise ApiError(
            message="Credential platform does not match the selected store platform",
            error_code="CREDENTIAL_PLATFORM_MISMATCH",
            status_code=400,
            detail={"credential_id": credential_id, "platform": credential.platform, "expected_platform": platform},
        )
    return credential if credential.status == "active" else None


def _derive_access_token_status(
    credential: ApiCredential,
    warnings: list[str],
) -> str:
    if not credential.encrypted_access_token:
        return "missing"

    access_token, decryptable = _safe_decrypt(credential.encrypted_access_token)
    if not decryptable:
        warnings.append("access_token_decrypt_failed")
        return "decrypt_failed"
    if not _is_configured(access_token):
        return "missing"

    if credential.token_expires_at is None:
        return "present"
    token_expires_at = credential.token_expires_at
    if token_expires_at.tzinfo is None:
        token_expires_at = token_expires_at.replace(tzinfo=get_utc_now().tzinfo)
    if token_expires_at <= get_utc_now():
        return "expired"
    return "valid_like"


def _build_naver_store_bound_readiness(db: Session, store_id: int) -> dict:
    store = db.get(Store, store_id)
    if store is None:
        raise ApiError(
            message="Store not found",
            error_code="STORE_NOT_FOUND",
            status_code=404,
            detail={"store_id": store_id},
        )
    if store.platform != "naver":
        raise ApiError(
            message="Selected store is not a Naver store",
            error_code="STORE_PLATFORM_MISMATCH",
            status_code=400,
            detail={"store_id": store_id, "platform": store.platform, "expected_platform": "naver"},
        )

    credential = _get_active_store_credential(db, store_id, "naver")
    warnings: list[str] = []
    missing_fields: list[str] = []
    api_base = NAVER_DEFAULT_API_BASE
    channel_no_configured = False
    access_token_status = "missing"
    refresh_token_configured = False
    token_expires_at = None
    auth_status = "not_configured"
    client_id_configured = False
    secret_key_configured = False
    secret_key_decryptable = False

    if credential is None:
        missing_fields.append("active_naver_credential")
        warnings.extend(["env_readiness_is_fallback_only", "channel_no_optional_missing", "access_token_missing"])
        return {
            "store_id": store.id,
            "platform": store.platform,
            "credential_id": None,
            "credential_name": None,
            "configured": False,
            "client_id_configured": False,
            "secret_key_configured": False,
            "secret_key_decryptable": False,
            "api_base": api_base,
            "channel_no_configured": False,
            "access_token_status": "missing",
            "refresh_token_configured": False,
            "token_expires_at": None,
            "auth_status": auth_status,
            "missing_fields": missing_fields,
            "warnings": warnings,
        }

    api_base = _naver_api_base_from_extra_config(credential.extra_config)
    explicit_api_base = (
        isinstance(credential.extra_config, dict)
        and isinstance(credential.extra_config.get("api_base"), str)
        and bool(credential.extra_config.get("api_base").strip())
    )
    channel_no_configured = bool(_naver_channel_no_from_extra_config(credential.extra_config))
    client_id_configured = _is_configured(credential.client_id)
    secret_key_configured = bool(credential.encrypted_secret_key)
    _, secret_key_decryptable = _safe_decrypt(credential.encrypted_secret_key)
    access_token_status = _derive_access_token_status(credential, warnings)
    refresh_token_configured = bool(credential.encrypted_refresh_token)
    token_expires_at = credential.token_expires_at
    auth_status = credential.auth_status

    if not client_id_configured:
        missing_fields.append("client_id")
    if not secret_key_configured:
        missing_fields.append("secret_key")
    if secret_key_configured and not secret_key_decryptable:
        warnings.append("secret_key_decrypt_failed")
    if not explicit_api_base:
        warnings.append("api_base_defaulted")
    if not channel_no_configured:
        warnings.append("channel_no_optional_missing")
    if access_token_status == "missing":
        warnings.append("access_token_missing")
    elif access_token_status == "expired":
        warnings.append("access_token_expired")

    configured = client_id_configured and secret_key_configured and secret_key_decryptable and bool(api_base)

    return {
        "store_id": store.id,
        "platform": store.platform,
        "credential_id": credential.id,
        "credential_name": credential.credential_name,
        "configured": configured,
        "client_id_configured": client_id_configured,
        "secret_key_configured": secret_key_configured,
        "secret_key_decryptable": secret_key_decryptable,
        "api_base": api_base,
        "channel_no_configured": channel_no_configured,
        "access_token_status": access_token_status,
        "refresh_token_configured": refresh_token_configured,
        "token_expires_at": token_expires_at,
        "auth_status": auth_status,
        "missing_fields": missing_fields,
        "warnings": warnings,
    }


def _new_smoke_result(platform: str) -> dict:
    result = {
        "platform": platform,
        "enabled": False,
        "configured": False,
        "test_mode": "readonly",
        "http_status": None,
        "error_code": None,
        "masked_message": "",
        "tested_at": get_utc_now().isoformat(),
    }
    for step in SMOKE_STEPS:
        result[step] = "skipped"
    return result


def _new_naver_store_bound_result(store_id: int, credential_id: int | None = None) -> dict:
    result = _new_smoke_result("naver")
    result.update({
        "store_id": store_id,
        "credential_id": credential_id,
        "path_kind": "store_bound",
        "grant_type_used": "SELF",
        "seller_account_id_configured": False,
        "channel_no_source": "not_attempted",
        "capability_result_ids": {},
    })
    return result


def _new_naver_env_fallback_result() -> dict:
    result = _new_smoke_result("naver")
    result.update({
        "store_id": None,
        "credential_id": None,
        "path_kind": "env_fallback",
        "grant_type_used": "SELF",
        "seller_account_id_configured": False,
        "channel_no_source": "not_attempted",
        "capability_result_ids": {},
    })
    return result


def _mark_failed(result: dict, error_code: str, message: str) -> dict:
    result["error_code"] = error_code
    result["masked_message"] = _mask_message(message)
    return result


def _mask_message(message: str | None) -> str:
    text = str(message or "")
    if not text:
        return ""
    text = re.sub(
        r"(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|access[_-]?key|secret[_-]?key|authorization|signature)",
        "credential_field",
        text,
    )
    text = re.sub(r"[A-Za-z0-9_\-+/=]{32,}", "[masked]", text)
    return text[:300]


def _is_ip_not_allowed(response: httpx.Response) -> bool:
    text = response.text.lower()
    return response.status_code in {401, 403} and any(token in text for token in ["ip", "whitelist", "white list", "allowed"])


def _step_from_response(result: dict, step: str, response: httpx.Response) -> bool:
    result["http_status"] = response.status_code
    if 200 <= response.status_code < 300:
        result[step] = "success"
        return True
    result[step] = "failed"
    if _is_ip_not_allowed(response):
        _mark_failed(result, "ip_not_allowed", f"{step} failed with IP allowlist response")
    elif response.status_code in {401, 403}:
        _mark_failed(result, "auth_failed", f"{step} failed with authorization response")
    else:
        _mark_failed(result, "readonly_request_failed", f"{step} failed with HTTP {response.status_code}")
    return False


def _load_naver_smoke_context(
    db: Session,
    store_id: int,
    credential_id: int | None,
) -> tuple[dict | None, dict]:
    result = _new_naver_store_bound_result(store_id=store_id, credential_id=credential_id)
    store = db.get(Store, store_id)
    if store is None:
        raise ApiError(
            message="Store not found",
            error_code="STORE_NOT_FOUND",
            status_code=404,
            detail={"store_id": store_id},
        )
    if store.platform != "naver":
        raise ApiError(
            message="Selected store is not a Naver store",
            error_code="STORE_PLATFORM_MISMATCH",
            status_code=400,
            detail={"store_id": store_id, "platform": store.platform, "expected_platform": "naver"},
        )

    credential = _get_store_bound_credential(db, store_id, credential_id, "naver")
    if credential is None:
        result["credential_id"] = credential_id
        result["test_mode"] = "real_readonly"
        return None, _mark_failed(result, "credential_not_ready", "Active Naver credential is required for a store-bound smoke test")

    result["credential_id"] = credential.id
    result["grant_type_used"] = _naver_grant_type_from_extra_config(credential.extra_config)
    result["seller_account_id_configured"] = bool(_naver_seller_account_id_from_extra_config(credential.extra_config))

    api_base = _naver_api_base_from_extra_config(credential.extra_config)
    client_id = credential.client_id.strip() if _is_configured(credential.client_id) else None
    secret_key, secret_key_decryptable = _safe_decrypt(credential.encrypted_secret_key)
    access_token, access_token_decryptable = _safe_decrypt(credential.encrypted_access_token)
    refresh_token, refresh_token_decryptable = _safe_decrypt(credential.encrypted_refresh_token)

    if not client_id:
        result["test_mode"] = "real_readonly"
        return None, _mark_failed(result, "credential_not_ready", "Naver client_id is not configured for the selected store")
    if credential.encrypted_secret_key and not secret_key_decryptable:
        result["test_mode"] = "real_readonly"
        return None, _mark_failed(result, "credential_decrypt_failed", "Naver secret_key could not be decrypted for the selected store")
    if not _is_configured(secret_key):
        result["test_mode"] = "real_readonly"
        return None, _mark_failed(result, "credential_not_ready", "Naver secret_key is not configured for the selected store")
    if result["grant_type_used"] == "SELLER" and not result["seller_account_id_configured"]:
        result["test_mode"] = "real_readonly"
        return None, _mark_failed(result, "seller_account_id_missing", "SELLER grant requires a configured seller account id")

    result["configured"] = True
    result["test_mode"] = "real_readonly"
    context = {
        "store_id": store.id,
        "credential_id": credential.id,
        "credential_name": credential.credential_name,
        "client_id": client_id,
        "secret_key": secret_key,
        "access_token": access_token if access_token_decryptable else None,
        "refresh_token": refresh_token if refresh_token_decryptable else None,
        "api_base": api_base.rstrip("/"),
        "grant_type_used": result["grant_type_used"],
        "seller_account_id": _naver_seller_account_id_from_extra_config(credential.extra_config),
        "seller_account_id_configured": result["seller_account_id_configured"],
        "channel_no": _naver_channel_no_from_extra_config(credential.extra_config),
        "channel_no_source": "credential_extra_config" if _naver_channel_no_from_extra_config(credential.extra_config) else "missing",
    }
    return context, result


def _request_naver_token_from_context(context: dict) -> tuple[str, int]:
    import bcrypt

    timestamp = str(int(time.time() * 1000))
    raw = f"{context['client_id']}_{timestamp}".encode("utf-8")
    secret = context["secret_key"].encode("utf-8")
    signed = bcrypt.hashpw(raw, secret)
    client_secret_sign = base64.b64encode(signed).decode("utf-8")
    payload = {
        "client_id": context["client_id"],
        "timestamp": timestamp,
        "client_secret_sign": client_secret_sign,
        "grant_type": "client_credentials",
        "type": context["grant_type_used"],
    }
    if context["grant_type_used"] == "SELLER" and context.get("seller_account_id"):
        payload["account_id"] = context["seller_account_id"]
    with httpx.Client(timeout=10.0) as client:
        response = client.post(f"{context['api_base']}/v1/oauth2/token", data=payload)
    if response.status_code in {401, 403}:
        error = RuntimeError("token_auth_failed")
        error.http_status = response.status_code
        raise error
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        error = RuntimeError("token_auth_failed")
        error.http_status = response.status_code
        raise error
    return token, response.status_code


def get_api_credential_readiness(
    db: Session | None = None,
    store_id: int | None = None,
) -> dict:
    settings = get_settings()
    real_api_test_enabled = bool(settings.real_api_test_enabled)

    coupang_fields = {
        "vendor_id": _field_status(settings.coupang_vendor_id),
        "access_key": _field_status(settings.coupang_access_key),
        "secret_key": _field_status(settings.coupang_secret_key),
    }
    naver_fields = {
        "client_id": _field_status(settings.naver_client_id),
        "client_secret": _field_status(settings.naver_client_secret),
        "api_base": _field_status(settings.naver_api_base),
    }

    coupang_credential_status = _platform_status(coupang_fields)
    naver_credential_status = _platform_status(naver_fields)

    return {
        "semantic_notice": READINESS_NOTICE,
        "env_fallback_notice": ENV_FALLBACK_NOTICE,
        "store_bound_readiness_notice": STORE_BOUND_READINESS_NOTICE,
        "real_api_test_enabled": real_api_test_enabled,
        "real_api_write_enabled": bool(settings.real_api_write_enabled),
        "platforms": [
            {
                "platform": "coupang",
                "credential_status": coupang_credential_status,
                "readiness_status": _readiness_status(coupang_credential_status, real_api_test_enabled),
                "fields": coupang_fields,
            },
            {
                "platform": "naver",
                "credential_status": naver_credential_status,
                "readiness_status": _readiness_status(naver_credential_status, real_api_test_enabled),
                "fields": naver_fields,
            },
        ],
        "store_bound_readiness": _build_naver_store_bound_readiness(db, store_id) if db is not None and store_id is not None else None,
    }


def run_api_credential_smoke_test(
    db: Session | None = None,
    platform: str = "all",
    mode: str = "readonly",
    store_id: int | None = None,
    credential_id: int | None = None,
) -> dict:
    settings = get_settings()
    if platform == "naver" and store_id is not None:
        if db is None:
            raise ApiError(
                message="Database session is required for store-bound Naver smoke tests",
                error_code="DB_SESSION_REQUIRED",
                status_code=500,
            )
        result, capability_results = _run_naver_store_bound_smoke_test(
            db=db,
            settings=settings,
            store_id=store_id,
            credential_id=credential_id,
        )
        if (
            db is not None
            and result.get("test_mode") == "real_readonly"
            and result.get("store_id") is not None
            and result.get("credential_id") is not None
            and result.get("error_code") != "real_api_test_disabled"
        ):
            result["capability_result_ids"] = _persist_real_readonly_capability_results(db, capability_results)
        return {
            "semantic_notice": SMOKE_NOTICE,
            "mode": mode,
            "real_api_test_enabled": bool(settings.real_api_test_enabled),
            "real_api_write_enabled": bool(settings.real_api_write_enabled),
            "results": [result],
            "capability_results": capability_results,
        }

    selected_platforms = ["coupang", "naver"] if platform == "all" else [platform]
    capability_results: list[dict] = []
    results = []
    for item in selected_platforms:
        platform_result, platform_capability_results = _run_platform_smoke_test(settings, item)
        results.append(platform_result)
        capability_results.extend(platform_capability_results)
    if db is not None and settings.real_api_test_enabled:
        for result in capability_results:
            if result.get("store_id") is not None and result.get("credential_id") is not None:
                _persist_real_readonly_capability_results(db, [result])

    return {
        "semantic_notice": SMOKE_NOTICE,
        "mode": mode,
        "real_api_test_enabled": bool(settings.real_api_test_enabled),
        "real_api_write_enabled": bool(settings.real_api_write_enabled),
        "results": results,
        "capability_results": capability_results,
    }


def _run_platform_smoke_test(settings, platform: str) -> tuple[dict, list[dict]]:
    result = _new_smoke_result(platform)
    if not settings.real_api_test_enabled:
        return _mark_failed(result, "real_api_test_disabled", "REAL_API_TEST_ENABLED is false"), [result]

    result["enabled"] = True
    if platform == "naver":
        return _run_naver_env_fallback_smoke_test(settings)
    return _run_coupang_smoke_test(settings, result)


def _run_naver_env_fallback_smoke_test(settings) -> tuple[dict, list[dict]]:
    result = _new_naver_env_fallback_result()
    result["enabled"] = True
    missing = [
        name
        for name, value in {
            "NAVER_CLIENT_ID": settings.naver_client_id,
            "NAVER_CLIENT_SECRET": settings.naver_client_secret,
            "NAVER_API_BASE": settings.naver_api_base,
        }.items()
        if not _is_configured(value)
    ]
    if missing:
        return _mark_failed(result, "missing_credentials", f"Missing required environment fields: {', '.join(missing)}"), []

    result["configured"] = True
    result["grant_type_used"] = "SELF"
    try:
        access_token, token_status = _request_naver_token(settings)
        result["http_status"] = token_status
        result["token_test"] = "success"
        headers = {"Authorization": f"Bearer {access_token}"}
        base = settings.naver_api_base.rstrip("/")
        with httpx.Client(timeout=10.0) as client:
            seller_response = client.get(f"{base}/v1/seller/account", headers=headers)
            if not _step_from_response(result, "seller_or_account_test", seller_response):
                return result

            channel_no = _extract_channel_no(seller_response.json()) or settings.naver_channel_no
            product_params = {"page": 1, "size": 1}
            if channel_no:
                product_params["channelNo"] = channel_no
                result["channel_no_source"] = "seller_account"
            elif settings.naver_channel_no:
                result["channel_no_source"] = "env_fallback"
            else:
                result["channel_no_source"] = "missing"
            product_response = client.get(f"{base}/v1/products/search", headers=headers, params=product_params)
            _step_from_response(result, "product_read_test", product_response)

            now = get_utc_now()
            order_params = {
                "from": (now - timedelta(days=1)).date().isoformat(),
                "to": now.date().isoformat(),
                "page": 1,
                "size": 1,
            }
            order_response = client.get(f"{base}/v1/pay-order/seller/product-orders", headers=headers, params=order_params)
            _step_from_response(result, "order_read_test", order_response)
            result["sales_read_test"] = "skipped"
            result["settlement_read_test"] = "skipped"
            result["customer_inquiry_read_test"] = "skipped"
            result["shipping_delivery_read_test"] = "skipped"
            if not result["masked_message"]:
                result["masked_message"] = "Readonly env fallback smoke test completed without returning raw API data."
    except ImportError:
        result["token_test"] = "failed"
        _mark_failed(result, "dependency_missing", "bcrypt dependency is required for Naver client_secret_sign")
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    except Exception as exc:
        result["http_status"] = getattr(exc, "http_status", result.get("http_status"))
        _mark_failed(result, "smoke_test_failed", str(exc))
    return result, []


def _run_naver_store_bound_smoke_test(
    db: Session,
    settings,
    store_id: int,
    credential_id: int | None,
) -> tuple[dict, list[dict]]:
    if not settings.real_api_test_enabled:
        result = _new_naver_store_bound_result(store_id=store_id, credential_id=credential_id)
        store = db.get(Store, store_id)
        if store is not None and store.platform == "naver":
            credential = _get_store_bound_credential(db, store_id, credential_id, "naver")
            if credential is not None:
                result["credential_id"] = credential.id
                result["configured"] = True
                result["grant_type_used"] = _naver_grant_type_from_extra_config(credential.extra_config)
                result["seller_account_id_configured"] = bool(_naver_seller_account_id_from_extra_config(credential.extra_config))
                result["channel_no_source"] = "credential_extra_config" if _naver_channel_no_from_extra_config(credential.extra_config) else "missing"
        result["test_mode"] = "disabled"
        result["enabled"] = False
        return _mark_failed(result, "real_api_test_disabled", "REAL_API_TEST_ENABLED is false"), []

    context, result = _load_naver_smoke_context(db, store_id, credential_id)
    capability_results: list[dict] = []

    result["enabled"] = True
    if context is None:
        capability_results.append(_build_capability_record(
            platform="naver",
            capability_key="naver.token_auth",
            capability_name="Naver token auth readonly test",
            api_category="auth",
            endpoint_path="/v1/oauth2/token",
            result=result,
            test_step="token_test",
            notes="Store-bound readonly smoke test failed before token exchange.",
        ) | {"store_id": store_id, "credential_id": result.get("credential_id")})
        return result, capability_results

    try:
        access_token, token_status = _request_naver_token_from_context(context)
        result["http_status"] = token_status
        result["token_test"] = "success"
        capability_results.append(_build_capability_record(
            platform="naver",
            capability_key="naver.token_auth",
            capability_name="Naver token auth readonly test",
            api_category="auth",
            endpoint_path="/v1/oauth2/token",
            result=result,
            test_step="token_test",
            notes=f"Store-bound readonly token exchange using {context['grant_type_used']} grant.",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})

        headers = {"Authorization": f"Bearer {access_token}"}
        seller_record = _run_naver_seller_account_read(context, result, headers)
        capability_results.append(seller_record)
        if result["seller_or_account_test"] != "success":
            capability_results.extend(_build_naver_docs_pending_capability_records(context, result))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly smoke test stopped after seller/account failure without returning raw API data."
            return result, capability_results

        product_record = _run_naver_product_read(context, result, headers)
        capability_results.append(product_record)

        order_record = _run_naver_order_read(context, result, headers)
        capability_results.append(order_record)
    except ImportError:
        result["token_test"] = "failed"
        _mark_failed(result, "dependency_missing", "bcrypt dependency is required for Naver client_secret_sign")
        capability_results.append(_build_capability_record(
            platform="naver",
            capability_key="naver.token_auth",
            capability_name="Naver token auth readonly test",
            api_category="auth",
            endpoint_path="/v1/oauth2/token",
            result=result,
            test_step="token_test",
            notes="Store-bound readonly token exchange requires bcrypt.",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
    except Exception as exc:
        result["http_status"] = getattr(exc, "http_status", result.get("http_status"))
        if str(exc) == "token_auth_failed":
            result["token_test"] = "failed"
            _mark_failed(result, "token_auth_failed", "Naver readonly token exchange failed")
            capability_results.append(_build_capability_record(
                platform="naver",
                capability_key="naver.token_auth",
                capability_name="Naver token auth readonly test",
                api_category="auth",
                endpoint_path="/v1/oauth2/token",
                result=result,
                test_step="token_test",
                notes="Store-bound readonly token exchange failed.",
            ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
        elif result.get("error_code") is None:
            _mark_failed(result, "readonly_request_failed", str(exc))

    capability_results.extend(_build_naver_docs_pending_capability_records(context, result))
    if not result["masked_message"]:
        result["masked_message"] = "Store-bound readonly smoke test completed without returning raw API data."
    return result, capability_results


def _request_naver_token(settings) -> tuple[str, int]:
    context = {
        "client_id": settings.naver_client_id,
        "secret_key": settings.naver_client_secret,
        "api_base": settings.naver_api_base.rstrip("/"),
        "grant_type_used": "SELF",
        "seller_account_id": None,
    }
    return _request_naver_token_from_context(context)


def _run_naver_seller_account_read(context: dict, result: dict, headers: dict[str, str]) -> dict:
    if not NAVER_REAL_SELLER_ACCOUNT_ENDPOINT_CONFIRMED:
        result["seller_or_account_test"] = "skipped"
        if result.get("error_code") is None:
            result["error_code"] = "naver_api_not_implemented"
        return _build_capability_record(
            platform="naver",
            capability_key="naver.seller_account_read",
            capability_name="Naver seller/account readonly test",
            api_category="seller",
            endpoint_path="/v1/seller/account",
            result=result,
            test_step="seller_or_account_test",
            notes="Seller/account readonly endpoint is not confirmed for real store-bound execution yet.",
            forced_test_status="not_tested",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{context['api_base']}/v1/seller/account", headers=headers)
    _step_from_response(result, "seller_or_account_test", response)
    if result["seller_or_account_test"] == "success":
        channel_no = _extract_channel_no(response.json())
        if channel_no:
            result["channel_no_source"] = "seller_account"
        elif context.get("channel_no"):
            result["channel_no_source"] = "credential_extra_config"
        else:
            result["channel_no_source"] = "missing"

    return _build_capability_record(
        platform="naver",
        capability_key="naver.seller_account_read",
        capability_name="Naver seller/account readonly test",
        api_category="seller",
        endpoint_path="/v1/seller/account",
        result=result,
        test_step="seller_or_account_test",
        notes="Readonly seller/account query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _run_naver_product_read(context: dict, result: dict, headers: dict[str, str]) -> dict:
    if not NAVER_REAL_PRODUCT_READ_ENDPOINT_CONFIRMED:
        result["product_read_test"] = "skipped"
        if result.get("error_code") is None:
            result["error_code"] = "naver_api_not_implemented"
        return _build_capability_record(
            platform="naver",
            capability_key="naver.product_read",
            capability_name="Naver product readonly test",
            api_category="products",
            endpoint_path="/v1/products/search",
            result=result,
            test_step="product_read_test",
            notes="Product readonly endpoint is not confirmed for real store-bound execution yet.",
            forced_test_status="not_tested",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}

    params = {"page": 1, "size": 1}
    channel_no = context.get("channel_no")
    if channel_no:
        params["channelNo"] = channel_no
        result["channel_no_source"] = result.get("channel_no_source") or "credential_extra_config"
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{context['api_base']}/v1/products/search", headers=headers, params=params)
    _step_from_response(result, "product_read_test", response)
    return _build_capability_record(
        platform="naver",
        capability_key="naver.product_read",
        capability_name="Naver product readonly test",
        api_category="products",
        endpoint_path="/v1/products/search",
        result=result,
        test_step="product_read_test",
        notes="Readonly product query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _run_naver_order_read(context: dict, result: dict, headers: dict[str, str]) -> dict:
    if not NAVER_REAL_ORDER_READ_ENDPOINT_CONFIRMED:
        result["order_read_test"] = "skipped"
        if result.get("error_code") is None:
            result["error_code"] = "naver_api_not_implemented"
        return _build_capability_record(
            platform="naver",
            capability_key="naver.order_read",
            capability_name="Naver order readonly test",
            api_category="orders",
            endpoint_path="/v1/pay-order/seller/product-orders",
            result=result,
            test_step="order_read_test",
            notes="Order readonly endpoint is not confirmed for real store-bound execution yet.",
            forced_test_status="not_tested",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}

    now = get_utc_now()
    params = {
        "from": (now - timedelta(days=1)).date().isoformat(),
        "to": now.date().isoformat(),
        "page": 1,
        "size": 1,
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{context['api_base']}/v1/pay-order/seller/product-orders", headers=headers, params=params)
    _step_from_response(result, "order_read_test", response)
    return _build_capability_record(
        platform="naver",
        capability_key="naver.order_read",
        capability_name="Naver order readonly test",
        api_category="orders",
        endpoint_path="/v1/pay-order/seller/product-orders",
        result=result,
        test_step="order_read_test",
        notes="Readonly order query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _build_naver_docs_pending_capability_records(context: dict, result: dict) -> list[dict]:
    for step in ("sales_read_test", "settlement_read_test", "customer_inquiry_read_test", "shipping_delivery_read_test"):
        result[step] = "skipped"
    docs_pending = [
        ("naver.sales_read", "Naver sales readonly test", "sales", None, "sales_read_test"),
        ("naver.settlement_read", "Naver settlement readonly test", "settlements", None, "settlement_read_test"),
        ("naver.customer_inquiry_read", "Naver customer inquiry readonly test", "inquiries", None, "customer_inquiry_read_test"),
        ("naver.shipping_delivery_read", "Naver shipping/delivery readonly test", "logistics", None, "shipping_delivery_read_test"),
    ]
    records: list[dict] = []
    for capability_key, capability_name, api_category, endpoint_path, step in docs_pending:
        records.append(_build_capability_record(
            platform="naver",
            capability_key=capability_key,
            capability_name=capability_name,
            api_category=api_category,
            endpoint_path=endpoint_path,
            result=result,
            test_step=step,
            notes="Docs pending. This readonly capability is not implemented in the store-bound smoke test yet.",
            forced_test_status="not_tested",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
    return records


def _extract_channel_no(payload: object) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"channelNo", "channel_no"} and value:
                return str(value)
            found = _extract_channel_no(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _extract_channel_no(item)
            if found:
                return found
    return None


def _run_coupang_smoke_test(settings, result: dict) -> tuple[dict, list[dict]]:
    missing = [
        name
        for name, value in {
            "COUPANG_VENDOR_ID": settings.coupang_vendor_id,
            "COUPANG_ACCESS_KEY": settings.coupang_access_key,
            "COUPANG_SECRET_KEY": settings.coupang_secret_key,
        }.items()
        if not _is_configured(value)
    ]
    if missing:
        _mark_failed(result, "missing_credentials", f"Missing required environment fields: {', '.join(missing)}")
        return result, [result]

    result["configured"] = True
    result["token_test"] = "skipped"
    capability_results = [result]
    try:
        now = get_utc_now()
        order_record, order_step = _run_coupang_order_read(settings, now, result)
        capability_results.append(order_record)
        result["seller_or_account_test"] = order_step["seller_or_account_test"]
        result["order_read_test"] = order_step["order_read_test"]
        result["http_status"] = order_step["http_status"]
        result["error_code"] = order_step["error_code"]
        result["masked_message"] = result["masked_message"] or order_step["masked_message"]

        capability_results.append(_run_coupang_product_read(settings, now, result))
        capability_results.append(_run_coupang_sales_read(settings, now, result))
        capability_results.append(_run_coupang_settlement_read(settings, now, result))
        if not result["masked_message"]:
            result["masked_message"] = "Readonly smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    except Exception as exc:
        _mark_failed(result, "smoke_test_failed", str(exc))
    return result, capability_results


def _run_coupang_order_read(settings, now, platform_result: dict) -> tuple[dict, dict]:
    result = _clone_smoke_result(platform_result, "order_read_test")
    try:
        response = _coupang_get(
            settings,
            f"/v2/providers/openapi/apis/api/v4/vendors/{settings.coupang_vendor_id}/ordersheets",
            urlencode({
                "createdAtFrom": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "createdAtTo": now.strftime("%Y-%m-%d"),
                "status": "ACCEPT",
                "maxPerPage": "1",
            }),
        )
        _step_from_response(result, "order_read_test", response)
        if result["order_read_test"] == "success":
            result["seller_or_account_test"] = "success"
        if not result["masked_message"]:
            result["masked_message"] = "Readonly order smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    return _build_capability_record(
        platform="coupang",
        capability_key="coupang.order_read",
        capability_name="Coupang order read readonly test",
        api_category="orders",
        endpoint_path="/v2/providers/openapi/apis/api/v4/vendors/{vendorId}/ordersheets",
        result=result,
        test_step="order_read_test",
        notes="Readonly order query only. No write operation was executed.",
    ), result


def _run_coupang_product_read(settings, now, platform_result: dict) -> dict:
    result = _clone_smoke_result(platform_result, "product_read_test")
    try:
        response = _coupang_get(
            settings,
            "/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
            urlencode({
                "vendorId": settings.coupang_vendor_id,
                "maxPerPage": "1",
                "createdAt": now.strftime("%Y-%m-%d"),
            }),
        )
        _step_from_response(result, "product_read_test", response)
        if not result["masked_message"]:
            result["masked_message"] = "Readonly product smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    return _build_capability_record(
        platform="coupang",
        capability_key="coupang.product_read",
        capability_name="Coupang product read readonly test",
        api_category="products",
        endpoint_path="/v2/providers/seller_api/apis/api/v1/marketplace/seller-products",
        result=result,
        test_step="product_read_test",
        notes="Readonly product query only. No create/update/delete operation was executed.",
    )


def _run_coupang_sales_read(settings, now, platform_result: dict) -> dict:
    result = _clone_smoke_result(platform_result, "sales_read_test")
    try:
        response = _coupang_get(
            settings,
            "/v2/providers/openapi/apis/api/v1/revenue-history",
            urlencode({
                "vendorId": settings.coupang_vendor_id,
                "recognitionDateFrom": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "recognitionDateTo": now.strftime("%Y-%m-%d"),
                "token": "",
                "maxPerPage": "1",
            }),
        )
        _step_from_response(result, "sales_read_test", response)
        if not result["masked_message"]:
            result["masked_message"] = "Readonly sales smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    return _build_capability_record(
        platform="coupang",
        capability_key="coupang.sales_read",
        capability_name="Coupang sales detail readonly test",
        api_category="sales",
        endpoint_path="/v2/providers/openapi/apis/api/v1/revenue-history",
        result=result,
        test_step="sales_read_test",
        notes="Readonly sales detail query only. No write operation was executed.",
    )


def _run_coupang_settlement_read(settings, now, platform_result: dict) -> dict:
    result = _clone_smoke_result(platform_result, "settlement_read_test")
    try:
        response = _coupang_get(
            settings,
            "/v2/providers/marketplace_openapi/apis/api/v1/settlement-histories",
            urlencode({
                "revenueRecognitionYearMonth": now.strftime("%Y-%m"),
            }),
        )
        _step_from_response(result, "settlement_read_test", response)
        if not result["masked_message"]:
            result["masked_message"] = "Readonly settlement smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    return _build_capability_record(
        platform="coupang",
        capability_key="coupang.settlement_read",
        capability_name="Coupang settlement readonly test",
        api_category="settlements",
        endpoint_path="/v2/providers/marketplace_openapi/apis/api/v1/settlement-histories",
        result=result,
        test_step="settlement_read_test",
        notes="Readonly settlement query only. No write operation was executed.",
    )


def _clone_smoke_result(result: dict, step: str) -> dict:
    cloned = dict(result)
    for key in SMOKE_STEPS:
        cloned[key] = result.get(key, "skipped")
    cloned[step] = "skipped"
    return cloned


def _build_capability_record(
    platform: str,
    capability_key: str,
    capability_name: str,
    api_category: str,
    endpoint_path: str,
    result: dict,
    test_step: str,
    notes: str,
    forced_test_status: str | None = None,
) -> dict:
    return {
        "platform": platform,
        "capability_key": capability_key,
        "capability_name": capability_name,
        "api_category": api_category,
        "endpoint_path": endpoint_path,
        "test_mode": "real_readonly",
        "test_status": forced_test_status or _step_status_from_result(result, test_step),
        "http_status": result.get("http_status"),
        "error_code": result.get("error_code"),
        "permission_result": _permission_result(result),
        "rate_limit_summary": None,
        "response_fields_observed": _response_fields_observed(result),
        "tested_at": result.get("tested_at") or get_utc_now().isoformat(),
        "notes": notes,
    }


def _permission_result(result: dict) -> str:
    if result.get("error_code") == "ip_not_allowed":
        return "IP allowlist rejected the readonly request."
    if result.get("error_code") == "auth_failed":
        return "Authentication or permission rejected the readonly request."
    if result.get("error_code") == "token_auth_failed":
        return "Token exchange was rejected by the readonly authentication path."
    return "Readonly smoke-test did not expose credential values or raw external response payloads."


def _response_fields_observed(result: dict) -> str:
    statuses = [f"{step}={result.get(step, 'skipped')}" for step in SMOKE_STEPS]
    return "; ".join(statuses)


def _step_status_from_result(result: dict, step: str) -> str:
    if result.get("error_code") in {"missing_credentials", "naver_api_not_implemented", "seller_account_id_missing"}:
        return "not_tested"
    if result.get("error_code") in {"auth_failed", "ip_not_allowed"}:
        return "permission_required"
    if result.get("error_code"):
        return "tested_failed"
    if result.get(step) == "success":
        return "tested_success"
    if result.get(step) == "skipped":
        return "not_tested"
    return "tested_failed"


def _persist_real_readonly_capability_results(db: Session, results: list[dict]) -> dict[str, int]:
    persisted: dict[str, int] = {}
    if not results:
        return persisted

    tested_at = get_utc_now()
    for result in results:
        if result.get("test_mode") != "real_readonly":
            continue
        store_id = result.get("store_id")
        credential_id = result.get("credential_id")
        if store_id is None or credential_id is None:
            continue

        capability = db.scalars(
            select(ApiCapabilityCheck)
            .where(
                ApiCapabilityCheck.platform == result["platform"],
                ApiCapabilityCheck.capability_key == result["capability_key"],
            )
            .order_by(ApiCapabilityCheck.id.asc())
        ).first()
        if capability is None:
            capability = ApiCapabilityCheck(
                platform=result["platform"],
                capability_key=result["capability_key"],
                capability_name=result["capability_name"],
                api_category=result["api_category"],
                endpoint_path=result["endpoint_path"],
                method="POST",
                required_credential_type="store-bound encrypted API credential",
                ordinary_store_supported="unknown",
                test_status=result["test_status"],
                test_mode="real_readonly",
                response_fields_summary=result["response_fields_observed"],
                error_codes_summary="real_api_test_disabled, credential_not_ready, credential_decrypt_failed, dependency_missing, token_auth_failed, auth_failed, ip_not_allowed, readonly_request_failed, naver_api_not_implemented, seller_account_id_missing",
                data_usefulness="medium",
                first_phase_candidate=False,
                sales_source_type="not_applicable",
                notes=result["notes"],
                last_checked_at=tested_at,
            )
            db.add(capability)
            db.flush()

        item = ApiCapabilityTestResult(
            store_id=store_id,
            credential_id=credential_id,
            capability_id=capability.id,
            test_mode=result["test_mode"],
            test_status=result["test_status"],
            http_status=result.get("http_status"),
            error_code=result.get("error_code"),
            permission_result=result.get("permission_result"),
            rate_limit_summary=result.get("rate_limit_summary"),
            response_fields_observed=result.get("response_fields_observed"),
            tested_at=tested_at,
            notes=result.get("notes"),
        )
        db.add(item)
        db.flush()
        capability.test_status = item.test_status
        capability.last_checked_at = tested_at
        persisted[result["capability_key"]] = item.id

    db.commit()
    return persisted


def _coupang_get(settings, path: str, query_string: str) -> httpx.Response:
    signed_date = get_utc_now().strftime("%y%m%dT%H%M%SZ")
    message = f"{signed_date}GET{path}{query_string}"
    signature = hmac.new(
        settings.coupang_secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"CEA algorithm=HmacSHA256, access-key={settings.coupang_access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )
    url = f"https://api-gateway.coupang.com{path}?{query_string}"
    with httpx.Client(timeout=10.0) as client:
        return client.get(url, headers={"Authorization": authorization})
