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

Phase Naver-ERP-13B is a real readonly refresh-repeat verification using the existing public preview endpoint only. The request keeps `real_preview=true`, `include_detail=true`, `complete_field_preview=true`, and `real_sync=false` over a recent 3-day KST window with `store_id=8`, `credential_id=7`, `page=1`, and `size=1`. The observed safe hash `id-hash-ab176f5db1` matched one existing real local Naver order, with `DELIVERED / 配送完成`, amount `330000 KRW`, quantity 1, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Database counts remained `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. 13B does not approve a refresh write, does not execute `real_sync=true`, does not save complete-field values, raw responses, tokens, headers, signatures, full buyer/receiver data, or addresses, and does not open formal Naver order sync or any platform write operation.

Phase Naver-ERP-13C is a documentation-only approval contract for a possible later selected-order local refresh. It does not change the public API, call Naver, write local data, or alter the existing guarded `real_sync=true` behavior. A later refresh write for selected safe hash `id-hash-ab176f5db1` requires a separate explicit user request, clean worktrees, a database backup, a fresh readonly preview, exact safe-hash match, exactly one existing local real Naver order, privacy gate success, one-row update limit, and post-write readback. It may update only sanitized order status, status labels, payment/delivery/claim status, quantity, amount, safe product/option text, timestamps, `last_synced_at`, and whitelisted metadata with `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. It must not create orders, write `products`, write `SyncLog`, add `ApiCapabilityTestResult tested_success`, persist complete-field preview payloads, raw responses, tokens, Authorization values, headers, signatures, full buyer or receiver data, addresses, zip codes, or open formal order sync or any Naver platform write action.

Phase Naver-ERP-13D is the selected-order local refresh write attempt result. It backed up the real database and ran fresh readonly Naver order previews, but did not write because the fresh preview hashes did not match approved hash `id-hash-ab176f5db1`. The 3-day window returned `id-hash-0c36f22281`; the targeted narrow probe returned `id-hash-a5870c77c2`. The selected refresh gate blocked, leaving `orders`, products, `SyncLog`, `ApiCapabilityTestResult tested_success`, and `order_status_events` unchanged. This phase did not execute `real_sync=true`, did not save raw responses or secrets, did not output full order ids or buyer privacy, and did not open formal Naver order sync.

Phase Naver-ERP-14A is a documentation-only order status timeline contract. It does not add schema, call Naver, write local data, or change the public preview endpoint. The planned model keeps `orders` as the latest sanitized snapshot and reserves future history for a separately approved timeline implementation, preferably an `order_status_events` table. Future events may contain only safe hashes, event type, raw status enum, Chinese status labels, safely observed payment/delivery/claim status labels, observed time, source phase, source type, mapping version, dedupe key, and safety booleans `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. No-change refreshes and `last_synced_at`-only refreshes must not create events. Unknown status observations must block real refresh writes until mapped. Timeline payloads must not persist complete-field preview payloads, raw responses, tokens, Authorization values, headers, signatures, full order ids, full product-order ids, full buyer or receiver data, phone numbers, addresses, zip codes, or Naver platform write instructions.

Phase Naver-ERP-14B adds a private mock-testable timeline mapper only; it does not add a public endpoint, public request field, schema, real API call, or persistent write. The helper compares a previous sanitized order snapshot with a fresh sanitized refresh preview and returns safe planned events, dedupe counts, or manual-review blocks. Planned events may contain only safe hashes, event type, raw status enum, Chinese labels, observed time, source phase, source type, mapping version, dedupe key, and safety booleans. It must keep `orders`, products, `SyncLog`, and `ApiCapabilityTestResult tested_success` unchanged, keep `raw_response_saved=false`, `privacy_fields_redacted=true`, `address_saved=false`, and keep formal order sync plus all Naver platform write operations closed. Unknown statuses must return manual-review metadata, not write approval; repeated same-status refreshes must dedupe or produce no event.

Phase Naver-ERP-14C is a display-planning contract for Orders UI only. It does not change Codex1 APIs, schema, runtime frontend code, or persistence. Future Orders UI should show the current local order snapshot as the primary status, keep status history collapsed by default, describe planned or unsaved timeline events as planned only, and place safe technical fields such as safe hashes, raw status enums, dedupe keys, mapping versions, source phase, and safety booleans in TechnicalDetails. Main page content must use seller-facing Chinese labels and must not expose raw responses, full order ids, full product-order ids, buyer/receiver privacy fields, phone numbers, addresses, zip codes, tokens, headers, signatures, or wording that formal order sync, platform writes, automatic refresh, or persisted timeline history is open before the dedicated schema/write phases.

Phase Naver-ERP-14D is a schema proposal only. It does not add models, migrations, endpoints, or writes. The proposed future table is `order_status_events`, linked to `orders.id` and scoped by `store_id` plus `platform`. Proposed fields include safe order hashes, `event_type`, raw status enums, Chinese labels, payment/delivery/claim status labels, `observed_at`, `source_phase`, `source_type`, `mapping_version`, `dedupe_key`, safety booleans, and sanitized metadata. The proposed uniqueness boundary is `store_id/platform/dedupe_key`; proposed indexes cover order/time, store/platform/time, store/event type, and product-order hash. Timeline schema implementation must be deferred to a mock schema gate, backup/rollback approval plan, and explicit migration phase. The table must not persist raw responses, complete-field preview payloads, tokens, Authorization values, headers, signatures, full IDs, buyer/receiver privacy data, phone numbers, addresses, or zip codes.

Phase Naver-ERP-14E is a mock schema gate only. It adds `verify_all.py` coverage that creates a temporary `order_status_events` table in the verification SQLite database, validates the proposed safe columns, required non-null fields, indexes, `store_id/platform/dedupe_key` uniqueness boundary, single safe event insert, duplicate rejection, safe metadata, and sensitive-field scanning. This phase does not create or alter the real `backend/codex1.db` schema, does not add a SQLAlchemy model, migration, public endpoint, real Naver call, real data write, Codex2 runtime change, or formal order sync approval. Real schema approval is still deferred to a later backup and rollback plan.

Phase Naver-ERP-14F is a schema approval plan only. It defines the preflight, backup, migration-shape, rollback, and post-migration verification requirements for a later `order_status_events` schema migration. It does not create the table, add a model or migration, call Naver, execute `real_sync=true`, write `orders`, products, `SyncLog`, or `ApiCapabilityTestResult`, modify Codex2 runtime UI, or open formal order sync. A later 14G migration must be separately approved, must back up `backend/codex1.db`, must verify baseline counts before and after, must create no event rows, must keep sensitive data out of schema checks and logs, and must not approve future event writes by merely creating the table.

Phase Naver-ERP-14G is a schema migration only. It creates the real `order_status_events` table and approved indexes in `backend/codex1.db`, adds a SQLAlchemy model plus idempotent SQLite upgrade script, and keeps the table empty after migration. The migration must leave `orders`, products, `SyncLog`, and `ApiCapabilityTestResult tested_success` counts unchanged, must not call Naver, must not execute `real_sync=true`, must not insert timeline events, and must not approve event writes, order refresh writes, platform write operations, Codex2 runtime UI display, or formal Naver order sync.

Phase Naver-ERP-14H is a mock event write gate only. It adds a private helper that can insert at most one `OrderStatusEvent` row inside the temporary `verify_all.py` database after fresh preview, selected safe-hash identity match, exactly one planned event, local order uniqueness, known non-unknown event type, valid dedupe key, safety booleans, sensitive-field screening, no existing duplicate event, `write_enabled=true`, and manual approval. It does not write the real `backend/codex1.db` event table, call Naver, execute `real_sync=true`, write `orders`, products, `SyncLog`, or `ApiCapabilityTestResult`, expose a public endpoint, modify Codex2 runtime UI, or open formal order sync.

Phase Naver-ERP-14I is a local readback verification after the blocked 13D selected-order refresh attempt. It confirms no timeline event exists for selected hash `id-hash-ab176f5db1`, because 13D did not pass the fresh selected-hash gate and did not update the local order. The selected order remains `DELIVERED`, `orders_refreshed=false`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`; `order_status_events_rows=0`. This phase does not call Naver, execute `real_sync=true`, write local data, insert events, expose a public endpoint, modify Codex2 runtime UI, or open formal order sync.

