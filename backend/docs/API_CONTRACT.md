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

`POST /api/v1/api-credentials/smoke-test` is a read-only smoke test endpoint. The env fallback path is a developer fallback only and does not write `ApiCapabilityTestResult`. The formal Naver path is store-bound and requires `store_id` plus an active credential. If `REAL_API_TEST_ENABLED=false`, the endpoint returns disabled results and does not create an external HTTP client or send any external request. The only accepted mode is `readonly`; write-like modes are rejected by validation. When testing is enabled, the endpoint may attempt minimal read-only token/account/channel checks and returns only step statuses plus capability mapping metadata. Naver product and order readonly checks remain protected by guardrails and are not sent to the real API. For Naver 401/403 responses, the backend now returns only safe classifications such as `ip_not_allowed`, `credential_invalid`, `permission_forbidden`, `product_api_not_allowed`, `token_auth_failed`, or `unknown_forbidden`; it does not return raw response bodies, headers, tokens, or signatures.

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
business_error_hint
safe_keyword_flags
tested_at
capability_mapping
```

The smoke-test response must not include access tokens, refresh tokens, client secrets, access keys, secret keys, authorization headers, request signatures, full channel numbers, or raw external response bodies. Naver capability records may include non-sensitive guardrail metadata such as `docs_confirmed`, `docs_reference_version`, `endpoint_confirmed`, `request_params_confirmed`, `grant_confirmed`, `preview_endpoint_planned`, `preferred_preview_strategy`, `safe_to_real_test`, and blocked reasons so docs-pending capabilities cannot be mistaken for real tested success. `REAL_API_WRITE_ENABLED=false` keeps write operations disabled and this endpoint never modifies products, orders, shipments, returns, exchanges, or customer inquiries.

### Planned Naver Product / Order Preview Guardrail

Naver Commerce API documentation is tracked against the current / 2.81.0 documentation line. Product and order preview are planned but not open for real requests in this phase:

| Planned API | Current status | Naver reference route | Preview strategy |
|---|---|---|---|
| `POST /api/v1/sync/products/naver/preview` | Endpoint exists; default blocked; readonly small-batch preview requires explicit gate; `safe_to_real_test=false` | `POST /v1/products/search` | Defaults to `guardrail_blocked`; `real_preview=true` may call only the minimum `{"page":P,"size":N}` body, with `P in {1,2}` and `N<=5` for `real_sync=false`, while `real_sync=true` remains limited to `page=1,size<=5` |
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

For the blocked scaffold path, the service does not create a Naver HTTP client, does not request a token, does not call `POST /v1/products/search`, does not write `products`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`. `real_preview=true` is an explicit micro-preview gate, not formal product sync availability. It is restricted to the approved local Naver store/credential, `status` null/ALL, `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, decryptable credential, configured channel number, and `minimum_request_body_confirmed=true`. The current split guardrail is: readonly preview keeps `real_sync=false` and allows `page in {1,2}` with `size<=5`, while the approved local sync path still requires `real_sync=true`, `page=1`, and `size<=5`. Credential decryption only means the local encrypted secret is readable; it does not mean product API access is available.

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
    "would_no_change": 0,
    "would_refresh_only": 0,
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

The dry-run reads local `products` by `store_id + platform=naver + external_product_id` only to estimate local impact. It does not write `products`, does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, and does not imply formal product sync availability. Multiple `channelProducts`, missing `channelProductNo`, and missing `productName` are skipped; missing price or stock is reported under `missing_optional_fields` without forcing a skip. Top-level `would_create` and `would_update` mirror `dry_run_diff` for compatibility.

Phase 6D-6M extends that readonly preview into a small-batch dry-run without opening batch sync. When `real_preview=true` and `real_sync=false`, the only allowed upstream body is `{"page":P,"size":N}` with `P in {1,2}` and `1 <= N <= 5`; no `productStatusTypes`, keyword, seller-product filters, channel number, date range, or product-number filters may be sent. Local sync does not inherit the second-page allowance and remains capped at `page=1`. `sample_ids` may contain up to 5 masked hashes. `dry_run_diff` also carries:

```json
{
  "single_channel_product_count": 0,
  "multiple_channel_products_count": 0,
  "missing_external_product_id_count": 0,
  "missing_product_name_count": 0,
  "missing_price_count": 0,
  "missing_stock_count": 0
}
```

In this readonly small-batch phase, `dry_run_diff.ready_for_local_sync` is intentionally fixed to `false` even if create/update candidates are found. That is a guardrail signal, not a parser failure. It prevents the preview response from being misread as a writable approval. `real_sync=false` continues to guarantee no `products`, no `SyncLog`, and no `ApiCapabilityTestResult tested_success` writes.

Phase 6D-6N-Pre-Impl adds an enhanced dry-run explanation layer before any batch write approval. `dry_run_diff` may include `diff_summary`, `create_reasons`, `update_reasons`, `changed_fields`, `unchanged_fields`, `missing_optional_fields`, `risk_flags`, `upsert_key_summary`, and `write_safety_summary`. Update diffs expose only field names and local product ids; they do not expose raw Naver values or full external ids. Create explanations use `external_product_id_not_found_locally` and confirm that the upsert key is `store_id + platform=naver + external_product_id`, sourced from `channelProductNo|channelProductId`; product-name matching and fuzzy matching remain disabled. Additional skip reasons are `duplicate_external_product_id_in_same_batch`, `invalid_status_shape`, `invalid_numeric_shape_for_price`, and `invalid_numeric_shape_for_stock`. Missing price or stock is still optional metadata, not an automatic skip.

Phase 6D-6P tightens the business meaning of the dry-run counters:

- `would_create`: local row not found by `store_id + platform=naver + external_product_id`
- `would_update`: business fields would change (`name`, `status`, `price`, `currency`, `stock_quantity`)
- `would_refresh_only`: only sync metadata would change (`last_synced_at`, `source_type`, sanitized `raw_data`)
- `would_no_change`: local row exists and neither business fields nor sync metadata would change
- `matched_existing_count`: local rows matched by key, regardless of whether they land in `would_update`, `would_refresh_only`, or `would_no_change`

`update_reasons` now refers to business-field updates only. `no_change_reasons` and `refresh_only_reasons` explain the matched-existing subsets that should not be presented to ordinary users as product-content updates. Dry-run remains preview-only: no `products`, no `SyncLog`, no `ApiCapabilityTestResult tested_success`, and no raw response/token/header/signature persistence.

Phase 6D-6R prepares the next expansion step without enabling larger writes. Readonly preview may now inspect `page=2,size=5` so pagination boundaries can be validated before any new write approval. `dry_run_diff.pagination_overlap_summary` includes `requested_page`, `requested_size`, `matched_existing_candidate_count`, `matched_existing_candidate_types`, masked match samples, and a `recommended_action` of either `continue_readonly_review` or `stop_and_review_pagination`. For non-first-page preview, any `matched_existing_count > 0` is treated as overlap risk and forces `stop_and_review_pagination`. `write_safety_summary` now also makes two blockers explicit: `missing_optional_fields_block_write_approval=true` and `non_first_page_match_requires_manual_review=true`. `size=10`, `page>2`, cross-page automatic writes, and formal batch sync remain blocked.

The enhanced dry-run is still preview-only. It does not execute `real_sync=true`, does not write `products`, does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, and does not save raw responses, tokens, headers, signatures, full channel numbers, HTML, image-detail content, or product raw payloads.

Phase 6D-6J is the write-design contract carried forward into the approved Naver product local sync small-batch path. It does not add a public batch sync endpoint. The approved write requires `real_sync=true`, `store_id=8`, `credential_id=7`, `page=1`, `size<=5`, `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, and dry-run candidates that are single-channel and have both `channelProductNo` and `productName`. It may create or update at most 5 `products` rows using `store_id + platform=naver + external_product_id`.

