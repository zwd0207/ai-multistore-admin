# API Contract

Base URL for local development:

```text
http://127.0.0.1:8000
```

All formal APIs use:

```text
/api/v1
```

Swagger UI:

```text
GET /docs
```

## Response Format

Success:

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "message": "店铺不存在",
  "error_code": "STORE_NOT_FOUND",
  "detail": {
    "store_id": 999999
  }
}
```

Sensitive fields are not returned by public APIs:

```text
access_key
secret_key
login_password
password_or_token
encrypted_password_or_token
encrypted_access_key
encrypted_secret_key
encrypted_access_token
encrypted_refresh_token
encrypted_login_password
full phone numbers
full addresses
ID numbers
bank card numbers
real full IP addresses
proxy passwords
remote desktop passwords
```

## Timezone Rules

Business time is fixed to `APP_TIMEZONE=Asia/Seoul`. Windows display timezone is not used as a business-time source. Database datetimes are UTC aware values; older SQLite development rows that come back as naive datetimes are treated as UTC for compatibility.

Daily filters and default daily context use Korean natural days. A KST date is converted to a UTC half-open range `[start, next_start)`. Frontend display should render UTC timestamps such as SyncLog times in KST.

## Health

| Method | Path | store_id | Sensitive Fields |
|---|---|---:|---|
| GET | `/api/v1/health` | No | No |

Response example:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "ok",
    "environment": "development",
    "api_version": "v1"
  }
}
```

## Stores

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| POST | `/api/v1/stores` | None | Store payload | No | No |
| GET | `/api/v1/stores` | `page`, `page_size` | None | No | No |
| GET | `/api/v1/stores/{store_id}` | None | None | Path | No |
| PUT | `/api/v1/stores/{store_id}` | None | Partial store payload | Path | No |
| DELETE | `/api/v1/stores/{store_id}` | None | None | Path | No |

Create body:

```json
{
  "name": "서울뷰티테스트",
  "platform": "naver",
  "country": "KR",
  "language": "ko-KR",
  "status": "active",
  "owner_name": "테스트 담당자",
  "remark": "네이버 스마트스토어 테스트 / 정품 소명 자료"
}
```

List response:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

Common errors: `STORE_NOT_FOUND`, `STORE_NAME_EXISTS`, `VALIDATION_ERROR`.

## Credentials

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| POST | `/api/v1/credentials` | None | Credential payload | Body | Input only, never returned |
| GET | `/api/v1/credentials` | `store_id` optional | None | Optional | No plaintext or encrypted values |
| GET | `/api/v1/credentials/{credential_id}` | None | None | No | No plaintext or encrypted values |
| PUT | `/api/v1/credentials/{credential_id}` | None | Partial credential payload | Optional body | Input only, never returned |
| DELETE | `/api/v1/credentials/{credential_id}` | None | None | No | No plaintext or encrypted values |

Create body:

```json
{
  "store_id": 1,
  "platform": "naver",
  "credential_name": "Naver mock credential",
  "vendor_id": null,
  "client_id": "naver-client-id",
  "access_key": "test access key",
  "secret_key": "test secret key",
  "access_token": "test access token",
  "refresh_token": "test refresh token",
  "token_expires_at": "2026-12-31T00:00:00+00:00",
  "market": "KR",
  "auth_status": "configured",
  "extra_config": {
    "allowed_ip": "127.0.0.1"
  },
  "api_remark": "Local configuration only. No real API validation is performed.",
  "status": "active"
}
```

Response example:

```json
{
  "success": true,
  "message": "created",
  "data": {
    "id": 1,
    "store_id": 1,
    "platform": "naver",
    "credential_name": "Naver mock credential",
    "vendor_id": null,
    "client_id": "naver-client-id",
    "token_expires_at": "2026-12-31T00:00:00+00:00",
    "market": "KR",
    "auth_status": "configured",
    "last_tested_at": null,
    "api_remark": "Local configuration only. No real API validation is performed.",
    "extra_config": {},
    "status": "active",
    "has_access_key": true,
    "has_secret_key": true,
    "has_access_token": true,
    "has_refresh_token": true,
    "created_at": "2026-06-29T00:00:00",
    "updated_at": "2026-06-29T00:00:00"
  }
}
```

`auth_status` is a local configuration or future test status only. This stage does not perform real Naver or Coupang API validation and does not refresh tokens.

Supported `auth_status` values:

