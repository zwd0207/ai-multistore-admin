# Phase ERP-Backup-1H: Backup restore drill using 1G manifest

## Scope

ERP-Backup-1H adds a local restore dry-run helper for previously created backup manifests.

This phase verifies backup evidence by copying the backup into a temporary restore location and checking the copy. It does not restore over `backend/codex1.db`, does not delete backup files, does not modify schema, does not write business rows, does not call platform APIs, and does not open formal product or order sync.

## Implementation

New helper:

```text
backend/scripts/restore_backup_dry_run.py
```

The helper:

- accepts a manifest path inside the approved local backup root;
- validates required manifest fields and safe flags;
- blocks manifests or backup files outside the approved root;
- verifies backup size and SHA-256 before any restore drill;
- copies the backup only to a temporary dry-run file;
- runs `PRAGMA integrity_check` and compares baseline table counts;
- blocks the production database path as a restore target;
- deletes only the temporary restore copy after verification.

## Real Local Drill

The phase was run against the real `ERP-Backup-1G` manifest:

```text
status=restore_dry_run_verified
manifest_valid=true
backup_verified=true
temporary_restore_verified=true
temporary_restore_deleted=true
real_restore_executed=false
production_db_touched=false
production_db_unchanged=true
backup_deleted=false
sqlite_integrity_check=ok
```

Observed safe counts matched the manifest:

```text
stores=8
products=9
orders=9
sync_logs=47
api_capability_test_results=26
tested_success_store8=8
operation_audit_logs=0
order_status_events=0
```

## Verification

`verify_all.py` now includes fixture coverage for:

- successful temporary restore dry-run from a manifest;
- production database target blocking;
- outside-manifest blocking;
- sensitive manifest blocking;
- production database hash and size remaining unchanged.

## Still Not Approved

- Real restore.
- Backup deletion.
- Backup cleanup automation.
- Restore UI.
- Cloud or remote backup upload.
- Formal Naver product or order batch sync.