Phase 6D-6K implements that approved small-batch test on the existing preview endpoint. The request must include `real_preview=true` and `real_sync=true`; `real_sync=true` without `real_preview=true` is blocked. The external Naver call is still readonly and remains `POST /v1/products/search` with body `{"page":1,"size":N}` where `1 <= N <= 5`. The local write path only runs after a successful preview response and only for up to 5 single-channel candidates on `page=1`. It creates or updates at most 5 `products` rows, returns a sanitized `local_sync_result`, and still does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, does not save tokens, and does not save raw Naver response payloads. This is not batch product sync and does not mark `naver.product_read.safe_to_real_test` as formally open.

Phase 6D-6N completes the first controlled local sync small-batch test on `page=1,size=5`, with 4 creates and 1 update, while keeping `SyncLog` unwritten, `ApiCapabilityTestResult tested_success` unchanged, and `raw_response_saved=false`. The local store now holds 5 Naver product rows for `store_id=8`. Phase 6D-6Q then verifies the post-sync readonly semantics: the same batch now returns `matched_existing_count=5`, `would_create=0`, `would_update=0`, `would_refresh_only=5`, and `would_skip=0`. That confirms the current first page is stable without declaring formal batch sync open.

Phase 6D-6S then validates `page=2,size=5` as a real readonly dry-run and returns `preview_status=success_empty`. That means there is currently no second-page product candidate to preview or write. The result does not change `products`, does not write `SyncLog`, does not add `ApiCapabilityTestResult tested_success`, and does not justify `page=2` local sync approval. `size=10`, `page=3`, and formal batch sync remain blocked.

