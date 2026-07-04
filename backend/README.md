# Codex 1 Backend

FastAPI backend for the AI multi-store operations and environment management system.

## Technology Stack

```text
FastAPI
SQLAlchemy 2.x
Pydantic v2
SQLite for development
cryptography.Fernet
Uvicorn
```

## Documentation Index

```text
docs/API_CONTRACT.md
docs/DATABASE_MODELS.md
docs/CODEX2_FRONTEND_HANDOFF.md
docs/CODEX3_MERGE_NOTES.md
```

## Current Scope

Stage 1F provides the backend foundation, secure credential base, mock data sync pipeline, local analytics APIs, and mock operations support modules:

- Versioned API prefix at `/api/v1`
- Compatible legacy health check at `/health`
- SQLAlchemy models for stores, API credentials, sync logs, products, orders, and customer inquiries
- Store CRUD endpoints
- Encrypted API credential storage
- Naver and Coupang mock client placeholders
- Mock product, order, and customer inquiry sync services
- Read endpoints for products, orders, and customer inquiries
- Sales statistics service and endpoints
- Dashboard summary endpoint
- AI daily context endpoint with structured data only
- API capability matrix backend records for docs-only/manual API ability planning
- Device environment, email account, important email, and appeal case models
- CRUD endpoints for device environments, email accounts, important emails, and appeal cases
- Sync log service and read endpoint
- Unified success and error response structure
- Repeatable seed data for Chinese, Korean, and mixed UTF-8 text

This stage still does not call real Naver or Coupang APIs. It also does not connect to real Gmail, Naver, Daum, Outlook, or other mail providers; does not read real mail; does not upload attachments; does not run OCR; and does not call OpenAI, DeepSeek, or any other model.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Directory Summary

```text
app/                       FastAPI application package
app/api/v1/                Public versioned API routes
app/api/v1/endpoints/      Endpoint modules
app/models/                SQLAlchemy models
app/schemas/               Pydantic request/response schemas
app/services/              Business logic, encryption, stats, mock sync
app/clients/               Naver/Coupang mock clients
scripts/                   Key generation, seed, verification scripts
docs/                      API contract and handoff documents
```

## Credential Encryption Key

API access keys and secret keys are encrypted with `cryptography.Fernet`. The app does not provide a default encryption key.

Generate a key:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\generate_key.py
```

Configure it in a local `.env` file:

```text
CREDENTIAL_ENCRYPTION_KEY=<generated Fernet key>
APP_TIMEZONE=Asia/Seoul
```

`.env.example` contains only the field name and a placeholder. Do not commit `.env`, generated encryption keys, real platform access keys, or real platform secret keys.

If `CREDENTIAL_ENCRYPTION_KEY` is missing or invalid, credential create/update/decrypt operations return a clear API error instead of silently using a fallback key.

## Business Timezone

The backend business timezone is fixed by `APP_TIMEZONE`, defaulting to `Asia/Seoul`. Windows display timezone is not used for business dates; the machine clock only needs to be network-synchronized accurately.

Rules:

- Database datetimes are stored as UTC aware values.
- SQLite may return older local development rows without offsets; service code treats naive datetimes as UTC for compatibility.
- "today", daily sales, daily order grouping, and AI daily context default dates use Korean natural days.
- Korean business day ranges use `[start, next_start)` in UTC. KST `2026-06-30` maps to UTC `2026-06-29T15:00:00+00:00` through `2026-06-30T15:00:00+00:00`.
- SyncLog timestamps are written in UTC. Frontend display should convert timestamps to KST in a later frontend stage.

## Run

```powershell
uvicorn app.main:app --reload
```

If port `8000` is occupied during Codex2 frontend integration, run on `8011`:

```powershell
uvicorn app.main:app --reload --port 8011
```

Then open:

- API root: http://127.0.0.1:8000/
- API v1 health check: http://127.0.0.1:8000/api/v1/health
- Legacy health check: http://127.0.0.1:8000/health
- Swagger docs: http://127.0.0.1:8000/docs

Codex2 local integration URLs:

```text
API base URL: http://127.0.0.1:8011/api/v1
Swagger: http://127.0.0.1:8011/docs
```

Codex2 Vite environment:

```text
VITE_API_BASE_URL=http://127.0.0.1:8011/api/v1
VITE_DATA_SOURCE=backend
```

Local CORS is enabled for:

```text
http://127.0.0.1:5173
http://localhost:5173
http://127.0.0.1:5174
http://localhost:5174
```

## Verification

Run the full regression suite:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\verify_all.py
```

Individual stage scripts are also available:

```text
scripts/verify_stage_1b.py
scripts/verify_stage_1c.py
scripts/verify_stage_1d.py
scripts/verify_stage_1e.py
scripts/verify_stage_1f.py
```

`scripts/verify_all.py` uses an isolated temporary SQLite database and does not mutate `backend/codex1.db`. It is safe to run during real API integration as long as the script keeps its temp-db guardrail.

The verification scripts rebuild the local SQLite database during tests and should be used for local validation only.

## API Response Format

Successful responses:

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

Error responses:

```json
{
  "success": false,
  "message": "店铺不存在",
  "error_code": "STORE_NOT_FOUND",
  "detail": {}
}
```

## Store APIs

All formal business APIs use the `/api/v1` prefix:

```text
GET    /api/v1/health
POST   /api/v1/stores
GET    /api/v1/stores?page=1&page_size=20
GET    /api/v1/stores/{store_id}
PUT    /api/v1/stores/{store_id}
DELETE /api/v1/stores/{store_id}
```

Deletion is currently a hard delete. A later stage can extend this to soft delete by changing the delete behavior to update `status` or adding a dedicated deleted marker.

## Credential APIs

Credential endpoints use the same unified response format:

```text
POST   /api/v1/credentials
GET    /api/v1/api-credentials/readiness
POST   /api/v1/api-credentials/smoke-test
GET    /api/v1/credentials?store_id={store_id}
GET    /api/v1/credentials/{credential_id}
PUT    /api/v1/credentials/{credential_id}
DELETE /api/v1/credentials/{credential_id}
```

Create and update requests accept `access_key` and `secret_key`, but the API never returns plaintext keys. Responses only include metadata such as `has_access_key` and `has_secret_key`.

`GET /api/v1/api-credentials/readiness` supports two paths. The env fallback path reads only local `.env` variable presence and remains a temporary developer path. The formal multi-store path is store-bound: `GET /api/v1/api-credentials/readiness?store_id=...` checks the selected store and its active encrypted credential metadata without calling Naver or Coupang. Neither path returns access keys, secret keys, client secrets, tokens, encrypted values, or decrypted database credentials.

`POST /api/v1/api-credentials/smoke-test` accepts `platform: naver | coupang | all` and `mode: readonly`. The env fallback path remains a developer-only fallback and does not write `ApiCapabilityTestResult`. The formal Naver path is store-bound and requires `store_id` plus an active credential. When `REAL_API_TEST_ENABLED=false`, the endpoint returns disabled results before creating any external HTTP client. When enabled, it runs only minimal read-only checks and still never returns keys, tokens, authorization headers, request signatures, or raw external response payloads. `REAL_API_WRITE_ENABLED=false` keeps write operations out of scope. Store-bound readonly smoke tests may write local `ApiCapabilityTestResult` records with `test_mode=real_readonly`; those records contain only step statuses, error code, HTTP status, timestamps, and docs-pending guardrail metadata. For Naver 401/403 responses, the backend now returns only safe classifications such as `ip_not_allowed`, `credential_invalid`, `permission_forbidden`, `product_api_not_allowed`, `token_auth_failed`, or `unknown_forbidden`, along with safe keyword flags and operator-facing business hints.

Naver product/order real preview is intentionally locked behind guardrails. The current reference documentation line is current / 2.81.0, but product and order requests are not yet sent to the real API. Planned preview endpoints are:

```text
POST /api/v1/sync/products/naver/preview
POST /api/v1/sync/orders/naver/preview
```

The Naver product preview route now exists with an explicit `real_preview` gate. `POST /api/v1/sync/products/naver/preview` still defaults to `real_preview=false` and returns `guardrail_status=blocked`, `preview_status=blocked`, `test_status=not_tested`, and `error_code=guardrail_blocked` before token exchange or external HTTP. When `real_preview=true`, the route first enforces the approved local store/credential, `status` null/ALL, `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, decryptable credential, configured channel number, and `minimum_request_body_confirmed=true`. The current split gate is deliberate: readonly preview keeps `real_sync=false` and allows `page in {1,2}` with `size<=5`, while the approved local sync small-batch test still requires `real_sync=true`, `page=1`, and `size<=5`. The only real Naver request body allowed by this gate is the minimum shape `{"page":P,"size":N}` for `POST /v1/products/search`, where readonly preview allows `P` in `{1,2}` and `N` in `1..5`, while local sync remains capped at `P=1` and `N<=5`. It does not pass internal `status=ALL`, `productStatusTypes`, keyword, seller product id, date filters, search keyword fields, product-number filters, or full channel number. Readonly preview does not write `products`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`. Credential decryptability only proves the local encrypted secret can be read; it does not prove formal Naver product sync access.

Phase 6D-6G completed a real Naver product readonly micro preview with HTTP 200. Phase 6D-6H keeps the endpoint preview-only and adds a sanitized field-mapping summary for frontend/business review. The response can include `product_field_mapping_summary`, `observed_field_names`, `missing_field_names`, `mapping_readiness`, and `channel_products_summary`, but it never returns raw product payloads, long HTML, image-detail payloads, full channel numbers, tokens, headers, signatures, or client secrets. The current `products` table can hold a first product snapshot with `external_product_id`, `name`, `status`, `price`, `currency`, `stock_quantity`, `source_type`, and JSON `raw_data`; Naver `originProductNo`, `channelProductNo`, display status, and channel-product counts must remain sanitized metadata in `raw_data` for a future sync phase. Multiple `channelProducts` are counted only and never expanded or written in preview.

Phase 6D-6I adds `dry_run_diff` to the same preview response. The dry-run estimates future local sync impact with `would_create`, `would_update`, `would_skip`, `skip_reasons`, `matched_existing_count`, and `incoming_candidate_count` by reading local `products` with `store_id + platform + external_product_id`; it never writes products, SyncLog, or capability success records. Single-channel products with `channelProductNo` and `productName` can become create/update candidates. Multiple `channelProducts`, missing external IDs, and missing product names are skipped. Missing price or stock is reported as optional metadata but does not force a skip. `dry_run_diff` is not formal sync availability, and real writes require a separately approved phase.

Phase 6D-6M expands only the readonly preview side into a small-batch dry-run. `real_preview=true` with `real_sync=false` may request up to 5 products through the same minimum body shape `{"page":P,"size":N}` and returns at most 5 masked `sample_ids`. In the current guarded implementation, readonly preview allows `page in {1,2}` and `1 <= size <= 5`; local sync is still not opened beyond `page=1`. The response keeps `dry_run_diff.would_create` and `would_update` for local impact estimation, and adds `single_channel_product_count`, `multiple_channel_products_count`, `missing_external_product_id_count`, `missing_product_name_count`, `missing_price_count`, and `missing_stock_count`. `ready_for_local_sync` is deliberately pinned to `false` in this small-batch preview so the frontend and operators do not confuse readonly observation with a writable sync approval. `real_sync=false` remains strictly no-write: no local product rows, no SyncLog, and no capability success writes.

Phase 6D-6N-Pre-Impl strengthens that dry-run with a safer explanation layer before any future batch write decision. The preview can now describe create/update/skip reasons with `diff_summary`, `create_reasons`, `update_reasons`, field-name-only `changed_fields` and `unchanged_fields`, `missing_optional_fields`, `risk_flags`, `upsert_key_summary`, and `write_safety_summary`. It still does not write `products`, does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, does not save raw responses, and does not open batch sync. New skip reasons include duplicate external IDs in the same preview batch, invalid status shape, invalid price shape, and invalid stock shape; all returned samples remain masked and raw payloads remain suppressed.

Phase 6D-6P narrows the dry-run business semantics so operators do not misread a pure key match as a content update. `would_update` now counts only business-field changes (`name`, `status`, `price`, `currency`, `stock_quantity`). Existing local rows with no business-field change but metadata-only refresh work, such as `last_synced_at`, `source_type`, or sanitized `raw_data`, move to `would_refresh_only`. Existing local rows with neither business changes nor metadata refresh move to `would_no_change`. `matched_existing_count` continues to report how many incoming candidates matched local rows by `store_id + platform + external_product_id`. The preview remains readonly: no `products`, no `SyncLog`, no `ApiCapabilityTestResult tested_success`, and no raw response/token/header/signature persistence.

Phase 6D-6R prepares the next expansion step without opening larger writes. Readonly preview is now allowed to inspect `page=2,size=5` so the team can validate pagination boundaries before any follow-up write approval. `dry_run_diff.pagination_overlap_summary` now reports `requested_page`, `requested_size`, `matched_existing_candidate_count`, per-type matched counts, masked match samples, and a `recommended_action` of either `continue_readonly_review` or `stop_and_review_pagination`. For non-first-page preview, any `matched_existing_count > 0` is treated as overlap risk and forces `stop_and_review_pagination`. `write_safety_summary` also now makes two blockers explicit: `missing_optional_fields_block_write_approval=true` and `non_first_page_match_requires_manual_review=true`. `size=10`, `page>2`, cross-page auto writes, and formal batch sync remain blocked.

