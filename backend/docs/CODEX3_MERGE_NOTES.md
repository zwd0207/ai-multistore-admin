# Codex3 Merge Notes

## Technology Stack

```text
FastAPI
SQLAlchemy 2.x
Pydantic v2
SQLite for development
cryptography.Fernet for local secret encryption
Uvicorn
```

## Directory Structure

```text
backend/app/main.py
backend/app/config.py
backend/app/database.py
backend/app/api/v1/
backend/app/models/
backend/app/schemas/
backend/app/services/
backend/app/clients/
backend/scripts/
backend/docs/
```

## Commit History Summary

```text
init: add codex1 planning document and gitignore
feat: scaffold FastAPI backend
feat: add store database models and CRUD API
feat: add encrypted credential foundation
feat: add mock product order inquiry sync pipeline
feat: add sales stats dashboard and ai context
feat: add operations support models and APIs
```

## Do Not Commit

```text
.env
*.db
*.sqlite
*.sqlite3
.venv/
__pycache__/
logs/
raw API response files
real credentials
real email tokens
real private buyer data
```

## Completed Modules

```text
Stores CRUD
Encrypted platform credentials
Mock Naver/Coupang clients
Sync logs
Mock product/order/customer-inquiry sync
Sales stats
Dashboard summary
AI daily context, structured only
Device environments
Email accounts
Important emails
Appeal cases
Verification scripts
Documentation
```

## Not Completed Real Integrations

```text
Real Naver API
Real Coupang API
Real platform signing
Real email provider connections
Real email ingestion
Real attachments
OCR
AI model calls
Frontend pages
Alembic migrations
PostgreSQL driver setup
```

## Alembic Recommendation

The current schema uses `Base.metadata.create_all`. Before production or multi-developer schema changes, introduce Alembic:

```text
alembic init migrations
create initial revision from current metadata
use migration scripts for future changes
```

## PostgreSQL Notes

Current config uses:

```text
DATABASE_URL=sqlite:///./codex1.db
```

Future PostgreSQL URL:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/codex1
```

Add PostgreSQL driver dependencies and check JSON/DateTime behavior before switching.

## Real Naver/Coupang API Boundary

Use existing client files:

```text
app/clients/naver_client.py
app/clients/coupang_client.py
```

Keep platform logic separate. Do not call real APIs from endpoints directly. Flow should remain:

```text
endpoint -> service -> credential_service internal decrypt -> platform client -> service writes db -> sync_log
```

Do not log plaintext credentials.

## Real Email Boundary

Use `EmailAccount` for encrypted token metadata. Real provider integrations should live in service/client modules, not endpoints.

Do not store:

```text
real attachment files in database
plaintext tokens
full addresses
ID cards
bank cards
legal documents
```

## Security Rules

- `CREDENTIAL_ENCRYPTION_KEY` must come from environment.
- No default encryption key is allowed.
- Public APIs must never return plaintext or encrypted secret values.
- Buyer phone is masked only.
- Device environment stores labels only.
- Internal method `get_decrypted_credential_for_internal_use()` must not be exposed as an API route.

## Codex2 Merge Checklist

Confirm these frontend paths before merge:

```text
GET /api/v1/stores
GET /api/v1/dashboard/summary
GET /api/v1/ai/daily-context
GET /api/v1/products
GET /api/v1/orders
GET /api/v1/customer-inquiries
GET /api/v1/device-environments
GET /api/v1/email-accounts
GET /api/v1/important-emails
GET /api/v1/appeal-cases
POST /api/v1/sync/products/mock
POST /api/v1/sync/orders/mock
POST /api/v1/sync/customer-inquiries/mock
```

All paths use `/api/v1`.

