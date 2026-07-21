# Phase ERP-Backup-1D: Real backup manifest implementation plan

## Scope

This phase is an implementation plan only. It defines how a later phase should create safe manifest files for real `backend/codex1.db` backups.

It does not create a backup, does not write a manifest file, does not restore a database, does not delete backup files, does not modify `backend/codex1.db`, does not change schema, does not write business data, does not call platform APIs, does not modify Codex2 runtime UI, and does not open formal sync.

## Goal

The first real backup manifest implementation should make every local database backup understandable, verifiable, and safe to reference from operation audit logs.

It should answer:

- Which database was backed up.
- Which phase or operation required the backup.
- Which exact backup file belongs to the manifest.
- Whether the backup file hash and size were verified.
- Whether SQLite integrity passed.
- Which safe baseline counts existed at backup time.
- Whether the backup is protected from cleanup.
- Whether it is linked to an operation audit correlation id.

## Future Manifest Writer

A later implementation phase may add a backend helper or script such as:

```text
create_backup_manifest(...)
```

It should accept safe inputs only:

- `phase`
- `operation_type`
- `source_db_path`
- `backup_path`
- `created_by_actor_type`
- `created_by_actor_label`
- `retention_class`
- `retention_reason`
- optional `related_store_ids`
- optional `related_platforms`
- optional safe `related_hashes`
- optional `operation_audit_correlation_id`

The helper should compute, not trust caller-provided values for:

- `backup_sha256`
- `backup_size_bytes`
- `sqlite_integrity_check`
- `sqlite_page_count`
- `sqlite_page_size`
- `baseline_counts`
- git commit hashes when available
- `created_at`
- sensitive scan outcome

## Required Manifest Fields

Initial required manifest fields should match the 1B/1C contract:

- `manifest_version`
- `backup_id`
- `phase`
- `operation_type`
- `created_at`
- `created_by_actor_type`
- `created_by_actor_label`
- `source_db_path`
- `backup_path`
- `backup_sha256`
- `backup_size_bytes`
- `backup_method`
- `sqlite_page_count`
- `sqlite_page_size`
- `sqlite_integrity_check`
- `git_commit_codex1`
- `git_commit_codex2`
- `baseline_counts`
- `related_store_ids`
- `related_platforms`
- `related_safe_hashes`
- `retention_class`
- `retention_reason`
- `retention_until`
- `legal_hold`
- `protected_from_auto_delete`
- `restore_drill_status`
- `last_restore_drill_at`
- `sensitive_scan_passed`
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `operation_audit_correlation_id`
- `notes`

## Manifest File Rules

The implementation should:

- Store manifest next to the backup file.
- Use UTF-8 JSON.
- Use a stable sorted-key format where practical.
- Write to a temporary `.tmp` path first.
- Flush and close the temp file.
- Re-open and parse the temp JSON.
- Rename atomically to `.manifest.json` only after validation.
- Never overwrite an existing manifest unless an explicit replacement phase is approved.
- Include a manifest schema version.

## Path Safety

The implementation must verify:

- `source_db_path` resolves to the intended `backend/codex1.db`.
- `backup_path` is inside the approved local backup directory.
- Manifest path is derived from `backup_path`.
- No path traversal is possible.
- Real restore target paths are not accepted by this manifest writer.
- Windows Unicode paths are handled as UTF-8 text in JSON.

## Baseline Counts

Initial safe baseline counts should include:

- stores
- products
- orders
- sync_logs
- api_capability_test_results
- tested_success for store 8
- order_status_events
- operation_audit_logs

Counts must be numeric only and must not include row contents or raw payloads.

## Sensitive Boundary

The manifest and any console output must not contain:

- token, refresh token, access token, or Authorization value
- request or response headers
- signature, bcrypt input, or client secret
- raw request or raw response body
- full channel number
- full order id or product-order id
- buyer or receiver full name
- buyer or receiver phone
- address, detailed address, zip code, or delivery memo
- raw platform payload snapshots

Allowed identifiers are safe hashes, backup ids, phase names, operation types, counts, booleans, timestamps, local paths, SHA-256 values, git commits, and safe status enums.

## Retention Defaults

The first manifest writer should only classify retention. It must not delete files.

Recommended defaults:

- `pre_write`: 90 days
- `pre_migration`: 180 days
- `pre_restore`: 180 days
- `manual_checkpoint`: 90 days
- `release_checkpoint`: 180 days
- `incident_response`: no automatic expiry

`protected_from_auto_delete` should default to true for pre-write, pre-migration, pre-restore, incident, and audit-linked backups.

## Operation Audit Relationship

If a backup is created for a future audited operation, the manifest may include a safe `operation_audit_correlation_id`.

The manifest writer itself should not write `operation_audit_logs` in the first implementation. Audit writer integration should remain a separate explicit phase unless the caller already owns an approved audit correlation chain.

## Future Verification Required

The implementation phase must prove:

- A temporary fixture backup can produce a valid manifest.
- A real backup path can be described without exposing secrets.
- SHA-256 and size match the backup file.
- SQLite integrity check passes.
- Baseline counts are numeric and safe.
- Invalid retention class blocks.
- Backup outside the approved directory blocks.
- Manifest with sensitive fields blocks.
- Existing manifest overwrite blocks.
- No real database data changes.
- No backup deletion occurs.

## Recommended Next Stage

`Phase ERP-Backup-1E: Backup manifest mock implementation gate`

That phase may add a helper and `verify_all.py` coverage using temporary files only. Real production backup creation should still remain separate until the manifest helper is proven.