Phase 6D-6T closes the current Naver product line by tightening safe error classification. Token or readonly 403 responses now surface only safe enums plus safe keyword flags:

- `ip_not_allowed`: IP / allowlist / gateway-IP signal detected
- `credential_invalid`: invalid client or client-secret style signal detected
- `permission_forbidden`: permission or forbidden signal detected outside the product-specific path
- `product_api_not_allowed`: token succeeded but the product API returned a permission-style 403
- `token_auth_failed`: token exchange failed without a stronger safe classification
- `unknown_forbidden`: readonly 403 without a stronger safe classification

The response may include `http_status`, `error_code`, `business_error_hint`, and `safe_keyword_flags`, but it must not include raw response text, request headers, `Authorization`, token values, signatures, `bcrypt` output, full `channel_no`, or full product identifiers.

`local_sync_result` response shape:

```json
{
  "requested": true,
  "status": "success",
  "source_type": "naver_real_sync",
  "created_count": 1,
  "updated_count": 0,
  "skipped_count": 0,
  "skip_reasons": {
    "multiple_channel_products": 0,
    "missing_external_product_id": 0,
    "missing_product_name": 0,
    "missing_optional_fields": 0
  },
  "sample_ids": ["id-hash-*"],
  "products_written": true,
  "sync_log_written": false,
  "capability_tested_success_written": false,
  "raw_response_saved": false,
  "write_limit": 5
}
```

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

Future local sync must skip multiple `channelProducts`, missing external IDs, and missing names. Missing price or stock records `missing_optional_fields`, increments `missing_price_count` or `missing_stock_count`, and now blocks write approval through `write_safety_summary.missing_optional_fields_block_write_approval=true`. For `page>1` readonly preview, any matched existing record must trigger `pagination_overlap_summary.recommended_action=stop_and_review_pagination` before another stage is considered. Before every approved write, back up `backend/codex1.db`; after writing, read back `products where store_id=8 and platform='naver'`. If field mapping is wrong, recover by deleting the affected small batch or restoring the backup. A future sanitized `SyncLog` may use `sync_type=naver_product_local_sync`, `requested_size`, created/updated/skipped counts, skip reasons, and `raw_response_saved=false`. It must not contain raw Naver responses, HTML, image-detail content, tokens, headers, signatures, client secrets, complete channel numbers, or long descriptions. `ApiCapabilityTestResult tested_success` remains unwritten until a separate capability decision explicitly changes that.

