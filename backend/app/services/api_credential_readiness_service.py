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
from app.core.timezone import get_utc_now
from app.models.api_capability import ApiCapabilityCheck, ApiCapabilityTestResult
from app.models.api_credential import ApiCredential
from app.models.store import Store


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
        "http_status": None,
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


def run_api_credential_smoke_test(
    db: Session | None = None,
    platform: str = "all",
    mode: str = "readonly",
) -> dict:
    settings = get_settings()
    selected_platforms = ["coupang", "naver"] if platform == "all" else [platform]
    capability_results: list[dict] = []
    results = []
    for item in selected_platforms:
        platform_result, platform_capability_results = _run_platform_smoke_test(settings, item)
        results.append(platform_result)
        capability_results.extend(platform_capability_results)
    if db is not None and settings.real_api_test_enabled:
        for result in capability_results:
            _record_real_readonly_result(db, result)

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
        return _run_naver_smoke_test(settings, result), [result]
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
        result["http_status"] = getattr(exc.response, "status_code", result.get("http_status"))
        _mark_failed(result, "network_error", str(exc))
    except Exception as exc:
        result["http_status"] = getattr(exc, "http_status", result.get("http_status"))
        _mark_failed(result, "smoke_test_failed", str(exc))
    return result


def _request_naver_token(settings) -> tuple[str, int]:
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
        error = RuntimeError("auth_failed")
        error.http_status = response.status_code
        raise error
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        error = RuntimeError("auth_failed")
        error.http_status = response.status_code
        raise error
    return token, response.status_code


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
    result = _clone_smoke_result(platform_result, "settlement_read_test")
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
        _step_from_response(result, "settlement_read_test", response)
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
        test_step="settlement_read_test",
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
) -> dict:
    return {
        "platform": platform,
        "capability_key": capability_key,
        "capability_name": capability_name,
        "api_category": api_category,
        "endpoint_path": endpoint_path,
        "test_mode": "real_readonly",
        "test_status": _step_status_from_result(result, test_step),
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
    return "Readonly smoke-test did not expose credential values or raw external response payloads."


def _response_fields_observed(result: dict) -> str:
    statuses = [f"{step}={result.get(step, 'skipped')}" for step in SMOKE_STEPS]
    return "; ".join(statuses)


def _step_status_from_result(result: dict, step: str) -> str:
    if result.get("error_code") == "missing_credentials":
        return "not_tested"
    if result.get("error_code") in {"auth_failed", "ip_not_allowed"}:
        return "permission_required"
    if result.get("error_code"):
        return "tested_failed"
    return "tested_success" if result.get(step) == "success" else "tested_failed"


def _record_real_readonly_result(db: Session, result: dict) -> None:
    if result.get("test_mode") != "real_readonly":
        return

    platform = result["platform"]
    store = db.scalars(
        select(Store)
        .where(Store.platform == platform)
        .order_by(Store.id.asc())
    ).first()
    if store is None:
        return

    capability = db.scalars(
        select(ApiCapabilityCheck)
        .where(
            ApiCapabilityCheck.platform == platform,
            ApiCapabilityCheck.capability_key == result["capability_key"],
        )
        .order_by(ApiCapabilityCheck.id.asc())
    ).first()
    if capability is None:
        capability = ApiCapabilityCheck(
            platform=platform,
            capability_key=result["capability_key"],
            capability_name=result["capability_name"],
            api_category=result["api_category"],
            endpoint_path=result["endpoint_path"],
            method="POST",
            required_credential_type="local .env platform credentials",
            ordinary_store_supported="unknown",
            test_status=result["test_status"],
            test_mode="real_readonly",
            response_fields_summary=result["response_fields_observed"],
            error_codes_summary="real_api_test_disabled, missing_credentials, auth_failed, ip_not_allowed, readonly_request_failed, network_error",
            data_usefulness="medium",
            first_phase_candidate=False,
            sales_source_type="not_applicable",
            notes=result["notes"],
            last_checked_at=get_utc_now(),
        )
        db.add(capability)
        db.flush()

    credential = db.scalars(
        select(ApiCredential)
        .where(ApiCredential.store_id == store.id, ApiCredential.platform == platform)
        .order_by(ApiCredential.id.asc())
    ).first()
    tested_at = get_utc_now()
    item = ApiCapabilityTestResult(
        store_id=store.id,
        credential_id=credential.id if credential is not None else None,
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
    capability.test_status = item.test_status
    capability.last_checked_at = tested_at
    db.commit()


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
