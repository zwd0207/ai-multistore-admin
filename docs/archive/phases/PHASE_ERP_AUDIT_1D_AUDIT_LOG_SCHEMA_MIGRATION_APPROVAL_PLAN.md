# Phase ERP-Audit-1D - Audit Log Schema Migration Approval Plan

## Summary

Phase ERP-Audit-1D defines the approval plan for a future real `operation_audit_logs` schema migration.

This phase is planning-only. It does not create the real table, does not run a migration, does not write audit rows, does not modify Codex1 runtime behavior, does not modify Codex2 runtime UI, does not call platform APIs, and does not change backup or restore behavior.

The purpose of this phase is to make the next migration step explicit, reviewable, reversible, and safe before any production database schema change is allowed.

## Current Baseline

Completed:

- ERP-Audit-1A defined the local operation audit log purpose and safety boundary.
- ERP-Audit-1B proposed the future `operation_audit_logs` table, indexes, enums, constraints, and sensitive-field ban.
- ERP-Audit-1C validated the proposed write gate in a temporary verification SQLite database only.

Not yet completed:

- No real `operation_audit_logs` table exists in `backend/codex1.db`.
- No SQLAlchemy model or runtime audit writer is active.
- No real operation audit rows are written.
- Logs / Audit UI does not yet read real operation audit rows.

## Approval Objective

Before a real migration phase is allowed, the operator must explicitly approve:

- the target database path.
- the backup path.
- the exact migration scope.
- the zero-row migration rule.
- the post-migration verification checklist.
- the rollback plan.
- the sensitive-data boundary.

The next real migration must not be inferred from this document. It must be a separate phase with a separate approval.

## Proposed Real Migration Scope

Future migration phase should be limited to:

- Create `operation_audit_logs`.
- Create approved indexes.
- Add no seed rows.
- Add no runtime audit writer.
- Add no API endpoint.
- Add no frontend audit table reader.
- Leave all business table row counts unchanged.

The migration must be idempotent where practical:

- If the table does not exist, create it.
- If the table exists with the approved shape, do not duplicate it.
- If the table exists with an incompatible shape, stop and require manual review.

## Required Pre-Migration Checks

Before running a real schema migration:

- `git status` must be clean for Codex1 and Codex2, except files intentionally modified for the migration phase.
- `python scripts/verify_all.py` must pass in Codex1.
- `git diff --check` must pass.
- Encoding scan must pass when available.
- The real database must be backed up before schema changes.
- The backup file must be copied outside the repo working tree backup target folder.
- Backup file size and SHA-256 must be recorded.
- `PRAGMA integrity_check` must pass before migration.
- Pre-migration row counts must be recorded for:
  - `orders`.
  - `products`.
  - `sync_logs`.
  - `api_capability_test_results`.
  - `order_status_events`.
  - any existing `operation_audit_logs`, if present.

## Required Backup

The future real migration must create a backup before touching `backend/codex1.db`.

