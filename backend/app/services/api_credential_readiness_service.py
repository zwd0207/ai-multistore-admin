import base64
import hashlib
import hmac
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.core.timezone import get_utc_now


SMOKE_STEPS = [
    "token_test",
    "seller_or_account_test",
    "product_read_test",
    "order_read_test",
    "settlement_read_test",
]
READINESS_NOTICE = (
    "Readiness only reports whether local environment variables are present. "
    "It does not return credential values, decrypt database credentials, call Naver or Coupang, "
    "refresh tokens, or execute sync."
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


def _new_smoke_result(platform: str) -> dict:
    result = {
        "platform": platform,
        "enabled": False,
        "configured": False,
        "error_code": None,
        "masked_message": "",
        "tested_at": get_utc_now().isoformat(),
    }
    for step in SMOKE_STEPS:
        result[step] = "skipped"
    return result


def _mark_failed(result: dict, error_code: str, message: str) -> dict:
    result["error_code"] = error_code
    result["masked_message"] = _mask_message(message)
    return result


def _mask_message(message: str | None) -> str:
    text = str(message or "")
    if not text:
        return ""
    for field_name in [
        "access_token",
        "refresh_token",
        "client_secret",
        "access_key",
        "secret_key",
        "authorization",
    ]:
        text = text.replace(field_name, field_name)
    return text[:300]


def _is_ip_not_allowed(response: httpx.Response) -> bool:
    text = response.text.lower()
    return response.status_code in {401, 403} and any(token in text for token in ["ip", "whitelist", "white list", "allowed"])


def _step_from_response(result: dict, step: str, response: httpx.Response) -> bool:
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


def get_api_credential_readiness() -> dict:
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
    }


def run_api_credential_smoke_test(platform: str = "all", mode: str = "readonly") -> dict:
    settings = get_settings()
    selected_platforms = ["coupang", "naver"] if platform == "all" else [platform]

    return {
        "semantic_notice": SMOKE_NOTICE,
        "mode": mode,
        "real_api_test_enabled": bool(settings.real_api_test_enabled),
        "real_api_write_enabled": bool(settings.real_api_write_enabled),
        "results": [_run_platform_smoke_test(settings, item) for item in selected_platforms],
    }


def _run_platform_smoke_test(settings, platform: str) -> dict:
    result = _new_smoke_result(platform)
    if not settings.real_api_test_enabled:
        return _mark_failed(result, "real_api_test_disabled", "REAL_API_TEST_ENABLED is false")

    result["enabled"] = True
    if platform == "naver":
        return _run_naver_smoke_test(settings, result)
    return _run_coupang_smoke_test(settings, result)


def _run_naver_smoke_test(settings, result: dict) -> dict:
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
        return _mark_failed(result, "missing_credentials", f"Missing required environment fields: {', '.join(missing)}")

    result["configured"] = True
    try:
        access_token = _request_naver_token(settings)
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
            result["settlement_read_test"] = "skipped"
            if not result["masked_message"]:
                result["masked_message"] = "Readonly smoke test completed without returning raw API data."
    except ImportError:
        result["token_test"] = "failed"
        _mark_failed(result, "dependency_missing", "bcrypt dependency is required for Naver client_secret_sign")
    except httpx.HTTPError as exc:
        _mark_failed(result, "network_error", str(exc))
    except Exception as exc:
        _mark_failed(result, "smoke_test_failed", str(exc))
    return result


def _request_naver_token(settings) -> str:
    import bcrypt

    timestamp = str(int(time.time() * 1000))
    raw = f"{settings.naver_client_id}_{timestamp}".encode("utf-8")
    secret = settings.naver_client_secret.encode("utf-8")
    signed = bcrypt.hashpw(raw, secret)
    client_secret_sign = base64.b64encode(signed).decode("utf-8")
    base = settings.naver_api_base.rstrip("/")
    payload = {
        "client_id": settings.naver_client_id,
        "timestamp": timestamp,
        "client_secret_sign": client_secret_sign,
        "grant_type": "client_credentials",
        "type": "SELF",
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.post(f"{base}/v1/oauth2/token", data=payload)
    if response.status_code in {401, 403}:
        raise RuntimeError("auth_failed")
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("auth_failed")
    return token


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


def _run_coupang_smoke_test(settings, result: dict) -> dict:
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
        return _mark_failed(result, "missing_credentials", f"Missing required environment fields: {', '.join(missing)}")

    result["configured"] = True
    result["token_test"] = "skipped"
    try:
        now = get_utc_now()
        path = f"/v2/providers/openapi/apis/api/v4/vendors/{settings.coupang_vendor_id}/ordersheets"
        query = {
            "createdAtFrom": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "createdAtTo": now.strftime("%Y-%m-%d"),
            "status": "ACCEPT",
            "maxPerPage": "1",
        }
        query_string = urlencode(query)
        response = _coupang_get(settings, path, query_string)
        if _step_from_response(result, "order_read_test", response):
            result["seller_or_account_test"] = "success"
        result["product_read_test"] = "skipped"
        result["settlement_read_test"] = "skipped"
        if not result["masked_message"]:
            result["masked_message"] = "Readonly smoke test completed without returning raw API data."
    except httpx.HTTPError as exc:
        _mark_failed(result, "network_error", str(exc))
    except Exception as exc:
        _mark_failed(result, "smoke_test_failed", str(exc))
    return result


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
