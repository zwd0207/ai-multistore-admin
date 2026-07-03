# Phase ERP-Backup-1C - Restore Verification Dry-Run

## Summary

Phase ERP-Backup-1C adds a temporary restore verification dry-run for the future backup system.

This phase does not restore the real database, does not replace `backend/codex1.db`, does not create production backup files, does not delete backup files, does not change schema, does not write business data, does not call platform APIs, and does not modify runtime UI.

## Scope

The dry-run is implemented in Codex1 `backend/scripts/verify_all.py`.

It uses only temporary files:

- a temporary SQLite source fixture.
- a temporary backup copy.
- a temporary manifest.
- a temporary restore target.

The real `backend/codex1.db` is checked before and after the dry-run to confirm it is unchanged.

## Verified Behavior

- Manifest required fields are present.
- `retention_class` must be one of the approved classes.
- `backup_sha256` must be a valid SHA-256 and match the backup file.
- `backup_size_bytes` must match the backup file.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.
- `sensitive_scan_passed=true`.
- Sensitive manifest keys and marker values are rejected.
- The restore target cannot be the production database path.
- The restore copy SHA-256 must match the manifest.
- `PRAGMA integrity_check` must return `ok`.
- Expected tables must exist in the temporary restored database.
- Restored row counts must match `baseline_counts`.
- The dry-run result must report `real_restore_executed=false`.

## Blocked Cases

The dry-run blocks:

- production database as restore target.
- tampered backup hash.
- invalid retention class.
- sensitive manifest content.
- unsafe saved flags.
- missing backup file.
- backup size mismatch.
- restore integrity failure.
- missing expected tables.
- count mismatch.

## Sensitive Boundary

Manifests and dry-run results must not contain:

- tokens.
- Authorization values.
- request or response headers.
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

## Result

ERP-Backup-1C proves that future restore verification can validate backup metadata and perform a temporary restore check without touching the production database.

Real backup creation, real restore approval, automatic cleanup, and runtime UI remain deferred to separate phases.