Phase Naver-ERP-15A is a documentation-only contract for a future Naver existing-order refresh batch gate. It does not add a public endpoint, does not add a public request field, does not change the current `POST /api/v1/sync/orders/naver/preview` real-preview guardrail, and does not call Naver or write local data. The current public real preview remains `page=1,size=1`; the current real write behavior remains single-order and bounded by the 24-hour write window. A later batch refresh may be considered only after a separate mock gate and approval phase. It must target existing local real Naver orders only, reject new-order candidates, require unique safe hashes, require exactly one local order match per safe hash, pass privacy and status mapping gates for every candidate, update only whitelisted sanitized refresh fields, block partial writes in the first batch, avoid complete-field preview payloads for persistence, and keep products, SyncLog, ApiCapabilityTestResult tested_success, timeline event insertion, platform write actions, and formal order sync closed unless separately approved.

Phase Naver-ERP-15B adds a private mock-testable existing-order refresh batch gate only. It does not add a public endpoint, public request field, real API call, schema change, real database write, or formal order sync approval. The helper accepts sanitized refresh previews plus optional approved safe hashes, defaults to a two-candidate limit, rejects stale previews, missing/duplicate safe hashes, new-order candidates, local-order mismatches, privacy failures, unknown statuses, sensitive/raw-response field names, and unapproved writes. When `write_enabled=true` and `manual_approval=true` inside `verify_all.py`, it can update two existing local Naver orders only in the temporary verification database; it must not create orders, write products, write SyncLog, add ApiCapabilityTestResult tested_success, insert timeline events, save raw responses or secrets, execute platform writes, or change the current public `page=1,size=1` real preview guardrail.

Phase Naver-ERP-15C is a controlled real readonly candidate discovery result under the current public Naver order preview guardrail. It uses `POST /api/v1/sync/orders/naver/preview` with `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. It returned HTTP 200 with feed/detail HTTP 200 and one safe candidate hash, `id-hash-67b5fc1c97`. The safe hash did not match an existing local real Naver order, so it is not eligible for the existing-order refresh batch gate and must be treated as a new-order candidate for a separate future approval path. Counts remained unchanged: `orders_store8=5`, real Naver local orders 2, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. The status mapper now recognizes `DELIVERY_COMPLETION` as `配送完成`. 15C does not add a public batch parameter, does not open probing beyond `size=1`, does not write orders, products, SyncLog, ApiCapabilityTestResult, or timeline events, and does not approve formal Naver order sync or any platform write.

Phase Naver-ERP-15D is a documentation-only approval contract for a future existing-order batch refresh. It does not run a real readonly batch probe, add a public request field, execute `real_sync=true`, write local data, or change the current public `page=1,size=1` real preview guardrail. A later batch write phase may be considered only after a fresh readonly candidate batch result and explicit human approval. The approval evidence must include approved safe hashes, candidate count within the first-batch limit, no duplicate hashes, no new-order candidates, exactly one existing local real Naver order per hash, privacy/status gates passing for every candidate, changed field names only, database backup path, and post-write readback requirements. It must keep products, SyncLog, ApiCapabilityTestResult tested_success, timeline event insertion, platform write actions, and formal order sync closed unless separately approved.

Phase Naver-ERP-15E is a documentation-only approval plan for a possible future readonly expansion of Naver existing-order refresh candidate discovery. It does not call Naver, add a public endpoint, change public request validation, execute `real_sync=true`, write local data, or open formal order sync. The current public contract remains `page=1,size=1` until a later implementation phase explicitly changes it. The plan blocks any existing-order batch refresh write from the 15C result because `id-hash-67b5fc1c97` did not match a local real Naver order. If a later phase implements readonly expansion, the first allowed shape should be `page=1`, `size=2`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`, with feed limited to `lastChangedFrom` and `limitCount=2`, detail limited to two ids, no writes, and per-candidate classification before any later approval. `real_sync=true`, `page>1`, and `size>2` remain blocked unless separately approved.

Phase Naver-ERP-16A is a documentation-only approval plan for the latest selected Naver new-order candidate. It does not call Naver, add a public endpoint, change request validation, execute `real_sync=true`, write local data, or open formal order sync. Safe hash `id-hash-67b5fc1c97` is routed to the selected new-order path because it did not match a local real Naver order in 15C. A later write may be considered only after a fresh readonly repeat verifies the selected hash, duplicate checks return zero local operational matches, privacy/status gates pass, and a separate explicit write approval plus database backup is completed. The future write must remain one-order only and must not write products, SyncLog, ApiCapabilityTestResult, or timeline events unless separately approved.

