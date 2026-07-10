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


class NaverReadonlyAuthError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        *,
        http_status: int | None = None,
        safe_keyword_flags: dict[str, bool] | None = None,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.http_status = http_status
        self.safe_keyword_flags = safe_keyword_flags or _empty_naver_safe_keyword_flags()
        self.business_error_hint = _naver_business_error_hint(error_code)


NAVER_CAPABILITY_MAP = {
    "naver.token_auth": {
        "capability_key": "naver.token_auth",
        "capability_name": "Naver token auth readonly test",
        "api_category": "auth",
        "endpoint_path": "/v1/oauth2/token",
        "method": "POST",
        "docs_confirmed": True,
        "implemented_now": True,
        "safe_to_real_test": True,
        "token_type_required": "SELF_or_SELLER",
        "account_id_required": "SELLER_only",
        "channel_no_required": False,
        "blocked_reason": None,
    },
    "naver.seller_account_read": {
        "capability_key": "naver.seller_account_read",
        "capability_name": "Naver seller/account readonly test",
        "api_category": "seller",
        "endpoint_path": "/v1/seller/account",
        "method": "GET",
        "docs_confirmed": True,
        "implemented_now": True,
        "safe_to_real_test": True,
        "token_type_required": "SELF_or_SELLER",
        "account_id_required": "SELLER_only",
        "channel_no_required": False,
        "blocked_reason": None,
    },
    "naver.seller_channels_read": {
        "capability_key": "naver.seller_channels_read",
        "capability_name": "Naver seller/channels readonly test",
        "api_category": "seller",
        "endpoint_path": "/v1/seller/channels",
        "method": "GET",
        "docs_confirmed": True,
        "implemented_now": True,
        "safe_to_real_test": True,
        "token_type_required": "SELF_or_SELLER",
        "account_id_required": "SELLER_only",
        "channel_no_required": False,
        "blocked_reason": None,
    },
    "naver.product_read": {
        "capability_key": "naver.product_read",
        "capability_name": "Naver product readonly test",
        "api_category": "products",
        "endpoint_path": "/v1/products/search",
        "method": "POST",
        "docs_confirmed": True,
        "docs_reference_version": "current/2.81.0",
        "endpoint_confirmed": True,
        "request_params_confirmed": "partial",
        "minimum_request_body_confirmed": True,
        "minimum_request_body_shape": "page_size_only",
        "status_filter_field": "productStatusTypes",
        "status_filter_confirmed": True,
        "response_field_paths_confirmed": "partial",
        "real_preview_gate_implemented": True,
        "preview_endpoint_implemented": True,
        "grant_confirmed": "partial",
        "implemented_now": True,
        "safe_to_real_test": False,
        "token_type_required": "SELF_or_SELLER_docs_review_pending",
        "account_id_required": "SELLER_only_docs_review_pending",
        "channel_no_required": False,
        "preview_endpoint_planned": True,
        "preferred_preview_strategy": "planned_naver_product_preview_endpoint",
        "blocked_reason": "Preview endpoint exists, but formal product sync remains blocked. Only the explicit size=1 readonly micro-preview gate may call the minimum page/size request body.",
    },
    "naver.order_read": {
        "capability_key": "naver.order_read",
        "capability_name": "Naver order readonly test",
        "api_category": "orders",
        "endpoint_path": "/v1/pay-order/seller/product-orders/last-changed-statuses",
        "method": "GET",
        "docs_confirmed": True,
        "docs_reference_version": "current/2.81.0",
        "endpoint_confirmed": "partial",
        "feed_endpoint": "/v1/pay-order/seller/product-orders/last-changed-statuses",
        "detail_endpoint": "/v1/pay-order/seller/product-orders/query",
        "deprecated_or_unconfirmed_endpoint": "/v1/pay-order/seller/product-orders",
        "request_params_confirmed": "partial",
        "grant_confirmed": "partial",
        "implemented_now": True,
        "safe_to_real_test": False,
        "token_type_required": "SELF_or_SELLER_docs_review_pending",
        "account_id_required": "SELLER_only_docs_review_pending",
        "channel_no_required": "unknown",
        "preview_endpoint_planned": True,
        "preferred_preview_strategy": "last_changed_feed_then_detail_query",
        "blocked_reason": "Preview strategy and request parameters are not fully implemented. The old direct product-orders draft path is deprecated_or_unconfirmed and must not be called.",
    },
    "naver.sales_read": {
        "capability_key": "naver.sales_read",
        "capability_name": "Naver sales readonly test",
        "api_category": "sales",
        "endpoint_path": None,
        "method": None,
        "docs_confirmed": False,
        "implemented_now": False,
        "safe_to_real_test": False,
        "token_type_required": "docs_pending",
        "account_id_required": "docs_pending",
        "channel_no_required": "docs_pending",
        "blocked_reason": "A safe readonly sales endpoint has not been locked down from official docs yet.",
    },
    "naver.settlement_read": {
        "capability_key": "naver.settlement_read",
        "capability_name": "Naver settlement readonly test",
        "api_category": "settlements",
        "endpoint_path": "/v1/pay-settle/settle/case",
        "method": "GET",
        "docs_confirmed": True,
        "implemented_now": False,
        "safe_to_real_test": False,
        "token_type_required": "docs_confirmation_pending",
        "account_id_required": "docs_confirmation_pending",
        "channel_no_required": "docs_confirmation_pending",
        "blocked_reason": "The endpoint is documented, but the readonly smoke-test has not confirmed grant and parameter semantics yet.",
    },
    "naver.customer_inquiry_read": {
        "capability_key": "naver.customer_inquiry_read",
        "capability_name": "Naver customer inquiry readonly test",
        "api_category": "inquiries",
        "endpoint_path": "/v1/pay-user/inquiries",
        "method": "GET",
        "docs_confirmed": True,
        "implemented_now": False,
        "safe_to_real_test": False,
        "token_type_required": "docs_confirmation_pending",
        "account_id_required": "docs_confirmation_pending",
        "channel_no_required": "docs_confirmation_pending",
        "blocked_reason": "The endpoint is documented, but the readonly smoke-test has not confirmed grant and request semantics yet.",
    },
    "naver.shipping_delivery_read": {
        "capability_key": "naver.shipping_delivery_read",
        "capability_name": "Naver shipping/delivery readonly test",
        "api_category": "logistics",
        "endpoint_path": None,
        "method": None,
        "docs_confirmed": False,
        "implemented_now": False,
        "safe_to_real_test": False,
        "token_type_required": "docs_pending",
        "account_id_required": "docs_pending",
        "channel_no_required": "docs_pending",
        "blocked_reason": "A dedicated shipping/delivery readonly smoke-test endpoint has not been confirmed from docs yet.",
    },
}
NAVER_SCOPE_DEFAULT = "token_auth"
NAVER_SCOPE_ALL = "all"
NAVER_CAPABILITY_SCOPES = {
    "token_auth",
    "seller_account",
    "seller_channels",
    "product_read",
    "order_read",
    NAVER_SCOPE_ALL,
}
NAVER_SCOPE_TO_CAPABILITIES = {
    "token_auth": ["naver.token_auth"],
    "seller_account": ["naver.token_auth", "naver.seller_account_read"],
    "seller_channels": ["naver.token_auth", "naver.seller_channels_read"],
    "product_read": ["naver.product_read"],
    "order_read": ["naver.order_read"],
    NAVER_SCOPE_ALL: [
        "naver.token_auth",
        "naver.seller_account_read",
        "naver.seller_channels_read",
        "naver.product_read",
        "naver.order_read",
        "naver.sales_read",
        "naver.settlement_read",
        "naver.customer_inquiry_read",
        "naver.shipping_delivery_read",
    ],
}
NAVER_CAPABILITY_TO_STEP = {
    "naver.token_auth": "token_test",
    "naver.seller_account_read": "seller_or_account_test",
    "naver.seller_channels_read": "seller_or_account_test",
    "naver.product_read": "product_read_test",
    "naver.order_read": "order_read_test",
    "naver.sales_read": "sales_read_test",
    "naver.settlement_read": "settlement_read_test",
    "naver.customer_inquiry_read": "customer_inquiry_read_test",
    "naver.shipping_delivery_read": "shipping_delivery_read_test",
}

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