Phase 6D-6J is the design lock carried forward into the approved Naver local product small-batch write path. It still does not add a public batch sync endpoint, and real writes remain separately approved. The write path requires `real_sync=true`, `store_id=8`, `credential_id=7`, `page=1`, `size<=5`, and at most 5 single-channel products from the readonly upstream body `{"page":1,"size":N}`. A write candidate must have `channelProductNo` and `productName`; multiple `channelProducts`, missing external IDs, missing names, duplicate external IDs in the same batch, invalid status shape, invalid price shape, and invalid stock shape are blocked or skipped before any write approval. The future row shape uses `platform=naver`, `source_type=naver_real_sync`, `currency=KRW`, and sanitized `raw_data` only: `platform_origin_product_no`, `platform_channel_product_id`, `display_status`, `channel_products_count`, `source_preview_id_hash`, `mapping_version=naver_product_v1`, `synced_from=naver_product_preview`, and `raw_response_saved=false`. Raw Naver responses, HTML, image detail payloads, tokens, headers, signatures, client secrets, full channel numbers, and long descriptions must never be stored. Before every approved write, back up `backend/codex1.db`; after writing, read back `products where store_id=8 and platform='naver'`. A future sanitized `SyncLog` may use `sync_type=naver_product_local_sync` with requested size and created/updated/skipped counts, but Phase 6D-6J itself does not write SyncLog or mark `ApiCapabilityTestResult tested_success`.

Phase 6D-6K implements that approved local sync small-batch gate on the existing preview endpoint. The request must include `real_preview=true` and `real_sync=true`; `real_sync=true` without `real_preview=true` is blocked. The external Naver call remains readonly and uses only the minimum body `{"page":1,"size":N}` with `1 <= N <= 5`. The local write path runs only after a successful preview response and only for up to 5 single-channel candidates on `page=1`. It may create or update at most 5 local `products` rows with `source_type=naver_real_sync` and sanitized `raw_data`; it does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, does not save raw response/token/header/signature, and does not open formal batch product sync.

Phase 6D-6N completed the first controlled Naver local sync small-batch test on `page=1,size=5`, resulting in 4 creates and 1 update while keeping `SyncLog` unwritten, keeping `ApiCapabilityTestResult tested_success` unchanged, and keeping `raw_response_saved=false`. The local store now holds 5 Naver product rows for `store_id=8`. Phase 6D-6Q then verified the post-sync readonly semantics: the same 5 local products now surface as `matched_existing_count=5`, `would_create=0`, `would_update=0`, `would_refresh_only=5`, and `would_skip=0`. That result confirms the current page-1 batch is stable, but it does not open larger writes or formal batch sync.

Phase 6D-6S then validates `page=2,size=5` as a real readonly dry-run and returns `preview_status=success_empty`. That means there is currently no second-page product candidate to preview or write. The result does not change `products`, does not write `SyncLog`, does not add `ApiCapabilityTestResult tested_success`, and does not justify `page=2` local sync approval. `size=10`, `page=3`, and formal batch sync remain blocked.

Phase 6D-6T closes the current Naver product line by tightening safe error classification. Token or readonly 403 responses now surface only safe enums plus safe keyword flags:

- `ip_not_allowed`: IP / allowlist / gateway-IP signal detected
- `credential_invalid`: invalid client or client-secret style signal detected
- `permission_forbidden`: permission or forbidden signal detected outside the product-specific path
- `product_api_not_allowed`: token succeeded but the product API returned a permission-style 403
- `token_auth_failed`: token exchange failed without a stronger safe classification
- `unknown_forbidden`: readonly 403 without a stronger safe classification

The response may include `http_status`, `error_code`, `business_error_hint`, and `safe_keyword_flags`, but it must not include raw response text, request headers, `Authorization`, token values, signatures, `bcrypt` output, full `channel_no`, or full product identifiers.

The planned product preview route is based on `POST /v1/products/search`. The planned order preview route should read `GET /v1/pay-order/seller/product-orders/last-changed-statuses` first, then query details with `POST /v1/pay-order/seller/product-orders/query`. The older direct `GET /v1/pay-order/seller/product-orders` draft is treated as deprecated or unconfirmed and must not be called. Until a later preview stage explicitly opens these routes, product/order capability results stay `guardrail_blocked`, `not_tested`, and `safe_to_real_test=false`.

The Naver order preview route now exists as a micro readonly scaffold. `POST /api/v1/sync/orders/naver/preview` defaults to `real_preview=false` and returns blocked before token or HTTP. `real_preview=true` is restricted to the approved local store/credential, `page=1`, `size=1`, a KST window of seven days or less, and `REAL_API_WRITE_ENABLED=false`. The feed request uses the verified shape `lastChangedFrom` plus `limitCount=1`, formats `lastChangedFrom` with milliseconds, and omits `lastChangedTo`; it does not pass page, size, or order_status through to Naver. When `include_detail=true`, detail lookup is allowed only if the feed returns a productOrderId, and it queries at most one ID with `POST /v1/pay-order/seller/product-orders/query`. If the feed is empty, detail is skipped with `detail_skipped_reason=no_changed_orders` and the time window is not expanded. The response may include sanitized diagnostic metadata and detail field-observation booleans, but it never returns a full URL, query values, raw error body, request headers, token, full order IDs, productOrderIds, buyer/receiver names, phones, addresses, delivery details, payment raw payloads, authorization headers, signatures, or full `channel_no`. It never writes `orders`, never writes `SyncLog`, never writes `ApiCapabilityTestResult tested_success`, and never stores tokens/raw responses.

Phase Naver-ERP-1A moves Naver orders into feed-to-detail readonly preview. The first probe should use a recent 24-hour `lastChangedFrom`; if it returns `success_empty`, one bounded recent-7-day readonly feed probe may be used before stopping. `success_empty` means the Naver order API is connected but the current time range has no changed orders, so detail must not be forced. If the feed returns a product order id, the detail query remains capped at one id and returns only a sanitized `detail_preview`: id hashes, status enum plus Chinese label, safe product/option text, quantity, amount, timestamps, masked buyer name/phone, `address_saved=false`, `privacy_fields_redacted=true`, `raw_response_saved=false`, `orders_written=false`, and `mapping_version=naver_order_detail_preview_v1`. Unknown status enums set `unknown_status_observed=true` instead of guessing. This phase does not write `orders`, does not write `SyncLog`, does not add `ApiCapabilityTestResult tested_success`, does not run dispatch/cancel/return/exchange writes, and does not open formal Naver order sync.

Phase Naver-ERP-1B locks the Naver order detail mapping and privacy gate without any real API call or database write. The future single-order payload may only use the safe whitelist: `store_id`, `platform=naver`, hashed external order ids, `order_status`, `order_status_label_zh`, safe payment/delivery/claim statuses, safe product and option text, `quantity`, `order_amount`, `currency=KRW`, `ordered_at`, `paid_at`, `last_changed_at`, `source_type`, `last_synced_at`, `mapping_version`, `raw_response_saved=false`, and `privacy_fields_redacted=true`. Buyer and receiver data may only appear as masked names, masked phones, or hashed buyer id. Address-like fields set `address_observed=true` when seen, but `address_saved` must remain false. Full productOrderId, orderId, buyer/receiver names, phones, zip code, detailed address, raw responses, request headers, token, `Authorization`, signatures, bcrypt output, and client secrets are forbidden in preview responses, logs, test snapshots, and future write payloads.

The 1B status map includes `PAYED` / `결제완료` -> `已付款 / 新订单`, `PLACE_PRODUCT_ORDER` / `발주확인` -> `已确认订单`, `DISPATCHED` / `배송중` -> `已发货 / 配送中`, `DELIVERED` / `배송완료` -> `配送完成`, `CANCELED` / `CANCELLED` / `취소` -> `已取消`, `CANCEL_REQUEST` / `취소요청` -> `取消请求`, `RETURN_REQUEST` / `반품요청` -> `退货请求`, `EXCHANGE_REQUEST` / `교환요청` -> `换货请求`, and `PURCHASE_DECIDED` / `구매확정` -> `已确认购买`. Unknown status values must return `unknown_status_observed=true` and `未识别状态，需人工确认`, while storing only the safe enum sample and never the raw response.

Phase Naver-ERP-1C is the first phase that may consider a one-row local order write, and only after explicit user approval. Its gate must back up `backend/codex1.db`, restrict `store_id=8` and `credential_id=7`, use only the latest feed-matched single detail, save only the 1B whitelist, keep all privacy fields masked or hashed, keep addresses unsaved, set `raw_response_saved=false` and `privacy_fields_redacted=true`, read back the written row, avoid `SyncLog`, avoid new `ApiCapabilityTestResult tested_success`, and avoid dispatch/cancel/return/exchange write operations. Formal order sync remains closed.

Phase Naver-ERP-1C implements that controlled one-row local write gate on the existing order preview route. The request must include `real_preview=true`, `include_detail=true`, and `real_sync=true`; `real_sync=true` without detail is blocked. The upstream Naver calls remain readonly: token exchange, one `last-changed-statuses` feed request with only `lastChangedFrom` and `limitCount=1`, and one detail query only when the feed returns a product order id. The write window is capped at 24 hours. If the feed is `success_empty`, the local write result is `skipped/no_changed_orders` and no 7-day fallback is attempted in this write phase. A successful write creates at most one `orders` row with `source_type=naver_real_order_sync`, stores the hashed product-order id as the local `external_order_id`, and puts only sanitized metadata into `raw_data`. Duplicate hashes return `already_exists` and `no_duplicate_created`. The phase still does not write `products`, does not write `SyncLog`, does not add `ApiCapabilityTestResult tested_success`, does not save raw responses/tokens/headers/signatures, does not save complete buyer or receiver privacy data, and does not open formal order sync or shipment/claim writes.

Phase Naver-ERP-1D verifies the 1C write after the fact without another local write. The local Naver order count is one, `products_store8` remains five, `SyncLog` remains zero, and `ApiCapabilityTestResult tested_success` remains unchanged. The written order uses a hashed product-order key, `source_type=naver_real_order_sync`, `PAYED` / `已付款 / 新订单`, `currency=KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`; buyer phone is empty or masked and address data is not stored. A follow-up 24-hour `real_sync=false` feed-to-detail preview returned HTTP 200 and matched the existing product-order hash, while `local_sync_result.status=not_requested` and the database counts stayed unchanged. This is a post-write verification only; formal Naver order sync, batch order writes, shipment writes, and claim writes remain closed.

Phase Naver-ERP-5D adds an explicit complete-field readonly preview option to the existing Naver order preview route. `complete_field_preview=true` is allowed only with `real_preview=true`, `include_detail=true`, and `real_sync=false`; it is blocked without detail and blocked with any local write request. The default `detail_preview` remains privacy-redacted and continues to be the only shape used by the current 1C write gate. The new `complete_field_preview` is for operator review only and may expose complete order id, product order id, platform product id, buyer/receiver names, buyer/receiver phones, receiver address, zip code, safe product text, quantity, amount, status, and timestamps in the response. It does not change the database schema, does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult`, does not save raw responses, tokens, headers, signatures, or client secrets, and does not open formal Naver order sync. Its `save_plan` keeps `codex1_schema_write_enabled=false`, `orders_written=false`, `raw_response_saved=false`, and `formal_order_sync_open=false`.

Phase Naver-ERP-11B adds a mock-testable selected new-order write gate helper for future candidate persistence planning. The helper is not wired to `POST /api/v1/sync/orders/naver/preview`, does not add a public API parameter, and does not call Naver. `verify_all.py` covers readonly not-requested, stale preview, missing candidate, changed candidate, duplicate candidate, not-unique candidate, privacy-blocked candidate, and a one-row mock success path inside the temporary verification database. The gate keeps the existing 24-hour real write path unchanged and continues to require fresh preview, safe hash matching, duplicate checks, privacy gates, `raw_response_saved=false`, `privacy_fields_redacted=true`, `address_saved=false`, no `products` write, no `SyncLog`, no `tested_success`, no platform write operation, and formal order sync closed.

Phase Naver-ERP-11D documents the real selected-candidate write approval plan after a successful readonly retry. It does not call Naver, does not write `orders`, and does not add a public API. The current candidate safe hash is `id-hash-ab176f5db1`, classified as `candidate_new` by readonly duplicate checks, but that is not a write operation. Any future 11E write must be separately requested, back up `backend/codex1.db`, re-run or revalidate the fresh selected candidate, keep `store_id=8` and `credential_id=7`, write at most one local order, preserve the existing 24-hour write gate behavior, keep `products`, `SyncLog`, and `tested_success` unchanged, persist only sanitized order fields, and keep formal order sync closed.

Phase Naver-ERP-11E completed one selected-candidate local Naver order write for safe hash `id-hash-ab176f5db1`. The database was backed up first. A fresh readonly preview returned HTTP 200, feed/detail HTTP 200, status `DELIVERED`, amount `330000 KRW`, quantity 1, and duplicate count 0. The selected helper wrote exactly one sanitized local order, moving `orders_store8` from 4 to 5 and real Naver local orders from 1 to 2. `products_store8` stayed 5, `sync_logs_store8` stayed 1, and `tested_success_store8` stayed 8. The written row uses `source_type=naver_real_order_sync`, hashed external order id only, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Formal Naver order sync and all Naver platform write operations remain closed.

Phase Naver-ERP-11F verifies the 11E selected-candidate order after the write using local database readback only. It does not call Naver, does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult`, and does not change schema or Codex2. The selected hash `id-hash-ab176f5db1` exists exactly once with `source_type=naver_real_order_sync`, `order_status=DELIVERED`, `quantity=1`, `order_amount=330000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Current counts remain `orders_store8=5`, real Naver local orders 2, mock Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. Candidate-row sensitive scanning returned zero matches for token, client secret, Authorization, headers, signature/bcrypt markers, raw response body markers, plain phone shape, and address keywords. Formal Naver order sync and all Naver platform write operations remain closed.

Phase Naver-ERP-13A adds a private mock-testable Naver local order refresh gate for future refresh planning. The helper is not wired to `POST /api/v1/sync/orders/naver/preview`, does not add a public API parameter, and does not call Naver. `verify_all.py` covers readonly not-requested, stale preview, identity mismatch, missing local order, privacy-blocked, manual-approval-required, one-row temporary mock refresh success, no-change repeat refresh, and sensitive field scanning. The gate can update exactly one existing local Naver order only inside the temporary verification database when `write_enabled=true` and `manual_approval=true`; it cannot create another order, write products, write SyncLog, add tested_success, save raw responses, execute platform writes, or open formal order sync.

Phase Naver-ERP-13B repeats the real readonly order preview path for the selected local refresh candidate. The request keeps `store_id=8`, `credential_id=7`, recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=true`, and `real_sync=false`. It returned HTTP 200 with `preview_status=success`, feed/detail HTTP 200, and safe hash `id-hash-ab176f5db1`, matching an existing real local Naver order with `DELIVERED / 配送完成`, `330000 KRW`, and quantity 1. Counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. This phase does not write local data, does not save raw responses, and does not approve refresh writes or formal order sync.