Phase Naver-ERP-16B is a real readonly repeat check for the selected new-order candidate. It uses the existing public `POST /api/v1/sync/orders/naver/preview` contract with `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. It returned HTTP 200 with feed/detail HTTP 200 and safe hash `id-hash-67b5fc1c97`, matching the 16A selected hash. Duplicate checks returned 0 real local matches and 0 mock/test matches, so the candidate remains `candidate_new`. Privacy/status gates passed and counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. 16B does not approve `real_sync=true`, local writes, timeline writes, platform writes, or formal order sync.

Phase Naver-ERP-16C is an approval-only contract for a later selected new-order single local write. It does not call Naver, add an endpoint, change request validation, execute `real_sync=true`, write local data, or open formal order sync. The only approved future write target is safe hash `id-hash-67b5fc1c97`. A later 16D may write at most one sanitized local Naver order only after clean worktrees, database backup, fresh readonly preview, selected-hash confirmation, zero duplicate matches, privacy/status gates, approved safe payload fields, and post-write readback. The future write must not write products, SyncLog, ApiCapabilityTestResult, or timeline events unless separately approved, and must not execute any Naver platform write operation.

Phase Naver-ERP-16C2 is an approval-only contract for the current 24-hour Naver new-order candidate. It does not call Naver, add an endpoint, change request validation, execute `real_sync=true`, write local data, change schema, or open formal order sync. The stopped 16D gate did not write because the 3-day readonly candidate was `id-hash-67b5fc1c97`, while the writeable 24-hour window returned `id-hash-bc5528d093`. The only approved future write target from 16C2 is safe hash `id-hash-bc5528d093`. A later retry may write at most one sanitized local Naver order only after clean worktrees, database backup, fresh 24-hour readonly preview, selected-hash confirmation, zero duplicate matches, privacy gate, required-field gate, approved safe payload fields, and post-write readback. The future write must not write products, SyncLog, ApiCapabilityTestResult, or timeline events unless separately approved, and must not execute any Naver platform write operation.

Phase Naver-ERP-16D-Retry is the controlled single local write result for safe hash `id-hash-bc5528d093`. It used the existing order preview and selected-candidate local write gate; it did not add an endpoint, change request validation, change schema, or execute any Naver platform write operation. After database backup and fresh 24-hour readonly preview, one sanitized local Naver order row was created. Post-write counts are `orders_store8=6`, real Naver local orders 3, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. The persisted row must remain hashed/sanitized with `source_type=naver_real_order_sync`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Formal Naver order sync, batch order sync, selected-candidate automation, timeline event insertion, and all platform write actions remain closed.

Phase Naver-ERP-16E is the local post-write verification contract. It does not call Naver, add an endpoint, change request validation, execute `real_sync=true`, write data, or open formal order sync. The selected safe hash `id-hash-bc5528d093` must have exactly one real local Naver order match. Default `GET /api/v1/orders?store_id=8&platform=naver` excludes mock/test orders and returns 3 real Naver orders, while `test_orders_excluded=3`. Dashboard summary for store 8 and platform Naver reports `order_count=3`, and sales summary reports `total_orders=3` with `total_sales_amount=1159000.00`. Responses and stored row data must remain sanitized and must not contain token, secret, Authorization, header, signature, raw platform response, full id key, address key, or plain phone patterns. Formal sync, batch writes, timeline insertion, and platform writes remain closed.

Phase Naver-ERP-17A expands safe readonly claim/status mapping without changing public endpoints, request validation, database schema, or formal sync gates. `COLLECT_DONE` must map to `售后取件完成` with `unknown_status_observed=false`; `COLLECT_REQUEST`, `COLLECTING`, `RETURN_DONE`, and `EXCHANGE_DONE` also have safe Chinese labels. Timeline mock mapping recognizes `COLLECT_DONE` as `claim_collected`. Existing persisted rows are not rewritten by this phase, and all Naver platform after-sales write actions remain closed.

Phase ERP-Audit-1A is a documentation-only contract for a future local operation audit trail. It does not add schema, endpoints, middleware, runtime UI, or audit rows. The future audit trail should use a dedicated `operation_audit_logs` table rather than overloading `SyncLog`. It should record safe accountability metadata such as actor type/id/label, action enum, operation phase, store/platform, target type/id/hash, correlation id, status, reason code, changed field names, safe before/after/count summaries, backup path, backup SHA-256, restore source path, safety flags, and sensitive-scan outcome. It must not store tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw platform responses, full channel numbers, full order ids, full product-order ids, buyer/receiver full names, phones, addresses, zip codes, or raw request bodies containing credentials or privacy data.

Phase ERP-Audit-1B is a schema proposal only. It does not add a model, migration, endpoint, middleware, runtime UI, or audit rows. The proposed `operation_audit_logs` table includes id/time, store/platform/environment, actor metadata, action, operation phase, correlation id, request id, status/reason, target metadata, safe JSON summaries, backup/restore path and SHA-256 fields, safety booleans, and notes. Proposed indexes cover created time, store/time, platform/time, actor/time, action/time, status/reason, target, target hash, correlation id, and request id. The proposal intentionally avoids a uniqueness constraint for ordinary audit rows so multiple approval/backup/write/verify rows can share a correlation id. The schema and future write service must reject tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, and zip codes.

Phase ERP-Audit-1C is a private mock write gate only. It adds `verify_all.py` coverage that creates `operation_audit_logs` inside the temporary verification SQLite database, validates required columns, defaults, planned indexes, no normal uniqueness constraint, valid SHA-256 metadata, manual approval blocking, safe row insertion, blocked-operation evidence rows, correlation chains, and sensitive JSON rejection. It does not add a public endpoint, public request field, SQLAlchemy model, real migration, middleware, runtime UI, real audit row, platform API call, backup/restore behavior, or formal sync approval. The mock gate must not write real `orders`, products, `SyncLog`, `ApiCapabilityTestResult tested_success`, raw responses, tokens, Authorization values, headers, signatures, client secrets, full channel/order/product-order ids, buyer/receiver privacy, phone numbers, addresses, or zip codes.

Phase ERP-Audit-1E creates the real local `operation_audit_logs` schema and indexes in `backend/codex1.db`. It is schema-only: no public endpoint, request field, middleware, runtime audit writer, frontend reader, restore execution, platform API call, formal sync approval, or audit row insertion is added. The table is intended for future safe accountability metadata only, with non-unique correlation-chain indexes and safe defaults (`environment=local`, `sensitive_scan_passed=false`, `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`). The migration must not change `orders`, products, `SyncLog`, `ApiCapabilityTestResult tested_success`, or `order_status_events` counts, and must keep `operation_audit_logs=0` immediately after schema creation. Future audit writers must continue to reject tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, and zip codes.

Phase ERP-Audit-1F is read-only post-migration verification only. It does not add a public endpoint, request field, middleware, runtime audit writer, frontend reader, restore execution, platform API call, formal sync approval, schema change, backup, audit row, or local business write. The real `operation_audit_logs` table must continue to have 34 approved columns, 10 approved non-unique indexes, no forbidden columns, safe defaults, no unique correlation constraint, and `operation_audit_logs=0`. Business counts must remain unchanged (`products=9`, `orders=9`, `sync_logs=47`, `tested_success=8`, `order_status_events=0`). Future work must still treat audit writes as closed until a separate mock writer gate and runtime writer phase are explicitly approved.

Phase ERP-Audit-1G adds a private service-level mock gate only. It does not add a public endpoint, request field, middleware, runtime writer, frontend reader, schema change, backup, platform API call, formal sync approval, or real audit row. The private helper may write safe audit rows only to the temporary `verify_all.py` database when `write_enabled=true`, `manual_approval=true`, and `verification_scope=verify_all_temp_db`. Missing approval, missing required fields, invalid SHA-256, unsafe saved flags, privacy failures, sensitive-scan failures, runtime-scope calls, and sensitive JSON payloads must be blocked without echoing secrets. The real `backend/codex1.db` must remain `operation_audit_logs=0` until a later explicitly approved runtime writer phase.

Phase ERP-Audit-1H adds a controlled local writer helper but still does not add a public endpoint, request field, middleware, frontend reader, automatic business instrumentation, backup execution, restore execution, platform API call, formal sync approval, or real audit row. `write_operation_audit_log_local` is available only to backend code and requires explicit write intent, manual approval, a private local scope, valid datetime and SHA-256 values, safe saved flags, privacy redaction, and sensitive JSON blocking. `verify_all.py` may write approved safe rows and blocked-operation evidence rows only to the temporary verification database. The real `backend/codex1.db` must remain `operation_audit_logs=0` until a later phase explicitly connects the writer to selected real local operations.

Phase ERP-Audit-1I is a documentation-only read API plan. It does not add a public endpoint, request field, middleware, frontend reader, schema change, audit row, platform API call, backup execution, restore execution, or formal sync approval. A future `GET /api/v1/operation-audit-logs` should be read-only, store-scoped, permission-aware, paginated, and limited to bounded filters such as `store_id`, `platform`, `status`, `target_type`, `action`, `actor_type`, date window, and safe `correlation_id`. Its main response should return business-first labels, safe counts, backup/restore evidence labels, and next-action text; advanced details may include only safe enums, abbreviated hashes, safe summary fields, and abbreviated SHA-256 metadata. A future `GET /api/v1/operation-audit-logs/summary` may support Dashboard or Logs summary cards. The API must never return tokens, Authorization values, request/response headers, signatures, bcrypt values, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer or receiver names, phones, addresses, zip codes, or full JSON payloads. When the table is empty, the future API should return an empty list plus a business message rather than an error. The next phase must verify this shape in a mock/private gate before any runtime route is exposed.

Phase ERP-Audit-1J adds private service-level mock gates for future read-only audit list and summary responses, but still does not add a public endpoint, request field, middleware, frontend reader, schema change, real audit row, platform API call, backup execution, restore execution, or formal sync approval. `list_operation_audit_logs_readonly_mock_gate` and `summarize_operation_audit_logs_readonly_mock_gate` require the private verification scope, enforce bounded filters and pagination, reject unsafe filters, return business-first labels, and keep raw JSON summaries out of the default response. Advanced details may include only safe enums, abbreviated hashes, abbreviated SHA-256 values, and safe field labels; they must not return raw `before_summary`, raw `after_summary`, raw `counts_summary`, raw `safety_flags`, tokens, Authorization values, headers, signatures, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, or zip codes. `verify_all.py` may insert temporary audit rows only in the verification database to prove the read shape; the real `backend/codex1.db` must remain unchanged until a separate route implementation phase is approved.

Phase ERP-Audit-1K is a documentation-only route implementation approval plan. It does not add a public endpoint, request field, middleware, frontend reader, schema change, audit row, platform API call, backup execution, restore execution, or formal sync approval. A later 1L may add only read-only list and summary routes for `operation_audit_logs`: `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`. These routes must use the 1J response shape, return an empty list plus a Chinese business message when the table has zero rows, enforce default `limit=20` and maximum `limit=50`, reject unsupported or unsafe filters, keep advanced details opt-in, and never return raw summaries, raw safety flags, tokens, Authorization values, headers, signatures, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, or zip codes. 1L must prove with `verify_all.py` that read calls write no audit rows or business rows and that no platform API is called.

Phase ERP-Audit-1L implements the approved local read-only audit routes: `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`. No POST, PUT, PATCH, DELETE, export, or detail audit route is added. The list route accepts only bounded filters (`store_id`, `platform`, `status`, `target_type`, `action`, `actor_type`, `date_from`, `date_to`, `correlation_id`, `limit`, `offset`, `include_advanced`), caps `limit` at 50, rejects unsupported query params without echoing raw names, rejects unsafe values, and returns an empty-list success message when no rows match. The summary route returns safe counts and `audit_runtime_status`. Advanced details remain opt-in and must not include raw `before_summary`, raw `after_summary`, raw `counts_summary`, or raw `safety_flags`. Route responses must not contain tokens, Authorization values, headers, signatures, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, or zip codes. `verify_all.py` confirms read calls do not write audit rows, business rows, `SyncLog`, `tested_success`, or `order_status_events`, and no platform API is called.

Phase ERP-Audit-1M is a post-implementation verification of the 1L local read-only audit routes. It does not change the public contract beyond strengthening verification of business error messages. Against the real local runtime database, `GET /api/v1/operation-audit-logs?store_id=8` and `GET /api/v1/operation-audit-logs/summary?store_id=8` return HTTP 200 empty-state responses because `operation_audit_logs=0`; non-GET methods remain 405. Unsupported filters return `unsupported_audit_log_filter` with a Chinese business message and do not echo the raw unsupported query key. Real database counts stay unchanged, and responses must still exclude tokens, Authorization values, headers, signatures, client secrets, raw request/response bodies, full platform ids, buyer/receiver privacy, phones, addresses, and zip codes. Frontend readers, audit writers, export/delete/detail routes, backups, restores, platform calls, and formal product/order sync remain closed.

Phase ERP-Audit-1N is a frontend readonly integration plan and does not change this backend API contract. A later Codex2 runtime implementation may add frontend client methods only for `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`. It must not add or call audit POST, PUT, PATCH, DELETE, export, or detail routes. The main Logs page should render the empty audit state as business-readable Chinese, keep SyncLog separate from operation audit rows, and avoid raw JSON, full hashes, full platform ids, `store_id`, `real_sync`, request ids, SHA-256 values, and backend enum clutter on the main page. Safe diagnostics may appear only in folded, redacted technical details. This plan does not approve audit writers, audit row creation, platform API calls, backup/restore execution, or formal product/order sync.

Phase ERP-Audit-1Q is an approval-plan-only contract for future audit writer integration. It does not add a public endpoint, request field, middleware, runtime writer wiring, schema change, frontend write behavior, audit row, platform API call, backup execution, restore execution, or formal sync approval. A later 1R must first verify audit writer integration patterns only in the temporary `verify_all.py` database. Future runtime audit rows may be considered only for explicitly approved local operations such as controlled Naver order writes/refreshes, backup evidence, restore dry-run evidence, and schema migration evidence. Those rows must form safe correlation chains, record only approved metadata and counts, set `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`, and must reject tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw request/response bodies, full channel/order/product-order ids, buyer/receiver full names, phones, addresses, and zip codes. Public audit write, delete, export, and raw detail routes remain closed.

Phase ERP-Audit-1R adds only a private service-level integration mock gate and does not change the public API surface. `write_operation_audit_integration_mock_gate` is callable by tests/services only and may write safe rows solely when `write_enabled=true`, `manual_approval=true`, and `verification_scope=verify_all_temp_db`. It supports approved mock operation types (`naver_order_local_write`, `naver_order_local_refresh`, `database_backup`, `restore_dry_run`, and `schema_migration`) and requires a single shared `correlation_id`, unique `request_id` values, complete operation-specific action chains, safe flags, privacy redaction, valid SHA-256 evidence, and sensitive-field rejection. The route contract remains unchanged: no public audit write, delete, export, or raw detail endpoint is added; runtime business-flow audit wiring remains closed; platform API calls, backup execution, restore execution, schema changes, and formal sync approval remain closed.

Phase ERP-Audit-1S is an approval-plan-only contract for future local runtime audit writer integration and does not change the public API surface. No endpoint, request field, route dependency, middleware, audit writer call site, schema change, audit row, platform API call, backup execution, restore execution, or formal sync approval is added. The first future runtime wiring direction is limited to controlled Naver selected-order local write/refresh evidence, pre-write backup evidence, and post-write verification evidence. A later mock-only selected-operation phase must still prove the call-site shape before any real runtime writer is connected. Public audit write, delete, export, and raw detail routes remain closed.

Phase ERP-Audit-1T is a planning-only contract for a future selected-operation mock wiring gate and does not change the public API surface. It selects `controlled_naver_order_local_refresh` as the first future mock target and requires a fake approval/backup/write-attempt/result/post-write-verification audit chain before any runtime writer can later be considered. It adds no endpoint, request field, service helper, route dependency, middleware, schema change, audit row, business row, platform API call, backup execution, restore execution, or formal sync approval. Public audit write, delete, export, and raw detail routes remain closed.

Phase ERP-Audit-1U adds only a private service-level selected-operation mock gate and does not change the public API surface. `write_selected_operation_audit_runtime_wiring_mock_gate` may be used by tests/services only with `operation_type=controlled_naver_order_local_refresh`, store 8, platform Naver, a safe target order hash, manual approval, backup evidence, fake write/readback results, audit write intent, and `verification_scope=verify_all_temp_db`. It writes the five-row audit chain only to the temporary verification database. No public audit write, delete, export, raw detail, route dependency, middleware, real runtime order-flow writer, schema change, platform API call, backup execution, restore execution, or formal sync approval is added.

Phase ERP-Audit-1V is an implementation-approval-plan-only contract and does not change the public API surface. It approves only a possible later implementation target, `controlled_naver_order_local_refresh`, and requires clean worktrees, verified database backup, baseline counts, explicit user approval, store 8 / Naver scoping, safe append-only audit rows, post-write readback, and sensitive-field scanning before any real runtime writer can be connected. It adds no endpoint, request field, service call, route dependency, middleware, schema change, audit row, business row, platform API call, backup execution, restore execution, or formal sync approval. Public audit write, delete, export, and raw detail routes remain closed.

Phase ERP-Audit-2D adds only a private service-level mock gate for the future selected-operation local implementation and does not change the public API surface. `write_selected_operation_audit_local_implementation_mock_gate` may be used by tests/services only with `operation_type=controlled_naver_order_local_refresh`, store 8, platform Naver, a safe `id-hash-*` target order hash, manual approval, verified backup evidence, local operation result, post-write verification, audit write intent, and `verification_scope=verify_all_temp_db`. It writes the five-row chain `approval_verified`, `pre_write_backup_verified`, `selected_operation_started`, `selected_operation_finished`, and `post_write_verification_finished` only to the temporary verification database. It blocks unsupported operation/store/platform values, missing approval, missing backup evidence, formal sync opened, platform writes enabled, raw-response saving, privacy failures, and sensitive payloads. No public audit write, delete, export, raw detail, route dependency, middleware, real runtime order-flow writer, schema change, platform API call, backup execution, restore execution, or formal sync approval is added.

Phase ERP-Backup-1A is a documentation-only backup and restore drill plan. It does not add a public endpoint, request field, service, script, model, migration, runtime UI, real backup file, restore operation, audit row, platform API call, or local data write. The future backup contract should protect `backend/codex1.db`, store backups under the approved local backup directory, produce a safe manifest with SHA-256, size, git commits, baseline counts, integrity-check result, and sensitive-scan outcome, and verify backups through a temporary restore drill before any real restore is considered. Real restore must remain a separate explicitly approved phase requiring a pre-restore backup, hash verification, backend stop, integrity checks, count checks, and post-restore verification. Backup manifests and restore logs must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full channel/order/product-order ids, buyer or receiver privacy, phone numbers, addresses, or zip codes.

Phase ERP-Backup-1B is a documentation-only metadata and retention plan. It does not add a public endpoint, request field, service, script, model, migration, runtime UI, real backup file, cleanup job, restore operation, audit row, platform API call, or local data write. Future backup manifests should include safe metadata such as manifest version, backup id, phase, operation type, actor label, source and backup paths, SHA-256, size, git commits, baseline counts, related store ids, retention class, retention reason, retention date, legal hold, protected-from-auto-delete flag, restore drill status, and sensitive-scan outcome. Cleanup must start as report-only, must not delete files automatically, and must protect latest known-good, pre-migration, pre-write, pre-restore, incident, legal-hold, audit-linked, and not-yet-drilled backups. Manifests and cleanup reports must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full channel/order/product-order ids, buyer or receiver privacy, phone numbers, addresses, or zip codes.

Phase ERP-Backup-1C is a private restore verification dry-run only. It does not add a public endpoint, request field, runtime service, production backup file, cleanup job, real restore operation, schema change, audit row, platform API call, or local data write. `verify_all.py` creates only temporary SQLite fixture files, validates manifest required fields, approved retention class, SHA-256 and file-size matching, safe flags, sensitive-field rejection, temporary restore target safety, restored copy hash, SQLite `PRAGMA integrity_check`, expected tables, and restored row counts. It must block `backend/codex1.db` as a restore target, confirm the real database is unchanged, and return `real_restore_executed=false`. Manifests and dry-run results must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full channel/order/product-order ids, buyer or receiver privacy, phone numbers, addresses, or zip codes.

Phase ERP-Backup-1D is an implementation-plan-only contract for future real backup manifest generation and does not change the public API surface. It defines the future manifest writer requirements for real `backend/codex1.db` backups: safe input fields, computed SHA-256/size/integrity data, approved path checks, atomic UTF-8 JSON writes, baseline counts, retention defaults, sensitive-field rejection, and optional operation-audit correlation. It adds no endpoint, request field, runtime service, script, model, migration, backup file, manifest file, cleanup job, restore operation, audit row, platform API call, or local data write.

Phase ERP-Backup-1E adds only private temporary-file verification for a future backup manifest writer and does not change the public API surface. The mock gate in `verify_all.py` creates temporary SQLite fixture backups and manifests only, computes SHA-256/size/integrity/page metadata/safe counts, validates retention and approved-root path safety, blocks sensitive content and manifest overwrite, and confirms the real `backend/codex1.db` is unchanged. It adds no endpoint, request field, runtime service, production backup file, production manifest file, cleanup job, restore operation, audit row, platform API call, or local data write.

Phase ERP-Backup-1F is an implementation-approval-plan-only contract for a future manual real local backup helper and does not change the public API surface. It defines the approved local backup root, source/path validation, SQLite backup method expectations, manifest generation, integrity checks, safe baseline counts, overwrite blocking, sensitive boundaries, and failure handling. It adds no endpoint, request field, runtime service, script, model, migration, production backup file, production manifest file, cleanup job, restore operation, audit row, platform API call, or local data write.

Phase ERP-Backup-1G implements a private local helper script, `scripts/create_local_backup.py`, and does not change the public API surface. The helper creates manual local backups only for the approved `backend/codex1.db` source and approved local backup root by default, uses SQLite online backup, validates the temporary backup before finalizing, writes a side-by-side UTF-8 manifest, records safe SHA-256/size/integrity/count metadata, and blocks unsupported paths, invalid retention classes, sensitive inputs, and existing target backup/manifest files. It adds no endpoint, request field, public runtime service, model, migration, cleanup job, restore operation, audit row, platform API call, or business-row write. Backup manifests must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full channel/order/product-order ids, buyer/receiver privacy, phones, addresses, or zip codes.

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

## Local Backup, Restore, and Audit Helpers

These helpers are local scripts and private service gates. They are not public business APIs and are not wired to platform sync endpoints.

### Restore Dry-Run Helper

```text
scripts/restore_backup_dry_run.py
```

Allowed output fields are safe operational metadata such as:

- `status`
- `manifest_valid`
- `backup_verified`
- `temporary_restore_verified`
- `temporary_restore_deleted`
- `real_restore_executed`
- `production_db_touched`
- `production_db_unchanged`
- `backup_deleted`
- `sqlite_integrity_check`
- safe baseline counts
- backup/manifest paths inside the approved local backup root
- SHA-256 values for backup verification

The helper must block the production database as a restore target and must never restore over `backend/codex1.db`.

### Backup List/Report Helper

```text
scripts/list_local_backups.py
```

Allowed output fields are safe report metadata such as:

- `status`
- `backup_count`
- `manifest_count`
- `all_manifests_valid`
- `all_sensitive_scans_passed`
- `backup_exists`
- `backup_inside_root`
- `backup_size_matches`
- abbreviated SHA-256
- retention metadata
- safe baseline counts

The helper must not delete backups, restore backups, or write audit or business rows.

### Backup Report Readonly API

```text
GET /api/v1/backups/local-report?limit={limit}
GET /api/v1/backups/local-report/summary?limit={limit}
```

These endpoints are local readonly APIs for approved backup-root manifests. They accept only `limit`; they must not accept backup root, restore path, delete flag, cleanup flag, upload target, or arbitrary filesystem path parameters.

Allowed response fields include:

- `status`
- `business_message`
- `backup_count`
- `manifest_count`
- `items`
- `summary`
- `latest_backup`
- `all_manifests_valid`
- `all_sensitive_scans_passed`
- abbreviated SHA-256
- retention metadata
- safe baseline counts
- `backup_deleted=false`
- `real_restore_executed=false`
- `production_db_touched=false`
- `rows_written=0`
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `formal_sync_open=false`
- `platform_writes_enabled=false`

Unsupported query parameters return HTTP 400 with safe business copy and no raw path echo. `POST`, `PUT`, `PATCH`, and `DELETE` are not supported.

### Backup Creation Audit Mock Gate

```text
write_backup_creation_audit_mock_gate(...)
```

This private service helper may write only to the temporary verification database. It requires private scope, manual approval, safe backup evidence, valid SHA-256, `sqlite_integrity_check=ok`, `backup_created=true`, `manifest_written=true`, `raw_response_saved=false`, `secrets_saved=false`, and `privacy_fields_redacted=true`.

The mock audit chain is:

```text
backup_planned
backup_created
backup_hash_verified
backup_integrity_verified
backup_manifest_verified
```

### Backup Creation Audit Runtime Wiring and Local Writer

```text
write_backup_creation_audit_runtime_wiring_mock_gate(...)
write_backup_creation_audit_local(...)
```

`write_backup_creation_audit_runtime_wiring_mock_gate` is a private 1Z verification helper. It accepts only safe backup evidence, manual approval, and the private verification scope, then writes the five-row backup audit chain only to the temporary verification database.

`write_backup_creation_audit_local` is the controlled 2A local writer for an approved real local backup. It is blocked unless the caller provides explicit write intent, manual approval, the private local writer scope, a successful backup helper result, a manifest path, valid SHA-256, `sqlite_integrity_check=ok`, `backup_created=true`, `manifest_written=true`, `raw_response_saved=false`, `secrets_saved=false`, and `privacy_fields_redacted=true`.

Allowed audit actions are exactly:

```text
backup_planned
backup_created
backup_hash_verified
backup_integrity_verified
backup_manifest_verified
```

The local writer may write only append-only `operation_audit_logs` rows. It must not write orders, products, `SyncLog`, `ApiCapabilityTestResult tested_success`, order timeline events, platform data, raw responses, tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, complete platform identifiers, buyer/receiver privacy, phones, addresses, or zip codes. It must not restore or delete backup files.

### Naver Order Refresh Backup Evidence Gate

```text
_evaluate_naver_order_refresh_batch_with_backup_evidence_gate(...)
```

This private helper wraps the existing Naver order refresh batch mock gate. Write-enabled paths require safe backup evidence before manual approval can proceed. Readonly paths do not require backup evidence because they do not write local data.

Phase Naver-ERP-18C is the controlled readonly repeat result. It uses the existing public `POST /api/v1/sync/orders/naver/preview` contract with `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. It returned HTTP 200 for token, feed, and detail. The safe observed hash was `id-hash-192b9c67e8`, with `DELIVERED / 配送完成`, amount `499000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. It did not write orders, products, SyncLog, `ApiCapabilityTestResult tested_success`, operation audit rows, or order status events, and it did not open formal order sync or execute any platform write operation.

Phase Naver-ERP-18D is the controlled refresh-write approval review result. It does not change the public API surface and does not approve a refresh write for safe hash `id-hash-192b9c67e8`, because local readback shows that hash does not match an existing real local Naver order. Existing-order refresh writes remain limited to exactly matched local real Naver orders only. A later selected new-order candidate approval plan is required before this candidate can be considered for a single new-order local write. 18D does not call Naver, execute `real_sync=true`, write local data, write audit rows, change schema, or open formal order sync.

Phase Naver-ERP-19A is the selected new-order candidate approval contract for safe hash `id-hash-192b9c67e8`. It does not change the public API surface, call Naver, execute `real_sync=true`, write data, write audit rows, change schema, or open formal sync. It approves only a later readonly repeat for the selected hash. A future single new-order local write must require exact selected-hash repeat, duplicate count zero, privacy and status gates, fresh database backup, one-order limit, post-write readback, audit evidence, no SyncLog write, no tested-success write, no product write, and no Naver platform write operation.

Phase Naver-ERP-19B is the selected new-order readonly repeat result. It uses the existing public `POST /api/v1/sync/orders/naver/preview` contract with `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail returned HTTP 200. The observed safe hash matched `id-hash-192b9c67e8`, remained `candidate_new`, and local duplicate real-order matches stayed zero. It did not write orders, products, SyncLog, `ApiCapabilityTestResult tested_success`, operation audit rows, or order status events, and it did not open formal order sync or execute any platform write operation.

