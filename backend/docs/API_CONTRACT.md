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
| GET | `/api/v1/api-credentials/readiness` | None | None | No | No secret, token, password, encrypted, or decrypted values |
| POST | `/api/v1/api-credentials/smoke-test` | None | `{ "platform": "naver" | "coupang" | "all", "mode": "readonly" }` | No | No secret, token, password, authorization header, request signature, encrypted, or decrypted values |
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

`auth_status` is local credential metadata plus future test state. Readiness does not call external APIs, and smoke-test does not persist or return token values.

`GET /api/v1/api-credentials/readiness` has two roles. The env fallback path reads only local environment variable presence and is a temporary developer fallback, not the final multi-store credential path. The formal multi-store path is store-bound: `GET /api/v1/api-credentials/readiness?store_id=...` checks the selected store, its active platform credential, decryptability, and token metadata without calling Naver or Coupang. Neither path returns access keys, secret keys, client secrets, tokens, passwords, or encrypted values.

Naver readiness requires only `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, and `NAVER_API_BASE` (default: `https://api.commerce.naver.com/external`). `NAVER_CHANNEL_NO`, `NAVER_ACCESS_TOKEN`, `NAVER_REFRESH_TOKEN`, and `NAVER_TOKEN_EXPIRES_AT` are not manual readiness requirements. Coupang readiness requires `COUPANG_VENDOR_ID`, `COUPANG_ACCESS_KEY`, and `COUPANG_SECRET_KEY`.

`POST /api/v1/api-credentials/smoke-test` is a read-only smoke test endpoint. The env fallback path is a developer fallback only and does not write `ApiCapabilityTestResult`. The formal Naver path is store-bound and requires `store_id` plus an active credential. If `REAL_API_TEST_ENABLED=false`, the endpoint returns disabled results and does not create an external HTTP client or send any external request. The only accepted mode is `readonly`; write-like modes are rejected by validation. When testing is enabled, the endpoint may attempt minimal read-only token/account/channel checks and returns only step statuses plus capability mapping metadata. Naver product and order readonly checks remain protected by guardrails and are not sent to the real API.

```text
platform
enabled
configured
http_status
token_test
seller_or_account_test
product_read_test
order_read_test
settlement_read_test
error_code
masked_message
tested_at
capability_mapping
```

The smoke-test response must not include access tokens, refresh tokens, client secrets, access keys, secret keys, authorization headers, request signatures, full channel numbers, or raw external response bodies. Naver capability records may include non-sensitive guardrail metadata such as `docs_confirmed`, `docs_reference_version`, `endpoint_confirmed`, `request_params_confirmed`, `grant_confirmed`, `preview_endpoint_planned`, `preferred_preview_strategy`, `safe_to_real_test`, and blocked reasons so docs-pending capabilities cannot be mistaken for real tested success. `REAL_API_WRITE_ENABLED=false` keeps write operations disabled and this endpoint never modifies products, orders, shipments, returns, exchanges, or customer inquiries.

### Planned Naver Product / Order Preview Guardrail

Naver Commerce API documentation is tracked against the current / 2.81.0 documentation line. Product and order preview are planned but not open for real requests in this phase:

| Planned API | Current status | Naver reference route | Preview strategy |
|---|---|---|---|
| `POST /api/v1/sync/products/naver/preview` | Endpoint exists; default blocked; size=1 real micro preview requires explicit gate; `safe_to_real_test=false` | `POST /v1/products/search` | Defaults to `guardrail_blocked`; `real_preview=true` may call only the minimum `{"page":1,"size":1}` body |
| `POST /api/v1/sync/orders/naver/preview` | Scaffold endpoint exists; default blocked; real micro preview requires explicit gate | `GET /v1/pay-order/seller/product-orders/last-changed-statuses`, then `POST /v1/pay-order/seller/product-orders/query` | Read last-changed feed first, then optionally query one detail by `productOrderId` |

The older direct order draft route `GET /v1/pay-order/seller/product-orders` is treated as `deprecated_or_unconfirmed` and must not be used for real readonly testing. Product and order preview, when implemented later, must be preview-only:

```text
No writes to products or orders
No token persistence
No raw response persistence
No client secret, token, Authorization header, signature, request header, or full channel_no output
Sanitized counts/samples only
```

`POST /api/v1/sync/products/naver/preview` currently returns HTTP 200 with a blocked scaffold payload so the frontend can show business status without treating product read as available:

```json
{
  "store_id": 8,
  "credential_id": 7,
  "platform": "naver",
  "preview_type": "products",
  "source_type": "naver_product_preview",
  "guardrail_status": "blocked",
  "test_status": "not_tested",
  "error_code": "guardrail_blocked",
  "page": 1,
  "size": 20,
  "has_more": false,
  "would_create": 0,
  "would_update": 0,
  "sample_ids": [],
  "field_observation": {
    "channel_no_configured": true,
    "request_params_confirmed": false,
    "safe_to_real_test": false
  },
  "business_status_summary": [
    "商品读取暂未开放真实测试",
    "当前系统已完成 Naver 账号与频道前置检测",
    "为避免误触真实业务数据，商品接口仍处于保护状态",
    "后续需要完成商品 preview 小流量真实测试后，才可进入本地同步"
  ],
  "semantic_notice": "Readonly preview scaffold only. No local product rows were written."
}
```

