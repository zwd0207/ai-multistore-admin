# Phase ERP-Backup-1E: Backup manifest mock implementation gate

## Scope

This phase adds a mock implementation gate for the future backup manifest writer.

It uses only temporary SQLite fixture files and temporary manifest files created by `verify_all.py`. It does not create a production backup, does not write a production manifest, does not restore the real database, does not delete backups, does not modify `backend/codex1.db`, does not change schema, does not write business data, does not call platform APIs, does not modify runtime UI, and does not open formal sync.

## Implemented

`verify_all.py` now includes a temporary manifest writer gate that:

- accepts safe manifest inputs,
- rejects missing required inputs,
- rejects invalid retention classes,
- rejects sensitive input fields or markers,
- rejects the production database path as a mock source,
- rejects backup files outside the approved temporary backup root,
- computes backup SHA-256 from the file,
- computes backup file size from the file,
- reads SQLite page count and page size,
- runs `PRAGMA integrity_check`,
- collects safe numeric baseline counts,
- writes a UTF-8 JSON `.tmp` manifest first,
- reopens and parses the temp JSON,
- atomically renames to `.manifest.json`,
- blocks overwriting an existing manifest,
- verifies the generated manifest through the existing restore dry-run manifest validator.

## Verified

The mock gate verifies:

- valid temporary fixture manifest creation,
- SHA-256 and file size match the temporary backup file,
- SQLite integrity returns `ok`,
- baseline counts are numeric and safe,
- `raw_response_saved=false`,
- `secrets_saved=false`,
- `privacy_fields_redacted=true`,
- `sensitive_scan_passed=true`,
- `pre_write` backup defaults to protected,
- `manual_checkpoint` without audit correlation is not auto-protected,
- manifest overwrite is blocked,
- unsafe retention class is blocked,
- sensitive notes/fields are blocked,
- production source path is blocked in the mock gate,
- backup outside the approved temporary root is blocked,
- the real `backend/codex1.db` file hash and size remain unchanged.

## Closed Boundaries

- No production backup creation.
- No production manifest file.
- No production restore.
- No backup deletion.
- No scheduled backup.
- No cleanup implementation.
- No audit row.
- No public API.
- No frontend runtime behavior.
- No platform API call.
- No formal sync approval.

## Sensitive Boundary

Manifest files and gate results must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw request/response bodies, full channel/order/product-order identifiers, buyer/receiver privacy, phones, addresses, zip codes, or raw platform payload snapshots.

Allowed manifest data includes safe paths, SHA-256 values, file sizes, git hashes, counts, booleans, timestamps, retention classes, phase names, operation types, safe hashes, and safe audit correlation ids.

## Next Step

The next backup phase should decide whether to implement a real local backup + manifest helper behind explicit approval, or first add a report-only backup inventory view.