`POST /api/v1/sync/orders/naver/preview` is a readonly micro preview scaffold. The default `real_preview=false` returns `guardrail_status=blocked` before token/HTTP. `real_preview=true` is allowed only for the approved local Naver store/credential, with `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, `page=1`, `size=1`, KST window <= 7 days, and `order_status` null/ALL. It still does not mean Naver order sync is open, and `naver.order_read.safe_to_real_test` remains false.

Phase 6D-6D-Fix2 fixes the feed request to the verified parameter shape: `lastChangedFrom` formatted with milliseconds plus `limitCount=1`, with `lastChangedTo` omitted. Page, size, and order_status remain local preview controls and are not passed through to the Naver feed. When `include_detail=true`, detail lookup runs only if the feed produced a productOrderId, and it queries at most one ID with `POST /v1/pay-order/seller/product-orders/query`. If the feed is empty, detail is skipped with `detail_skipped_reason=no_changed_orders` and the time window is not expanded. Detail responses are reduced to field-observation booleans and sanitized field-name summaries such as `detail_record_observed`, status/product-name presence, buyer/receiver presence booleans, `privacy_fields_suppressed=true`, `raw_response_saved=false`, and `orders_written=false`. It never returns a full URL, query values, raw error body, full order IDs, full productOrderIds, buyer/receiver names, phone numbers, addresses, delivery detail, payment raw payload, raw response bodies, tokens, authorization headers, signatures, or full channel numbers. It does not write `orders`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`.

Phase Naver-ERP-1A extends that readonly preview response with a sanitized `detail_preview` when and only when the feed returns a product order id and `include_detail=true`. The feed call still sends only `lastChangedFrom` and `limitCount=1`; it does not send `lastChangedTo`, page, size, or order status to Naver. The recommended operational sequence is one recent-24-hour feed probe, then at most one bounded recent-7-day feed probe if the first result is `success_empty`. If both are empty, stop without detail. `success_empty` returns `business_message="Naver 订单接口已连接。当前时间范围内没有新的订单变更，暂时不需要处理订单同步。"` and keeps `detail_called=false`, `orders_written=false`, `raw_response_saved=false`.

Allowed `detail_preview` fields:

```json
{
  "product_order_id_hash": "id-hash-*",
  "order_id_hash": "id-hash-*",
  "external_product_order_id_hash": "id-hash-*",
  "external_order_id_hash": "id-hash-*",
  "store_id": 8,
  "platform": "naver",
  "order_status": {"raw": "PAYED", "label_zh": "已付款 / 新订单", "unknown_status_observed": false},
  "order_status_label_zh": "已付款 / 新订单",
  "payment_status": "PAYED",
  "product_name": "safe product text",
  "option_name": "safe option text",
  "quantity": 1,
  "order_amount": "1000",
  "currency": "KRW",
  "ordered_at": "UTC-aware ISO timestamp or null",
  "paid_at": "UTC-aware ISO timestamp or null",
  "last_changed_at": "UTC-aware ISO timestamp or null",
  "delivery_status": {"raw": "DISPATCHED", "label_zh": "已发货 / 配送中", "unknown_status_observed": false},
  "delivery_status_label_zh": "已发货 / 配送中",
  "claim_status": {"raw": "RETURN_REQUEST", "label_zh": "退货请求", "unknown_status_observed": false},
  "claim_status_label_zh": "退货请求",
  "buyer_name_masked": "masked-or-null",
  "buyer_phone_masked": "****1234",
  "buyer_id_hash": "id-hash-* or null",
  "receiver_name_masked": "masked-or-null",
  "receiver_phone_masked": "****1234 or null",
  "address_observed": true,
  "address_saved": false,
  "source_type": "naver_order_preview",
  "last_synced_at": "UTC-aware ISO timestamp",
  "raw_response_saved": false,
  "privacy_fields_redacted": true,
  "orders_written": false,
  "mapping_version": "naver_order_detail_preview_v1",
  "unknown_status_observed": false,
  "safe_status_samples": ["PAYED"]
}
```

Known status labels include `PAYED` / `결제완료` -> `已付款 / 新订单`, `PLACE_PRODUCT_ORDER` / `발주확인` -> `已确认订单`, `DISPATCHED` / `배송중` -> `已发货 / 配送中`, `DELIVERED` / `배송완료` -> `配送完成`, `CANCELED` / `CANCELLED` / `취소` -> `已取消`, `CANCEL_REQUEST` / `취소요청` -> `取消请求`, `RETURN_REQUEST` / `반품요청` -> `退货请求`, `EXCHANGE_REQUEST` / `교환요청` -> `换货请求`, and `PURCHASE_DECIDED` / `구매확정` -> `已确认购买`. Unknown enums must set `unknown_status_observed=true` and use `未识别状态，需人工确认`; do not infer a business meaning.

