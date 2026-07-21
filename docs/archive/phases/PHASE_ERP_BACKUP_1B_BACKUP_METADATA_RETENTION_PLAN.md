# Phase ERP-Backup-1B - Backup Metadata and Retention Plan

## Summary

Phase ERP-Backup-1B defines the metadata and retention policy for future local database backups.

This phase is planning-only. It does not create backup files, delete backup files, restore a database, modify `backend/codex1.db`, change schema, write business data, call platform APIs, modify runtime UI, or change backup/restore behavior.

## Goals

The backup system must make every backup understandable and governable:

- What database was backed up.
- Which phase required the backup.
- Who or what initiated it.
- Which git commits and table counts were present.
- Whether the file hash and integrity checks passed.
- Whether the backup is eligible for retention or cleanup.
- Whether it is protected from deletion because it supports a write, migration, restore, or audit chain.

## Metadata Model

Each backup should have one manifest file next to the backup file.

Recommended manifest fields:

- `manifest_version`.
- `backup_id`.
- `phase`.
- `operation_type`.
- `created_at`.
- `created_by_actor_type`.
- `created_by_actor_label`.
- `source_db_path`.
- `source_db_sha256_before_backup`, if safely available.
- `backup_path`.
- `backup_sha256`.
- `backup_size_bytes`.
- `backup_method`.
- `sqlite_page_count`.
- `sqlite_page_size`.
- `sqlite_integrity_check`.
- `git_commit_codex1`.
- `git_commit_codex2`.
- `baseline_counts`.
- `related_store_ids`.
- `related_platforms`.
- `related_safe_hashes`.
- `retention_class`.
- `retention_reason`.
- `retention_until`.
- `legal_hold`.
- `protected_from_auto_delete`.
- `restore_drill_status`.
- `last_restore_drill_at`.
- `sensitive_scan_passed`.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.
- `operation_audit_correlation_id`, once the audit log exists.
- `notes`.

The manifest should be JSON and UTF-8 encoded.

## Retention Classes

Recommended retention classes:

- `pre_write`: backup made before a controlled local data write.
- `pre_migration`: backup made before a schema migration.
- `pre_restore`: backup made before replacing or restoring the live database.
- `scheduled_daily`: routine daily backup.
- `scheduled_weekly`: routine weekly backup.
- `manual_checkpoint`: manually requested checkpoint.
- `release_checkpoint`: backup made before a release or deployment milestone.
- `incident_response`: backup made during investigation or recovery.

## Retention Policy

Initial retention policy:

- `pre_write`: keep at least 90 days.
- `pre_migration`: keep at least 180 days.
- `pre_restore`: keep at least 180 days.
- `manual_checkpoint`: keep at least 90 days.
- `release_checkpoint`: keep at least 180 days.
- `incident_response`: keep until manually cleared.
- `scheduled_daily`: keep 14 daily copies after scheduled backups exist.
- `scheduled_weekly`: keep 8 weekly copies after scheduled backups exist.

No backup should be auto-deleted in the first implementation. Cleanup should start as a report-only phase that lists deletion candidates but deletes nothing.

## Protected Backups

A backup must be protected from auto-delete when:

- It is the latest known good backup.
- It was created before a schema migration.
- It was created before a local write that changed `orders`, products, timeline events, credentials, settings, or audit data.
- It was used as a restore source.
- It is linked to an unresolved incident.
- It has `legal_hold=true`.
- It has no successful restore drill yet and no newer verified replacement.
- It is referenced by `operation_audit_logs` once the audit log exists.

## Cleanup Gate

Future cleanup must be a separate explicit phase.

Cleanup must:

1. Run in report-only mode first.
2. Verify every deletion candidate has a manifest.
3. Verify the candidate is outside the protected set.
4. Verify the candidate has a valid SHA-256 and readable manifest.
5. Verify at least one newer known-good backup exists.
6. Verify the candidate is older than its retention window.
7. Require manual approval before deletion.
8. Log safe deletion evidence in the future operation audit log.

The first cleanup implementation must not delete files automatically.

## Sensitive Boundary

Backup files may contain the actual SQLite database and therefore must stay local and protected.

Manifest files, logs, and UI summaries must not contain:

- tokens.
- Authorization values.
- request headers.
- response headers.
- signatures.
- bcrypt inputs.
- client secrets.
- raw platform responses.
- full channel numbers.
- full order ids.
- full product-order ids.
- buyer or receiver full names.
- phone numbers.
- addresses.
- zip codes.

Manifests may contain safe hashes, counts, booleans, paths, file sizes, SHA-256 values, phase names, and safe status enums.

## Restore Relationship

Restore tooling must use manifest metadata to confirm:

- The backup file hash matches `backup_sha256`.
- The backup belongs to the expected project.
- The backup was created from `backend/codex1.db`.
- The backup has a successful integrity check.
- The backup is not marked superseded by an incident rollback.
- The restore operation has explicit approval.

Real restore remains a separate approved phase.

## Future Audit Relationship

Once `operation_audit_logs` exists, backup creation and retention decisions should write safe audit rows with:

- `action=database_backup_created`.
- `action=backup_retention_reviewed`.
- `action=backup_cleanup_candidate_reported`.
- `action=backup_cleanup_executed`, only after a future approved cleanup phase.
- `target_type=backup`.
- `target_hash` or safe `backup_id`.
- `backup_path`.
- `backup_sha256`.
- `correlation_id`.
- `status`.
- `reason_code`.

Audit rows must not store raw database contents or sensitive business payloads.

## Recommended Next Phase

Recommended next phase:

```text
Phase ERP-Backup-1C: Backup manifest mock validation gate
```

1C should validate a safe manifest fixture in a temporary test location, check required fields, retention class rules, protected-from-delete rules, SHA-256 format, sensitive-field rejection, and report-only cleanup classification without touching real backups or `backend/codex1.db`.
