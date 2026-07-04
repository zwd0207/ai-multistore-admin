# Phase ERP-Backup-1G: Real local backup helper implementation

## Scope

ERP-Backup-1G implements the first real local backup helper for `backend/codex1.db`.

This phase may create one local SQLite backup and one side-by-side manifest under the approved local backup directory:

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\
```

It does not restore a database, delete backup files, modify schema, write business rows, write `operation_audit_logs`, call platform APIs, modify Codex2 runtime UI, or open formal product/order sync.

## Implementation

New helper:

```text
backend/scripts/create_local_backup.py
```

The helper:

- only backs up the approved default source `backend/codex1.db` unless a test explicitly opts into a fixture source;
- only writes to the approved backup root unless a test explicitly opts into a fixture root;
- uses SQLite online backup API from a read-only source connection;
- writes a temporary backup first, validates it, then atomically moves it into the final backup path;
- writes a temporary UTF-8 JSON manifest first, validates it, then atomically moves it next to the backup;
- blocks invalid retention classes, sensitive inputs, missing sources, unsupported paths, and existing target backup/manifest files;
- returns only safe status enums, paths, SHA-256, sizes, counts, booleans, and retention metadata.

## Manifest

The manifest records safe backup evidence:

- manifest version, backup id, phase, operation type, actor type/label;
- source and backup paths;
- source pre-backup SHA-256 and size;
- backup SHA-256 and size;
- SQLite backup method, page metadata, and `PRAGMA integrity_check`;
- Codex1 and Codex2 git commits;
- numeric baseline counts for stores, products, orders, sync logs, API capability results, order status events, operation audit logs, and `tested_success_store8`;
- retention class, reason, retention-until, legal hold, protected-from-auto-delete, restore drill status;
- safety booleans: `raw_response_saved=false`, `secrets_saved=false`, `privacy_fields_redacted=true`, `sensitive_scan_passed=true`.

It must not store tokens, Authorization values, request/response headers, signatures, bcrypt inputs, client secrets, raw responses, full channel ids, full order/product-order ids, buyer/receiver full names, phones, addresses, or zip codes.

## Verification

`verify_all.py` now includes a private fixture test for the real helper path. It proves:

- fixture backup and manifest are created in a temporary approved root;
- production `backend/codex1.db` hash and size remain unchanged;
- backup integrity is `ok`;
- manifest fields are complete and match backup SHA-256/size;
- invalid retention is blocked;
- sensitive input is blocked;
- missing source is blocked;
- non-approved source/root are blocked by default;
- duplicate backup/manifest filenames are blocked;
- no restore, delete, platform API call, schema change, business write, or audit write occurs.

## Real Backup Result

The phase executes one real local backup after helper and mock verification pass.

Expected real-backup result shape:

```text
status=backup_created
backup_created=true
manifest_written=true
real_restore_executed=false
backup_deleted=false
raw_response_saved=false
secrets_saved=false
privacy_fields_redacted=true
sqlite_integrity_check=ok
```

The backup and manifest are intentionally ignored by git and remain local runtime evidence.

## Still Not Approved

- Real restore.
- Backup deletion or cleanup automation.
- Scheduled backups.
- Backup UI controls.
- Remote/cloud backup upload.
- Backup encryption-at-rest changes.
- Automatic audit writing for backup creation.
- Formal Naver product/order batch sync.