For the blocked scaffold path, the service does not create a Naver HTTP client, does not request a token, does not call `POST /v1/products/search`, does not write `products`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`. `real_preview=true` is an explicit micro-preview gate, not formal product sync availability. It is restricted to the approved local Naver store/credential, `page=1`, `size=1`, and `status` null/ALL with `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, decryptable credential, configured channel number, and `minimum_request_body_confirmed=true`. Credential decryption only means the local encrypted secret is readable; it does not mean product API access is available.

Phase 6D-6G confirms the official minimum product search request body for the micro gate as `{"page":1,"size":1}`. The public request may pass `status=null` or `status=ALL`, but the Naver request must not send internal `ALL`, `productStatusTypes`, keyword, seller product id, date filters, search keyword fields, channel product numbers, origin product numbers, group product numbers, or full channel number. A successful preview may return `preview_status=success` or `success_empty`, masked `sample_ids`, and field-observation booleans such as product id/name/status/price/stock presence. It still never writes `products`, never writes `SyncLog`, never writes `ApiCapabilityTestResult tested_success`, never saves token/raw response, and never marks formal product sync as available.

Phase 6D-6H adds product field-mapping summary fields to the preview response:

```text
product_field_mapping_summary
observed_field_names
missing_field_names
mapping_readiness
channel_products_summary
```

The summary is design metadata only. `external_product_id` is planned to prefer `contents[].channelProducts[].channelProductNo` when exactly one channel product is observed, with `contents[].originProductNo` retained as sanitized metadata. Product name maps to `products.name`, sale status to `products.status`, display status to sanitized `products.raw_data.display_status`, price to `products.price` as KRW Decimal, and stock to `products.stock_quantity` as int. Multiple `channelProducts` return only counts and `multiple_observed=true`; preview never expands raw channel payloads and never writes multiple products. The existing `products` table is sufficient for a first Naver snapshot, but `originProductNo`, `channelProductNo`, display status, and channel count must stay in sanitized `raw_data` metadata in a future sync phase. Raw Naver product responses, long HTML, image-detail payloads, tokens, headers, signatures, client secrets, and full channel numbers must not be returned or persisted.

Phase 6D-6I adds a local sync dry-run diff to Naver product preview:

```json
{
  "dry_run_diff": {
    "would_create": 0,
    "would_update": 0,
    "would_skip": 0,
    "skip_reasons": {
      "multiple_channel_products": 0,
      "missing_external_product_id": 0,
      "missing_product_name": 0,
      "missing_optional_fields": 0
    },
    "matched_existing_count": 0,
    "incoming_candidate_count": 0,
    "ready_for_local_sync": false,
    "source_type": "naver_product_preview_dry_run"
  }
}
```

The dry-run reads local `products` by `store_id + platform=naver + external_product_id` only to estimate create/update counts. It does not write `products`, does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, and does not imply formal product sync availability. Multiple `channelProducts`, missing `channelProductNo`, and missing `productName` are skipped; missing price or stock is reported under `missing_optional_fields` without forcing a skip. Top-level `would_create` and `would_update` mirror `dry_run_diff` for compatibility.

Phase 6D-6J is only the write-design contract for a later Naver product local sync phase. It does not add a public sync endpoint and does not write any table. A future approved write must require `real_sync=true`, `store_id=8`, `credential_id=7`, `page=1`, `size=1`, `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, and a dry-run candidate that is single-channel and has both `channelProductNo` and `productName`. It may create or update at most one `products` row using `store_id + platform=naver + external_product_id`.

Future Naver product local sync field mapping:

```text
store_id                 request store id
platform                 naver
external_product_id      contents[].channelProducts[].channelProductNo
name                     contents[].channelProducts[].productName, max 300 chars
status                   contents[].channelProducts[].statusType
price                    salePrice | discountPrice | price, Decimal, default 0 if missing
currency                 KRW
stock_quantity           stockQuantity | quantity | inventory, int, default 0 if missing
source_type              naver_real_sync
last_synced_at           UTC write time
```

Future `products.raw_data` must be sanitized metadata only:

```json
{
  "platform_origin_product_no": "masked-or-bounded-id",
  "platform_channel_product_id": "masked-or-bounded-id",
  "display_status": "ON",
  "channel_products_count": 1,
  "source_preview_id_hash": "id-hash-*",
  "mapping_version": "naver_product_v1",
  "synced_from": "naver_product_preview",
  "raw_response_saved": false
}
```

Future local sync must skip multiple `channelProducts`, missing external IDs, and missing names. Missing price or stock records `missing_optional_fields` but does not block the row. Before the first approved write, back up `backend/codex1.db`; after writing, read back `products where store_id=8 and platform='naver'`. If field mapping is wrong, recover by deleting the single row or restoring the backup. A future sanitized `SyncLog` may use `sync_type=naver_product_local_sync`, `requested_size=1`, created/updated/skipped counts, skip reasons, and `raw_response_saved=false`. It must not contain raw Naver responses, HTML, image-detail content, tokens, headers, signatures, client secrets, complete channel numbers, or long descriptions. `ApiCapabilityTestResult tested_success` remains unwritten until a separate capability decision explicitly changes that.

`POST /api/v1/sync/orders/naver/preview` is a readonly micro preview scaffold. The default `real_preview=false` returns `guardrail_status=blocked` before token/HTTP. `real_preview=true` is allowed only for the approved local Naver store/credential, with `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, `page=1`, `size=1`, KST window <= 1 day, and `order_status` null/ALL. It still does not mean Naver order sync is open, and `naver.order_read.safe_to_real_test` remains false.