Phase Naver-ERP-1A does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`; does not save raw responses, token values, `Authorization`, request headers, signatures, bcrypt output, or client secrets; does not output full `channel_no`, full product order ids, full order ids, full buyer names, full phones, or addresses; and does not open dispatch, cancel, return, exchange, delivery write, sales, settlement, customer-service, or formal order sync flows.

Phase Naver-ERP-1B freezes the mapping and privacy gate for later single-order writes. Future writes may save only: `store_id`, `platform=naver`, `external_order_id_hash`, `external_product_order_id_hash`, `order_status`, `order_status_label_zh`, safely observed payment status, safe product/option text, `quantity`, `order_amount`, `currency=KRW`, `ordered_at`, `paid_at`, `last_changed_at`, safely observed delivery/claim statuses plus Chinese labels, `source_type`, `last_synced_at`, `mapping_version`, `raw_response_saved=false`, and `privacy_fields_redacted=true`. Buyer and receiver fields are limited to `buyer_name_masked`, `buyer_phone_masked`, `buyer_id_hash`, `receiver_name_masked`, and `receiver_phone_masked`; complete buyer/receiver names and phones are forbidden. If any address, zip, postal, road-name, base-address, or detailed-address field is observed, the preview may expose only `address_observed=true` and must keep `address_saved=false`.

Phase Naver-ERP-1B still performs no real API request and writes no `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`. It also does not change schema, Codex2, dispatch, cancel, return, exchange, delivery write, sales, settlement, customer-service, or formal order sync flows. Phase Naver-ERP-1C is the first possible single-order local write stage, and it requires explicit user approval, a `codex1.db` backup, `store_id=8`, `credential_id=7`, the latest feed-matched one-detail payload, the whitelist above, masked or hashed privacy fields, `address_saved=false`, `raw_response_saved=false`, `privacy_fields_redacted=true`, post-write readback, no `SyncLog`, no new `tested_success`, and no shipment/claim write operation.

Phase Naver-ERP-1C adds a controlled one-row local write gate to `POST /api/v1/sync/orders/naver/preview`; it does not add a formal order sync endpoint. The request must include `real_preview=true`, `include_detail=true`, and `real_sync=true`. `real_sync=true` without `real_preview=true` or without detail is rejected before external HTTP. The upstream calls remain readonly and minimal: token exchange, `GET /v1/pay-order/seller/product-orders/last-changed-statuses` with only `lastChangedFrom` and `limitCount=1`, and `POST /v1/pay-order/seller/product-orders/query` for exactly one product order id only when the feed is non-empty. The write-phase window is capped at 24 hours; a 7-day fallback is not part of 1C.

The 1C local write result is returned as `local_sync_result`. Possible statuses are `not_requested`, `skipped` with `skip_reason=no_changed_orders`, `blocked` with `skip_reason=privacy_gate_failed` or `detail_request_failed`, `already_exists` with `no_duplicate_created=true`, and `success`. On success, exactly one local `orders` row is created with `store_id=8`, `platform=naver`, `external_order_id=<external_product_order_id_hash>`, `source_type=naver_real_order_sync`, masked buyer fields, safe product text, amount, quantity, status, timestamps, and sanitized `raw_data`. The row must keep `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Full `productOrderId`, full `orderId`, full buyer/receiver names, full phones, address, zip code, raw response, token, `Authorization`, headers, signatures, bcrypt output, and client secrets are forbidden in the row and in the response.

Phase Naver-ERP-1C still does not write `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`; does not execute any Naver dispatch, cancel, return, exchange, delivery write, sales, settlement, or customer-service write; and does not declare formal Naver order sync open.

Phase Naver-ERP-1D is the post-write verification contract. It performs local readback plus a 24-hour `real_sync=false` feed-to-detail preview only. The expected verified state is `orders_store8=1`, `products_store8=5`, `sync_logs_store8=0`, and unchanged `tested_success_store8`. The stored order must use a hashed product-order key as `orders.external_order_id`, `source_type=naver_real_order_sync`, `raw_response_saved=false`, `privacy_fields_redacted=true`, `address_saved=false`, `currency=KRW`, and safe order status labels. A follow-up preview may confirm that the current product-order hash matches the existing local hash, but it must keep `local_sync_result.requested=false`, `local_sync_result.status=not_requested`, and must not create a duplicate. 1D does not execute `real_sync=true`, does not write another order, and does not open formal Naver order sync.