Phase Naver-ERP-19C is the selected new-order single local write approval contract for safe hash `id-hash-192b9c67e8`. It does not change the public API surface, call Naver, execute `real_sync=true`, write data, write audit rows, create backups, change schema, or open formal sync. A later 19D may write at most one local Naver order only after clean worktrees, fresh database backup, fresh readonly preview, duplicate count zero, privacy and status gates, one-candidate limit, post-write readback, and five-row operation audit evidence. It must not write products, SyncLog, `ApiCapabilityTestResult tested_success`, or Naver platform data.

Phase Naver-ERP-19D is the selected new-order single local write result. It uses the existing public preview endpoint only for a fresh readonly repeat with `real_sync=false`, then uses the private selected-new-order local write gate for exactly one local order after the backup, duplicate, privacy, and sensitive scans pass. The selected safe hash is `id-hash-192b9c67e8`; local counts changed as expected: `orders_store8=6 -> 7`, `products_store8=5 -> 5`, `sync_logs_store8=1 -> 1`, `tested_success_store8=8 -> 8`, and `order_status_events=0 -> 0`. Five append-only audit rows were written under one correlation id. This does not open formal order sync and does not enable any Naver platform write operation.

Phase Naver-ERP-19E is post-write readback verification. It confirms the selected safe hash exists exactly once, `orders_store8=7`, `operation_audit_logs=10`, and five 19D audit actions exist: `approval_verified`, `pre_write_backup_verified`, `selected_operation_started`, `selected_operation_finished`, and `post_write_verification_finished`. 19E does not call Naver or write data.