```text
not_configured
configured
needs_test
test_failed
test_passed
```

Common errors: `STORE_NOT_FOUND`, `CREDENTIAL_NOT_FOUND`, `ENCRYPTION_KEY_MISSING`, `ENCRYPTION_KEY_INVALID`, `VALIDATION_ERROR`.

## Platform Logins

Platform login credentials are for manual Naver SmartStore / Coupang Wing backend login records only. They are not API keys and this stage does not perform real platform login checks.

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/platform-logins` | `store_id`, `page`, `page_size` | None | Required | No password or encrypted password |
| POST | `/api/v1/platform-logins` | None | Platform login payload | Body | Input password only |
| GET | `/api/v1/platform-logins/{login_id}` | None | None | No | No password or encrypted password |
| PUT | `/api/v1/platform-logins/{login_id}` | None | Partial platform login payload | Optional body | Input password only |

Create body:

```json
{
  "store_id": 1,
  "platform": "naver",
  "login_label": "Naver SmartStore 后台登录",
  "login_account": "operator@example.com",
  "login_password": "test password",
  "email_account_id": 1,
  "device_environment_id": 1,
  "login_status": "unknown",
  "remark": "本地保存人工登录信息，不进行真实登录校验。"
}
```

Response example:

```json
{
  "success": true,
  "message": "created",
  "data": {
    "id": 1,
    "store_id": 1,
    "platform": "naver",
    "login_label": "Naver SmartStore 后台登录",
    "login_account": "operator@example.com",
    "email_account_id": 1,
    "device_environment_id": 1,
    "login_status": "unknown",
    "last_login_check_at": null,
    "remark": "本地保存人工登录信息，不进行真实登录校验。",
    "hasLoginPassword": true,
    "created_at": "2026-06-30T00:00:00",
    "updated_at": "2026-06-30T00:00:00"
  }
}
```

Common errors: `STORE_NOT_FOUND`, `PLATFORM_NOT_SUPPORTED`, `PLATFORM_LOGIN_NOT_FOUND`, `EMAIL_ACCOUNT_NOT_FOUND`, `EMAIL_ACCOUNT_STORE_MISMATCH`, `DEVICE_ENVIRONMENT_NOT_FOUND`, `DEVICE_ENVIRONMENT_STORE_MISMATCH`, `ENCRYPTION_KEY_MISSING`, `ENCRYPTION_KEY_INVALID`, `VALIDATION_ERROR`.

## API Capabilities

API capability records are platform-level docs-only or manual planning records. They do not prove that a selected store credential can call an endpoint. This stage does not call Naver or Coupang, does not use real keys, and does not create real sync results.

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/api-capabilities` | `platform`, `api_category`, `test_status`, `test_mode`, `first_phase_candidate`, `sales_source_type` | None | No | No |
| GET | `/api/v1/api-capabilities/summary` | `store_id` optional, `platform` optional | None | Optional | No secret, token, password, or encrypted values |
| POST | `/api/v1/api-capabilities` | None | Capability payload | No | No |
| GET | `/api/v1/api-capabilities/{capability_id}` | None | None | No | No |
| PUT | `/api/v1/api-capabilities/{capability_id}` | None | Partial capability payload | No | No |

Create body:

```json
{
  "platform": "coupang",
  "capability_key": "orders.list",
  "capability_name": "Coupang order list docs-only check",
  "api_category": "orders",
  "endpoint_path": "/v2/providers/openapi/apis/api/v4/vendors/{vendorId}/ordersheets",
  "method": "GET",
  "required_credential_type": "vendor_id + access_key + secret_key",
  "required_permission": "manual permission note",
  "ordinary_store_supported": "unknown",
  "test_status": "planned",
  "test_mode": "docs_only",
  "request_params_summary": "createdAtFrom, createdAtTo",
  "response_fields_summary": "order id, status, amount fields need future readonly confirmation",
  "error_codes_summary": "permission and throttling codes need future readonly confirmation",
  "data_usefulness": "high",
  "first_phase_candidate": true,
  "sales_source_type": "order-derived",
  "official_doc_url": "https://example.invalid/docs-placeholder",
  "notes": "Platform-level record only."
}
```

Supported `test_status` values:

```text
not_tested
planned
tested_success
tested_failed
unavailable
permission_required
```

Supported `test_mode` values:

```text
docs_only
manual
mock
sandbox
real_readonly
```

