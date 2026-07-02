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

`POST /api/v1/api-credentials/smoke-test` accepts `platform: naver | coupang | all` and `mode: readonly`. The env fallback path remains a developer-only fallback and does not write `ApiCapabilityTestResult`. The formal Naver path is store-bound and requires `store_id` plus an active credential. When `REAL_API_TEST_ENABLED=false`, the endpoint returns disabled results before creating any external HTTP client. When enabled, it runs only minimal read-only checks and still never returns keys, tokens, authorization headers, request signatures, or raw external response payloads. `REAL_API_WRITE_ENABLED=false` keeps write operations out of scope. Store-bound readonly smoke tests may write local `ApiCapabilityTestResult` records with `test_mode=real_readonly`; those records contain only step statuses, error code, HTTP status, timestamps, and docs-pending guardrail metadata.

Naver product/order real preview is intentionally locked behind guardrails. The current reference documentation line is current / 2.81.0, but product and order requests are not yet sent to the real API. Planned preview endpoints are:

```text
POST /api/v1/sync/products/naver/preview
POST /api/v1/sync/orders/naver/preview
```

The Naver product preview route now exists with an explicit `real_preview` gate. `POST /api/v1/sync/products/naver/preview` still defaults to `real_preview=false` and returns `guardrail_status=blocked`, `preview_status=blocked`, `test_status=not_tested`, and `error_code=guardrail_blocked` before token exchange or external HTTP. When `real_preview=true`, the route first enforces the approved local store/credential, `page=1`, `status` null/ALL, `REAL_API_TEST_ENABLED=true`, `REAL_API_WRITE_ENABLED=false`, decryptable credential, configured channel number, and `minimum_request_body_confirmed=true`. Phase 6D-6M splits the gate in two: readonly preview keeps `real_sync=false` and allows `size<=5`, while the already approved one-row local sync micro-test still requires `real_sync=true` and `size=1`. The only real Naver request body allowed by the readonly small-batch gate is `{"page":1,"size":N}` for `POST /v1/products/search`, where `N` is 1 through 5; it does not pass internal `status=ALL`, `productStatusTypes`, keyword, seller product id, date filters, search keyword fields, product-number filters, or full channel number. This preview does not write `products`, does not write `SyncLog`, and does not write `ApiCapabilityTestResult tested_success`. Credential decryptability only proves the local encrypted secret can be read; it does not prove formal Naver product sync access.

Phase 6D-6G completed a real Naver product readonly micro preview with HTTP 200. Phase 6D-6H keeps the endpoint preview-only and adds a sanitized field-mapping summary for frontend/business review. The response can include `product_field_mapping_summary`, `observed_field_names`, `missing_field_names`, `mapping_readiness`, and `channel_products_summary`, but it never returns raw product payloads, long HTML, image-detail payloads, full channel numbers, tokens, headers, signatures, or client secrets. The current `products` table can hold a first product snapshot with `external_product_id`, `name`, `status`, `price`, `currency`, `stock_quantity`, `source_type`, and JSON `raw_data`; Naver `originProductNo`, `channelProductNo`, display status, and channel-product counts must remain sanitized metadata in `raw_data` for a future sync phase. Multiple `channelProducts` are counted only and never expanded or written in preview.

Phase 6D-6I adds `dry_run_diff` to the same preview response. The dry-run estimates future local sync impact with `would_create`, `would_update`, `would_skip`, `skip_reasons`, `matched_existing_count`, and `incoming_candidate_count` by reading local `products` with `store_id + platform + external_product_id`; it never writes products, SyncLog, or capability success records. Single-channel products with `channelProductNo` and `productName` can become create/update candidates. Multiple `channelProducts`, missing external IDs, and missing product names are skipped. Missing price or stock is reported as optional metadata but does not force a skip. `dry_run_diff` is not formal sync availability, and real writes require a separately approved phase.

Phase 6D-6M expands only the readonly preview side into a small-batch dry-run. `real_preview=true` with `real_sync=false` may request up to 5 products through the same minimum body shape `{"page":1,"size":N}` and returns at most 5 masked `sample_ids`. The response keeps `dry_run_diff.would_create` and `would_update` for local impact estimation, and adds `single_channel_product_count`, `multiple_channel_products_count`, `missing_external_product_id_count`, `missing_product_name_count`, `missing_price_count`, and `missing_stock_count`. `ready_for_local_sync` is deliberately pinned to `false` in this small-batch preview so the frontend and operators do not confuse readonly observation with a writable sync approval. `real_sync=false` remains strictly no-write: no local product rows, no SyncLog, and no capability success writes.