def _naver_capability_meta(capability_key: str) -> dict:
    meta = NAVER_CAPABILITY_MAP.get(capability_key)
    if meta is None:
        raise KeyError(f"Unknown Naver capability key: {capability_key}")
    return meta


def _build_naver_capability_mapping_summary() -> list[dict]:
    return [
        {
            "capability_key": meta["capability_key"],
            "endpoint": meta["endpoint_path"],
            "method": meta["method"],
            "docs_confirmed": meta["docs_confirmed"],
            "docs_reference_version": meta.get("docs_reference_version"),
            "endpoint_confirmed": meta.get("endpoint_confirmed", meta["docs_confirmed"]),
            "request_params_confirmed": meta.get("request_params_confirmed"),
            "minimum_request_body_confirmed": meta.get("minimum_request_body_confirmed"),
            "minimum_request_body_shape": meta.get("minimum_request_body_shape"),
            "status_filter_field": meta.get("status_filter_field"),
            "status_filter_confirmed": meta.get("status_filter_confirmed"),
            "response_field_paths_confirmed": meta.get("response_field_paths_confirmed"),
            "real_preview_gate_implemented": meta.get("real_preview_gate_implemented", False),
            "preview_endpoint_implemented": meta.get("preview_endpoint_implemented", False),
            "grant_confirmed": meta.get("grant_confirmed"),
            "implemented_now": meta["implemented_now"],
            "safe_to_real_test": meta["safe_to_real_test"],
            "token_type_required": meta["token_type_required"],
            "account_id_required": meta["account_id_required"],
            "channel_no_required": meta["channel_no_required"],
            "preview_endpoint_planned": meta.get("preview_endpoint_planned", False),
            "preferred_preview_strategy": meta.get("preferred_preview_strategy"),
            "feed_endpoint": meta.get("feed_endpoint"),
            "detail_endpoint": meta.get("detail_endpoint"),
            "deprecated_or_unconfirmed_endpoint": meta.get("deprecated_or_unconfirmed_endpoint"),
            "blocked_reason": meta["blocked_reason"],
        }
        for meta in NAVER_CAPABILITY_MAP.values()
    ]