`real_readonly` is a future marker for platform-level capability planning only in this stage. There is no real readonly test endpoint in Phase 6B-1.

Summary response:

```json
{
  "semantic_notice": "docs-only/manual/mock/sandbox records do not mean real platform connection or real sync success. tested_success is a record status only, and real_readonly is reserved for a future explicit read-only test stage.",
  "platform_summary": [
    {
      "platform": "naver",
      "total_capabilities": 1,
      "docs_only_count": 0,
      "manual_count": 1,
      "tested_success_count": 0,
      "not_tested_count": 0,
      "permission_required_count": 0,
      "unavailable_count": 0,
      "first_phase_candidate_count": 1,
      "real_readonly_count": 0,
      "last_checked_at": "2026-06-30T00:00:00+00:00"
    }
  ],
  "store_result_summary": [
    {
      "store_id": 1,
      "platform": "naver",
      "total_results": 1,
      "credential_bound_results": 1,
      "docs_only_count": 0,
      "manual_count": 1,
      "mock_count": 0,
      "sandbox_count": 0,
      "tested_success_count": 0,
      "tested_failed_count": 0,
      "permission_required_count": 0,
      "unavailable_count": 0,
      "not_tested_count": 0,
      "latest_tested_at": "2026-06-30T00:00:00+00:00",
      "missing_first_phase_candidates": []
    }
  ],
  "attention_items": []
}
```

`store_result_summary` is an empty array when `store_id` is not provided. Summary timestamps remain UTC aware strings; frontends should display them in KST. Summary counts are local records only: `docs_only` / `manual` mean documentation or operator notes, `tested_success` is only a record status, and `real_readonly_count` is a future marker count. The summary endpoint does not call Naver or Coupang and does not execute sync.

## API Capability Test Results

API capability test results are store and optional credential-level manual records. They can bind a store, an API credential, and a platform capability. This stage stores manual/docs/mock/sandbox notes only and does not decrypt API credentials.

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/api-capability-results` | `store_id`, `credential_id`, `capability_id`, `test_status`, `test_mode` | None | Optional | No secret or token values |
| POST | `/api/v1/api-capability-results` | None | Result payload | Body | No secret or token values |
| GET | `/api/v1/api-capability-results/{result_id}` | None | None | No | No secret or token values |

Create body:

```json
{
  "store_id": 1,
  "credential_id": 1,
  "capability_id": 1,
  "test_mode": "manual",
  "test_status": "planned",
  "http_status": null,
  "error_code": null,
  "permission_result": "Manual planning record only.",
  "rate_limit_summary": null,
  "response_fields_observed": "No real response observed.",
  "notes": "No real Naver/Coupang API call was made."
}
```

Binding rules:

- `store_id` must exist.
- `credential_id`, when provided, must exist and belong to the same store.
- `capability_id` must exist.
- Credential platform must match capability platform.
- `real_readonly` test results are reserved for a future explicitly approved read-only API test endpoint.

Common errors: `API_CAPABILITY_NOT_FOUND`, `API_CAPABILITY_RESULT_NOT_FOUND`, `STORE_NOT_FOUND`, `CREDENTIAL_NOT_FOUND`, `CREDENTIAL_STORE_MISMATCH`, `CREDENTIAL_PLATFORM_MISMATCH`, `INVALID_API_CAPABILITY_FILTER`, `VALIDATION_ERROR`.

## Dashboard and AI Context API Capability Summary

`GET /api/v1/dashboard/summary` includes `api_capability_summary` using the same structure as `/api/v1/api-capabilities/summary`. Existing dashboard fields remain unchanged, including `business_timezone`, `business_date`, `business_day_start`, and `business_day_end`.

`GET /api/v1/ai/daily-context` includes `api_capability_context` using the same structure. This context is intended to tell downstream AI features the current local capability record boundaries. It must not be interpreted as real platform connection status or real sync coverage.

## Sync Logs

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/sync-logs` | `store_id` optional | None | Optional | No |

Response example:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "store_id": 1,
        "platform": "naver",
        "sync_type": "products",
        "status": "success",
        "message": "products mock sync success",
        "raw_summary": {
          "中文": "同步成功",
          "한국어": "동기화 성공"
        }
      }
    ],
    "total": 1
  }
}
```

## Products, Orders, Customer Inquiries

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/products` | `store_id` required, `platform` optional | None | Required | No |
| GET | `/api/v1/orders` | `store_id` required, `platform` optional | None | Required | Only `buyer_masked_phone` |
| GET | `/api/v1/customer-inquiries` | `store_id` required, `platform` optional | None | Required | No |