Phase Naver-ERP-13C documents the future selected-order refresh approval gate without calling Naver or writing local data. A later refresh write for safe hash `id-hash-ab176f5db1` requires a separate explicit user request, clean worktrees, a `backend/codex1.db` backup, a fresh readonly preview, exact safe-hash match, exactly one existing local real Naver order, privacy gate success, a one-row update limit, and post-write readback. The future refresh may update only sanitized status, delivery/claim/payment, quantity, amount, safe product/option text, timestamps, and whitelisted metadata. It must not persist complete-field preview values, raw responses, tokens, headers, signatures, full buyer or receiver data, addresses, or zip codes; must not create orders; must not write products, SyncLog, or tested_success; and must not open formal order sync or platform write actions.

Phase Naver-ERP-13D attempted the selected-order local refresh write after backing up `backend/codex1.db`, but no local write was performed. The fresh 3-day readonly preview returned HTTP 200/detail HTTP 200 for safe hash `id-hash-0c36f22281`, and a targeted narrow readonly probe returned safe hash `id-hash-a5870c77c2`; neither matched the approved selected hash `id-hash-ab176f5db1`. The refresh gate blocked on selected-hash mismatch, leaving `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. Formal order sync remains closed.

Phase Naver-ERP-14A plans Naver order status timeline behavior before any selected-order refresh write. It does not call Naver, write local data, change schema, or open formal order sync. The plan keeps `orders` as the latest sanitized snapshot and recommends a future separately approved `order_status_events` table for history such as payment, confirmation, dispatch, delivery, cancel, return, exchange, and unknown-status observations. Future timeline events may store only safe hashes, status enums and Chinese labels, event type, observed time, source phase, mapping version, dedupe key, and safety booleans. They must not store complete-field preview payloads, raw responses, tokens, headers, signatures, full buyer or receiver data, addresses, zip codes, or full order/product-order ids. A no-change refresh or `last_synced_at`-only refresh must not create a fake timeline event.

Phase Naver-ERP-14B adds a private mock-testable status timeline mapper. It is not wired to a public endpoint, does not call Naver, does not write local data, does not create a timeline table, and does not change schema. The mapper compares a previous sanitized local snapshot with a fresh sanitized refresh preview and returns planned safe timeline events, dedupe results, or manual-review blocks. `verify_all.py` covers delivered, delivery-status, cancel, return, exchange, unknown-status, privacy-blocked, identity-mismatch, no-change, deduped refresh, and sensitive scan cases. It keeps `orders`, products, SyncLog, tested_success, raw response saving, platform writes, and formal order sync closed.

Phase Naver-ERP-14C plans Orders UI status timeline display without changing runtime frontend code, backend APIs, or schema. The UI should keep the current local order snapshot as the primary status, show future status history in a collapsed section, use seller-facing Chinese labels on the main page, and move safe raw enums, hashes, dedupe keys, mapping versions, and gate flags into TechnicalDetails. It must not show raw responses, full order ids, full product-order ids, buyer/receiver privacy data, phones, addresses, zip codes, tokens, headers, signatures, or wording that implies automatic refresh, persisted timeline history, platform writes, or formal Naver order sync is open.

Phase Naver-ERP-14D proposes a future `order_status_events` table without changing models, schema, APIs, or runtime behavior. The proposed table links to `orders.id`, remains store-scoped, stores only safe hashes, event type, status enums and Chinese labels, observed time, source phase/type, mapping version, dedupe key, safety booleans, and sanitized metadata. It proposes `store_id/platform/dedupe_key` uniqueness plus order/time and store/event indexes. It forbids raw responses, complete-field payloads, tokens, headers, signatures, full order/product-order ids, buyer/receiver privacy data, phones, addresses, and zip codes. Future schema work must go through mock schema gate, backup/rollback approval, and a separately approved migration phase.

Phase Naver-ERP-14E adds the mock schema gate for that future `order_status_events` table inside `verify_all.py` only. The gate uses the temporary verification SQLite database, creates the proposed table shape, checks required columns, required indexes, the `store_id/platform/dedupe_key` uniqueness boundary, one safe mock event insert, duplicate rejection, safe metadata, and sensitive-field scanning. It keeps the real `backend/codex1.db` schema unchanged and does not add a model, migration, endpoint, Naver API call, real data write, Codex2 runtime change, or formal order sync approval. Real schema approval remains deferred to a later 14F backup/rollback plan.

Phase Naver-ERP-14F documents the approval and rollback plan for a future `order_status_events` schema migration. It is planning-only: it does not create the table, add a model or migration, call Naver, execute `real_sync=true`, write business data, modify Codex2 runtime UI, or open formal order sync. The plan requires a clean worktree, real database backup, baseline count capture, no pre-existing event table, post-migration column/index/dedupe verification, no inserted event rows, unchanged `orders`, products, SyncLog, and tested_success counts, sensitive-field scans, and explicit user approval before the separate 14G schema migration. Creating the schema in 14G still must not approve event writes or formal order sync.

Phase Naver-ERP-14G creates the real `order_status_events` schema in `backend/codex1.db` after backup. The migration adds an `OrderStatusEvent` model and an idempotent SQLite upgrade script, creates the table with approved safe columns, keeps only the approved dedupe/product-hash/composite indexes, and leaves the table empty. Existing `orders`, products, SyncLog, and tested_success counts remain unchanged. 14G still does not call Naver, execute `real_sync=true`, insert timeline events, approve event writes, approve order refresh writes, modify Codex2 runtime UI, or open formal Naver order sync.

Phase Naver-ERP-14H adds a private mock-testable single timeline event write gate. It is exercised only by `verify_all.py` in the temporary verification database. The gate requires a fresh readonly preview, exactly one planned event from the 14B mapper, selected hash identity match, exactly one local Naver order, known non-unknown event type, valid dedupe key, no existing matching event, safety booleans, no sensitive fields, and manual approval before inserting one mock `OrderStatusEvent` row. It does not write the real `backend/codex1.db` event table, call Naver, write `orders`, products, SyncLog, or tested_success, modify Codex2 runtime UI, or open formal order sync.

Phase Naver-ERP-14I verifies timeline state after the blocked 13D selected-order refresh attempt using local readback only. The selected hash `id-hash-ab176f5db1` remains `DELIVERED` with `orders_refreshed=false`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`; `order_status_events_rows=0` and selected-hash timeline events are 0. This is the expected result because 13D did not pass the fresh selected-hash gate. 14I does not call Naver, execute `real_sync=true`, write local data, insert events, modify Codex2 runtime UI, or open formal order sync.

Phase Naver-ERP-15A documents a future Naver order refresh batch gate without changing runtime behavior. The current public real preview guardrail remains `page=1,size=1`, and the current write gate remains single-order only. A future batch refresh must target only already-existing local real Naver orders, start with readonly candidate discovery, reject duplicate safe hashes, reject mixed new-order candidates, require exact safe-hash matches to one local order each, pass privacy/status/field whitelist gates for every candidate, block partial writes in the first batch, and require explicit approval plus `backend/codex1.db` backup before any later local write phase. Timeline event insertion, new-order creation, shipment/claim platform writes, SyncLog writes, tested_success writes, and formal order sync remain closed.

Phase Naver-ERP-15B adds a private mock-testable batch refresh gate for existing local Naver orders. The helper is not wired to `POST /api/v1/sync/orders/naver/preview`, does not add a public request field, does not call Naver, and does not alter the current `page=1,size=1` real preview cap. `verify_all.py` covers readonly not-requested, stale preview, candidate limit exceeded, duplicate safe hash, new-order candidate, privacy failure, unknown status, sensitive/raw-response field, manual approval required, two-row temporary mock update, no-change repeat, and sensitive scanning. The gate writes only in the temporary verification database and keeps real orders, products, SyncLog, tested_success, timeline events, platform writes, and formal order sync closed.

Phase Naver-ERP-15C runs a controlled real readonly candidate discovery under the existing Naver order preview guardrail. The request stays `store_id=8`, `credential_id=7`, recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. It returned HTTP 200, feed/detail HTTP 200, and safe hash `id-hash-67b5fc1c97`, but that hash did not match an existing local real Naver order, so it is classified as a new-order candidate rather than an existing-order refresh candidate. Counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. `DELIVERY_COMPLETION` is now mapped to `配送完成`. True batch probing beyond `size=1`, refresh batch writes, new-order writes, timeline event insertion, platform writes, and formal Naver order sync remain closed.

Phase Naver-ERP-15D documents the human approval plan for a future Naver existing-order batch refresh. It is planning-only: it does not run a real readonly batch probe, does not change the current `page=1,size=1` public preview guardrail, does not execute `real_sync=true`, and does not write local data. A later write phase must require clean worktrees, a `backend/codex1.db` backup, explicit approved safe hashes, a fresh readonly candidate batch result, no duplicate hashes, no new-order candidates, every safe hash matching exactly one existing local real Naver order, privacy/status/field whitelist gates passing, full-batch blocking on any failure, no timeline event insertion unless separately approved, and post-write readback. Formal order sync and all Naver platform write actions remain closed.

Phase Naver-ERP-15E documents the approval plan for a future readonly expansion of Naver existing-order refresh candidate discovery. It does not call Naver, change the public `page=1,size=1` guardrail, execute `real_sync=true`, write local data, or open formal order sync. The plan keeps the 15C hash `id-hash-67b5fc1c97` classified as a new-order candidate, blocks batch refresh writing from that result, and says any later readonly expansion must be a separate guarded implementation phase, first limited to `page=1`, `size=2`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Future expanded candidates must be classified as existing-refresh, new-order, duplicate, ambiguous-local-match, or blocked before any later approval.

Phase Naver-ERP-16A documents the approval plan for the latest Naver new-order candidate. It is planning-only and does not call Naver, execute `real_sync=true`, write local data, change schema, modify Codex2 runtime UI, or open formal order sync. The plan routes safe hash `id-hash-67b5fc1c97` to the selected new-order path and keeps it out of the existing-order refresh batch path. A later write requires a fresh readonly repeat, duplicate checks, privacy/status gates, explicit write approval, `backend/codex1.db` backup, one-order limit, no products/SyncLog/tested_success/timeline writes, and no Naver platform write action.

