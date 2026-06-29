# Codex 1 Backend

FastAPI backend for the AI multi-store operations and environment management system.

## Current Scope

Stage 1C provides the backend foundation and secure credential base only:

- Versioned API prefix at `/api/v1`
- Compatible legacy health check at `/health`
- SQLAlchemy models for stores, API credentials, and sync logs
- Store CRUD endpoints
- Encrypted API credential storage
- Naver and Coupang mock client placeholders
- Sync log service and read endpoint
- Unified success and error response structure
- Repeatable seed data for Chinese, Korean, and mixed UTF-8 text

Product sync, order sync, customer inquiries, sales, dashboard, devices, email, appeals, and real Naver/Coupang API calls are not implemented in this stage.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
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
```

`.env.example` contains only the field name and a placeholder. Do not commit `.env`, generated encryption keys, real platform access keys, or real platform secret keys.

If `CREDENTIAL_ENCRYPTION_KEY` is missing or invalid, credential create/update/decrypt operations return a clear API error instead of silently using a fallback key.

## Run

```powershell
uvicorn app.main:app --reload
```

Then open:

- API root: http://127.0.0.1:8000/
- API v1 health check: http://127.0.0.1:8000/api/v1/health
- Legacy health check: http://127.0.0.1:8000/health
- Swagger docs: http://127.0.0.1:8000/docs

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

## Platform Client Placeholders

Current platform clients are mock placeholders only:

```text
app/clients/naver_client.py
app/clients/coupang_client.py
```

They require an internal decrypted credential object and provide mock methods such as `test_connection()`, `fetch_products_mock()`, `fetch_orders_mock()`, and `fetch_customer_inquiries_mock()`.

They do not call real Naver or Coupang APIs, do not contain real keys, and must not print plaintext credentials.

## Sync Logs

Sync logs track future platform operations and credential tests. Each log is bound to a `store_id`.

Service functions live in:

```text
app/services/sync_log_service.py
```

Read endpoint:

```text
GET /api/v1/sync-logs?store_id={store_id}
```

Supported status values for this stage are `running`, `success`, and `failed`. `message`, `error_detail`, and `raw_summary` support Chinese, Korean, and mixed UTF-8 text.

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

Stage 1C verification also writes Chinese and Korean credential metadata and sync log messages, then reads them back through services and API responses.

## PostgreSQL Migration Note

The database URL is configured through `DATABASE_URL` in `.env` or the process environment. For a future PostgreSQL switch, set a PostgreSQL SQLAlchemy URL, for example:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/codex1
```

PostgreSQL driver dependencies and migration tooling will be added in a later stage.

## Local Files

Do not commit local secrets or runtime data:

- `.env`
- SQLite database files such as `*.db`, `*.sqlite`, `*.sqlite3`
- virtual environments
- `__pycache__`
- logs and raw API response files