### Role Permission Mock Gates

```text
evaluate_store_scoped_access_mock_gate(...)
evaluate_sensitive_action_approval_mock_gate(...)
role_permission_inventory()
```

ERP-Auth-1B and ERP-Auth-1C add private backend service helpers. ERP-Auth-1F exposes a narrow mock-only API wrapper around those helpers for frontend role/action visibility. These routes do not create sessions, do not add user tables, do not change schema, and are not production auth dependencies.

`evaluate_store_scoped_access_mock_gate(...)` verifies private verification scope, safe actor context, known role, requested store scope, and operation permission. `evaluate_sensitive_action_approval_mock_gate(...)` additionally verifies that a sensitive action has manual approval and an approving role.

The first roles are `owner`, `admin`, `operator`, `auditor`, and `viewer`. Sensitive actions include local order writes, order refresh batch writes, backup creation, database restore, credential updates, schema migrations, and formal sync opening.

The mock gate response must keep `real_database_written=false`, `orders_written=false`, `products_written=false`, `sync_log_written=false`, `capability_tested_success_written=false`, `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`, `formal_sync_open=false`, and `platform_writes_enabled=false`.

Runtime mock permission API:

```text
GET /api/v1/permissions/role-inventory
POST /api/v1/permissions/mock-check
POST /api/v1/permissions/sensitive-action/mock-check
```

