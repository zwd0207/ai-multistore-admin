# Phase ERP-Backup-1F: Real local backup implementation approval plan

## Scope

This phase is an approval plan only. It defines the boundary for a later phase that may implement real local backup creation for `backend/codex1.db`.

It does not create a backup, does not write a production manifest, does not restore a database, does not delete backup files, does not modify `backend/codex1.db`, does not change schema, does not write business data, does not call platform APIs, does not modify runtime UI, and does not open formal sync.

## Current Baseline

- Backup and restore drill plan is documented.
- Backup metadata and retention policy is documented.
- Restore verification dry-run is covered in `verify_all.py` with temporary fixture files.
- Backup manifest mock implementation gate is covered in `verify_all.py` with temporary fixture files.
- Real production backup creation is still not implemented.
- Real production manifest writing is still not implemented.
- Real restore remains closed.

## Approved Future Target

A later implementation phase may add a local helper or script to create a real local backup of:

```text
backend/codex1.db
```

The initial target should be manual/on-demand backup creation only. Scheduled backups, cleanup, restore execution, and UI controls should remain separate phases.

## Approved Backup Directory

Initial approved backup root:

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\
```

The implementation must:

- create the directory if missing,
- verify the resolved backup path stays inside this root,
- reject path traversal,
- reject overwrite of an existing backup or manifest,
- use phase-stamped filenames,
- keep backup and manifest side by side.

## Required Implementation Behavior

The future real backup helper must:

1. Confirm source path resolves to the intended `backend/codex1.db`.
2. Confirm source database exists.
3. Record pre-backup source size and SHA-256 if safely available.
4. Use a consistent SQLite backup method, preferably SQLite online backup API.
5. Write the backup file to a new unique path.
6. Reopen the backup read-only.
7. Run `PRAGMA integrity_check`.
8. Compute backup SHA-256 and file size.
9. Collect safe numeric baseline counts.
10. Generate a manifest using the 1E-proven manifest writer pattern.
11. Reopen and validate the manifest.
12. Verify backup file and manifest are both inside the approved backup root.
13. Return only safe paths, SHA-256, counts, booleans, and status enums.

## Required Inputs

The future helper may accept:

- `phase`
- `operation_type`
- `created_by_actor_type`
- `created_by_actor_label`
- `retention_class`
- `retention_reason`
- optional `related_store_ids`
- optional `related_platforms`
- optional safe `related_hashes`
- optional `operation_audit_correlation_id`

It must not accept caller-provided `backup_sha256`, `backup_size_bytes`, `sqlite_integrity_check`, or `baseline_counts` as trusted values.

## Required Baseline Counts

The first real backup implementation must report:

- stores
- products
- orders
- sync_logs
- api_capability_test_results
- tested_success for store 8
- order_status_events
- operation_audit_logs

Counts must be numeric only and must not include row contents.

## Safety Boundary

The helper output, manifest, logs, and docs must not contain:

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

Allowed values include safe local paths, SHA-256 values, file sizes, git commit hashes, numeric counts, booleans, timestamps, retention classes, phase names, operation types, safe hashes, and safe audit correlation ids.

## Failure Handling

The future implementation must stop without creating a partially trusted backup if:

- source DB is missing,
- source path is not the intended database,
- backup path is outside approved root,
- target backup or manifest already exists,
- SQLite backup fails,
- backup file cannot be reopened,
- integrity check fails,
- manifest validation fails,
- sensitive scan fails,
- SHA-256 or file size cannot be computed.

If a partial backup or temp manifest is created during a failed attempt, the helper may remove only its own temporary file. It must not delete existing backups.

## Audit Relationship

The first real backup helper may return data suitable for a future audit chain, but it should not write `operation_audit_logs` unless a separate phase explicitly approves audit integration.

If an audit correlation id is provided, it may appear in the manifest as a safe string.

## Required Verification For The Later Implementation Phase

The implementation phase must prove:

- Real local backup file is created only in the approved backup directory.
- Production `backend/codex1.db` is not modified by the backup.
- Manifest is written next to the backup.
- Manifest SHA-256 and size match the backup.
- Backup integrity check is `ok`.
- Baseline counts are safe and numeric.
- Existing backup/manifest overwrite is blocked.
- Invalid approved-root path is blocked.
- Sensitive manifest input is blocked.
- No backup deletion occurs.
- No restore occurs.
- No platform API call occurs.
- `verify_all.py` still passes.

## Not Yet Approved

- Scheduled backups.
- Backup cleanup or deletion.
- Real restore.
- Backup UI controls.
- Remote backup upload.
- Cloud storage.
- Encryption-at-rest changes.
- Cross-machine backup migration.
- Automatic audit writing.

## Recommended Next Stage

`Phase ERP-Backup-1G: Real local backup helper implementation`

That phase may create one real local backup only after explicit approval and must stop immediately after verification and documentation.