Phase Naver-ERP-16B repeats the selected new-order real readonly preview under the current public `page=1,size=1` guardrail with `real_sync=false`. It returned HTTP 200, feed/detail HTTP 200, and the same selected safe hash `id-hash-67b5fc1c97`. The candidate remains `candidate_new`: real local match count 0, mock/test match count 0, privacy gate passed, status gate passed, required business fields were present, and counts stayed unchanged (`orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `order_status_events_rows=0`). 16B does not write local data, insert timeline events, execute platform writes, or open formal order sync.

Phase Naver-ERP-16C documents the approval gate for a later selected new-order single local write. It is approval-only: it does not call Naver, back up or write `backend/codex1.db`, execute `real_sync=true`, change schema, modify Codex2 runtime UI, or open formal order sync. The only approved future write target is safe hash `id-hash-67b5fc1c97`. A later 16D must re-check clean worktrees, back up the database, run a fresh readonly preview, confirm the selected hash, confirm duplicate counts are still zero, pass privacy/status gates, write at most one sanitized local order, write no products/SyncLog/tested_success/timeline rows, and perform post-write readback plus sensitive scans.

Phase Naver-ERP-16C2 documents the approval plan for the current 24-hour Naver new-order candidate after the stopped 16D gate. It is approval-only: it does not call Naver, execute `real_sync=true`, back up or write `backend/codex1.db`, change schema, modify Codex2 runtime UI, or open formal order sync. The stopped 16D gate did not write because the 3-day readonly candidate was `id-hash-67b5fc1c97`, while the 24-hour writeable window returned `id-hash-bc5528d093`. 16C2 approves only a later one-row retry plan for `id-hash-bc5528d093`; that future retry must still back up the database, rerun fresh readonly preview, confirm the safe hash, confirm zero duplicate matches, pass privacy and required-field gates, write no products/SyncLog/tested_success/timeline rows, and execute no Naver platform write operation.

Phase Naver-ERP-16D-Retry performed one controlled local Naver order write for safe hash `id-hash-bc5528d093`. The phase backed up `backend/codex1.db`, reran a fresh 24-hour readonly preview, confirmed HTTP 200 with token/feed/detail HTTP 200, confirmed the approved safe hash and zero local duplicate matches, then wrote one sanitized `orders` row through the selected-candidate local write gate. Counts after the write are `orders_store8=6`, real Naver local orders 3, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. The row uses `source_type=naver_real_order_sync`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. This does not open formal order sync, batch order sync, timeline event insertion, or any Naver platform write operation.

Phase Naver-ERP-16E verifies the 16D-Retry write locally without calling Naver or writing data. Direct readback confirmed safe hash `id-hash-bc5528d093` has exactly one real local match and remains sanitized. `GET /api/v1/orders?store_id=8&platform=naver` returns 3 real Naver orders by default and excludes 3 mock/test rows. `GET /api/v1/dashboard/summary?store_id=8&platform=naver` reports `order_count=3`, and `GET /api/v1/stats/sales?store_id=8&platform=naver` reports `total_orders=3` and `total_sales_amount=1159000.00`. Sensitive scans found no token, secret, Authorization, header, signature, raw platform response, full id key, address key, or plain phone pattern. Formal order sync and all Naver platform writes remain closed.

Phase Naver-ERP-17A expands readonly Naver claim/status labels without calling Naver, writing data, changing schema, or opening formal sync. `COLLECT_DONE` is now mapped to `售后取件完成` and no longer sets `unknown_status_observed=true`; related safe mappings cover claim pickup request/in-progress, return completion, and exchange completion states. The timeline mock mapper recognizes `COLLECT_DONE` as `claim_collected`. Existing persisted order rows are not rewritten by this phase, so historical sanitized raw_data labels should be handled by UI display cleanup or a later approved refresh. All Naver after-sales platform write actions remain closed.

Phase ERP-Audit-1A plans a future local operation audit log separate from `SyncLog`. The planned `operation_audit_logs` trail should answer who approved or performed an operation, what store/object was affected, when it happened, what safe field names or counts changed, which backup/restore evidence is linked, and whether the result was success, failed, blocked, skipped, or planned. The phase is planning-only: it does not create the table, write audit rows, change runtime behavior, or alter backup/restore flows. Future audit rows must never store tokens, Authorization values, request/response headers, signatures, bcrypt inputs, client secrets, raw platform responses, full channel numbers, full order/product-order ids, buyer/receiver full names, phones, addresses, or zip codes.

Phase ERP-Audit-1B proposes the future `operation_audit_logs` schema without creating it. The proposal keeps audit rows separate from `SyncLog` and includes actor, action, operation phase, target, status/reason, correlation id, safe summaries, backup/restore path plus SHA-256 fields, safety booleans, and notes. It recommends indexes by time, store, platform, actor, action, target, hash, correlation id, request id, and status/reason, with no uniqueness constraint for normal audit rows because approval/backup/write/verify chains share a correlation id. The proposal still forbids token/header/signature/secret/raw response/full id/privacy/address fields and defers all real schema work to a later mock schema gate and migration approval.

Phase ERP-Audit-1C adds a mock write gate for the future `operation_audit_logs` table inside `verify_all.py` only. The test creates the proposed table shape in the isolated temporary verification SQLite database, validates required columns, defaults, non-unique correlation-chain indexes, SHA-256 format checks, manual-approval gating, safe row insertion, blocked-operation evidence rows, and sensitive JSON rejection. It confirms multiple audit rows may share one `correlation_id` and that `orders`, products, `SyncLog`, and `ApiCapabilityTestResult tested_success` counts are unchanged. This phase does not create or alter the real `backend/codex1.db` schema, add a SQLAlchemy model, run a migration, expose an endpoint, write real audit rows, call platform APIs, save raw responses or secrets, or change backup/restore runtime behavior.

Phase ERP-Audit-1E creates the real `operation_audit_logs` table and approved non-unique indexes in `backend/codex1.db` after a verified pre-migration backup. The migration is schema-only and inserts zero audit rows. Post-migration verification confirmed SQLite integrity, `operation_audit_logs=0`, unchanged `stores`, products, orders, `SyncLog`, `ApiCapabilityTestResult tested_success`, and `order_status_events` counts, and idempotent repeat execution. This phase does not add a runtime audit writer, public audit endpoint, frontend audit reader, restore execution, platform API call, raw response storage, secret storage, or formal product/order sync approval.

Phase ERP-Audit-1F performs a read-only post-migration verification of the real `operation_audit_logs` table. It opens `backend/codex1.db` in SQLite read-only mode, confirms integrity, 34 approved columns, 10 approved non-unique indexes, safe defaults, no forbidden audit columns, no public audit route, `operation_audit_logs=0`, and unchanged business counts (`products=9`, `orders=9`, `sync_logs=47`, `tested_success=8`, `order_status_events=0`). It does not change schema, create a backup, write audit rows, write business data, call platform APIs, add runtime audit services, or open formal sync.

Phase ERP-Audit-1G adds a private audit writer service mock gate in `app/services/operation_audit_service.py` and verifies it only against the temporary `verify_all.py` database. The helper is blocked by default and writes only with `write_enabled=true`, `manual_approval=true`, and `verification_scope=verify_all_temp_db`. Tests cover missing approval, missing required fields, invalid SHA-256, unsafe saved flags, privacy failures, sensitive JSON blocking, safe mock rows, blocked-operation evidence rows, shared correlation ids, and unchanged business counts. This phase does not write real `operation_audit_logs`, add a public audit endpoint, enable runtime audit writing, call platform APIs, or open formal sync.

Phase ERP-Audit-1H implements a controlled local audit writer entry point in `app/services/operation_audit_service.py`. The new `write_operation_audit_log_local` helper requires explicit write intent, manual approval, a private local scope, valid timestamps, valid SHA-256 metadata, safe flags, and sensitive JSON rejection. `verify_all.py` proves approved safe rows and blocked-operation evidence rows can be written to the temporary verification database only, while business counts stay unchanged. This phase does not write real `operation_audit_logs`, expose a public audit endpoint, add a frontend reader, automatically instrument order/product flows, call platform APIs, or open formal sync.

Phase ERP-Audit-1I documents the future read-only API contract for `operation_audit_logs`. The planned API should provide bounded store/platform/status/action/date filters, business-first Chinese labels, an empty-state message when `operation_audit_logs=0`, a safe summary endpoint direction, and folded advanced details for safe enums and abbreviated hashes only. It must not return tokens, Authorization values, headers, signatures, client secrets, raw request/response bodies, full platform identifiers, buyer/receiver privacy, phones, addresses, or full JSON payloads. This phase does not add a route, public audit API, frontend reader, schema change, audit row, platform API call, or formal sync approval.

Phase ERP-Audit-1J adds private mock-gate coverage for future read-only audit log list and summary responses. `list_operation_audit_logs_readonly_mock_gate` and `summarize_operation_audit_logs_readonly_mock_gate` require the private verification scope, enforce bounded filters and pagination, return Chinese business labels, keep raw JSON summaries out of the default response, and limit advanced details to safe enums, abbreviated hashes, abbreviated SHA-256 values, and safe field labels. `verify_all.py` writes temporary audit rows only inside the verification database and confirms no business rows change. This phase does not add a public endpoint, frontend reader, real audit row, schema change, platform API call, or formal sync approval.

Phase ERP-Audit-1K documents the approval boundary for a future local read-only audit logs route implementation. A later 1L may add only `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`, using the 1J response shape, bounded filters, capped pagination, empty-state success behavior, opt-in advanced details, and strict sensitive-field scanning. 1K itself does not add routes, register routers, write audit rows, change schema, modify frontend runtime code, call platform APIs, or open formal sync. The real `operation_audit_logs` table remains at zero rows until a separately approved writer integration phase.

Phase ERP-Audit-1L implements the approved local read-only audit log list and summary routes. `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary` use the 1J service response shape, reject unsupported filters, cap pagination, keep advanced details opt-in, and avoid raw summaries, raw safety flags, secrets, platform payloads, full platform ids, and buyer/receiver privacy. `verify_all.py` confirms the routes expose only GET, read temporary audit rows safely, return an empty success state when no rows match, and write no audit or business rows. This phase does not add write/export/delete/detail routes, frontend readers, schema changes, platform API calls, backup execution, restore execution, or formal sync approval.

Phase ERP-Audit-1M verifies the 1L read-only audit API against the real local `backend/codex1.db` runtime database. `GET /api/v1/operation-audit-logs?store_id=8` and `GET /api/v1/operation-audit-logs/summary?store_id=8` return HTTP 200 with a business empty state because `operation_audit_logs=0`; `POST`, `PUT`, `PATCH`, and `DELETE` remain 405. Unsupported filters return safe Chinese business copy and do not echo raw unsupported field names. Real counts stayed unchanged: `operation_audit_logs=0`, `products=9`, `orders=9`, `sync_logs=47`, `tested_success_store8=8`, and `order_status_events=0`. This phase does not add frontend readers, audit writers, schema changes, platform API calls, backup execution, restore execution, or formal sync approval.

Phase ERP-Audit-1N is a frontend integration plan only. It does not change Codex1 runtime code or API behavior. The future Codex2 Logs page may read only `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`, show `operation_audit_logs=0` as a normal business empty state, keep SyncLog as a separate `同步记录` section, and place safe diagnostics only in folded `TechnicalDetails`. The plan forbids audit write/delete/export/detail calls, raw JSON display, full hashes or platform ids on the main page, platform API calls, local data writes, audit writer activation, backup/restore execution, and formal product/order sync approval.

Phase ERP-Audit-1Q is an audit writer integration approval plan only. It does not change Codex1 runtime code, add middleware, add public write routes, write `operation_audit_logs`, modify schema, call platform APIs, execute backup/restore, or open formal sync. A later 1R must first prove the integration through a private temporary-database mock gate. Future real audit rows may only be connected to explicitly approved local operations such as controlled Naver order writes/refreshes, backup evidence, restore dry-run evidence, or schema migration evidence, and must use safe correlation-chain rows with no tokens, Authorization values, headers, signatures, client secrets, raw responses, full platform ids, buyer/receiver privacy, phones, addresses, or zip codes.

Phase ERP-Audit-1R adds the private audit writer integration mock gate. It verifies complete multi-row correlation chains for selected local operation types only in the temporary `verify_all.py` database: controlled Naver order local write/refresh evidence, database backup evidence, restore dry-run evidence, and schema migration evidence. The gate requires explicit write intent, manual approval, `verification_scope=verify_all_temp_db`, one shared `correlation_id`, unique `request_id` values, complete required action chains, safe saved flags, privacy redaction, valid SHA-256 metadata, and sensitive-field rejection. It does not connect runtime business flows, add public write routes, write the real `backend/codex1.db`, modify schema, call platform APIs, execute backup/restore, or open formal sync. Audit write/delete/export/raw detail routes remain closed.

Phase ERP-Audit-1S is an approval plan only for future local runtime audit writer integration. It does not change Codex1 runtime behavior, connect writer calls to routes/services, add middleware, write `operation_audit_logs`, modify schema, call platform APIs, execute backup/restore, or open formal sync. The approved future direction is narrow: controlled Naver selected-order local write/refresh audit evidence, pre-write backup evidence, and post-write verification evidence. Future runtime wiring must still pass a separate mock-only selected-operation phase, require explicit user approval, use one shared `correlation_id`, unique `request_id` values, safe whitelisted fields, `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`, and sensitive-field scanning.

Phase ERP-Audit-1T is a mock-wiring plan only and does not change Codex1 code or public API behavior. It selects `controlled_naver_order_local_refresh` as the first future mock target, defines the fake selected-operation input, required approval/backup/write-attempt/result/verification audit chain, block cases, safe flags, and forbidden data. It does not connect the writer to real order flows, write `operation_audit_logs`, write business data, modify schema, call platform APIs, execute backup/restore, add public audit write/delete/export/detail routes, or open formal sync.

Phase ERP-Audit-1U adds a private selected-operation audit runtime wiring mock gate for `controlled_naver_order_local_refresh`. The helper requires store 8, platform Naver, a safe target order hash, manual approval, backup evidence, fake write and readback results, audit write intent, and the private verification scope, then writes a five-row safe audit chain only to the temporary `verify_all.py` database. `verify_all.py` covers success, blocked writes, missing scope, missing approval, missing backup, unsupported store/platform/operation, invalid fake statuses, sensitive payload rejection, and unchanged business counts. This phase does not connect real runtime order flows, write the real `operation_audit_logs`, modify schema, call platform APIs, execute backup/restore, add public audit write/delete/export/detail routes, or open formal sync.

Phase ERP-Audit-1V is an implementation approval plan only. It does not add code, connect runtime order flows, write `operation_audit_logs`, modify schema, call platform APIs, execute backup/restore, add public audit write/delete/export/detail routes, or open formal sync. It allows a later phase to consider connecting the audit writer only to `controlled_naver_order_local_refresh`, and only after clean worktrees, a verified database backup, baseline counts, explicit user approval, store 8 / Naver scoping, safe append-only rows, post-write readback, and sensitive-field scans.

Phase ERP-Backup-1A documents the database backup and restore drill plan for `backend/codex1.db`. It defines the local backup directory, filename and manifest convention, SHA-256 verification, SQLite integrity checks, temporary restore drill steps, real restore approval boundary, and which future write or migration phases must require a backup. This phase is planning-only: it does not create a backup, restore a database, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior. Backup manifests must not store tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw responses, full channel/order/product-order ids, buyer/receiver privacy, phone numbers, addresses, or zip codes.

Phase ERP-Backup-1B documents the backup metadata and retention plan. It defines future manifest fields, retention classes such as `pre_write`, `pre_migration`, `pre_restore`, `scheduled_daily`, `scheduled_weekly`, `manual_checkpoint`, `release_checkpoint`, and `incident_response`, initial retention windows, protected-from-auto-delete rules, report-only cleanup gates, restore metadata checks, and future operation-audit relationships. This phase does not create backups, delete backups, restore a database, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior. The first cleanup implementation must only report deletion candidates and must never delete files automatically.

Phase ERP-Backup-1C adds a private restore verification dry-run to `verify_all.py`. It uses only temporary SQLite fixture files to validate backup manifest required fields, approved retention classes, SHA-256 and file-size matching, safe flags, sensitive-field rejection, temporary restore path safety, restored copy hash, SQLite `PRAGMA integrity_check`, expected tables, and restored row counts. It explicitly blocks `backend/codex1.db` as a restore target and confirms the real database remains unchanged. This phase does not create production backups, restore the real database, delete backups, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior.

Phase ERP-Backup-1D is a real backup manifest implementation plan only. It defines the future manifest writer contract for real `backend/codex1.db` backups, including required fields, computed SHA-256/size/integrity metadata, path safety, atomic UTF-8 JSON writes, safe baseline counts, retention defaults, sensitive-field rejection, and future operation-audit correlation. It does not create backup files, write manifest files, restore a database, delete backups, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior.

Phase ERP-Backup-1E adds a temporary-file backup manifest mock implementation gate in `verify_all.py`. It uses temporary SQLite fixture backups only, computes SHA-256, size, SQLite integrity, page metadata, and safe baseline counts, writes a UTF-8 JSON temp manifest before atomic rename, validates it with the restore dry-run manifest gate, blocks invalid retention, sensitive inputs, production source path, path traversal/outside-root backups, and manifest overwrite, and confirms the real `backend/codex1.db` hash and size remain unchanged. It does not create production backups, write production manifests, restore a database, delete backups, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior.

Phase ERP-Backup-1F is a real local backup implementation approval plan only. It defines the future manual backup helper boundary for `backend/codex1.db`, including the approved local backup root, source/path checks, SQLite backup method expectations, manifest generation, integrity checks, safe baseline counts, overwrite blocking, sensitive boundaries, and failure handling. It does not create backup files, write production manifests, restore a database, delete backups, modify schema, write local data, call platform APIs, change runtime UI, or alter backup/restore behavior.

Phase ERP-Backup-1G implements the first manual local backup helper at `scripts/create_local_backup.py`. It backs up only the approved `backend/codex1.db` source to the approved local backup root by default, uses SQLite online backup, validates the temporary backup before finalizing, writes a side-by-side UTF-8 manifest, records safe SHA-256/size/integrity/count metadata, and blocks unsupported paths, invalid retention classes, sensitive inputs, and existing target backup/manifest files. `verify_all.py` covers the helper with temporary fixture databases and confirms the real `backend/codex1.db` hash and size remain unchanged. This phase may create one real local backup and manifest, but it does not restore a database, delete backups, modify schema, write business rows, write `operation_audit_logs`, call platform APIs, change runtime UI, or open formal sync.

Phase Naver-ERP-5H polishes readonly order status mapping for complete-field preview. The mapper now recognizes common Naver delivery aliases such as `READY`, `DELIVERING`, `DELIVERED`, `DELIVERY_COMPLETED`, and `배송완료`. If a complete-field payload has an unknown delivery status but the order status itself clearly means待发货, 배송중/配送中, or 配送完成, the delivery display label may be derived from the order status for operator readability. This is display metadata only: it does not change the 1C write gate, does not write `orders`, does not save raw response data, and does not open formal order sync.

### Phase Naver-ERP-MasterPlan: basic ERP priority roadmap

Current priority is the normal Naver ERP loop: products -> orders -> inventory -> delivery/claims -> order-based sales -> Dashboard. Email center, appeal center, AI appeal replies, AI mail recognition, and deep customer-service automation stay out of scope until the operational ERP base is stable.

Current baseline:

- Naver store `store_id=8` and `credential_id=7` have passed token, seller/account, and seller/channel readonly checks.
- Naver product `page=1,size=5` local small-batch sync is complete; local `products_store8=5`; post-sync dry-run reports `matched_existing_count=5`, `would_create=0`, `would_update=0`, `would_refresh_only=5`, and `would_skip=0`.
- Naver product `page=2,size=5` readonly dry-run returned `success_empty`, so there is currently no second-page product candidate to write.
- Naver product formal batch sync is still closed. The 5-row local sync is a controlled test only.

Roadmap:

| Order | Phase | Goal | Risk | Real API | Local writes | Codex2 |
|---:|---|---|---|---|---|---|
| 1 | `Phase Naver-ERP-1: Order feed-to-detail readonly preview` | Read the last-changed order feed; if one `productOrderId` appears, query one sanitized detail preview | Medium | Yes, readonly | No | No |
| 2 | `Phase Naver-ERP-2: Order detail mapping and privacy gate` | Lock order field whitelist, Chinese status mapping, privacy masking, and mock coverage | Medium | No | No | No |
| 3 | `Phase Naver-ERP-3: Single Naver order local write` | After manual approval, write exactly one sanitized order row | High | Yes, readonly | Yes, one row | Later |
| 4 | `Phase Naver-ERP-4: Inventory basic alerts` | Use local `stock_quantity` for zero-stock, low-stock, and stock-change notices | Low | No | No | Yes |
| 5 | `Phase Naver-ERP-5: Delivery and claim readonly classification` | Classify shipping, cancellation, return, and exchange states from order feed/detail | Medium | Yes, readonly | No | Yes |
| 6 | `Phase Naver-ERP-6: Order-based sales summary` | Summarize today/week/month order amount and order counts from local orders | Medium | No | No | Yes |
| 7 | `Phase Naver-ERP-7: Naver Dashboard ERP summary` | Show connection, product, order, shipping, claim, inventory, and sales work items | Medium | No | No | Yes |
| 8 | `Phase Naver-ERP-8: Product expansion review only` | Revisit product readonly expansion only if new platform products appear | Medium | Yes, readonly | No | Optional |

Module decisions:

- Product management is temporarily closed at the 5-row test. Further expansion must stay small-step and readonly first (`page in {1,2}`, `size<=5`) until new candidates exist. `would_refresh_only` must never be presented as product-content updates.
- Order management is the next main line. Wait for a real changed order or confirm a recent Seller Center order event, then run one-day feed preview and at most one detail preview. The first detail stage must not write `orders`.
- A future single-order write may store only sanitized business fields: store/platform, hashed or masked external order key, product name, quantity, order amount, currency, order status, paid/ordered times, source type, last synced time, and sanitized metadata. Full buyer name, full phone, address, raw order detail, full `productOrderId`, and raw response are forbidden in persisted rows. The only exception for display is the explicit Phase Naver-ERP-5D `complete_field_preview=true` readonly response, which is never used as a write payload.
- Inventory v1 is based on local product `stock_quantity`; no procurement, warehouse, or purchasing workflow is introduced in this roadmap. A global low-stock threshold is acceptable before product-level thresholds exist.
- Delivery and claim v1 is readonly classification only. Shipment write APIs, dispatch actions, cancellation approval, return approval, and exchange actions require separate later approval.
- Sales v1 uses local order amounts only. Settlement or final amount must not be displayed as profit or withdrawable balance.
- Dashboard v1 should use seller-facing language only. Technical fields such as `error_code`, `http_status`, `store_id`, `credential_id`, `real_preview`, `real_sync`, full channel numbers, and full platform IDs belong only in technical detail views.
- Phase Naver-ERP-5J cleans seller-facing local order list semantics: local test rows with `source_type in {"mock_sync", "local_frontend_mock"}` remain stored for audit/testing but are excluded by default from `/orders`, order sales stats, Dashboard order counts, recent orders, and local order amount summaries. Use the readonly diagnostic flag `include_test_orders=true` only when intentionally inspecting local test rows.

Global ERP safety gates:

- Keep `store_id=8` and `credential_id=7` for Naver real-preview phases until a separate expansion approval.
- Preview/dry-run first, small window first, single-row write first, and manual approval before any broader local write.
- Do not save tokens, `Authorization`, request headers, signatures, bcrypt output, raw responses, full channel numbers, full product IDs, full order IDs, full `productOrderId`, buyer addresses, or full buyer phone numbers. Full order/product/buyer fields may be displayed only in the explicit Phase Naver-ERP-5D complete-field readonly preview and must not be persisted.
- Any write phase must back up `backend/codex1.db`, verify no duplicate key, verify no sensitive persistence, and verify no unexpected `SyncLog` or `ApiCapabilityTestResult tested_success` writes.
- Formal Naver product or order batch sync remains closed until a separately named phase approves it.

Future Naver preview endpoints must remain preview-only: no writes to `products` or `orders`, no raw response persistence, no token persistence, and no output of client secrets, tokens, authorization headers, request signatures, request headers, or full `channel_no` values.

The database stores only:

```text
encrypted_access_key
encrypted_secret_key
```

Internal decryption is restricted to `app.services.credential_service.get_decrypted_credential_for_internal_use`, intended for platform client initialization. Do not expose that decrypted result through API routes or logs.

Credential deletion is currently a hard delete. A later stage can extend this to soft delete or status-based deactivation.

## API Capability Matrix APIs

Phase 6B-1 adds backend records for API capability planning only:

```text
GET    /api/v1/api-capabilities
GET    /api/v1/api-capabilities/summary
POST   /api/v1/api-capabilities
GET    /api/v1/api-capabilities/{capability_id}
PUT    /api/v1/api-capabilities/{capability_id}
GET    /api/v1/api-capability-results
POST   /api/v1/api-capability-results
GET    /api/v1/api-capability-results/{result_id}
```

`api_capability_checks` records platform-level docs-only or manual API capability notes. It answers what an endpoint appears to provide and what permission may be required.

`api_capability_test_results` records store and credential-level manual/docs/mock/sandbox notes. It answers whether a selected store/credential has a planning or future test record for that capability.

Important limits:

- This stage does not call Naver or Coupang.
- This stage does not use real keys or refresh tokens.
- This stage does not implement a real read-only test endpoint.
- A docs-only capability record does not mean the selected store credential has been validated.
- A `tested_success` status is a record status only and must not be described as full sync support.
- Responses do not include API secrets, tokens, or encrypted credential values.

Phase 6B-3A adds API capability summaries:

- `/api/v1/api-capabilities/summary` aggregates platform-level capability records and optional store-level result records.
- `/api/v1/dashboard/summary` includes `api_capability_summary`.
- `/api/v1/ai/daily-context` includes `api_capability_context`.
- Summary timestamps remain UTC aware strings; Codex2 displays them as KST.
- Summary records do not call Naver or Coupang, do not use real keys, do not refresh tokens, and do not produce real sync results.

## Data Models

All business data is bound to `store_id` and stores the source `platform`.

Stage 1D adds:

```text
products
orders
customer_inquiries
```

`products` stores platform product snapshots with `external_product_id`, `name`, `sku`, `brand`, `category`, `price`, `currency`, `stock_quantity`, and JSON `raw_data`. For future Naver sync, `raw_data` must store only sanitized metadata such as platform origin/channel IDs and display-status summaries, never raw Naver product responses.

`orders` stores mock order snapshots with `external_order_id`, `buyer_name`, `buyer_masked_phone`, `product_name`, `quantity`, `order_amount`, `order_status`, `paid_at`, `ordered_at`, and JSON `raw_data`.

Only masked buyer phones are stored, for example `010-****-1234`. Do not add full phone numbers, full addresses, ID numbers, or other sensitive buyer privacy fields.

`customer_inquiries` stores mock customer inquiry snapshots with `external_inquiry_id`, `inquiry_type`, `customer_name`, `title`, `content`, `status`, `received_at`, `answered_at`, and JSON `raw_data`.

Service-layer upsert avoids duplicate records by:

```text
products: store_id + platform + external_product_id
orders: store_id + platform + external_order_id
customer_inquiries: store_id + platform + external_inquiry_id
```

## Query APIs

```text
GET /api/v1/products?store_id={store_id}
GET /api/v1/orders?store_id={store_id}
GET /api/v1/customer-inquiries?store_id={store_id}
```

Optional `platform` filtering is supported:

```text
GET /api/v1/products?store_id={store_id}&platform=naver
```

Queries return Chinese, Korean, and mixed UTF-8 content through the unified response format. Missing stores and unsupported platforms return structured errors.

## Mock Sync APIs

Mock sync endpoints:

```text
POST /api/v1/sync/products/mock?store_id={store_id}&platform={platform}
POST /api/v1/sync/orders/mock?store_id={store_id}&platform={platform}
POST /api/v1/sync/customer-inquiries/mock?store_id={store_id}&platform={platform}
```

The sync service:

1. Validates `store_id` and `platform`.
2. Finds the encrypted platform credential for `store_id + platform`.
3. Decrypts credentials internally.
4. Initializes the matching mock client.
5. Fetches mock data only.
6. Upserts data into the local database.
7. Writes `sync_logs` for running, success, or failed states.

Mock product data includes `SK-II 神仙水测试商品`, `타이틀리스트 캐디백 테스트`, and `ECCO 골프화 / 中文运营测试`.

Mock order data includes only masked phones such as `010-****-1234`, `010-****-5678`, and `010-****-9012`.

Mock inquiry data includes `正品申诉资料咨询`, `배송지연 문의`, and `Naver 정품 소명 / 中文备注`.

## Sales Statistics APIs

Statistics are calculated from the local `orders` table only. The logic lives in `app/services/stats_service.py`, not in endpoint handlers.

Date filters use Korean business dates from `APP_TIMEZONE=Asia/Seoul`. Orders are filtered by the UTC range for the selected KST natural day. `/stats/sales/by-date` groups by converting `ordered_at` to KST before taking the date.

```text
GET /api/v1/stats/sales?store_id={store_id}
GET /api/v1/stats/sales/by-platform?store_id={store_id}
GET /api/v1/stats/sales/by-date?store_id={store_id}&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Optional parameters:

```text
platform
start_date
end_date
```

Sales responses include:

```text
total_orders
total_sales_amount
currency
paid_orders
canceled_orders
failed_orders
latest_ordered_at
```

No-data queries return `success: true` with zero totals and empty arrays. Date parsing errors return `INVALID_DATE_FORMAT`.

## Dashboard Summary API

```text
GET /api/v1/dashboard/summary?store_id={store_id}
```

Optional parameters:

```text
platform
start_date
end_date
```

The dashboard summary is calculated from local `stores`, `products`, `orders`, `customer_inquiries`, and `sync_logs`.

When date filters are omitted, dashboard totals remain scope totals, not "today" totals. The response includes the current KST business day metadata: `business_timezone`, `business_date`, `business_day_start`, and `business_day_end`.

It returns:

```text
store_count
business_timezone
business_date
business_day_start
business_day_end
product_count
order_count
customer_inquiry_count
total_sales_amount
currency
latest_sync_logs
open_customer_inquiries
recent_orders
risk_flags
```

`latest_sync_logs` and `recent_orders` are limited to 5 records. `recent_orders` returns only `buyer_masked_phone`, never full phone numbers or addresses.

Current `risk_flags` rules:

- `FAILED_SYNC_LOG`: failed sync logs exist.
- `OPEN_CUSTOMER_INQUIRIES`: open customer inquiries exist.
- `NO_RECENT_ORDERS`: no order data exists in the requested scope.
- `SUSPENDED_STORE`: store status is `suspended`.

## AI Daily Context API

```text
GET /api/v1/ai/daily-context?store_id={store_id}&date=YYYY-MM-DD
```

If `date` is omitted, the backend uses the current Korean business date, not the Windows display date. The response includes `business_timezone`, `business_day_start`, and `business_day_end`.

This endpoint returns structured context for a future AI report pipeline:

```text
date
scope
sales_summary
order_summary
customer_inquiry_summary
sync_summary
risk_flags
recommended_focus
```

It does not call any model and does not generate final AI prose. `recommended_focus` is generated from local rules such as checking open inquiries, failed sync logs, recent order drops, and authenticity-related inquiries.

The response does not include plaintext platform credentials, full buyer phone numbers, addresses, ID numbers, or other sensitive privacy fields.

## Operations Support Models

Stage 1F adds local-only support modules. All records are bound to `store_id`.

`device_environments` stores only environment labels and metadata:

```text
environment_name
device_type
os_name
browser_name
ip_label
proxy_label
status
last_used_at
remark
```

Do not store real full IP addresses, proxy passwords, remote desktop passwords, or similar secrets.

`email_accounts` stores email account metadata:

```text
email_address
provider
account_label
encrypted_password_or_token
status
last_checked_at
remark
```

`password_or_token` is encrypted with the same Fernet encryption service used for platform credentials. API responses never return plaintext password/token and do not expose the encrypted value.

`important_emails` stores mock important mail records only:

```text
platform
mail_type
sender
subject
snippet
body_text
received_at
status
priority
related_case_id
raw_data
```

No real attachments are stored.

`appeal_cases` stores mock appeal case metadata:

```text
platform
case_type
case_title
case_status
external_case_id
deadline_at
summary
action_required
raw_data
```

Do not store real ID cards, bank cards, full addresses, legal files, or other private materials.

## Operations Support APIs

Device environments:

```text
GET    /api/v1/device-environments?store_id={store_id}
POST   /api/v1/device-environments
GET    /api/v1/device-environments/{environment_id}
PUT    /api/v1/device-environments/{environment_id}
DELETE /api/v1/device-environments/{environment_id}
```

Email accounts:

```text
GET    /api/v1/email-accounts?store_id={store_id}
POST   /api/v1/email-accounts
GET    /api/v1/email-accounts/{email_account_id}
PUT    /api/v1/email-accounts/{email_account_id}
DELETE /api/v1/email-accounts/{email_account_id}
```

Important emails:

```text
GET    /api/v1/important-emails?store_id={store_id}
POST   /api/v1/important-emails
GET    /api/v1/important-emails/{email_id}
PUT    /api/v1/important-emails/{email_id}
DELETE /api/v1/important-emails/{email_id}
```

Appeal cases:

```text
GET    /api/v1/appeal-cases?store_id={store_id}
POST   /api/v1/appeal-cases
GET    /api/v1/appeal-cases/{case_id}
PUT    /api/v1/appeal-cases/{case_id}
DELETE /api/v1/appeal-cases/{case_id}
```

List endpoints support `page` and `page_size`. Missing stores return `STORE_NOT_FOUND`.

## Platform Client Placeholders

Current platform clients are mock placeholders only:

```text
app/clients/naver_client.py
app/clients/coupang_client.py
```

They require an internal decrypted credential object and provide mock methods such as `test_connection()`, `fetch_products_mock()`, `fetch_orders_mock()`, and `fetch_customer_inquiries_mock()`.

They do not call real Naver or Coupang APIs, do not contain real keys, do not implement real signatures, and must not print plaintext credentials.

## Sync Logs

Sync logs track future platform operations, credential tests, and Stage 1D mock sync runs. Each log is bound to a `store_id`.

SyncLog timestamps are stored in UTC. Frontend display should convert them to KST for Korean business operations.

Service functions live in:

```text
app/services/sync_log_service.py
```

Read endpoint:

```text
GET /api/v1/sync-logs?store_id={store_id}
```

Supported status values for this stage are `running`, `success`, and `failed`. `message`, `error_detail`, and `raw_summary` support Chinese, Korean, and mixed UTF-8 text. Mock sync writes `products`, `orders`, and `customer_inquiries` sync types.

## Database Initialization

The app initializes tables automatically on startup through SQLAlchemy `Base.metadata.create_all`.

Manual initialization can also be triggered by importing and running `init_db()`:

```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.database import init_db; init_db()"
```

The default development database is SQLite:

```text
sqlite:///./codex1.db
```

SQLite database files such as `*.db`, `*.sqlite`, and `*.sqlite3` are ignored by `.gitignore` and must not be committed.

## Seed Data

Run the repeatable seed script:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed.py
```

The script inserts stores only when a matching `name` does not already exist, so it can be run multiple times safely.

Seed data rule:

- `name` is the real store-name-style field, for example `东方优选测试店`, `서울뷰티테스트`, `강남스포츠테스트`, or `Global Korea Test Store`.
- `remark` stores business test text such as 正品申诉, 订单同步, 고객문의, 배송지연, and 정품 소명 자료.
- Do not use business scenario descriptions as store names.

## UTF-8 Verification

The seed data intentionally includes:

- Chinese store name and Chinese remark
- Korean store names and Korean remarks
- Mixed Chinese/Korean operational remark text

Use `GET /api/v1/stores` after running the seed script to verify Chinese and Korean text is stored and returned without mojibake.

Stage 1F verification writes Chinese, Korean, and mixed device/email/important-email/appeal-case data, then reads it back through APIs. It also verifies encrypted email token storage and checks that real IPs, proxy passwords, platform keys, full phones, full addresses, ID numbers, and bank card numbers are not returned.

## PostgreSQL Migration Note

The database URL is configured through `DATABASE_URL` in `.env` or the process environment. For a future PostgreSQL switch, set a PostgreSQL SQLAlchemy URL, for example:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/codex1
```

PostgreSQL driver dependencies and migration tooling will be added in a later stage.

## Productionization Recommendations

- Introduce Alembic before schema changes become collaborative.
- Add PostgreSQL driver and validate JSON/DateTime behavior before switching from SQLite.
- Keep platform API clients separated by provider.
- Keep all external API calls behind service layers.
- Add audit logging before real credential or email integrations.
- Continue enforcing UTF-8 for Chinese, Korean, and mixed text.

## Local Files

Do not commit local secrets or runtime data:

- `.env`
- SQLite database files such as `*.db`, `*.sqlite`, `*.sqlite3`
- virtual environments
- `__pycache__`
- logs and raw API response files

## Backup, Restore, and Audit Guardrails

ERP-Backup-1H adds `scripts/restore_backup_dry_run.py` for local restore drills. It accepts only approved-root manifests by default, validates the manifest and backup SHA-256/size, copies the backup to a temporary restore file, checks SQLite integrity and baseline counts, blocks the production database path as a restore target, and deletes only the temporary restore copy. The real 1G manifest drill completed with `status=restore_dry_run_verified`, `real_restore_executed=false`, `production_db_touched=false`, and `backup_deleted=false`.

ERP-Backup-1I adds `scripts/list_local_backups.py` for readonly backup reporting. It lists approved-root manifests, validates required fields and safety booleans, reports whether the backup exists inside the root, returns abbreviated SHA-256, safe counts, and retention metadata, and never deletes or restores backup files.

ERP-Backup-1J approves a narrow readonly API surface for backup reports. ERP-Backup-1K adds a private mock gate in `app/services/backup_service.py` that verifies safe report output from temporary backup manifests only. ERP-Backup-1L implements `GET /api/v1/backups/local-report` and `GET /api/v1/backups/local-report/summary`. These endpoints accept only `limit`, read only the approved local backup root, reject unsupported query parameters, return safe backup evidence and Chinese business messages, and keep `backup_deleted=false`, `real_restore_executed=false`, `production_db_touched=false`, and `rows_written=0`.

ERP-Audit-1W documents the future backup creation audit chain. ERP-Audit-1X adds a private mock gate that writes `backup_planned`, `backup_created`, `backup_hash_verified`, `backup_integrity_verified`, and `backup_manifest_verified` only inside the temporary `verify_all.py` database after manual approval, private scope, verified backup evidence, and safety flags. It does not write real audit rows.

ERP-Audit-1Y documents the future runtime wiring approval plan for connecting successful manual backup creation to append-only audit rows. A later implementation must require explicit approval, clean worktrees, a successful backup helper result, valid SHA-256, `sqlite_integrity_check=ok`, `manifest_written=true`, safe saved flags, post-write readback, and sensitive-field scanning.

ERP-Audit-1Z adds a private backup-creation audit runtime-wiring mock gate. It validates the same five-row backup audit chain that a successful backup helper call will need, but writes only to the temporary `verify_all.py` database under the private verification scope. It does not write the real `operation_audit_logs` table, create backups, restore or delete backups, write business rows, call platform APIs, or open formal sync.

ERP-Audit-2A implements the controlled local backup-creation audit writer. After an approved real local backup is created and its manifest, SHA-256, SQLite integrity, and safety flags pass validation, the helper may write five append-only rows to `operation_audit_logs`: `backup_planned`, `backup_created`, `backup_hash_verified`, `backup_integrity_verified`, and `backup_manifest_verified`. The helper is blocked without explicit write intent, manual approval, and the private local writer scope. It does not write products, orders, `SyncLog`, `ApiCapabilityTestResult tested_success`, or order timeline rows, and it does not restore/delete backups or call platform APIs.

ERP-Audit-2B verifies the 2A audit chain by readback only. It checks one shared correlation id, the five expected actions, safe backup SHA-256 evidence, `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`, unchanged business-table counts, and no sensitive values. It does not write new rows, restore or delete backups, call platform APIs, change schema, or open formal sync.

ERP-Audit-2D adds a private selected-operation audit local implementation mock gate. It validates the future `controlled_naver_order_local_refresh` audit chain using only the temporary `verify_all.py` database: `approval_verified`, `pre_write_backup_verified`, `selected_operation_started`, `selected_operation_finished`, and `post_write_verification_finished`. The helper requires store 8, platform Naver, safe target hash, manual approval, verified backup evidence, formal sync closed, platform writes disabled, privacy redaction, and sensitive-field blocking. It does not write the real database, call platform APIs, change schema, or open formal order sync.

Naver-ERP-18A adds a private order-refresh backup evidence gate around the existing Naver order refresh batch mock gate. Write-enabled refresh paths require safe backup evidence before the existing manual approval gate can proceed. Readonly refresh paths do not require backup evidence because they do not write data. The helper is not wired to a public endpoint and does not open formal Naver order sync.

Naver-ERP-18B documents the approval plan for a future controlled Naver order refresh write with real backup evidence. It remains planning-only: no Naver call, no `real_sync=true`, no local order writes, no timeline events, no SyncLog writes, no tested-success writes, no schema change, and no formal Naver order sync opening.

Naver-ERP-18C repeats the controlled Naver order refresh preview in readonly mode after outbound IP allowlist confirmation. The request used store 8, credential 7, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail returned HTTP 200. The safe observed order hash was `id-hash-192b9c67e8`, with `DELIVERED / 配送完成`, amount `499000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Orders, products, SyncLog, tested-success records, operation audit logs, and order status events stayed unchanged. Formal order sync remains closed.

Naver-ERP-18D reviews the 18C candidate for controlled refresh-write approval and blocks the refresh path. Local readback shows safe hash `id-hash-192b9c67e8` does not match an existing real local Naver order; refresh writes remain limited to existing local orders only. The safe next direction is a separate selected new-order candidate approval plan if the operator wants to consider writing this candidate. This phase does not call Naver, execute `real_sync=true`, write local data, write audit rows, change schema, or open formal order sync.

Naver-ERP-19A documents the selected new-order candidate approval plan for safe hash `id-hash-192b9c67e8`. The candidate is approved only for a fresh readonly repeat before any write can be considered. It is not approved for existing-order refresh. A future write requires exact selected-hash repeat, duplicate count zero, privacy and status gates, fresh database backup, one-order limit, post-write readback, audit evidence, no SyncLog write, no tested-success write, no product write, no platform write, and no formal order sync opening.

Naver-ERP-19B repeats the selected new-order candidate readonly preview. Token, feed, and detail returned HTTP 200, and the observed safe hash matched `id-hash-192b9c67e8`. The candidate remains `candidate_new`, with `配送完成`, amount `499000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Counts stayed unchanged: `orders_store8=6`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=5`, and `order_status_events=0`. Formal order sync remains closed.

Naver-ERP-19C approves only a later one-order local write for safe hash `id-hash-192b9c67e8`. The future write requires clean worktrees, fresh database backup, fresh readonly preview, duplicate count zero, privacy gate, one-candidate limit, post-write readback, and five-row operation audit evidence. This phase does not call Naver, execute `real_sync=true`, write local data, write audit rows, create backups, change schema, or open formal order sync.

Naver-ERP-19D executes the approved one-order local write after a fresh database backup and a fresh Naver readonly preview. Token, feed, and detail returned HTTP 200, the safe hash matched `id-hash-192b9c67e8`, and the privacy gate passed. Exactly one local Naver order was created: `orders_store8=6 -> 7`. Products, SyncLog, tested-success records, and order status events did not change. Five append-only `operation_audit_logs` rows were written for approval, backup verification, operation start, operation finish, and post-write verification. Formal Naver order sync remains closed.

Naver-ERP-19E verifies the 19D result by readback only. The selected safe hash exists exactly once, `orders_store8=7`, `operation_audit_logs=10`, and the 19D audit chain has exactly five safe rows under one correlation id. The verification does not call Naver, write data, change schema, or open formal order sync.

ERP-Auth-1A defines the first local ERP role and permission model: `owner`, `admin`, `operator`, `auditor`, and `viewer`; store-scoped access; and sensitive action approval for local writes, refreshes, backups, restores, credential updates, schema migrations, and formal sync opening. It is planning-only.

ERP-Auth-1B adds `app/services/permission_service.py` with a private `evaluate_store_scoped_access_mock_gate(...)`. The mock gate verifies private scope, safe actor context, role, requested store, operation permission, and store assignment. It is covered by `verify_all.py` and is not wired to public routes or runtime flows.

ERP-Auth-1C adds `evaluate_sensitive_action_approval_mock_gate(...)`. The mock gate checks manual approval and role authority for sensitive actions. It writes no orders, products, SyncLog, tested-success records, audit rows, or platform data, and keeps formal sync closed.

ERP-Auth-1D documents the future Codex2 role-aware action visibility plan. It does not change runtime frontend code.

Naver-ERP-20A documents the next controlled order refresh batch approval plan. It requires future backup evidence, readonly candidate repeat, store-scoped role permission, sensitive-action approval, audit evidence, readback, and sensitive scan before any later write phase. It does not call Naver, write data, or open formal order sync.

Naver-ERP-20B repeats the controlled Naver order refresh preview in readonly mode. The request used store 8, credential 7, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail returned HTTP 200. The safe observed hash was `id-hash-192b9c67e8`, matched exactly one existing local Naver order, and is classified as an existing local refresh candidate. Counts stayed unchanged: `orders_total=10`, `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=10`, and `order_status_events=0`. Formal order sync remains closed.

Naver-ERP-20C is approval planning only. It does not execute the refresh write. A later controlled refresh write still requires clean worktrees, fresh backup evidence, fresh readonly repeat, exact identity match, store-scoped role permission, sensitive-action approval, audit evidence, post-write readback, and sensitive scan. It does not write orders, products, SyncLog, tested-success records, audit rows, or timeline events.

ERP-Auth-1E approves a narrow runtime mock permission API surface for frontend visibility planning. ERP-Auth-1F implements `GET /api/v1/permissions/role-inventory`, `POST /api/v1/permissions/mock-check`, and `POST /api/v1/permissions/sensitive-action/mock-check`. These routes wrap the existing private permission mock gates and return only safe role, store-scope, permission, approval, and business-message fields. They do not create a real auth session, add user tables, change schema, write local data, call platform APIs, store secrets, save raw responses, or open formal sync.

Naver-ERP-20D approves only one controlled existing-order refresh attempt for safe hash `id-hash-192b9c67e8`, with runtime permission mock evidence and sensitive-action approval evidence. It does not write local order data or open formal order sync.

Naver-ERP-20E creates a pre-write backup, repeats the readonly Naver preview, and runs the controlled refresh gate for safe hash `id-hash-192b9c67e8`. The gate finds no business-field changes, so it does not update the order. It writes five append-only `operation_audit_logs` rows under correlation id `audit-corr-20e-192b9c67e8`, with terminal action `local_write_blocked` and reason `no_business_field_change`. Orders, products, SyncLog, tested-success rows, and order status events remain unchanged.

Naver-ERP-20F verifies the 20E result by readback only: `orders_total=10`, `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=15`, and `order_status_events=0`. The selected safe hash exists exactly once. Formal Naver order sync remains closed.

ERP-Auth-1G and ERP-Auth-1H are planning-only. 1G defines future frontend-wide permission visibility rules. 1H records that the runtime permission API remains mock-only and must not be treated as production authentication until user/session/role/store-membership schema, route dependencies, assignment UI, and cross-store isolation tests are separately approved.

ERP-Auth-1I proposes the future production-auth user/role schema: `erp_users`, `erp_roles`, `erp_permissions`, and `erp_role_permissions`. ERP-Auth-1J proposes `erp_store_memberships` so every permission decision can prove store scope before a preview, local write, backup, restore, migration, or formal-sync approval. These two phases are proposal-only and do not create real auth sessions or migrate schema.

ERP-Auth-1K adds a temporary-database auth schema mock migration gate in `scripts/verify_all.py`. The gate creates the proposed auth tables only inside the isolated verification database, seeds owner/admin/operator/auditor/viewer role evidence, checks store 8 membership and cross-store isolation, blocks sensitive column names, confirms business counts are unchanged, and verifies the real `backend/codex1.db` file is not touched.

ERP-Backup-2A documents the future restore runbook and operator checklist. Real restore remains closed. A later restore must require backup manifest verification, SHA-256/size checks, temporary restore dry-run, baseline-count review, pre-restore backup, human approval, audit evidence, rollback instructions, and post-restore verification.

Naver-ERP-21A records the display boundary for the 20E/20F no-change refresh result. The operator-facing wording should say the selected order was checked, no business fields changed, no local update was forced, and audit evidence was recorded. It must not imply formal Naver order sync is open.

ERP-Auth-1L approves only the narrow auth schema migration. ERP-Auth-1M implements `app/models/auth.py` and `scripts/upgrade_auth_schema.py`, then applies the migration to the real local SQLite database after creating a pre-migration backup. The migration creates auth foundation tables and seeds only safe role/permission metadata. It keeps `erp_users=0` and `erp_store_memberships=0`, so no production login or store membership assignment is active.

ERP-Auth-1N verifies the real local migration by readback: `erp_roles=5`, `erp_permissions=10`, `erp_role_permissions=35`, `erp_users=0`, and `erp_store_memberships=0`. The admin role can approve `orders.refresh_batch_write`; the operator role cannot receive that permission. Business counts stay stable.

ERP-Backup-2B adds a private restore runbook mock drill gate in `app/services/backup_service.py`. It checks manifest/hash/temp-restore/approval/audit/rollback/post-restore checklist readiness but never executes a real restore, touches the production database, deletes backups, writes rows, exposes a public API, or opens formal sync.

Naver-ERP-21B records the expected UI/audit display for a no-change Naver order refresh. The result should be treated as "checked, no business fields changed, no forced update, audit evidence recorded", not as an error and not as formal sync availability.

These phases continue to forbid storing tokens, Authorization values, request or response headers, signatures, bcrypt inputs, client secrets, raw external responses, complete channel ids, complete order/product-order ids, complete buyer or receiver names, phones, addresses, or zip codes.

### Formal Batch Sync Production Gate Boundary

ERP-Batch-1A prioritizes formal product/order batch sync readiness, but it does not open formal sync. The required production gate includes human approval, store-scoped role permission, sensitive-action approval, fresh readonly preview evidence, verified database backup evidence, duplicate protection, field whitelist verification, rollback and recovery planning, store-level failure isolation, append-only audit evidence, post-write readback, and sensitive-field scanning.

ERP-Batch-1B adds a private mock helper in `app/services/sync_service.py`:

```text
_evaluate_formal_batch_sync_production_gate(...)
```

The helper supports `naver_order_batch`, `naver_order_refresh_batch`, and `naver_product_batch`. It checks the formal-batch gate without wiring a public endpoint, calling Naver, writing orders or products, writing SyncLog, adding tested-success rows, or opening formal sync. Passing output means the gate is ready for a later controlled execution phase only.

The auth role model now includes safe sensitive permission keys for:

```text
products.batch_sync_write
orders.batch_sync_write
orders.refresh_batch_write
```

These permissions are metadata for gate planning. They do not create users, sessions, or active store memberships.

The local seed was applied after a fresh database backup. Current auth metadata counts are `erp_roles=5`, `erp_permissions=13`, `erp_role_permissions=41`, `erp_users=0`, and `erp_store_memberships=0`.

Naver-Order-Batch-1A documents the future order batch refresh path. Naver-Product-Batch-1A documents the future product batch sync path. ERP-Multistore-1A documents the large-scale multi-store production model. All three remain planning/gate phases; platform shipment, cancel, return, exchange, refund, settlement, customer service, mail, appeal, and AI automation writes remain closed.

ERP-Batch-1C and ERP-Batch-1D plan the future readonly evidence API and approval UI for formal batch sync. No new execution endpoint is open yet.

Naver-Order-Batch-1B uses the existing protected Naver order preview route in readonly mode only. A recent 3-day KST window returned HTTP `200`, `preview_status=success`, safe hash `id-hash-192b9c67e8`, and `local_sync_status=not_requested`. No local order write, product write, SyncLog write, tested-success write, audit write, or timeline event write occurred.

Naver-Product-Batch-1B uses the existing protected Naver product preview route in readonly mode only. `page=1,size=5` returned `would_create=0`, `would_update=3`, `would_refresh_only=2`, `would_skip=0`, and changed field `stock_quantity`. `page=2,size=5` returned `success_empty`. No product write occurred. The observed stock changes are manual-review evidence, not write approval.

ERP-Multistore-1B plans store membership assignment approval only. It does not create users, create memberships, activate login, or enable multi-store production operation.

Naver-Product-Batch-1C documents the approval boundary for the observed stock-only product changes. Naver-Product-Batch-1D adds a private mock gate:

```text
_evaluate_naver_product_stock_change_mock_write_gate(...)
```

The helper accepts only stock-only evidence (`changed_fields=["stock_quantity"]`), requires backup evidence, audit/rollback readiness, and admin approval for `products.batch_sync_write`, and keeps `products_written=false`.

ERP-Batch-1E adds a private mock gate for future readonly evidence APIs:

```text
_evaluate_batch_readonly_evidence_api_mock_gate(...)
```

It normalizes safe batch evidence for future approval screens but does not expose a public endpoint.

ERP-Multistore-1C adds a private store-membership assignment mock gate:

```text
evaluate_store_membership_assignment_mock_gate(...)
```

It checks safe target user hash, target store, target role, assignment reason, admin approval for `store_membership.assign`, and duplicate active membership. It does not create users or memberships.

ERP-Auth-1O remains planning-only for future role assignment approval. Production login, user creation, route-level authorization, and real store memberships remain closed.

Naver-Product-Batch-1E approves a controlled stock-only local write for the latest Naver product readonly evidence. The approval is limited to `store_id=8`, `credential_id=7`, `page=1,size=5`, `would_create=0`, `would_skip=0`, and `changed_fields=["stock_quantity"]`. It requires a verified database backup, admin approval for `products.batch_sync_write`, audit/rollback readiness, and does not write products by itself.

Naver-Product-Batch-1F adds a narrow private local writer:

```text
_sync_naver_product_stock_change_local_write(...)
```

The writer updates only `products.stock_quantity` on already-existing local Naver products. It blocks creates, skipped candidates, non-stock field changes, missing backup evidence, missing approval, and writes above the phase limit. It does not update product name, status, price, currency, source type, raw data, SyncLog, tested-success, orders, timeline events, operation audit rows, users, or store memberships. Formal Naver product batch sync remains closed.

Naver-Product-Batch-1G verifies the post-write state: `products_store8` stays at 5, only the approved stock values may change, page 2 remains readonly/empty evidence, no raw response or secrets are saved, and formal product sync remains closed.

ERP-Batch-1F remains an implementation plan for a future local readonly evidence API. The current code only has the private evidence normalizer; no public evidence API route is open.

ERP-Multistore-1D remains an approval plan for future real store membership assignment. No `erp_users` or `erp_store_memberships` rows are created by this phase, and large-scale multi-store production operation remains closed.

ERP-Batch-1G and ERP-Batch-1H add the local readonly batch evidence route:

```text
POST /api/v1/batch/readonly-evidence
```

The route normalizes safe approval evidence only. It does not call Naver or other platforms, does not write business rows, does not expose raw responses or secrets, and does not open formal product or order batch sync.

ERP-Multistore-1E adds a runtime mock gate:

```text
evaluate_store_membership_assignment_runtime_mock_gate(...)
```

It reads the real auth tables to verify target user existence, active role, approval, and duplicate active memberships. It still returns only `membership_would_create=true` and keeps `membership_written=false`.

Naver-Product-Batch-1H verifies that Products UI wording remains safe after the stock-only write: no pending product business update should be shown after post-write evidence, inventory reminders remain separate, and formal product batch sync stays closed.

Naver-Product-Batch-1I plans the rollback drill required before any future product batch sync opening. The drill must restore only to a temporary copy and compare safe product summaries; real restore remains closed.

ERP-Batch-1I documents the Codex2 approval UI integration plan for readonly batch evidence. ERP-Batch-1J implements the read-only UI display against `POST /api/v1/batch/readonly-evidence`; the UI shows business wording for product/order evidence and keeps `phase`, `sync_kind`, `would_*`, and safety flags folded in technical details. The display route does not call Naver, does not write rows, and does not open formal product or order batch sync.

ERP-Multistore-1F documents the future store-membership assignment readonly API plan. The current runtime gate can read auth tables, but no public membership assignment API is opened yet, and no `erp_users` or `erp_store_memberships` rows are created.

Naver-Product-Batch-1J adds a private rollback drill mock gate:

```text
_evaluate_naver_product_batch_rollback_drill_mock_gate(...)
```

It verifies a prior stock-only write summary, backup evidence, rollback checklist, temporary-restore planning, readback planning, and sensitive-scan planning. It blocks real restore requests and production database restore targets. It does not restore a database, write products, write orders, write SyncLog, write tested-success, write audit rows, or open formal product batch sync.

Naver-Order-Batch-1C aligns Naver order batch readonly evidence with the shared batch evidence API shape. Order batch evidence may describe candidate counts, safe changed-field names, duplicate checks, and whitelist checks for manual review only. It does not call Naver, write orders, write timeline events, or open formal order batch sync.

ERP-Multistore-1G adds a safe readonly membership assignment API:

```text
POST /api/v1/permissions/store-membership/readonly-check
```

The route reads existing auth tables through the runtime mock gate and returns business messages for missing target users, duplicate active memberships, blocked checks, or ready-for-later-assignment checks. It never creates users, sessions, role assignments, or store memberships, and keeps `membership_written=false`.

ERP-Multistore-1H keeps the local implementation boundary explicit: this API may support a future admin UI, but real user creation, production login, route-level auth enforcement, and real membership writes remain separate approval phases.

Naver-Product-Batch-1K plans a readonly rollback-drill report for the controlled stock-only product write path. The future report should show backup evidence, rollback checklist readiness, temporary-restore planning, readback planning, and sensitive-scan planning only. It must not execute real restore or open formal product batch sync.

Naver-Order-Batch-1D confirms the Orders approval evidence UI remains a readonly review surface for Naver order batch evidence. It must not call Naver, write orders, write timeline events, or imply that formal order batch sync is open.

ERP-Batch-1L cleans backend batch evidence wording. The default readonly evidence item message is now Chinese business wording, and the local evidence response says that no platform call, sync, product write, or order write was executed.

Naver-Product-Batch-1L adds a private readonly rollback report mock gate:

```text
_evaluate_naver_product_batch_rollback_drill_readonly_report_mock_gate(...)
```

It consumes the existing rollback drill gate output and produces a safe report shape with backup evidence, stock-only write summary, rollback checklist, temporary restore plan, readback plan, and sensitive-scan plan. It never restores a database, touches the production database, writes products, writes orders, writes SyncLog, writes tested-success rows, or opens formal product batch sync.

Naver-Order-Batch-1E aligns order-batch evidence wording. If an order evidence item does not provide its own business message, the backend now returns Chinese business wording and a next action that keeps formal order batch sync closed.

ERP-Batch-1M adds audit-linkage planning to readonly batch evidence through `operation_audit_rows_planned=true` while keeping `operation_audit_rows_written=false`. Future formal batch writes must still be separately approved and must create append-only audit chains.

ERP-Multistore-1K is a Codex2 walkthrough phase for the Accounts store-membership readonly panel. It verifies the UI can show membership readiness in business wording while keeping real user creation, login sessions, role assignment, and store membership writes closed.

ERP-Multistore-1L is a planning-only approval boundary for future real user invitation. A later implementation must require explicit approval, store-scoped permission, backup evidence, append-only audit evidence, invite expiry, post-create readback, and safe identifier display. This phase creates no users and writes no memberships.

Naver-Product-Batch-1M plans a future rollback readonly report UI. The UI should show backup evidence, stock-only write summary, rollback checklist readiness, temporary restore planning, readback planning, sensitive-scan planning, and the fact that formal product batch sync remains closed.

ERP-Batch-1N adds a private mock gate:

```text
_evaluate_batch_approval_audit_evidence_mock_gate(...)
```

It verifies that future batch approval evidence includes store scope, required product/order batch permissions, duplicate and whitelist checks, human approval planning, and a complete audit evidence plan. It keeps `operation_audit_rows_planned=true`, `operation_audit_rows_written=false`, `orders_written=false`, `products_written=false`, and `formal_sync_open=false`.

Naver-Order-Batch-1F is a planning-only readiness contract for order batch approval evidence. Future order batch refresh writes still require fresh readonly evidence, backup, permission, privacy gates, field whitelist, duplicate protection, append-only audit chain, readback, sensitive scan, and rollback reference. Formal order batch sync remains closed.

ERP-Multistore-1M adds a private mock gate:

```text
evaluate_real_user_invitation_mock_gate(...)
```

It verifies safe user and login hashes, masked login identifier display, target stores, target role, manual approval, backup planning, audit planning, and future membership assignment planning. It keeps `users_written=false`, `membership_written=false`, `role_assignment_written=false`, `real_auth_session_created=false`, and `operation_audit_rows_written=false`.

ERP-Multistore-1N is a readonly API plan only. A later user-invitation readiness route may wrap the private gate for administrator review, but no public route is added in this phase and real invitations remain closed.

Naver-Product-Batch-1N adds a Codex2 mock display plan for product rollback readonly reports. The UI may show backup evidence, stock-only impact, restore status, and next manual review action, while keeping restore/write/audit flags folded in technical details. It does not call Naver, restore a database, write products, or open formal product batch sync.

ERP-Batch-1O is a route plan only for a future batch approval audit-readiness local route. The current private audit evidence gate remains private; no public route is added and no audit rows are written.

Naver-Order-Batch-1G is a UI wording plan only. Future order batch audit readiness should be shown in business language while keeping `sync_kind`, `would_*`, changed fields, and audit flags folded. Formal order batch sync remains closed.

ERP-Multistore-1O verifies the user invitation readonly API mock gate boundary. Safe user hash, safe login hash, masked login identifier, target stores, target role, manual approval, backup planning, audit planning, and membership assignment planning are required. It keeps user creation, invite sending, auth sessions, role assignment, store membership writes, and audit-row writes closed.

ERP-Multistore-1P adds a local readonly API:

```text
POST /api/v1/permissions/user-invitation/readonly-check
```

The route wraps the private invitation mock gate and returns seller/admin-readable business messages for ready, duplicate target user, unmasked login identifier, missing approval, and permission-blocked cases. It never creates users, sends invitations, creates sessions, assigns roles, assigns store memberships, writes audit rows, or opens formal sync.

Naver-Product-Batch-1O is a backend route plan only for a future product rollback readonly report. No route is added in this phase. Future implementation must remain readonly and must not execute restore, write products, write audit rows, or open formal product batch sync.

ERP-Batch-1P adds a service-level mock gate:

```text
evaluate_batch_approval_audit_evidence_local_route_mock_gate(...)
```

It wraps the private batch approval audit evidence gate and records the future route path as planned evidence only. It keeps `public_endpoint_enabled=false`, `operation_audit_rows_written=false`, `orders_written=false`, `products_written=false`, and `formal_sync_open=false`.

Naver-Order-Batch-1H adds Codex2 readonly UI display for order batch audit readiness. The backend contract remains unchanged: no Naver API call, no order write, no product write, no SyncLog, no tested-success row, no shipment/cancel/return/exchange write, and formal order batch sync remains closed.

ERP-Multistore-1Q plans the Codex2 user invitation readonly UI. The UI must show invitation readiness in business language while keeping hashes, skip reasons, write flags, and audit flags folded.

ERP-Multistore-1R implements the Codex2 user invitation readonly UI against the existing readonly API/data-provider method. It does not create users, send invitations, create sessions, assign roles, assign store memberships, or call platform APIs.

ERP-Batch-1Q is a plan-only boundary for a future readonly local route:

```text
POST /api/v1/batch/approval-audit-evidence
```

No route is added in this phase. Future implementation must remain readonly and must not write audit rows, products, orders, SyncLog, tested-success rows, or open formal sync.

Naver-Product-Batch-1P adds a service-level mock gate:

```text
evaluate_naver_product_rollback_readonly_report_backend_route_mock_gate(...)
```

It wraps the existing rollback readonly report gate and records a planned future route path while keeping `public_endpoint_enabled=false`, `real_restore_executed=false`, `production_db_touched=false`, `products_written=false`, and `formal_product_sync_open=false`.

Naver-Order-Batch-1I is a Codex2 walkthrough phase for the Orders audit readiness panel. The panel remains readonly and must not imply formal order batch sync is open.

ERP-Batch-1R closes the mock-gate boundary for the batch approval audit evidence readonly route. The gate still requires readonly evidence, approval context, and a complete audit evidence plan while keeping `operation_audit_rows_written=false`, `orders_written=false`, `products_written=false`, and `formal_sync_open=false`.

ERP-Batch-1S adds a local readonly route:

```text
POST /api/v1/batch/approval-audit-evidence
```

The route returns approval audit-evidence readiness for local review. It rejects sensitive markers and writes no audit rows, orders, products, SyncLog, tested-success rows, or platform data.

Naver-Product-Batch-1Q plans the local product rollback readonly report route. The route is limited to backup, rollback checklist, readback, and sensitive-scan evidence; real restore and product writes remain closed.

Naver-Product-Batch-1R adds a local readonly route:

```text
POST /api/v1/batch/naver/products/rollback-readonly-report
```

The route wraps the rollback readonly report gate. It executes no restore, touches no production database, writes no products or audit rows, and keeps formal product batch sync closed.

ERP-Multistore-1S verifies the Codex2 Accounts user invitation readiness panel in backend and mock modes. Real invitation, user creation, role assignment, and store membership writes remain closed.

ERP-Batch-2F adds a service-level mock gate:

```text
evaluate_formal_batch_approval_decision_mock_gate(...)
```

The gate requires fresh readonly evidence, approval-audit evidence, backup manifest verification, rollback readiness, permission gate evidence, field whitelist, duplicate check, sensitive scan, post-write readback planning, and audit correlation planning. It only returns `formal_batch_approval_decision_mock_ready` for manual review readiness. It keeps execution unapproved, does not expose a route, writes no audit rows or business rows, and keeps formal product/order batch execution closed.

ERP-Batch-2G is a readonly API plan only. No new route is exposed in this phase.

ERP-Batch-2H adds a Codex2 Orders readonly approval-decision panel. The backend contract remains no platform call, no product write, no order write, no SyncLog write, no tested-success write, no audit-row write, and no formal batch execution.

ERP-Multistore-2C adds a service-level mock gate:

```text
evaluate_real_user_invitation_approval_checklist_mock_gate(...)
```

The gate verifies masked login display, target user/login hashes, target stores, target role, admin approval, backup evidence, audit plan, membership assignment plan, invite expiry, one-time invite planning, post-create readback, rollback/disable-user readiness, privacy display, and login boundary acknowledgement. It creates no user, sends no invitation, creates no auth session, assigns no role, writes no membership, and writes no audit row.

ERP-Multistore-2D is a Codex2 UI implementation plan only. Real user invitation remains closed.

ERP-Batch-2I adds a service-level mock gate:

```text
evaluate_formal_batch_approval_decision_readonly_api_mock_gate(...)
```

It wraps the 2F approval decision gate and verifies the future readonly API shape: business wording, folded technical details, no execution button, no write endpoint, hidden sensitive fields on the main page, separate route implementation, and closed formal execution boundary. It keeps `public_endpoint_enabled=false`, `backend_route_implemented=false`, `execution_approved=false`, `orders_written=false`, `products_written=false`, `operation_audit_rows_written=false`, and `formal_sync_open=false`.

ERP-Batch-2J is a local readonly API implementation plan only for:

```text
POST /api/v1/batch/approval-decision/readonly-check
```

No route is added in this phase.

ERP-Multistore-2E is a readonly API plan only for a future invitation approval checklist route. Real invitation, user creation, auth sessions, role assignment, membership writes, and audit-row writes remain closed.

ERP-Multistore-2F adds Codex2 Accounts mock display for invitation approval checklist wording. It does not change backend write contracts.

Naver-Order-Batch-2A documents the approval boundary for any future Naver order batch execution. Future execution requires fresh readonly candidates, store-scoped approval, permission checks, backup, privacy gate, whitelist, duplicate protection, audit chain, readback, and rollback planning. No Naver call or local order write is performed in this phase.

ERP-Batch-2K adds a service-level local-route mock gate:

```text
evaluate_formal_batch_approval_decision_readonly_api_local_route_mock_gate(...)
```

It keeps the planned approval-decision readonly route unexposed while verifying route shape, business wording, folded technical details, and closed execution boundaries.

ERP-Batch-2L exposes a local readonly route:

```text
POST /api/v1/batch/approval-decision/readonly-check
```

The route returns approval-decision readiness for local review. It writes no orders, products, SyncLog, tested-success rows, timeline events, or audit rows, and it does not approve batch execution.

ERP-Multistore-2G adds a service-level mock gate:

```text
evaluate_real_user_invitation_approval_checklist_readonly_api_mock_gate(...)
```

It verifies the future invitation checklist readonly API contract while keeping `public_endpoint_enabled=false`, `backend_route_implemented=false`, `invitation_sent=false`, `users_written=false`, `membership_written=false`, and `operation_audit_rows_written=false`.

ERP-Multistore-2H is a local API implementation plan only. No invitation checklist route is exposed in this phase.

Naver-Order-Batch-2B adds a service-level mock gate:

```text
evaluate_naver_order_batch_execution_approval_mock_gate(...)
```

It verifies Naver order batch execution approval readiness using fresh readonly candidates, backup, store-scoped approval, permission gate, privacy gate, whitelist, delivery/claim mapping review, duplicate protection, audit chain, readback, rollback, and sensitive scan. It does not call Naver, write orders, write timeline events, or enable shipment/cancel/return/exchange platform writes.

ERP-Batch-2M plans Codex2 frontend integration for the approval-decision readonly API. It adds no backend write contract and does not approve formal batch execution.

ERP-Batch-2N integrates Codex2 Orders with:

```text
POST /api/v1/batch/approval-decision/readonly-check
```

The frontend displays review readiness in business wording while keeping execution flags and route metadata folded. The backend contract remains readonly: no Naver call, no order/product write, no SyncLog/tested-success write, no audit-row write, and no formal product/order batch execution.

ERP-Multistore-2I adds a service-level local-route mock gate:

```text
evaluate_real_user_invitation_approval_checklist_readonly_api_local_route_mock_gate(...)
```

It verifies the invitation approval checklist route boundary while keeping `public_endpoint_enabled=false`, `backend_route_implemented=false`, `invitation_sent=false`, `users_written=false`, `membership_written=false`, and `operation_audit_rows_written=false`.

ERP-Multistore-2J exposes a local readonly route:

```text
POST /api/v1/permissions/user-invitation/approval-checklist/readonly-check
```

The route returns checklist readiness for local review only. It does not create users, send invitations, create auth sessions, assign roles, write store memberships, write audit rows, or open formal sync.

Naver-Order-Batch-2C plans the future order batch execution approval readonly UI. No Naver call, local order write, or platform order write is performed.