Recommended backup directory:

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\
```

Recommended filename:

```text
codex1.db.backup-erp-audit-schema-migration-YYYYMMDD-HHMMSS
```

Required backup metadata:

- absolute backup path.
- file size.
- SHA-256.
- created timestamp.
- source database path.
- phase name.
- operator approval note.

## Proposed Table Shape

The approved table remains the 1B proposal:

- `id`.
- `created_at`.
- `updated_at`.
- `store_id`.
- `platform`.
- `environment`.
- `actor_type`.
- `actor_id`.
- `actor_label`.
- `actor_role`.
- `action`.
- `operation_phase`.
- `correlation_id`.
- `request_id`.
- `status`.
- `reason_code`.
- `target_type`.
- `target_id`.
- `target_hash`.
- `target_label`.
- `changed_field_names`.
- `before_summary`.
- `after_summary`.
- `counts_summary`.
- `safety_flags`.
- `backup_path`.
- `backup_sha256`.
- `restore_source_path`.
- `restore_source_sha256`.
- `sensitive_scan_passed`.
- `raw_response_saved`.
- `secrets_saved`.
- `privacy_fields_redacted`.
- `notes`.

Required safe defaults:

- `environment='local'`.
- `sensitive_scan_passed=false`.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.

## Proposed Indexes

The approved indexes remain the 1B proposal:

- `ix_operation_audit_logs_created_at`.
- `ix_operation_audit_logs_store_created_at`.
- `ix_operation_audit_logs_platform_created_at`.
- `ix_operation_audit_logs_actor_created_at`.
- `ix_operation_audit_logs_action_created_at`.
- `ix_operation_audit_logs_status_reason`.
- `ix_operation_audit_logs_target`.
- `ix_operation_audit_logs_target_hash`.
- `ix_operation_audit_logs_correlation_id`.
- `ix_operation_audit_logs_request_id`.

No uniqueness constraint should be added for normal audit rows. Multiple rows may share one `correlation_id`.

## Sensitive Data Boundary

The schema and future writer must not store:

- tokens.
- Authorization values.
- request headers.
- response headers.
- signatures.
- bcrypt/signature input.
- client secrets.
- raw request bodies.
- raw response bodies.
- full channel numbers.
- full order ids.
- full product-order ids.
- buyer full names.
- receiver full names.
- full phone numbers.
- addresses.
- zip codes.
- raw platform payloads.

Allowed values:

- safe hashes.
- local numeric ids.
- field names only.
- counts.
- booleans.
- safe status enums.
- Chinese business labels.
- backup paths.
- backup SHA-256 values.
- safe reason codes.

## Required Post-Migration Verification

After the future migration:

- `PRAGMA integrity_check` must pass.
- `operation_audit_logs` must exist.
- Required columns must exist.
- Required indexes must exist.
- Default booleans must match the approved safe defaults.
- Business table row counts must remain unchanged.
- The migration must insert zero audit rows.
- No `orders`, `products`, `SyncLog`, `ApiCapabilityTestResult tested_success`, or `order_status_events` rows may be created or modified.
- Sensitive schema and serialized metadata scans must pass.
- `python scripts/verify_all.py` must pass.

## Rollback Plan

If migration fails before commit:

- stop immediately.
- do not continue with runtime code changes.
- restore the backed-up database only after explicit approval.
- record the failure summary in the phase report.

If migration succeeds but verification fails:

- stop immediately.
- do not write audit rows.
- do not run application features that depend on the new table.
- compare table shape and counts.
- either fix with a separately approved corrective migration or restore from backup after explicit approval.

No automatic restore is approved by this phase.

## Next Real Migration Gate

The next real migration phase should be:

```text
Phase ERP-Audit-1E: Audit log schema migration
```

1E should be allowed to modify Codex1 schema only after explicit approval. It should create the real table and indexes, insert zero rows, and verify the database before and after migration.

## Still Not Approved

ERP-Audit-1D does not approve:

- creating the real table.
- running a real schema migration.
- writing audit rows.
- creating runtime audit services.
- adding audit endpoints.
- adding audit UI readers.
- changing `SyncLog`.
- restoring a database.
- calling platform APIs.
- opening product or order formal batch sync.

## Recommended Following Stages

1. `Phase ERP-Audit-1E: Audit log schema migration`
   - create real table and indexes only after explicit approval.

2. `Phase ERP-Audit-1F: Audit log post-migration verification`
   - read back schema, defaults, indexes, and unchanged business counts.

3. `Phase ERP-Audit-1G: Audit writer service mock gate`
   - implement private writer helper in tests only.

4. `Phase ERP-Audit-1H: Audit writer local implementation`
   - add runtime writer but only for explicitly approved local events.

5. `Phase ERP-Audit-1I: Audit logs UI read-only plan`
   - plan how Logs / Audit should display real audit rows in business language.