`POST /api/v1/permissions/mock-check` accepts:

```json
{
  "actor_context": {
    "actor_id": "safe local actor label",
    "role": "operator",
    "store_ids": [8]
  },
  "store_id": 8,
  "operation_key": "orders.read"
}
```

`POST /api/v1/permissions/sensitive-action/mock-check` accepts the same safe actor context plus:

```json
{
  "action_key": "orders.refresh_batch_write",
  "manual_approval": false
}
```

Allowed response data is limited to safe role label, actor hash, requested store id, operation/action key, booleans for store-scope/permission/approval status, safe `skip_reason`, business message, and safety flags. Responses must include `mock_permission_api=true`, `public_endpoint_enabled=true`, `real_auth_session_created=false`, `real_database_written=false`, `raw_response_saved=false`, `formal_sync_open=false`, and `platform_writes_enabled=false`. The API must not return token, Authorization, request or response headers, signatures, bcrypt inputs, client secrets, raw responses, complete channel/order/product-order ids, complete buyer/receiver privacy, phones, addresses, or zip codes.

### Naver Order Refresh Batch Approval Plan

Phase Naver-ERP-20A does not change the public API surface. A later controlled refresh batch write may be considered only after backup evidence, fresh readonly preview, existing-order identity match, store-scoped role permission, sensitive-action approval, audit chain preparation, post-write readback, and sensitive scan all pass. Formal order sync remains closed.

Phase Naver-ERP-20B uses the existing `POST /api/v1/sync/orders/naver/preview` contract in readonly mode with a recent 3-day KST window, `store_id=8`, `credential_id=7`, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail returned HTTP 200. The safe hash `id-hash-192b9c67e8` matched exactly one existing local Naver order, so it is an existing local refresh candidate. It did not write orders, products, SyncLog, tested-success rows, audit rows, or timeline events.

Phase Naver-ERP-20C is planning-only. It does not execute a refresh write and does not add a new write route. A later refresh write must repeat 20B readonly evidence, verify exact identity match, require fresh backup evidence, pass the runtime permission mock gate, require sensitive action approval, write append-only audit evidence, and pass post-write readback plus sensitive scan.

Phase Naver-ERP-20D is the controlled refresh write approval with permission evidence. It does not add a new route and does not write orders. The runtime permission mock API must show store-scoped permission for `orders.refresh_batch_write` and sensitive-action approval before the later refresh gate can run.

Phase Naver-ERP-20E uses the existing private refresh batch gate with `max_batch_size=1`, the existing backup evidence gate, and a fresh readonly Naver preview for safe hash `id-hash-192b9c67e8`. The gate outcome is `batch_refresh_no_change`: no whitelisted business fields changed, so no local order update is forced. The operation writes five append-only audit rows with correlation id `audit-corr-20e-192b9c67e8`; the terminal row is `local_write_blocked` with reason `no_business_field_change`. This is an expected safe outcome, not a formal sync opening.

Phase Naver-ERP-20F verifies the 20E result by readback only. The selected safe hash exists exactly once, business counts remain stable, and the 20E audit chain contains `approval_planned`, `pre_write_backup_verified`, `local_write_attempted`, `local_write_blocked`, and `post_write_verification_succeeded`.

Phase ERP-Auth-1G is a frontend-wide visibility plan for the mock permission API. Phase ERP-Auth-1H records the production-auth boundary: the current permission API must not be treated as final authentication or authorization until user, session, role, store-membership, route-dependency, and role-assignment flows are separately designed, migrated, tested, backed up, and approved.

### Future Auth Schema Proposal and Mock Migration Gate

ERP-Auth-1I proposes future auth tables:

```text
erp_users
erp_roles
erp_permissions
erp_role_permissions
```

ERP-Auth-1J proposes:

```text
erp_store_memberships
```

