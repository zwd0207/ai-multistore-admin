# Phase ERP-Backup-1K: Backup report readonly API mock gate

## Scope

ERP-Backup-1K adds a private mock gate for the future backup report readonly API.

It uses temporary fixture backups and manifests only. It does not read or write business data, does not restore a database, does not delete backups, does not write audit rows, does not call platform APIs, does not change schema, and does not open formal sync.

## Implementation

New service module:

```text
backend/app/services/backup_service.py
```

Private mock helper:

```text
list_backup_report_readonly_mock_gate(...)
```

The helper requires `verification_scope=verify_all_temp_db` when reading from a custom temporary root. It blocks missing scope, invalid limits, unsafe fields, and sensitive markers.

## Verification

`verify_all.py` covers:

- missing mock scope blocked;
- invalid limit blocked;
- safe temporary manifest report succeeds;
- report contains business message, counts, safe booleans, and abbreviated SHA-256;
- no restore;
- no backup deletion;
- no production database touch;
- no row writes;
- no sensitive markers;
- production `backend/codex1.db` hash and size unchanged.

## Still Not Approved

- Public restore/delete/cleanup endpoints.
- Frontend backup UI.
- Runtime audit writing for backup report reads.
- Formal Naver product/order sync.