def _naver_forced_test_status(capability_key: str) -> str | None:
    meta = _naver_capability_meta(capability_key)
    if meta["safe_to_real_test"]:
        return None
    return "not_tested"


def _resolve_naver_capability_scope(capability_scope: str | None) -> str:
    if capability_scope is None:
        return NAVER_SCOPE_DEFAULT
    normalized = capability_scope.strip().lower()
    if normalized not in NAVER_CAPABILITY_SCOPES:
        raise ValueError(f"Unsupported Naver capability scope: {capability_scope}")
    return normalized


def _naver_scope_capabilities(capability_scope: str) -> list[str]:
    return list(NAVER_SCOPE_TO_CAPABILITIES[capability_scope])


def _naver_step_for_capability(capability_key: str) -> str | None:
    return NAVER_CAPABILITY_TO_STEP.get(capability_key)


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


def _build_naver_business_status_summary(result: dict) -> dict:
    token_status = result.get("token_test", "skipped")
    seller_status = result.get("seller_or_account_test", "skipped")
    channel_observed = bool(result.get("channel_no_observed"))
    channel_persisted = bool(result.get("channel_no_persisted"))
    multiple_channels = bool(result.get("multiple_channels_observed"))
    error_hint = result.get("business_error_hint") or _naver_business_error_hint(result.get("error_code"))

    if token_status == "success":
        auth_message = "Naver 平台授权检测成功。"
    elif token_status == "failed":
        auth_message = error_hint or "Naver 平台授权检测失败，请检查 Client ID / Client Secret 或 API 权限。"
    else:
        auth_message = "Naver 平台授权暂未检测。"

    if seller_status == "success":
        channels_message = "店铺频道信息读取成功，系统已确认该 Naver 凭证可读取频道信息。"
    elif seller_status == "failed":
        channels_message = error_hint or "店铺频道信息读取失败，请检查 API 权限或平台授权状态。"
    else:
        channels_message = "店铺频道信息暂未读取。"

    if multiple_channels:
        channel_message = "识别到多个店铺频道，需要人工确认后再保存频道编号。"
    elif channel_persisted:
        channel_message = "已识别并保存店铺频道编号。"
    elif channel_observed:
        channel_message = "已识别店铺频道编号，但本次未写入凭证配置。"
    elif result.get("channel_no_configured"):
        channel_message = "店铺频道编号已配置。"
    else:
        channel_message = "暂未识别到店铺频道编号，后续商品/订单同步可能需要补充或自动识别 channel_no。"

    return {
        "platform_auth_status": auth_message,
        "seller_channels": channels_message,
        "channel_no": channel_message,
        "product_order_guardrail": "为避免误触真实业务数据，商品/订单接口当前仍处于保护状态，暂未开放真实请求。",
    }


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
        "business_error_hint": None,
        "safe_keyword_flags": _empty_naver_safe_keyword_flags(),
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
        "channel_no_observed": False,
        "channel_no_configured": False,
        "channel_no_persisted": False,
        "multiple_channels_observed": False,
        "business_status_summary": {},
        "capability_result_ids": {},
        "capability_mapping": _build_naver_capability_mapping_summary(),
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
        "channel_no_observed": False,
        "channel_no_configured": False,
        "channel_no_persisted": False,
        "multiple_channels_observed": False,
        "business_status_summary": {},
        "capability_result_ids": {},
        "capability_mapping": _build_naver_capability_mapping_summary(),
    })
    return result


def _mark_failed(result: dict, error_code: str, message: str) -> dict:
    result["error_code"] = error_code
    result["masked_message"] = _mask_message(message)
    result["business_error_hint"] = _naver_business_error_hint(error_code)
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


