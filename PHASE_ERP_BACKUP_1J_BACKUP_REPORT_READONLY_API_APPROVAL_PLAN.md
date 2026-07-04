# Phase ERP-Backup-1J: Backup report readonly API approval plan

## Scope

ERP-Backup-1J approves a narrow backend-only path for exposing local backup manifest evidence through a readonly API.

This phase is planning-only. It does not add routes, write data, restore a database, delete backups, call platform APIs, change schema, modify Codex2 runtime UI, or open formal product/order sync.

## Approved Direction

The future local API may expose only:

```text
GET /api/v1/backups/local-report
GET /api/v1/backups/local-report/summary
```

The API must read from the already approved local backup root and must not accept a backup root or arbitrary filesystem path from the caller.

Allowed fields:

- report status and business message;
- backup and manifest counts;
- manifest validity and sensitive-scan booleans;
- backup existence and size-match booleans;
- abbreviated SHA-256;
- retention metadata;
- safe baseline counts;
- safety booleans such as `raw_response_saved=false`, `secrets_saved=false`, and `privacy_fields_redacted=true`.

## Guardrails

The future API must:

- allow only `GET`;
- cap `limit`;
- reject unsupported query parameters without echoing raw values;
- avoid restore, delete, cleanup, upload, or write operations;
- avoid writing `operation_audit_logs`;
- avoid writing business tables;
- avoid platform API calls;
- keep formal Naver sync closed.

## Still Not Approved

- Restore API.
- Backup delete API.
- Backup creation API from frontend.
- Retention cleanup automation.
- Backup report frontend display.

