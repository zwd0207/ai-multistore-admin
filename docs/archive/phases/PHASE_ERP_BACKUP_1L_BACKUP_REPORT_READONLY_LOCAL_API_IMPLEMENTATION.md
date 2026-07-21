# Phase ERP-Backup-1L: Backup report readonly local API implementation

## Scope

ERP-Backup-1L implements the approved local backup report readonly API.

This phase exposes only read endpoints. It does not restore a database, delete backups, create backups, write audit rows, write business rows, change schema, call platform APIs, modify Codex2 runtime UI, or open formal sync.

## Implementation

New route module:

```text
backend/app/api/v1/endpoints/backups.py
```

Registered routes:

```text
GET /api/v1/backups/local-report
GET /api/v1/backups/local-report/summary
```

The endpoint accepts only:

```text
limit
```

It does not accept backup root, restore path, delete flag, cleanup flag, upload target, or arbitrary filesystem path parameters.

## Response Safety

The API returns safe operational fields:

- `status`
- `business_message`
- `backup_count`
- `manifest_count`
- safe item summaries
- `summary`
- abbreviated SHA-256
- retention metadata
- `backup_deleted=false`
- `real_restore_executed=false`
- `production_db_touched=false`
- `rows_written=0`
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `formal_sync_open=false`
- `platform_writes_enabled=false`

Unsupported query parameters return HTTP 400 with safe business copy and do not echo raw parameter values.

## Verification

`verify_all.py` covers:

- local report endpoint returns HTTP 200;
- summary endpoint returns HTTP 200;
- unsupported path-like query is blocked;
- `POST` and `DELETE` remain 405;
- no restore/delete/write actions occur;
- production `backend/codex1.db` hash and size remain unchanged;
- sensitive scan passes.

## Still Not Approved

- Backup report frontend integration.
- Backup creation from UI.
- Restore API.
- Delete or retention cleanup API.
- Formal Naver product/order batch sync.

