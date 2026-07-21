# Phase ERP-Backup-1I: Backup list/report readonly helper

## Scope

ERP-Backup-1I adds a readonly local backup report helper.

This phase lists backup manifests and safe metadata only. It does not restore a database, delete backup files, modify schema, write business rows, write audit rows, call platform APIs, or open formal product or order sync.

## Implementation

New helper:

```text
backend/scripts/list_local_backups.py
```

The helper:

- reads manifests only from the approved backup root by default;
- reports backup count and manifest count;
- validates required manifest fields;
- reports whether the backup file exists and remains inside the backup root;
- reports size match and abbreviated SHA-256 only;
- returns safe baseline counts, retention metadata, and safety booleans;
- blocks custom roots unless a test explicitly opts in.

## Real Local Report

The phase was run against the approved local backup root and returned:

```text
status=backup_report_ready
backup_count=1
manifest_count=1
all_manifests_valid=true
all_sensitive_scans_passed=true
backup_deleted=false
real_restore_executed=false
production_db_touched=false
raw_response_saved=false
secrets_saved=false
privacy_fields_redacted=true
```

The latest manifest corresponds to `ERP-Backup-1G` and records the safe counts from the real local backup checkpoint.

## Verification

`verify_all.py` now includes fixture coverage for:

- custom-root blocking by default;
- temporary-root report generation when explicitly allowed in tests;
- multiple manifest sorting and validation;
- abbreviated SHA output;
- sensitive scan checks;
- production database hash and size remaining unchanged.

## Still Not Approved

- Backup deletion.
- Retention cleanup automation.
- Real restore.
- Backup UI controls.
- Remote backup upload.
- Formal Naver product or order batch sync.

