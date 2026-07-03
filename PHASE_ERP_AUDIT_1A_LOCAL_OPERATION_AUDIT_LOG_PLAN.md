# Phase ERP-Audit-1A - Local Operation Audit Log Plan

## Summary

Phase ERP-Audit-1A defines the local operation audit log plan for production ERP use.

This phase is planning-only. It does not create a database table, does not run a migration, does not write audit rows, does not modify runtime frontend UI, does not call platform APIs, and does not change backup or restore behavior.

The production goal is simple:

```text
Who did what, when, against which store/data object, with what result, and can we recover?
```

## Why SyncLog Is Not Enough

`SyncLog` records sync-like jobs and platform data flows. It is not a complete local operation audit trail.

Production ERP needs a separate audit log for:

- approvals.
- manual local writes.
- credential changes.
- store changes.
- order/product edits.
- batch refresh gates.
- backup creation.
- restore attempts.
- export/import actions.
- dangerous blocked operations.

`SyncLog` can remain sync-focused. `operation_audit_logs` should be the human/accountability layer.

## Proposed Table

Future schema name:

```text
operation_audit_logs
```

Recommended columns:

- `id`.
- `created_at`.
- `store_id`.
- `platform`.
- `actor_type`: `human`, `system`, `automation`, `test`.
- `actor_id`: nullable for now.
- `actor_label`: safe display label, for example `local_admin`.
- `actor_role`: safe role label.
- `action`: safe enum, for example `order_refresh_batch_approved`.
- `operation_phase`: phase name, for example `Naver-ERP-15D`.
- `target_type`: `order`, `product`, `credential`, `backup`, `restore`, `settings`, `sync_gate`.
- `target_id`: local numeric id when safe.
- `target_hash`: safe hash such as `id-hash-...`.
- `correlation_id`: groups approval, backup, write, and verification rows.
- `request_id`: local request id when available.
- `status`: `success`, `failed`, `blocked`, `skipped`, `planned`.
- `reason_code`: safe enum.
- `changed_field_names`: JSON list of field names only.
- `before_summary`: sanitized JSON summary.
- `after_summary`: sanitized JSON summary.
- `counts_summary`: sanitized JSON counts.
- `backup_path`: local backup path when the operation creates or uses a backup.
- `backup_sha256`: hash of the backup file when available.
- `restore_source_path`: local restore source path when relevant.
- `safety_flags`: JSON object with booleans such as `raw_response_saved=false`.
- `sensitive_scan_passed`.
- `raw_response_saved`.
- `secrets_saved`.
- `notes`: operator-safe note.

## Required Audit Events

The first implementation should record audit events for:

- user-approved local writes.
- blocked local writes.
- Naver order refresh gates.
- Naver order refresh batch approval.
- product/order sync gate outcomes.
- credential create/update/delete.
- backup creation.
- restore dry-run.
- restore execution.
- schema migration approval.
- schema migration execution.

## Sensitive Data Boundary

Audit logs must never store:

- tokens.
- Authorization values.
- request or response headers.
- signatures.
- bcrypt/signature inputs.
- client secrets.
- raw platform responses.
- full `channel_no`.
- full order ids.
- full product-order ids.
- buyer or receiver full names.
- full phone numbers.
- full addresses.
- zip codes.
- complete request bodies containing credentials or privacy.

Allowed audit data:

- safe hashes.
- local numeric ids.
- field names only.
- counts.
- safe status enums.
- Chinese status labels.
- backup file path.
- backup SHA-256.
- safe reason codes.

## Backup And Restore Linkage

Every production write phase should create or reference an audit correlation id:

1. approval row.
2. backup-created row.
3. write-started row.
4. write-result row.
5. verification-result row.

Every restore flow should create:

1. restore-requested row.
2. restore-dry-run row.
3. restore-executed row, only if explicitly approved.
4. post-restore-verification row.

This makes rollback explainable without exposing raw platform data.

## Suggested Indexes

Future indexes:

- `created_at`.
- `store_id, created_at`.
- `platform, created_at`.
- `actor_type, actor_id, created_at`.
- `action, created_at`.
- `target_type, target_id`.
- `target_hash`.
- `correlation_id`.
- `status, reason_code`.

## API And UI Direction

Future backend endpoints:

- `GET /api/v1/audit-logs`.
- `GET /api/v1/audit-logs/{id}`.
- `GET /api/v1/audit-logs/by-correlation/{correlation_id}`.

Future frontend views:

- Logs / Audit tab.
- store-scoped operation history.
- backup/restore history.
- write approval history.
- blocked operation history.

Main UI should show seller-friendly operation text. Technical fields should stay in details.

## Verification Plan

Future `verify_all.py` coverage should include:

- schema shape in a temporary database.
- sensitive-field rejection.
- safe row creation.
- blocked write row creation.
- approval/backup/write/verify correlation id chain.
- backup SHA-256 format.
- restore dry-run event.
- no raw response/token/header/signature/client secret leaks.

## Recommended Next Stages

1. `Phase ERP-Audit-1B: Operation audit log mock schema gate`
   - temporary verification database only.
   - no real schema change.

2. `Phase ERP-Audit-1C: Operation audit log schema approval plan`
   - backup and rollback plan for real schema migration.

3. `Phase ERP-Audit-1D: Operation audit log schema migration`
   - create the real table and indexes.
   - insert no rows during migration.

4. `Phase ERP-Audit-1E: Audit logging service mock gate`
   - private helper and verify_all coverage.

5. `Phase ERP-Audit-1F: Backup manifest plan`
   - define backup file metadata and SHA-256 checks.

6. `Phase ERP-Audit-1G: Restore dry-run plan`
   - define how restore is verified before execution.

## Current Boundary

ERP-Audit-1A only defines the plan. It does not make the system production-auditable yet.