Phase 6D-6N-Pre-Impl strengthens that dry-run with a safer explanation layer before any future batch write decision. The preview can now describe create/update/skip reasons with `diff_summary`, `create_reasons`, `update_reasons`, field-name-only `changed_fields` and `unchanged_fields`, `missing_optional_fields`, `risk_flags`, `upsert_key_summary`, and `write_safety_summary`. It still does not write `products`, does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, does not save raw responses, and does not open batch sync. New skip reasons include duplicate external IDs in the same preview batch, invalid status shape, invalid price shape, and invalid stock shape; all returned samples remain masked and raw payloads remain suppressed.

Phase 6D-6J is a design lock for the first Naver local product write and still performs no writes. The future write phase must be named separately, must require `real_sync=true`, and is limited to `store_id=8`, `credential_id=7`, `page=1`, `size=1`, and at most one single-channel product. A write candidate must have `channelProductNo` and `productName`; multiple `channelProducts`, missing external IDs, or missing names are skipped. The future row would use `platform=naver`, `source_type=naver_real_sync`, `currency=KRW`, and sanitized `raw_data` only: `platform_origin_product_no`, `platform_channel_product_id`, `display_status`, `channel_products_count`, `source_preview_id_hash`, `mapping_version=naver_product_v1`, `synced_from=naver_product_preview`, and `raw_response_saved=false`. Raw Naver responses, HTML, image detail payloads, tokens, headers, signatures, client secrets, full channel numbers, and long descriptions must never be stored. Before the first approved write, back up `backend/codex1.db`; after writing, read back `products where store_id=8 and platform='naver'`. A future sanitized `SyncLog` may use `sync_type=naver_product_local_sync` with requested size and created/updated/skipped counts, but Phase 6D-6J does not write SyncLog or mark `ApiCapabilityTestResult tested_success`.

Phase 6D-6K adds the approved one-row Naver product local sync micro-test gate to `POST /api/v1/sync/products/naver/preview`. It still requires `real_preview=true` and adds `real_sync=true`; it remains limited to `store_id=8`, `credential_id=7`, `page=1`, `size=1`, the readonly Naver request body `{"page":1,"size":1}`, and a single `channelProducts[]` candidate with `channelProductNo` and `productName`. The micro-test may create or update at most one local `products` row with `source_type=naver_real_sync` and sanitized `raw_data`; it does not write `SyncLog`, does not write `ApiCapabilityTestResult tested_success`, does not save raw response/token/header/signature, and does not open batch product sync.

The planned product preview route is based on `POST /v1/products/search`. The planned order preview route should read `GET /v1/pay-order/seller/product-orders/last-changed-statuses` first, then query details with `POST /v1/pay-order/seller/product-orders/query`. The older direct `GET /v1/pay-order/seller/product-orders` draft is treated as deprecated or unconfirmed and must not be called. Until a later preview stage explicitly opens these routes, product/order capability results stay `guardrail_blocked`, `not_tested`, and `safe_to_real_test=false`.

The Naver order preview route now exists as a micro readonly scaffold. `POST /api/v1/sync/orders/naver/preview` defaults to `real_preview=false` and returns blocked before token or HTTP. `real_preview=true` is restricted to the approved local store/credential, `page=1`, `size=1`, a KST window of one day or less, and `REAL_API_WRITE_ENABLED=false`. The feed request uses the verified shape `lastChangedFrom` plus `limitCount=1`, formats `lastChangedFrom` with milliseconds, and omits `lastChangedTo`; it does not pass page, size, or order_status through to Naver. When `include_detail=true`, detail lookup is allowed only if the feed returns a productOrderId, and it queries at most one ID with `POST /v1/pay-order/seller/product-orders/query`. If the feed is empty, detail is skipped with `detail_skipped_reason=no_changed_orders` and the time window is not expanded. The response may include sanitized diagnostic metadata and detail field-observation booleans, but it never returns a full URL, query values, raw error body, request headers, token, full order IDs, productOrderIds, buyer/receiver names, phones, addresses, delivery details, payment raw payloads, authorization headers, signatures, or full `channel_no`. It never writes `orders`, never writes `SyncLog`, never writes `ApiCapabilityTestResult tested_success`, and never stores tokens/raw responses.

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