Product response item:

```json
{
  "id": 1,
  "store_id": 1,
  "platform": "naver",
  "external_product_id": "naver-1-product-mixed",
  "name": "ECCO 골프화 / 中文运营测试",
  "brand": "ECCO",
  "category": "스포츠화",
  "raw_data": {
    "中文": "运营测试",
    "한국어": "골프화"
  }
}
```

Order response item:

```json
{
  "id": 1,
  "store_id": 1,
  "platform": "naver",
  "external_order_id": "naver-1-order-cn",
  "buyer_name": "中文测试买家",
  "buyer_masked_phone": "010-****-1234",
  "product_name": "SK-II 神仙水测试商品",
  "order_amount": "129000.00"
}
```

Inquiry response item:

```json
{
  "id": 1,
  "store_id": 1,
  "platform": "naver",
  "external_inquiry_id": "naver-1-inquiry-mixed",
  "inquiry_type": "authenticity",
  "title": "Naver 정품 소명 / 中文备注",
  "content": "고객문의 처리 후 中文运营备注에 기록해야 합니다."
}
```

Common errors: `STORE_NOT_FOUND`, `PLATFORM_NOT_SUPPORTED`, `VALIDATION_ERROR`.

## Mock Sync

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| POST | `/api/v1/sync/products/mock` | `store_id`, `platform` | None | Required | No |
| POST | `/api/v1/sync/orders/mock` | `store_id`, `platform` | None | Required | No |
| POST | `/api/v1/sync/customer-inquiries/mock` | `store_id`, `platform` | None | Required | No |

Response example:

```json
{
  "success": true,
  "message": "mock sync completed",
  "data": {
    "platform": "naver",
    "store_id": 1,
    "sync_type": "products",
    "write_result": {
      "created": 3,
      "updated": 0,
      "total": 3
    }
  }
}
```

Common errors: `STORE_NOT_FOUND`, `CREDENTIAL_NOT_FOUND`, `PLATFORM_NOT_SUPPORTED`, `ENCRYPTION_KEY_MISSING`.

## Stats

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/stats/sales` | `store_id`, `platform`, `start_date`, `end_date` | None | Optional | No |
| GET | `/api/v1/stats/sales/by-platform` | `store_id`, `start_date`, `end_date` | None | Optional | No |
| GET | `/api/v1/stats/sales/by-date` | `store_id`, `platform`, `start_date`, `end_date` | None | Optional | No |

Date filters are interpreted as KST business dates. `/stats/sales/by-date` groups orders after converting `ordered_at` to KST.

Response example:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "store_id": 1,
    "platform": null,
    "total_orders": 3,
    "total_sales_amount": "916000.00",
    "currency": "KRW",
    "paid_orders": 3,
    "canceled_orders": 0,
    "failed_orders": 0,
    "latest_ordered_at": "2026-06-29T00:00:00"
  }
}
```

Common errors: `STORE_NOT_FOUND`, `PLATFORM_NOT_SUPPORTED`, `INVALID_DATE_FORMAT`.

## Dashboard Summary

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/dashboard/summary` | `store_id`, `platform`, `start_date`, `end_date` | None | Optional | Masked orders only |

Response example:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "store_count": 1,
    "business_timezone": "Asia/Seoul",
    "business_date": "2026-06-30",
    "business_day_start": "2026-06-29T15:00:00+00:00",
    "business_day_end": "2026-06-30T15:00:00+00:00",
    "product_count": 3,
    "order_count": 3,
    "customer_inquiry_count": 3,
    "total_sales_amount": "916000.00",
    "currency": "KRW",
    "latest_sync_logs": [],
    "open_customer_inquiries": 3,
    "recent_orders": [],
    "risk_flags": [
      {
        "code": "OPEN_CUSTOMER_INQUIRIES",
        "level": "info",
        "message": "存在未处理客服咨询 / 미처리 고객문의가 있습니다"
      }
    ]
  }
}
```

Dashboard date filters use KST business dates. Without date filters, dashboard counts are scope totals, not automatically today-only totals.