def _empty_naver_safe_keyword_flags() -> dict[str, bool]:
    return {
        "ip_keyword": False,
        "allowed_keyword": False,
        "whitelist_keyword": False,
        "gateway_keyword": False,
        "invalid_keyword": False,
        "client_keyword": False,
        "client_secret_keyword": False,
        "credential_keyword": False,
        "permission_keyword": False,
        "forbidden_keyword": False,
        "not_allowed_keyword": False,
        "product_keyword": False,
    }


def _naver_safe_keyword_flags_from_text(text: str | None) -> dict[str, bool]:
    normalized = str(text or "").lower()
    compact = normalized.replace("_", " ").replace("-", " ")
    return {
        "ip_keyword": "ip" in compact,
        "allowed_keyword": "allowed" in compact,
        "whitelist_keyword": any(token in compact for token in ["whitelist", "white list", "allowlist", "allow list"]),
        "gateway_keyword": "gateway" in compact,
        "invalid_keyword": "invalid" in compact,
        "client_keyword": "client" in compact,
        "client_secret_keyword": any(token in compact for token in ["client secret", "clientsecret", "client_secret", "secret key"]),
        "credential_keyword": "credential" in compact,
        "permission_keyword": "permission" in compact,
        "forbidden_keyword": "forbidden" in compact,
        "not_allowed_keyword": any(token in compact for token in ["not allowed", "not_allowed", "no permission"]),
        "product_keyword": "product" in compact,
    }


def _classify_naver_forbidden_response(
    response: httpx.Response,
    *,
    stage: str,
    scope: str | None = None,
) -> tuple[str, dict[str, bool]]:
    flags = _naver_safe_keyword_flags_from_text(getattr(response, "text", ""))
    if response.status_code not in {401, 403}:
        return "readonly_request_failed", flags

    ip_signal = flags["ip_keyword"] and (
        flags["allowed_keyword"]
        or flags["whitelist_keyword"]
        or flags["gateway_keyword"]
        or flags["not_allowed_keyword"]
    )
    if ip_signal:
        return "ip_not_allowed", flags

    credential_signal = flags["invalid_keyword"] and (
        flags["client_keyword"] or flags["client_secret_keyword"] or flags["credential_keyword"]
    )
    if credential_signal:
        return "credential_invalid", flags

    permission_signal = flags["permission_keyword"] or flags["forbidden_keyword"] or flags["not_allowed_keyword"]
    if scope == "product" and response.status_code == 403 and permission_signal:
        return "product_api_not_allowed", flags
    if permission_signal:
        return "permission_forbidden", flags
    if stage == "token":
        return "token_auth_failed", flags
    return "unknown_forbidden", flags


def _naver_business_error_hint(error_code: str | None) -> str | None:
    if error_code == "ip_not_allowed":
        return "Naver API request IP is not allowed. Check API usage IP / allowed IP settings in Naver Commerce API Center."
    if error_code == "credential_invalid":
        return "Naver connection credentials may be invalid. Check Client ID / Client Secret."
    if error_code == "permission_forbidden":
        return "Naver API permission is insufficient. Check whether this app has the required API permission."
    if error_code == "product_api_not_allowed":
        return "Naver product API permission is not available. Check whether product API access is granted."
    if error_code == "token_auth_failed":
        return "Naver access validation failed. Check connection credentials or platform permission settings."
    if error_code == "unknown_forbidden":
        return "Naver access was rejected. Check IP allowlist and API permission settings."
    if error_code == "auth_failed":
        return "Naver access validation failed. Check connection credentials or platform permission settings."
    return None


def _is_ip_not_allowed(response: httpx.Response) -> bool:
    return _classify_naver_forbidden_response(response, stage="readonly")[0] == "ip_not_allowed"


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