The proposed schema stores safe identifiers such as user hashes, masked login identifiers, role keys, permission keys, and store membership status. It must not store tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full platform order or product-order ids, buyer or receiver names, phones, addresses, or zip codes.

ERP-Auth-1K adds only a `verify_all.py` temporary-database mock migration gate. It verifies the future table shape, seed roles, permission links, admin approval capability, store 8 membership, store 9 isolation, sensitive-column exclusions, and unchanged business counts. It does not expose a public auth API, create sessions, write production auth rows, migrate `backend/codex1.db`, call platform APIs, or open formal sync.

ERP-Auth-1L approves the real local migration only after clean worktrees, a pre-migration backup, manifest evidence, and `verify_all.py` success. ERP-Auth-1M implements and applies the schema through:

```text
scripts/upgrade_auth_schema.py
```

The real local migration may seed system role/permission metadata, but it must keep:

- `erp_users=0`
- `erp_store_memberships=0`
- `real_auth_session_created=false`
- `formal_sync_open=false`
- `platform_writes_enabled=false`

ERP-Auth-1N verifies the applied local schema by readback. The current verified counts are:

```text
erp_roles=5
erp_permissions=10
erp_role_permissions=35
erp_users=0
erp_store_memberships=0
```

No public user, role, login, or store-membership API is available yet.

### Restore Runbook Boundary

ERP-Backup-2A is planning-only. Real restore remains closed. Any later restore implementation must require source backup manifest verification, SHA-256 and size checks, temporary restore dry-run, baseline-count review, pre-restore backup, human approval, audit evidence, rollback instructions, and post-restore verification.

ERP-Backup-2B adds a private restore runbook mock drill gate:

```text
evaluate_restore_runbook_mock_drill_gate(...)
```

It verifies checklist readiness only. It must keep `real_restore_executed=false`, `production_db_touched=false`, `backup_deleted=false`, `rows_written=0`, `raw_response_saved=false`, `secrets_saved=false`, and `privacy_fields_redacted=true`.

### No-Change Order Refresh Display Boundary

Naver-ERP-21A is a display check for the 20E/20F result. A no-change refresh should be shown as a checked order with no business-field changes and no forced local update. The audit rows may be displayed as evidence, but the UI and APIs must not describe that outcome as formal Naver order sync availability.

Naver-ERP-21B keeps the same runtime wording boundary: `no_business_field_change` is an audit reason and administrator diagnostic, not a seller-facing error.

The helper must keep:

- `formal_order_sync_open=false`
- `platform_writes_enabled=false`
- `raw_response_saved=false`
- `privacy_fields_redacted=true`
- `products_written=false`
- `sync_log_written=false`
- `capability_tested_success_written=false`
- `timeline_events_written=false`

### Sensitive Boundary

Local backup, restore, audit, and order-refresh gate responses must not include tokens, Authorization values, request or response headers, signatures, bcrypt inputs, client secrets, raw external responses, complete channel ids, complete order/product-order ids, complete buyer or receiver names, phones, addresses, or zip codes.

### Formal Batch Sync Gate Contract

No public formal product/order batch sync endpoint is open yet.

Phase ERP-Batch-1B adds only a private backend helper:

```text
_evaluate_formal_batch_sync_production_gate(...)
```

Allowed `sync_kind` values:

```text
naver_order_batch
naver_order_refresh_batch
naver_product_batch
```

The helper must require:

- private verification scope
- valid target store ids
- positive candidate and batch counts
- conservative batch-size limits
- fresh readonly preview evidence
- `real_sync=false`
- `raw_response_saved=false`
- `privacy_fields_redacted=true`
- duplicate check passed
- field whitelist verified
- verified backup evidence
- audit plan ready
- rollback plan ready
- duplicate protection ready
- failure isolation ready
- multi-store isolation ready
- store-scoped permission and sensitive-action approval for every target store

A passing helper result may return:

```text
status=formal_batch_gate_ready_for_later_execution
```

but must still keep:

```text
formal_sync_open=false
formal_order_sync_open=false
formal_product_sync_open=false
platform_writes_enabled=false
orders_written=false
products_written=false
sync_log_written=false
capability_tested_success_written=false
real_api_called=false
public_endpoint_enabled=false
```

The role/permission model includes planning keys `products.batch_sync_write`, `orders.batch_sync_write`, and `orders.refresh_batch_write`. These keys are not production login, not active user assignment, and not a formal sync opening.

The contract continues to prohibit storing or returning tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw external responses, complete channel ids, complete order/product-order ids, complete buyer or receiver privacy, phones, addresses, or zip codes.

### Readonly Evidence Planning Contract

ERP-Batch-1C plans a future readonly evidence API for formal batch approval screens. This route is not implemented yet and must not be treated as a write path.

Future evidence responses may include safe fields only:

```text
safe evidence id
store id
platform
sync kind
readonly window label
candidate count
would_create
would_update
would_refresh_only
would_skip
changed_field_names
duplicate_check_passed
field_whitelist_verified
backup_required
permission_required
audit_required
business_message
next_action
```

The current readonly evidence is still produced by existing protected preview routes:

```text
POST /api/v1/sync/orders/naver/preview
POST /api/v1/sync/products/naver/preview
```

Naver-Order-Batch-1B used the order preview route with `real_preview=true`, `include_detail=true`, and `real_sync=false`. The protected endpoint remains limited to `page=1,size=1`, so the current batch-candidate window is one candidate at a time.

Naver-Product-Batch-1B used the product preview route with `real_preview=true` and `real_sync=false`. `page=1,size=5` observed stock-quantity changes on 3 existing products; `page=2,size=5` returned empty. This evidence requires manual review before any later write phase.

No evidence route may include token, Authorization, headers, signature, bcrypt input, client secret, raw response, full channel id, full product/order id, full buyer or receiver privacy, phone, address, or zip code.

### Product Stock-Change Mock Gate Contract

Phase Naver-Product-Batch-1D adds a private helper only:

```text
_evaluate_naver_product_stock_change_mock_write_gate(...)
```

The helper may return `stock_change_mock_gate_ready_for_later_write_phase` only when:

- `store_id=8`
- dry-run evidence is present and safe
- changed fields are exactly `stock_quantity`
- approved changed fields match observed changed fields
- `would_update > 0`
- `would_create = 0`
- `would_skip = 0`
- backup evidence is verified
- audit plan is ready
- rollback plan is ready
- `products.batch_sync_write` approval passes

The helper must keep:

```text
products_written=false
orders_written=false
sync_log_written=false
capability_tested_success_written=false
operation_audit_rows_written=false
formal_product_sync_open=false
platform_writes_enabled=false
```

### Store Membership Assignment Mock Gate Contract

Phase ERP-Multistore-1C adds a private helper only:

```text
evaluate_store_membership_assignment_mock_gate(...)
```

The helper checks target user safe hash, target store id, target role, assignment reason, `store_membership.assign` approval, and duplicate active membership.

It must keep:

```text
membership_written=false
real_database_written=false
real_auth_session_created=false
formal_sync_open=false
platform_writes_enabled=false
```

No public user, role, login, or membership assignment endpoint is open yet.

### Product Stock-Change Local Write Contract

Phase Naver-Product-Batch-1E adds a controlled approval wrapper:

```text
_evaluate_naver_product_stock_change_real_write_approval(...)
```

The wrapper may return `stock_change_real_write_approved` only when the stock-change evidence already passes the private gate, backup evidence is verified, an admin role approves `products.batch_sync_write`, and rollback/audit planning is ready. It does not write products by itself and keeps:

```text
products_written=false
real_database_written=false
formal_product_sync_open=false
platform_writes_enabled=false
```

Phase Naver-Product-Batch-1F adds:

```text
_sync_naver_product_stock_change_local_write(...)
```

The helper is private and may update only `products.stock_quantity` for existing `store_id=8`, `platform=naver` products. It must block:

- product creates
- skipped candidates
- non-stock field changes
- missing backup evidence
- missing approval gate
- write counts above the phase limit

