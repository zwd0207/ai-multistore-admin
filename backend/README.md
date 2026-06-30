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
GET    /api/v1/credentials?store_id={store_id}
GET    /api/v1/credentials/{credential_id}
PUT    /api/v1/credentials/{credential_id}
DELETE /api/v1/credentials/{credential_id}
```

Create and update requests accept `access_key` and `secret_key`, but the API never returns plaintext keys. Responses only include metadata such as `has_access_key` and `has_secret_key`.

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

`products` stores platform product snapshots with `external_product_id`, `name`, `sku`, `brand`, `category`, `price`, `currency`, `stock_quantity`, and JSON `raw_data`.

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
