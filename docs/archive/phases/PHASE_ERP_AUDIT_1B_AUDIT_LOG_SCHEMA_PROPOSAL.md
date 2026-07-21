# Phase ERP-Audit-1B - Audit Log Schema Proposal

## Summary

Phase ERP-Audit-1B proposes the future `operation_audit_logs` schema.

This phase is proposal-only. It does not create a table, does not add a SQLAlchemy model, does not run a migration, does not write audit rows, does not modify runtime UI, and does not change backup or restore behavior.

## Proposed Table

Table name:

```text
operation_audit_logs
```

Purpose:

```text
Record safe accountability metadata for local ERP operations.
```

It must remain separate from `sync_logs`, because `sync_logs` describes sync jobs while `operation_audit_logs` describes local decisions, approvals, writes, backups, restores, and blocked operations.

## Proposed Columns

Identity and time:

- `id INTEGER PRIMARY KEY`.
- `created_at DATETIME NOT NULL`.
- `updated_at DATETIME NOT NULL`.

Scope:

- `store_id INTEGER NULL INDEX`.
- `platform VARCHAR(50) NULL INDEX`.
- `environment VARCHAR(30) NOT NULL DEFAULT 'local'`.

Actor:

- `actor_type VARCHAR(30) NOT NULL`.
- `actor_id VARCHAR(120) NULL`.
- `actor_label VARCHAR(160) NULL`.
- `actor_role VARCHAR(80) NULL`.

Operation:

- `action VARCHAR(120) NOT NULL INDEX`.
- `operation_phase VARCHAR(120) NULL`.
- `correlation_id VARCHAR(80) NOT NULL INDEX`.
- `request_id VARCHAR(120) NULL INDEX`.
- `status VARCHAR(30) NOT NULL INDEX`.
- `reason_code VARCHAR(120) NULL INDEX`.

Target:

- `target_type VARCHAR(80) NULL INDEX`.
- `target_id INTEGER NULL`.
- `target_hash VARCHAR(160) NULL INDEX`.
- `target_label VARCHAR(200) NULL`.

Safe summaries:

- `changed_field_names JSON NULL`.
- `before_summary JSON NULL`.
- `after_summary JSON NULL`.
- `counts_summary JSON NULL`.
- `safety_flags JSON NULL`.

Backup and restore:

- `backup_path VARCHAR(500) NULL`.
- `backup_sha256 VARCHAR(64) NULL`.
- `restore_source_path VARCHAR(500) NULL`.
- `restore_source_sha256 VARCHAR(64) NULL`.

Security booleans:

- `sensitive_scan_passed BOOLEAN NOT NULL DEFAULT false`.
- `raw_response_saved BOOLEAN NOT NULL DEFAULT false`.
- `secrets_saved BOOLEAN NOT NULL DEFAULT false`.
- `privacy_fields_redacted BOOLEAN NOT NULL DEFAULT true`.

Notes:

- `notes TEXT NULL`.

## Enum Direction

Recommended `actor_type` values:

- `human`.
- `system`.
- `automation`.
- `test`.

Recommended `status` values:

- `planned`.
- `success`.
- `failed`.
- `blocked`.
- `skipped`.
- `rolled_back`.

Recommended `target_type` values:

- `order`.
- `product`.
- `credential`.
- `store`.
- `backup`.
- `restore`.
- `schema`.
- `sync_gate`.
- `settings`.
- `audit_log`.

Recommended action examples:

- `order_refresh_batch_approval_planned`.
- `order_refresh_batch_write_blocked`.
- `order_refresh_batch_write_started`.
- `order_refresh_batch_write_succeeded`.
- `database_backup_created`.
- `database_restore_dry_run`.
- `database_restore_executed`.
- `credential_created`.
- `credential_updated`.
- `schema_migration_approved`.
- `schema_migration_executed`.

## Constraints

Recommended constraints:

- `correlation_id` must not be empty.
- `action` must not be empty.
- `status` must not be empty.
- `backup_sha256`, when present, must be 64 lowercase hex characters.
- `restore_source_sha256`, when present, must be 64 lowercase hex characters.
- `raw_response_saved` must default to false.
- `secrets_saved` must default to false.
- `privacy_fields_redacted` must default to true.

Do not add a uniqueness constraint for normal audit rows. Multiple rows in the same `correlation_id` are expected.

## Indexes

Recommended indexes:

- `ix_operation_audit_logs_created_at`.
- `ix_operation_audit_logs_store_created_at` on `store_id, created_at`.
- `ix_operation_audit_logs_platform_created_at` on `platform, created_at`.
- `ix_operation_audit_logs_actor_created_at` on `actor_type, actor_id, created_at`.
- `ix_operation_audit_logs_action_created_at` on `action, created_at`.
- `ix_operation_audit_logs_status_reason` on `status, reason_code`.
- `ix_operation_audit_logs_target` on `target_type, target_id`.
- `ix_operation_audit_logs_target_hash`.
- `ix_operation_audit_logs_correlation_id`.
- `ix_operation_audit_logs_request_id`.

## Sensitive Field Ban

The schema must not include columns for:

- token.
- Authorization.
- request headers.
- response headers.
- signature.
- bcrypt input.
- client secret.
- raw request body.
- raw response body.
- full channel number.
- full order id.
- full product-order id.
- buyer full name.
- receiver full name.
- full phone number.
- address.
- zip code.

JSON summary columns must also reject these values at write time.

## Safe JSON Summary Shape

`before_summary`, `after_summary`, and `counts_summary` may contain only:

- field names.
- counts.
- booleans.
- safe hashes.
- local numeric ids.
- safe status enums.
- Chinese labels.
- backup metadata.
- reason codes.

They must not contain raw platform payloads or privacy-bearing data.

## Backup And Restore Relationship

Backup rows should use:

- `target_type='backup'`.
- `action='database_backup_created'`.
- `backup_path`.
- `backup_sha256`.
- `status='success'` or `failed`.

Restore rows should use:

- `target_type='restore'`.
- `action='database_restore_dry_run'` or `database_restore_executed`.
- `restore_source_path`.
- `restore_source_sha256`.
- a shared `correlation_id` with approval and verification rows.

## Migration Boundary

The future migration phase must:

- back up `backend/codex1.db`.
- create the table and indexes.
- insert zero audit rows during schema creation.
- leave existing business table counts unchanged.
- verify required columns, defaults, and indexes.
- run sensitive-field schema scans.

## Future Verify Coverage

`verify_all.py` should later cover:

- temporary schema shape.
- required columns.
- required indexes.
- default booleans.
- SHA-256 validation.
- safe row insertion.
- blocked row insertion.
- correlation chain.
- sensitive JSON rejection.
- no raw response/token/header/signature/client secret leakage.

## Recommended Next Stage

Recommended next phase:

```text
Phase ERP-Audit-1C: Audit log mock schema gate
```

1C should create the proposed table only in the temporary verification database and validate the shape before a real migration is considered.