Phase 6D-6D-Fix2 fixes the feed request to the verified parameter shape: `lastChangedFrom` formatted with milliseconds plus `limitCount=1`, with `lastChangedTo` omitted. Page, size, and order_status remain local preview controls and are not passed through to the Naver feed. When `include_detail=true`, detail lookup runs only if the feed produced a productOrderId, and it queries at most one ID with `POST /v1/pay-order/seller/product-orders/query`. If the feed is empty, detail is skipped with `detail_skipped_reason=no_changed_orders` and the time window is not expanded. Detail responses are reduced to field-observation booleans and sanitized field-name summaries such as `detail_record_observed`, status/product-name presence, buyer/receiver presence booleans, `privacy_fields_suppressed=true`, `raw_response_saved=false`, and `orders_written=false`. It never returns a full URL, query values, raw error body, full order IDs, full productOrderIds, buyer/receiver names, phone numbers, addresses, delivery detail, payment raw payload, raw response bodies, tokens, authorization headers, signatures, or full channel numbers. It does not write `orders`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`.

Current frontend-facing business wording should remain conservative:

```text
商品读取：前置条件部分满足，暂未开放真实测试
订单读取：前置条件部分满足，暂未开放真实测试
商品/订单接口当前仍处于保护状态，等待 preview 实现
```

When `REAL_API_TEST_ENABLED=true`, the smoke-test endpoint may write a store-level `ApiCapabilityTestResult` with `test_mode=real_readonly`. That write is limited to local result metadata: step statuses, `error_code`, `http_status`, `tested_at`, and short operator notes. Public `POST /api/v1/api-capability-results` still rejects manually supplied `real_readonly` payloads; only this readonly smoke-test endpoint can create those records.

Example readiness response:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "real_api_test_enabled": false,
    "real_api_write_enabled": false,
    "platforms": [
      {
        "platform": "coupang",
        "credential_status": "configured",
        "readiness_status": "disabled",
        "fields": {
          "vendor_id": "configured",
          "access_key": "configured",
          "secret_key": "configured"
        }
      }
    ]
  }
}
```

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

`real_readonly` is reserved for the Phase 6C readonly smoke-test endpoint. It must not be created through the generic manual result API.

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

`store_result_summary` is an empty array when `store_id` is not provided. Summary timestamps remain UTC aware strings; frontends should display them in KST. Summary counts are local records only: `docs_only` / `manual` mean documentation or operator notes, `tested_success` is only a record status, and `real_readonly_count` means local readonly smoke-test records exist. The summary endpoint itself does not call Naver or Coupang and does not execute sync.

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
- `real_readonly` test results are reserved for the explicitly approved readonly smoke-test endpoint and cannot be created by the generic manual result API.

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
  "source_type": "mock_sync",
  "last_synced_at": "2026-07-01T00:00:00+00:00",
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
  "order_amount": "129000.00",
  "source_type": "mock_sync",
  "last_synced_at": "2026-07-01T00:00:00+00:00"
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

## Coupang Order Readonly Preview

| Method | Path | Query | Body | store_id | Sensitive Fields |
|---|---|---|---|---:|---|
| POST | `/api/v1/sync/orders/coupang/preview` | None | Preview payload | Required in body | No plaintext credential, signature, header, or raw external response |

Request body:

```json
{
  "store_id": 1,
  "start_date": "2026-06-30",
  "end_date": "2026-07-01",
  "max_pages": 3
}
```

Preview rules:

- `store_id` is required and only that store's Coupang credential is used.
- The inclusive KST business-date window must be 3 days or less.
- `max_pages` defaults to `1` and cannot exceed `3`.
- Preview returns only dry-run metadata such as `would_create`, `would_update`, `sample_ids`, `page_count`, `next_cursor_exists`, and `source_type=real_coupang`.
- Preview never writes into `orders`, never performs platform write operations, and never stores raw external responses, authorization headers, signatures, access keys, or secret keys.
- `SyncLog.raw_summary`, if present, contains masked preview metadata only.
- If `REAL_API_TEST_ENABLED=false`, the endpoint returns `REAL_API_TEST_DISABLED` and must not send any external request.

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