Phase Naver-ERP-5D adds `complete_field_preview` to `POST /api/v1/sync/orders/naver/preview` for explicit operator review of complete Naver order fields. The request must keep `real_preview=true`, `include_detail=true`, and `real_sync=false`; `complete_field_preview=true` without detail returns `guardrail_blocked`, and combining it with `real_sync=true` also returns `guardrail_blocked`. When requested and a single detail payload is available, the response includes `complete_field_preview.requested=true`, `preview_only=true`, and a `complete_fields` object that may contain the full order id, product order id, platform product id, buyer/receiver names, buyer/receiver phones, receiver address, zip code, safe product/option text, quantity, order amount, status fields, and timestamps. This is display-only. The existing sanitized `detail_preview` remains unchanged and is still the only payload shape allowed by the current 1C write path. 5D does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`; does not save raw responses, token values, `Authorization`, request headers, signatures, bcrypt output, or client secrets; does not change schema; and does not open formal Naver order sync.

Phase Naver-ERP-11B defines and verifies a private selected new-order write gate for mock/fake coverage only. It does not add a new public endpoint, does not add a public request field, does not call Naver, and does not alter the 24-hour `real_sync=true` gate. The private gate accepts a selected safe product-order hash plus fresh sanitized candidate previews in tests, requires exactly one matching `candidate_new`, rejects stale/missing/changed/not-unique/duplicate/privacy-blocked candidates, and can create at most one row only inside the temporary verification database when `write_enabled=true`. It must keep `products`, `SyncLog`, and `ApiCapabilityTestResult tested_success` unchanged, keep `raw_response_saved=false`, `privacy_fields_redacted=true`, `address_saved=false`, and keep formal order sync and all Naver platform write operations closed.

Phase Naver-ERP-11D is an approval-plan contract for a possible later selected-candidate local write. It is documentation-only and does not change the public API. The selected candidate safe hash from the successful readonly retry is `id-hash-ab176f5db1`; it may enter a later 11E write only after explicit user approval, database backup, fresh candidate validation, zero duplicate matches, privacy gate success, and a one-row write limit. The later write must not persist full order ids, full product order ids, full buyer or receiver data, addresses, raw responses, tokens, Authorization values, request headers, signatures, bcrypt output, or client secrets. It must not write `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`, and it must not execute any Naver platform write action or open formal order sync.

Phase Naver-ERP-11E is the selected-candidate single local write result. It persisted exactly one sanitized local order for safe hash `id-hash-ab176f5db1` after database backup, fresh readonly preview, duplicate check, and privacy gate success. Post-write counts are `orders_store8=5`, real Naver local orders 2, mock Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. The row must remain hashed/sanitized with `source_type=naver_real_order_sync`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. This does not open batch order sync, refresh automation, or Naver platform write operations.

Phase Naver-ERP-11F is the selected-candidate post-write verification contract. It is local readback only and must not call Naver, execute `real_sync=true`, write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult`, modify schema, or open any platform write action. The verified selected candidate is `id-hash-ab176f5db1`, and it must exist exactly once with `store_id=8`, `platform=naver`, `source_type=naver_real_order_sync`, `order_status=DELIVERED`, `currency=KRW`, `quantity=1`, `order_amount=330000`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Verified counts are `orders_store8=5`, real Naver local orders 2, mock Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. Candidate-row scanning must not expose or persist token values, client secrets, Authorization values, headers, signatures, bcrypt output, raw response bodies, full order ids, full product order ids, full buyer or receiver privacy data, phone numbers, or addresses. Formal Naver order sync remains closed.

Phase Naver-ERP-13A defines a private local refresh mock gate for future order refresh planning. It does not add a public endpoint, does not add a public request field, does not call Naver, and does not alter the existing 24-hour `real_sync=true` write gate. The private gate accepts a selected local order hash plus a fresh sanitized refresh preview, requires identity match, exactly one existing local Naver order, privacy gate success, and manual approval before a temporary mock update can run. It rejects stale/missing/mismatched/privacy-blocked/unapproved refresh attempts. When `write_enabled=true` and `manual_approval=true` inside `verify_all.py`, it may update exactly one existing order in the temporary verification database, but it must not create another order, write `products`, write `SyncLog`, add `ApiCapabilityTestResult tested_success`, save raw responses, execute platform writes, or open formal order sync.