def _step_from_naver_response(
    result: dict,
    step: str,
    response: httpx.Response,
    *,
    scope: str | None = None,
) -> bool:
    result["http_status"] = response.status_code
    if 200 <= response.status_code < 300:
        result[step] = "success"
        result["safe_keyword_flags"] = _empty_naver_safe_keyword_flags()
        return True
    result[step] = "failed"
    error_code, safe_keyword_flags = _classify_naver_forbidden_response(
        response,
        stage="readonly",
        scope=scope,
    )
    result["safe_keyword_flags"] = safe_keyword_flags
    if error_code == "readonly_request_failed":
        _mark_failed(result, error_code, f"{step} failed with HTTP {response.status_code}")
    else:
        _mark_failed(result, error_code, f"{step} failed with classified readonly response")
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
    result["channel_no_configured"] = bool(_naver_channel_no_from_extra_config(credential.extra_config))

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
        error_code, safe_keyword_flags = _classify_naver_forbidden_response(
            response,
            stage="token",
            scope="token",
        )
        raise NaverReadonlyAuthError(
            error_code,
            http_status=response.status_code,
            safe_keyword_flags=safe_keyword_flags,
        )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise NaverReadonlyAuthError(
            "token_auth_failed",
            http_status=response.status_code,
            safe_keyword_flags=_empty_naver_safe_keyword_flags(),
        )
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
    capability_scope: str | None = None,
    persist_channel_no: bool = False,
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
            capability_scope=_resolve_naver_capability_scope(capability_scope),
            persist_channel_no=persist_channel_no,
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
            if channel_no:
                result["channel_no_source"] = "seller_account"
            elif settings.naver_channel_no:
                result["channel_no_source"] = "env_fallback"
            else:
                result["channel_no_source"] = "missing"
            result["product_read_test"] = "skipped"
            result["order_read_test"] = "skipped"
            result["sales_read_test"] = "skipped"
            result["settlement_read_test"] = "skipped"
            result["customer_inquiry_read_test"] = "skipped"
            result["shipping_delivery_read_test"] = "skipped"
            if not result["masked_message"]:
                result["masked_message"] = "Readonly env fallback completed token and seller/account checks only. Product/order remain guardrail_blocked."
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
    capability_scope: str,
    persist_channel_no: bool = False,
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
                result["channel_no_configured"] = bool(_naver_channel_no_from_extra_config(credential.extra_config))
        result["test_mode"] = "disabled"
        result["enabled"] = False
        result["business_status_summary"] = _build_naver_business_status_summary(result)
        return _mark_failed(result, "real_api_test_disabled", "REAL_API_TEST_ENABLED is false"), []

    context, result = _load_naver_smoke_context(db, store_id, credential_id)
    capability_results: list[dict] = []
    selected_capabilities = _naver_scope_capabilities(capability_scope)

    result["enabled"] = True
    result["capability_scope"] = capability_scope
    if context is None:
        result["business_status_summary"] = _build_naver_business_status_summary(result)
        capability_results.append(_build_naver_capability_record(
            capability_key="naver.token_auth",
            result=result,
            test_step="token_test",
            notes="Store-bound readonly smoke test failed before token exchange.",
        ) | {"store_id": store_id, "credential_id": result.get("credential_id")})
        return result, capability_results

    if capability_scope in {"product_read", "order_read"}:
        selected_capability = selected_capabilities[0]
        if not _naver_capability_meta(selected_capability)["safe_to_real_test"]:
            _mark_failed(result, "guardrail_blocked", "Selected readonly capability is guardrail_blocked and was not executed.")
            capability_results.append(_build_naver_scope_docs_pending_record(context, result, selected_capability))
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

    try:
        access_token, token_status = _request_naver_token_from_context(context)
        result["http_status"] = token_status
        result["token_test"] = "success"
        token_record = _build_naver_capability_record(
            capability_key="naver.token_auth",
            result=result,
            test_step="token_test",
            notes=f"Store-bound readonly token exchange using {context['grant_type_used']} grant.",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}
        capability_results.append(token_record)

        if capability_scope == "token_auth":
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly token exchange completed without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        headers = {"Authorization": f"Bearer {access_token}"}
        if capability_scope == "seller_account":
            capability_results.append(_run_naver_seller_account_read(context, result, headers))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly seller/account smoke test completed without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        if capability_scope == "seller_channels":
            capability_results.append(_run_naver_seller_channels_read(
                context,
                result,
                headers,
                db=db,
                persist_channel_no=persist_channel_no,
            ))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly seller/channels smoke test completed without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        if capability_scope == "product_read":
            capability_results.append(_run_naver_product_read(context, result, headers))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly product smoke test completed without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        if capability_scope == "order_read":
            capability_results.append(_run_naver_order_read(context, result, headers))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly order smoke test completed without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        capability_results.append(_run_naver_seller_account_read(context, result, headers))
        if result["seller_or_account_test"] != "success":
            capability_results.extend(_build_naver_docs_pending_capability_records(
                context,
                result,
                [capability for capability in selected_capabilities if capability not in {"naver.token_auth", "naver.seller_account_read"}],
            ))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly smoke test stopped after seller/account failure without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        capability_results.append(_run_naver_seller_channels_read(context, result, headers))
        if result["seller_or_account_test"] != "success":
            capability_results.extend(_build_naver_docs_pending_capability_records(
                context,
                result,
                [capability for capability in selected_capabilities if capability not in {"naver.token_auth", "naver.seller_account_read", "naver.seller_channels_read"}],
            ))
            if not result["masked_message"]:
                result["masked_message"] = "Store-bound readonly smoke test stopped after seller/channels failure without returning raw API data."
            result["business_status_summary"] = _build_naver_business_status_summary(result)
            return result, capability_results

        for guarded_capability in ["naver.product_read", "naver.order_read"]:
            if guarded_capability not in selected_capabilities:
                continue
            capability_results.append(_build_naver_scope_docs_pending_record(context, result, guarded_capability))

        capability_results.extend(_build_naver_docs_pending_capability_records(
            context,
            result,
            [
                capability
                for capability in selected_capabilities
                if capability in {
                    "naver.sales_read",
                    "naver.settlement_read",
                    "naver.customer_inquiry_read",
                    "naver.shipping_delivery_read",
                }
            ],
        ))
    except ImportError:
        result["token_test"] = "failed"
        _mark_failed(result, "dependency_missing", "bcrypt dependency is required for Naver client_secret_sign")
        capability_results.append(_build_naver_capability_record(
            capability_key="naver.token_auth",
            result=result,
            test_step="token_test",
            notes="Store-bound readonly token exchange requires bcrypt.",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
    except NaverReadonlyAuthError as exc:
        result["http_status"] = exc.http_status
        result["token_test"] = "failed"
        result["safe_keyword_flags"] = exc.safe_keyword_flags
        _mark_failed(result, exc.error_code, exc.business_error_hint or "Naver readonly token exchange failed")
        capability_results.append(_build_naver_capability_record(
            capability_key="naver.token_auth",
            result=result,
            test_step="token_test",
            notes="Store-bound readonly token exchange failed.",
        ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
    except Exception as exc:
        result["http_status"] = getattr(exc, "http_status", result.get("http_status"))
        if str(exc) == "token_auth_failed":
            result["token_test"] = "failed"
            _mark_failed(result, "token_auth_failed", "Naver readonly token exchange failed")
            capability_results.append(_build_naver_capability_record(
                capability_key="naver.token_auth",
                result=result,
                test_step="token_test",
                notes="Store-bound readonly token exchange failed.",
            ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]})
        elif result.get("error_code") is None:
            _mark_failed(result, "readonly_request_failed", str(exc))

    if not result["masked_message"]:
        result["masked_message"] = "Store-bound readonly smoke test completed without returning raw API data."
    result["business_status_summary"] = _build_naver_business_status_summary(result)
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
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{context['api_base']}/v1/seller/account", headers=headers)
    _step_from_naver_response(result, "seller_or_account_test", response, scope="seller_account")
    if result["seller_or_account_test"] == "success":
        channel_no = _extract_channel_no(response.json())
        if channel_no:
            result["channel_no_source"] = "seller_account"
        elif context.get("channel_no"):
            result["channel_no_source"] = "credential_extra_config"
        else:
            result["channel_no_source"] = "missing"

    return _build_naver_capability_record(
        capability_key="naver.seller_account_read",
        result=result,
        test_step="seller_or_account_test",
        notes="Readonly seller/account query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _run_naver_product_read(context: dict, result: dict, headers: dict[str, str]) -> dict:
    params = {"page": 1, "size": 1}
    channel_no = context.get("channel_no")
    if channel_no:
        params["channelNo"] = channel_no
        result["channel_no_source"] = result.get("channel_no_source") or "credential_extra_config"
    with httpx.Client(timeout=10.0) as client:
        response = client.post(f"{context['api_base']}/v1/products/search", headers=headers, params=params)
    _step_from_naver_response(result, "product_read_test", response, scope="product")
    return _build_naver_capability_record(
        capability_key="naver.product_read",
        result=result,
        test_step="product_read_test",
        notes="Readonly product query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _run_naver_order_read(context: dict, result: dict, headers: dict[str, str]) -> dict:
    _mark_failed(
        result,
        "guardrail_blocked",
        "Naver order readonly preview must use last-changed feed then detail query. The direct product-orders draft path is deprecated_or_unconfirmed.",
    )
    result["order_read_test"] = "skipped"
    return _build_naver_capability_record(
        capability_key="naver.order_read",
        result=result,
        test_step="order_read_test",
        notes="Readonly order query was not executed. Future preview must use last-changed feed then detail query.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _run_naver_seller_channels_read(
    context: dict,
    result: dict,
    headers: dict[str, str],
    db: Session | None = None,
    persist_channel_no: bool = False,
) -> dict:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{context['api_base']}/v1/seller/channels", headers=headers)
    _step_from_naver_response(result, "seller_or_account_test", response, scope="seller_channels")
    if result["seller_or_account_test"] == "success":
        channel_numbers = _extract_channel_no_values(response.json())
        result["channel_no_observed"] = bool(channel_numbers)
        result["multiple_channels_observed"] = len(channel_numbers) > 1
        if len(channel_numbers) == 1:
            result["channel_no_source"] = "seller_channels"
            if persist_channel_no and db is not None:
                _persist_naver_channel_no(db, context, channel_numbers[0])
                result["channel_no_persisted"] = True
                result["channel_no_configured"] = True
        elif len(channel_numbers) > 1:
            result["channel_no_source"] = "seller_channels_multiple"
        elif context.get("channel_no"):
            result["channel_no_source"] = "credential_extra_config"
            result["channel_no_configured"] = True
        else:
            result["channel_no_source"] = "missing"
    return _build_naver_capability_record(
        capability_key="naver.seller_channels_read",
        result=result,
        test_step="seller_or_account_test",
        notes="Readonly seller/channels query only. No write operation was executed.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _build_naver_scope_docs_pending_record(
    context: dict,
    result: dict,
    capability_key: str,
) -> dict:
    step = _naver_step_for_capability(capability_key)
    if step is not None and result.get(step, "skipped") == "skipped":
        result[step] = "skipped"
    return _build_naver_capability_record(
        capability_key=capability_key,
        result=result,
        test_step=step,
        notes="Docs pending. This readonly capability is not approved for real tested_success in the store-bound smoke test yet.",
    ) | {"store_id": context["store_id"], "credential_id": context["credential_id"]}


def _build_naver_docs_pending_capability_records(
    context: dict,
    result: dict,
    capability_keys: list[str] | None = None,
) -> list[dict]:
    selected_keys = capability_keys or [
        "naver.seller_channels_read",
        "naver.sales_read",
        "naver.settlement_read",
        "naver.customer_inquiry_read",
        "naver.shipping_delivery_read",
    ]
    records: list[dict] = []
    for capability_key in selected_keys:
        records.append(_build_naver_scope_docs_pending_record(context, result, capability_key))
    return records


def _persist_naver_channel_no(db: Session, context: dict, channel_no: str) -> None:
    credential = db.get(ApiCredential, context["credential_id"])
    if credential is None or credential.store_id != context["store_id"] or credential.platform != "naver":
        raise ApiError(
            message="Naver credential is not available for channel_no persistence",
            error_code="CREDENTIAL_NOT_READY",
            status_code=400,
            detail={"store_id": context["store_id"], "credential_id": context["credential_id"]},
        )
    extra_config = dict(credential.extra_config or {})
    extra_config["channel_no"] = channel_no.strip()
    credential.extra_config = extra_config
    db.flush()


def _extract_channel_no_values(payload: object) -> list[str]:
    values: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, value in item.items():
                if key in {"channelNo", "channel_no"} and value:
                    text = str(value).strip()
                    if text and text not in values:
                        values.append(text)
                    continue
                visit(value)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(payload)
    return values


def _extract_channel_no(payload: object) -> str | None:
    values = _extract_channel_no_values(payload)
    if values:
        return values[0]
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


def _build_naver_capability_record(
    capability_key: str,
    result: dict,
    notes: str,
    test_step: str | None = None,
    forced_test_status: str | None = None,
) -> dict:
    meta = _naver_capability_meta(capability_key)
    meta_forced_status = _naver_forced_test_status(capability_key)
    note_parts = [notes]
    if meta["blocked_reason"]:
        note_parts.append(f"Guardrail: {meta['blocked_reason']}")
    return _build_capability_record(
        platform="naver",
        capability_key=meta["capability_key"],
        capability_name=meta["capability_name"],
        api_category=meta["api_category"],
        endpoint_path=meta["endpoint_path"],
        method=meta["method"],
        result=result,
        test_step=test_step,
        notes=" ".join(note_parts),
        forced_test_status=forced_test_status or meta_forced_status,
        extra_fields={
            "docs_confirmed": meta["docs_confirmed"],
            "docs_reference_version": meta.get("docs_reference_version"),
            "endpoint_confirmed": meta.get("endpoint_confirmed", meta["docs_confirmed"]),
            "request_params_confirmed": meta.get("request_params_confirmed"),
            "grant_confirmed": meta.get("grant_confirmed"),
            "implemented_now": meta["implemented_now"],
            "safe_to_real_test": meta["safe_to_real_test"],
            "token_type_required": meta["token_type_required"],
            "account_id_required": meta["account_id_required"],
            "channel_no_required": meta["channel_no_required"],
            "preview_endpoint_planned": meta.get("preview_endpoint_planned", False),
            "preferred_preview_strategy": meta.get("preferred_preview_strategy"),
            "feed_endpoint": meta.get("feed_endpoint"),
            "detail_endpoint": meta.get("detail_endpoint"),
            "deprecated_or_unconfirmed_endpoint": meta.get("deprecated_or_unconfirmed_endpoint"),
            "blocked_reason": meta["blocked_reason"],
        },
    )


def _build_capability_record(
    platform: str,
    capability_key: str,
    capability_name: str,
    api_category: str,
    endpoint_path: str | None,
    result: dict,
    test_step: str | None,
    notes: str,
    forced_test_status: str | None = None,
    method: str | None = None,
    extra_fields: dict | None = None,
) -> dict:
    record = {
        "platform": platform,
        "capability_key": capability_key,
        "capability_name": capability_name,
        "api_category": api_category,
        "endpoint_path": endpoint_path,
        "method": method,
        "test_mode": "real_readonly",
        "test_status": forced_test_status or _step_status_from_result(result, test_step),
        "http_status": result.get("http_status"),
        "error_code": result.get("error_code"),
        "business_error_hint": result.get("business_error_hint"),
        "safe_keyword_flags": dict(result.get("safe_keyword_flags") or _empty_naver_safe_keyword_flags()),
        "permission_result": _permission_result(result),
        "rate_limit_summary": None,
        "response_fields_observed": _response_fields_observed(result),
        "tested_at": result.get("tested_at") or get_utc_now().isoformat(),
        "notes": notes,
    }
    if extra_fields:
        record.update(extra_fields)
    return record


def _permission_result(result: dict) -> str:
    if result.get("error_code") == "ip_not_allowed":
        return "IP allowlist rejected the readonly request."
    if result.get("error_code") == "credential_invalid":
        return "Credential fields were rejected by the readonly authentication path."
    if result.get("error_code") == "permission_forbidden":
        return "Readonly request was rejected by the API permission layer."
    if result.get("error_code") == "product_api_not_allowed":
        return "Readonly product API request was rejected by the product permission layer."
    if result.get("error_code") == "unknown_forbidden":
        return "Readonly request returned a forbidden response without a stronger safe classification."
    if result.get("error_code") == "auth_failed":
        return "Authentication or permission rejected the readonly request."
    if result.get("error_code") == "token_auth_failed":
        return "Token exchange was rejected by the readonly authentication path."
    return "Readonly smoke-test did not expose credential values or raw external response payloads."


def _response_fields_observed(result: dict) -> str:
    statuses = [f"{step}={result.get(step, 'skipped')}" for step in SMOKE_STEPS]
    safe_keyword_flags = [
        key
        for key, enabled in (result.get("safe_keyword_flags") or {}).items()
        if enabled
    ]
    statuses.extend([
        f"path_kind={result.get('path_kind', 'unknown')}",
        f"capability_scope={result.get('capability_scope', 'unknown')}",
        f"grant_type_used={result.get('grant_type_used', 'unknown')}",
        f"seller_account_id_configured={bool(result.get('seller_account_id_configured'))}",
        f"channel_no_source={result.get('channel_no_source', 'unknown')}",
        f"channel_no_observed={bool(result.get('channel_no_observed'))}",
        f"channel_no_configured={bool(result.get('channel_no_configured'))}",
        f"channel_no_persisted={bool(result.get('channel_no_persisted'))}",
        f"multiple_channels_observed={bool(result.get('multiple_channels_observed'))}",
        f"http_status={result.get('http_status')}",
        f"error_code={result.get('error_code')}",
        f"safe_keyword_flags={','.join(safe_keyword_flags) if safe_keyword_flags else 'none'}",
    ])
    return "; ".join(statuses)


def _step_status_from_result(result: dict, step: str) -> str:
    if step is None:
        return "not_tested"
    if result.get("error_code") in {"missing_credentials", "naver_api_not_implemented", "seller_account_id_missing", "guardrail_blocked"}:
        return "not_tested"
    if result.get("error_code") in {"auth_failed", "ip_not_allowed", "permission_forbidden", "product_api_not_allowed", "unknown_forbidden"}:
        return "permission_required"
    if result.get("error_code") in {"credential_invalid", "token_auth_failed"}:
        return "tested_failed"
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
                method=result.get("method"),
                required_credential_type="store-bound encrypted API credential",
                ordinary_store_supported="unknown",
                test_status=result["test_status"],
                test_mode="real_readonly",
                response_fields_summary=result["response_fields_observed"],
                error_codes_summary="real_api_test_disabled, credential_not_ready, credential_decrypt_failed, dependency_missing, token_auth_failed, credential_invalid, permission_forbidden, product_api_not_allowed, unknown_forbidden, auth_failed, ip_not_allowed, readonly_request_failed, guardrail_blocked, naver_api_not_implemented, seller_account_id_missing",
                data_usefulness="medium",
                first_phase_candidate=False,
                sales_source_type="not_applicable",
                notes=result["notes"],
                last_checked_at=tested_at,
            )
            db.add(capability)
            db.flush()
        else:
            capability.method = result.get("method")
            capability.endpoint_path = result.get("endpoint_path")
            capability.capability_name = result["capability_name"]
            capability.api_category = result["api_category"]
            capability.notes = result["notes"]

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