It must not write orders, SyncLog, tested-success, operation audit rows, timeline events, users, or store memberships. It must not save raw response, token, Authorization, headers, signature, client secret, full channel id, or full external product id in its result.

Phase ERP-Batch-1F is still a plan for a future readonly evidence API. No public readonly evidence route is available yet.

Phase ERP-Multistore-1D is still an approval plan. Real user creation and real store membership assignment remain closed.

### Batch Readonly Evidence API Contract

Phase ERP-Batch-1H exposes a local readonly endpoint:

```text
POST /api/v1/batch/readonly-evidence
```

Request body:

```json
{
  "max_items": 10,
  "evidence_items": [
    {
      "evidence_id": "safe-label",
      "store_id": 8,
      "sync_kind": "naver_product_batch",
      "window_label": "page=1,size=5 post-write",
      "candidate_count": 5,
      "would_create": 0,
      "would_update": 0,
      "would_refresh_only": 5,
      "would_skip": 0,
      "changed_field_names": [],
      "duplicate_check_passed": true,
      "field_whitelist_verified": true,
      "real_sync": false,
      "raw_response_saved": false,
      "privacy_fields_redacted": true,
      "formal_sync_open": false
    }
  ]
}
```

Successful response status is `readonly_evidence_api_ready`. Blocked unsafe input returns a safe blocked payload with `skip_reason`, not raw input.

The endpoint must keep:

```text
real_api_called=false
real_database_written=false
orders_written=false
products_written=false
sync_log_written=false
capability_tested_success_written=false
operation_audit_rows_written=false
timeline_events_written=false
raw_response_saved=false
secrets_saved=false
formal_sync_open=false
platform_writes_enabled=false
```

It must not return token, Authorization, headers, signature, bcrypt input, client secret, raw response, full channel id, full platform order id, full product id, buyer/receiver privacy, phone, address, or zip code.

### Store Membership Runtime Mock Contract

Phase ERP-Multistore-1E adds:

```text
evaluate_store_membership_assignment_runtime_mock_gate(...)
```

It reads existing auth tables to check target user existence, active role, approval, and duplicate memberships. It does not create users, memberships, sessions, or role assignments.

### Batch Approval UI Evidence Contract

Phase ERP-Batch-1J connects the frontend approval evidence display to:

```text
POST /api/v1/batch/readonly-evidence
```

The endpoint remains a normalizer only. UI callers may submit safe product/order evidence items, but the backend response must keep all execution flags closed:

```text
real_api_called=false
real_database_written=false
orders_written=false
products_written=false
sync_log_written=false
capability_tested_success_written=false
operation_audit_rows_written=false
timeline_events_written=false
formal_product_sync_open=false
formal_order_sync_open=false
platform_writes_enabled=false
```

Main UI should show business wording such as "approval evidence is ready" and "formal batch sync remains closed". Technical fields such as `sync_kind`, `would_create`, `would_update`, `would_refresh_only`, `phase`, and safety booleans should stay in folded technical details.

### Store Membership Assignment Readonly API Plan

Phase ERP-Multistore-1F is planning-only. A later readonly API may expose safe membership-assignment readiness for administrators, but it must not create users, assign roles, create store memberships, open login, or enable large-scale multi-store production operation.

The future API should return only safe fields:

```text
target_user_exists
target_role_exists
duplicate_active_membership
membership_would_create
membership_written=false
real_database_written=false
raw_response_saved=false
secrets_saved=false
formal_sync_open=false
```

### Store Membership Readonly API Contract

Phase ERP-Multistore-1G exposes the readonly contract:

```text
POST /api/v1/permissions/store-membership/readonly-check
```

Request body:

```json
{
  "actor_context": {
    "actor_id": "admin-safe-id",
    "role": "admin",
    "store_ids": [8]
  },
  "target_user_key_hash": "user-hash-safe",
  "target_store_id": 8,
  "target_role": "operator",
  "manual_approval": true,
  "assignment_reason": "safe business reason"
}
```

Successful readiness response status is `membership_assignment_runtime_mock_ready`. Blocked responses may include safe `skip_reason` values such as `target_user_not_found`, `duplicate_active_membership`, `manual_approval_required`, or `membership_assignment_sensitive_material_blocked`.

The response must keep:

```text
store_membership_readonly_api_mock_gate=true
readonly_api_mock_gate=true
public_endpoint_enabled=true
membership_written=false
real_database_written=false
real_auth_session_created=false
raw_response_saved=false
secrets_saved=false
formal_sync_open=false
platform_writes_enabled=false
```

Main UI should show the Chinese `business_message`. Technical fields such as `phase`, `skip_reason`, `target_user_exists`, `target_role_exists`, and `duplicate_active_membership` should stay folded in diagnostics.

The endpoint must not create users, create role assignments, create store memberships, open login sessions, write orders, write products, write SyncLog, write tested-success rows, or expose token, Authorization, headers, signature, bcrypt input, client secret, raw response, buyer privacy, or complete platform identifiers.

### Product Rollback Drill Mock Gate Contract

Phase Naver-Product-Batch-1J adds a private mock gate:

```text
_evaluate_naver_product_batch_rollback_drill_mock_gate(...)
```

It requires verified backup evidence, a prior `Naver-Product-Batch-1F` stock-only write summary, and a rollback checklist covering manifest availability, pre-write counts, changed product hashes, reviewed rollback SQL, temporary restore dry-run planning, post-rollback readback planning, sensitive scanning, and formal-sync closure.

It must block:

- missing rollback checklist flags
- real restore requests
- production database restore targets
- non-stock write summaries
- product creates
- unsafe backup evidence
- sensitive material in any rollback evidence

It must keep:

```text
rollback_executed=false
real_restore_executed=false
production_db_touched=false
products_written=false
orders_written=false
sync_log_written=false
capability_tested_success_written=false
operation_audit_rows_written=false
formal_product_sync_open=false
```

### Order Batch Readonly Evidence Alignment

Phase Naver-Order-Batch-1C uses the shared batch readonly evidence API shape for order-batch review evidence. Order evidence may include safe changed-field names such as `order_status`, `delivery_status`, `claim_status`, and `payment_status`.

This alignment is not an order sync endpoint. It must not call Naver, write orders, write timeline events, save raw responses, expose buyer privacy, or open formal order batch sync.

### Batch Evidence Business Wording Contract

Phase ERP-Batch-1L requires backend fallback messages for readonly batch evidence to be Chinese business wording:

```text
只读批量证据已整理，等待人工审核。
批量同步只读证据已整理。本次不会调用平台、不会同步、不会写入商品或订单。
```

The endpoint remains a readonly normalizer. It must not use backend wording to imply that product or order batch sync is open.

### Product Rollback Drill Readonly Report Contract

Phase Naver-Product-Batch-1L adds a private report gate:

```text
_evaluate_naver_product_batch_rollback_drill_readonly_report_mock_gate(...)
```

The report may include safe sections such as backup evidence, stock-only write summary, rollback checklist, temporary restore planning, readback planning, and sensitive-scan planning.

It must keep:

```text
report_ready=true
real_restore_executed=false
rollback_executed=false
production_db_touched=false
products_written=false
orders_written=false
sync_log_written=false
capability_tested_success_written=false
operation_audit_rows_written=false
raw_response_saved=false
secrets_saved=false
formal_product_sync_open=false
```

The report must not restore a database, write products, write orders, expose raw responses, expose full product ids, or imply formal Naver product batch sync is open.

### Order Batch Evidence Wording Contract

Phase Naver-Order-Batch-1E requires order-batch readonly evidence defaults to be business-readable Chinese. Missing order evidence messages should default to:

```text
Naver 订单批量只读证据已整理，等待人工审核。
继续人工审核订单证据；正式订单批量同步仍未开放。
```

This is only approval evidence wording. It must not call Naver, write orders, write timeline events, or open formal order batch sync.

### Batch Evidence Audit Linkage Contract

Phase ERP-Batch-1M adds audit-linkage planning to readonly batch evidence:

```text
operation_audit_rows_planned=true
operation_audit_rows_written=false
```

Future product or order batch writes must create append-only audit rows in a separately approved execution phase. The readonly evidence route must not write audit rows by itself.