Phase Naver-ERP-5H refines status labels for the same readonly complete-field preview response. `order_status_label_zh` and `delivery_status_label_zh` recognize `READY`, `DELIVERING`, `DISPATCHED`, `DELIVERED`, `DELIVERY_COMPLETED`, Korean labels such as `배송중` / `배송완료`, and the existing cancel/return/exchange states. If `delivery_status` is unknown or absent while `order_status` clearly represents a delivery-stage state, `delivery_status_label_zh` may be derived from `order_status`, with `delivery_status_derived_from_order_status=true` in `complete_fields`. This flag is display-only and must never be treated as a platform write instruction or formal order sync approval.

### Planned Naver ERP v1 Contract

Phase Naver-ERP-MasterPlan keeps the current Naver focus on normal ERP operations: products -> orders -> inventory -> delivery/claims -> order-based sales -> Dashboard. Mail, appeals, AI reply generation, AI mail recognition, and deep customer-service automation are intentionally outside this contract until the core ERP loop is stable.

Current Naver baseline:

- `store_id=8`, `credential_id=7`, token/auth/account/channel checks passed.
- Product small-batch local sync completed for `page=1,size=5`; `products_store8=5`.
- Product post-sync dry-run reports no create and no business update: `would_create=0`, `would_update=0`, `would_refresh_only=5`, `would_skip=0`.
- Product `page=2,size=5` readonly dry-run returned `success_empty`; `page=2` local sync is not justified.
- Formal product batch sync, order batch sync, shipment writes, claim writes, settlement sync, and platform write actions remain closed.

Planned ERP phases:

| Phase | Contract intent | Real API | Writes | Public API impact |
|---|---|---:|---:|---|
| `Naver-ERP-1` | Order feed-to-detail readonly preview; one-day window, one feed item, at most one detail | Yes, readonly | No | Existing `POST /api/v1/sync/orders/naver/preview` only |
| `Naver-ERP-2` | Order detail mapping, status Chinese labels, privacy gate, mock tests | No | No | No new route required |
| `Naver-ERP-3` | Single sanitized order local write after separate approval | Yes, readonly upstream | Yes, one row | Existing or narrowly gated order preview route may carry explicit write intent in a later phase |
| `Naver-ERP-4` | Inventory basic alerts from local `products.stock_quantity` | No | No | Existing product/dashboard reads may expose summary fields later |
| `Naver-ERP-5` | Delivery and claim readonly classification from order feed/detail | Yes, readonly | No | Order/dashboard summaries may expose seller-facing counts later |
| `Naver-ERP-6` | Order-amount sales summary from local orders | No | No | Existing stats/dashboard endpoints only |
| `Naver-ERP-7` | Dashboard ERP summary for connection, products, orders, shipping, claims, inventory, sales | No | No | Dashboard response may add business summary fields later |
| `Naver-ERP-8` | Product expansion review only when platform products change | Yes, readonly | No | Product preview remains guarded |

Naver product v1 contract:

- Product line is temporarily closed after the 5-row local write test. Continue product expansion only through small readonly previews (`page in {1,2}`, `size<=5`) until new candidates exist.
- Product business update fields remain `name`, `status`, `price`, `currency`, and `stock_quantity`.
- `would_refresh_only` means sync metadata refresh only and must not be displayed as "products need update".
- Future product sync history may record sanitized counts, timestamps, diff categories, and `raw_response_saved=false`; it must not store raw Naver payloads.

Naver order v1 contract:

- Next executable step is `Naver-ERP-1`: call the existing order preview only with `real_preview=true`, approved store/credential, `page=1`, `size=1`, a recent 24-hour default window or one bounded 7-day fallback probe, and `include_detail` only for a single feed-produced product order id.
- Default sanitized detail preview may expose only safe booleans/counts/field names and seller-facing status summaries. It must not expose full order ids, full product order ids, buyer/receiver names, full phones, addresses, delivery raw payloads, payment raw payloads, raw response bodies, headers, tokens, signatures, or full channel numbers. The explicit 5D `complete_field_preview=true` path is the only readonly display exception for complete order/product/buyer fields, and its response is never a persistence payload.
- A future single-order write may persist only sanitized business fields: `store_id`, `platform`, masked or hashed external order key, `product_name`, `quantity`, `order_amount`, `currency`, `order_status`, `paid_at`, `ordered_at`, `source_type`, `last_synced_at`, and sanitized metadata. Full buyer privacy fields and raw detail remain forbidden.
- Order status mapping must be seller-facing Chinese labels for new order, paid/ready-to-ship, shipped, in delivery, delivered, cancellation requested, return requested, exchange requested, refunded, and abnormal/unknown.

Naver inventory, delivery, claims, sales, and Dashboard contract:

- Inventory v1 is derived from local `products.stock_quantity`: zero stock, low stock, and stock-change notices. No procurement, warehouse, or purchasing workflow is part of this phase.
- Delivery v1 is readonly display only. Shipment/dispatch write APIs are out of scope until a separate write phase.
- Cancellation, return, and exchange v1 are readonly classifications. They can enter Dashboard todo counts, but action workflows and separate after-sales tables require a later design.
- Sales v1 uses local `orders.order_amount` only. Settlement amount, final amount, and fee fields must not be displayed as profit or withdrawable balance.
- Dashboard v1 should expose business summaries, not technical diagnostics. Technical fields such as `error_code`, `http_status`, `safe_keyword_flags`, `business_error_hint`, `real_preview`, `real_sync`, `store_id`, and `credential_id` belong only in technical details.

All Naver ERP phases inherit these safety gates:

```text
Preview/dry-run before local writes
Small window before larger window
Single-row order write before multi-row order write
Manual approval before any broader write
No token / Authorization / headers / signature / bcrypt persistence
No raw response persistence
No full channel_no, full product id, full order id, or full productOrderId output by default
Buyer privacy is masked or suppressed by default
Full order/product/buyer fields are display-only in explicit 5D complete-field readonly preview
Every business row is bound to store_id and platform
Formal batch sync requires a separately approved phase
```

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
| GET | `/api/v1/orders` | `store_id` required, `platform` optional, `include_test_orders` optional default `false` | None | Required | Only `buyer_masked_phone` |
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
  "external_order_id": "id-hash-56fb9c2a46",
  "buyer_name": "김**",
  "buyer_masked_phone": null,
  "product_name": "PXG 휠 캐디백 여성 바퀴형 골프백",
  "order_amount": "499000.00",
  "source_type": "naver_real_order_sync",
  "last_synced_at": "2026-07-01T00:00:00+00:00"
}
```

Phase Naver-ERP-5J default order-list behavior:

- Seller-facing `/api/v1/orders`, sales stats, and Dashboard summaries exclude local order test rows by default.
- Excluded local test source types are `mock_sync` and `local_frontend_mock`.
- The rows are not deleted. They can be inspected with `include_test_orders=true`.
- `/api/v1/orders` returns `include_test_orders` and `test_orders_excluded` metadata so Codex2 can show that test rows were isolated without loading them into the main list.
- The diagnostic flag is readonly and must not be described as formal Naver order sync.

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
| GET | `/api/v1/stats/sales` | `store_id`, `platform`, `start_date`, `end_date`, `include_test_orders` optional default `false` | None | Optional | No |
| GET | `/api/v1/stats/sales/by-platform` | `store_id`, `start_date`, `end_date`, `include_test_orders` optional default `false` | None | Optional | No |
| GET | `/api/v1/stats/sales/by-date` | `store_id`, `platform`, `start_date`, `end_date`, `include_test_orders` optional default `false` | None | Optional | No |

Date filters are interpreted as KST business dates. `/stats/sales/by-date` groups orders after converting `ordered_at` to KST. By default, local test orders with `source_type in {"mock_sync", "local_frontend_mock"}` are excluded from sales stats; `include_test_orders=true` is a readonly diagnostic override.

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
| GET | `/api/v1/dashboard/summary` | `store_id`, `platform`, `start_date`, `end_date`, `include_test_orders` optional default `false` | None | Optional | Masked orders only |

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
