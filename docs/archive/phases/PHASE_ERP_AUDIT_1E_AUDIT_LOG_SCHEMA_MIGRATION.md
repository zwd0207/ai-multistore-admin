# Phase ERP-Audit-1E - Audit Log Schema Migration

## Summary

Phase ERP-Audit-1E creates the real local `operation_audit_logs` schema in `backend/codex1.db`.

This phase changes database schema only. It does not write audit rows, does not expose audit endpoints, does not add a frontend audit reader, does not call platform APIs, does not write orders/products/SyncLog rows, and does not open formal product or order sync.

## Files Changed

- `backend/app/models/operation_audit_log.py`
- `backend/app/models/__init__.py`
- `backend/app/models/store.py`
- `backend/app/database.py`
- `backend/scripts/upgrade_operation_audit_logs_schema.py`
- `backend/scripts/verify_all.py`
- `backend/README.md`
- `backend/docs/API_CONTRACT.md`
- `README.md`

## Backup

The real database was backed up before migration.

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\codex1.db.backup-erp-audit-1e-schema-migration-20260703-220137
```

Backup metadata:

- size_bytes: `724992`
- sha256: `357b21de8b8c7f8c6daead21bc93a11c68444fa341692a4c0ad8c35df0a84aba`
- integrity_check: `ok`

## Pre-Migration Counts

```text
stores=8
products=9
orders=9
sync_logs=47
api_capability_test_results=26
tested_success=8
order_status_events=0
operation_audit_logs=not present
```

SQLite integrity check before migration: `ok`.

## Migration Result

Executed:

```powershell
.\.venv\Scripts\python.exe scripts\upgrade_operation_audit_logs_schema.py
```

Result:

```text
operation audit logs schema upgraded: operation_audit_logs
```

The script was run a second time to verify idempotency.

```text
operation audit logs schema already up to date
```

## Created Schema

The real `operation_audit_logs` table now exists with 34 approved columns:

- id/time fields.
- store/platform/environment scope.
- actor metadata.
- action and operation phase.
- correlation/request ids.
- status and reason code.
- target metadata.
- safe JSON summaries.
- backup/restore path and SHA-256 fields.
- safety booleans.
- notes.

The table has the approved non-unique indexes:

- `ix_operation_audit_logs_created_at`
- `ix_operation_audit_logs_store_created_at`
- `ix_operation_audit_logs_platform_created_at`
- `ix_operation_audit_logs_actor_created_at`
- `ix_operation_audit_logs_action_created_at`
- `ix_operation_audit_logs_status_reason`
- `ix_operation_audit_logs_target`
- `ix_operation_audit_logs_target_hash`
- `ix_operation_audit_logs_correlation_id`
- `ix_operation_audit_logs_request_id`

No unique index was added because approval/backup/write/verification chains must be able to share one `correlation_id`.

## Post-Migration Counts

```text
stores=8
products=9
orders=9
sync_logs=47
api_capability_test_results=26
tested_success=8
order_status_events=0
operation_audit_logs=0
```

SQLite integrity check after migration: `ok`.

Business table counts remained unchanged. The migration inserted zero audit rows.

## Safety Boundary

Still not approved:

- runtime audit writer.
- audit API endpoints.
- Logs / Audit UI reader for real audit rows.
- database restore execution.
- platform API calls.
- product or order formal batch sync.
- shipment, cancel, return, exchange, refund, settlement, or other platform write operations.

The audit schema and future writer must not store tokens, Authorization values, request/response headers, signatures, bcrypt inputs, client secrets, raw platform responses, full channel numbers, full order ids, full product-order ids, buyer/receiver full names, phones, addresses, zip codes, or raw request bodies containing credentials or privacy data.

## Verification

- temporary `verify_all.py` schema gate: passed through `operation audit log schema migration gate: ok`.
- temporary `verify_all.py` mock write gate: passed through `operation audit log mock write gate: ok`.
- real DB post-migration readback: passed.
- idempotent migration repeat: passed.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1F: Audit log post-migration verification
```

1F should be verification-only: read back the real table, indexes, zero-row state, unchanged business counts, sensitive boundary, and docs without adding a runtime writer yet.
