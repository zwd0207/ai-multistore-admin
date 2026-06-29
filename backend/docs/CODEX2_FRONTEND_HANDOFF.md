# Codex2 Frontend Handoff

This backend is ready for local frontend integration against mock data and local SQLite state.

## Run Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Base URL:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Setup Data

Generate encryption key:

```powershell
.\.venv\Scripts\python.exe scripts\generate_key.py
```

Set `CREDENTIAL_ENCRYPTION_KEY` in local `.env`.

Seed stores:

```powershell
.\.venv\Scripts\python.exe scripts\seed.py
```

For full mock data, run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_stage_1d.py
.\.venv\Scripts\python.exe scripts\verify_stage_1e.py
.\.venv\Scripts\python.exe scripts\verify_stage_1f.py
```

These scripts rebuild the local SQLite database for verification. Use them for test data reset, not production data.

## Unified Response

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
  "detail": {}
}
```

Frontend should show `message` and can branch on `error_code`.

## Primary Screens And APIs

Store selector:

```text
GET /api/v1/stores?page=1&page_size=100
```

Dashboard:

```text
GET /api/v1/dashboard/summary?store_id={store_id}
```

AI daily context:

```text
GET /api/v1/ai/daily-context?store_id={store_id}&date=YYYY-MM-DD
```

Products:

```text
GET /api/v1/products?store_id={store_id}
```

Orders:

```text
GET /api/v1/orders?store_id={store_id}
```

Customer inquiries:

```text
GET /api/v1/customer-inquiries?store_id={store_id}
```

Operations support:

```text
GET /api/v1/device-environments?store_id={store_id}
GET /api/v1/email-accounts?store_id={store_id}
GET /api/v1/important-emails?store_id={store_id}
GET /api/v1/appeal-cases?store_id={store_id}
```

Sales stats:

```text
GET /api/v1/stats/sales?store_id={store_id}
GET /api/v1/stats/sales/by-platform?store_id={store_id}
GET /api/v1/stats/sales/by-date?store_id={store_id}
```

## Mock Sync Buttons

For a selected store with credentials:

```text
POST /api/v1/sync/products/mock?store_id={store_id}&platform=naver
POST /api/v1/sync/orders/mock?store_id={store_id}&platform=naver
POST /api/v1/sync/customer-inquiries/mock?store_id={store_id}&platform=naver
```

Supported platforms:

```text
naver
coupang
```

## Sensitive Fields Frontend Must Not Display

The backend should not return these, and the frontend must not attempt to display them:

```text
access_key
secret_key
encrypted_access_key
encrypted_secret_key
password_or_token
encrypted_password_or_token
full phone numbers
full addresses
ID numbers
bank card numbers
real full IPs
proxy passwords
remote desktop passwords
```

Use `has_access_key`, `has_secret_key`, and `has_password_or_token` for status badges.

## Korean And Chinese Text

The API returns UTF-8 JSON. UI components should support:

```text
东方优选测试店
서울뷰티테스트
ECCO 골프화 / 中文运营测试
정품 소명 자료 제출 안내
Coupang 정산 보류 / 销售资料准备 / 中文备注
```

Avoid fixed-width assumptions for mixed Chinese/Korean text.