## AI Daily Context

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/ai/daily-context` | `store_id`, `date` | None | Optional | Masked orders only |

This endpoint returns structured data only. It does not call a model and does not generate final AI prose.

Response example:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "date": "2026-06-30",
    "business_timezone": "Asia/Seoul",
    "business_day_start": "2026-06-29T15:00:00+00:00",
    "business_day_end": "2026-06-30T15:00:00+00:00",
    "scope": {
      "store_id": 1,
      "platform": "naver"
    },
    "sales_summary": {},
    "order_summary": {},
    "customer_inquiry_summary": {},
    "sync_summary": {},
    "risk_flags": [],
    "recommended_focus": []
  }
}
```

If `date` is omitted, the backend uses the current KST business date.

## Operations Support

### Device Environments

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/device-environments` | `store_id`, `page`, `page_size` | None | Required | Labels only |
| POST | `/api/v1/device-environments` | None | Device payload | Body | Labels only |
| GET | `/api/v1/device-environments/{environment_id}` | None | None | No | Labels only |
| PUT | `/api/v1/device-environments/{environment_id}` | None | Partial payload | Optional body | Labels only |
| DELETE | `/api/v1/device-environments/{environment_id}` | None | None | No | Labels only |

Create body:

```json
{
  "store_id": 1,
  "environment_name": "韩国本土运营环境-测试",
  "device_type": "desktop",
  "os_name": "Windows 10",
  "browser_name": "Chrome",
  "ip_label": "韩国住宅IP-测试",
  "proxy_label": "Seoul Proxy Label",
  "status": "active",
  "remark": "用于 Naver / Coupang 店铺运营环境测试，不保存真实代理密码。"
}
```

### Email Accounts

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/email-accounts` | `store_id`, `page`, `page_size` | None | Required | No password/token |
| POST | `/api/v1/email-accounts` | None | Email account payload | Body | Input token only |
| GET | `/api/v1/email-accounts/{email_account_id}` | None | None | No | No password/token |
| PUT | `/api/v1/email-accounts/{email_account_id}` | None | Partial payload | Optional body | Input token only |
| DELETE | `/api/v1/email-accounts/{email_account_id}` | None | None | No | No password/token |

Create body:

```json
{
  "store_id": 1,
  "email_address": "test-store@example.com",
  "provider": "gmail",
  "account_label": "Naver 正品申诉接收邮箱",
  "password_or_token": "test token",
  "status": "active",
  "remark": "네이버 정품 소명 / Coupang 정산 보류 메일 수신 테스트"
}
```

Response contains `has_password_or_token`, not plaintext or encrypted token.

### Important Emails

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/important-emails` | `store_id`, `page`, `page_size` | None | Required | No attachments |
| POST | `/api/v1/important-emails` | None | Important email payload | Body | No attachments |
| GET | `/api/v1/important-emails/{email_id}` | None | None | No | No attachments |
| PUT | `/api/v1/important-emails/{email_id}` | None | Partial payload | Optional body | No attachments |
| DELETE | `/api/v1/important-emails/{email_id}` | None | None | No | No attachments |

Create body:

```json
{
  "store_id": 1,
  "email_account_id": 1,
  "platform": "naver",
  "mail_type": "authenticity",
  "sender": "no-reply@mock.naver.test",
  "subject": "정품 소명 자료 제출 안내",
  "snippet": "카드명세서와 구매영수증 제출이 필요합니다.",
  "body_text": "Naver 正品申诉 / 정품 소명 자료 / 中文运营备注",
  "received_at": "2026-06-29T10:00:00+00:00",
  "status": "unread",
  "priority": "urgent"
}
```

### Appeal Cases

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| GET | `/api/v1/appeal-cases` | `store_id`, `page`, `page_size` | None | Required | No private documents |
| POST | `/api/v1/appeal-cases` | None | Appeal case payload | Body | No private documents |
| GET | `/api/v1/appeal-cases/{case_id}` | None | None | No | No private documents |
| PUT | `/api/v1/appeal-cases/{case_id}` | None | Partial payload | Optional body | No private documents |
| DELETE | `/api/v1/appeal-cases/{case_id}` | None | None | No | No private documents |

Create body:

```json
{
  "store_id": 1,
  "platform": "coupang",
  "case_type": "settlement_hold",
  "case_title": "Coupang 结算扣款申诉测试",
  "case_status": "preparing",
  "external_case_id": "MOCK-CASE-001",
  "summary": "Coupang 정산 보류 / 销售资料准备 / 中文备注",
  "action_required": "准备采购表、销售明细、沟通邮件"
}
```
