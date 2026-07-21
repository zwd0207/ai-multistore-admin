# Phase Naver-ERP-18A: Controlled order refresh with backup evidence gate

## Scope

Naver-ERP-18A adds a mock-testable backup evidence gate in front of future controlled Naver order refresh writes.

This phase does not call Naver, does not write the real database, does not write `orders`, `products`, `SyncLog`, `ApiCapabilityTestResult`, or timeline events, does not modify schema, and does not open formal Naver order sync.

## Implementation

Updated helper module:

```text
backend/app/services/sync_service.py
```

New private helper:

```text
_evaluate_naver_order_refresh_batch_with_backup_evidence_gate(...)
```

The helper wraps the existing order refresh batch mock gate. When `write_enabled=true` and backup evidence is required, the write path is blocked unless backup evidence verifies:

- 64-character SHA-256;
- `sqlite_integrity_check=ok`;
- `backup_created=true`;
- `manifest_written=true`;
- `raw_response_saved=false`;
- `secrets_saved=false`;
- `privacy_fields_redacted=true`;
- no sensitive markers in serialized evidence.

Readonly preview paths do not require backup evidence because they do not write data.

## Verification

`verify_all.py` now covers:

- readonly path without backup evidence;
- write path blocked when backup evidence is missing;
- write path blocked when safety flags fail;
- write path blocked when serialized evidence contains sensitive markers;
- backup evidence verification before the existing manual approval gate;
- successful temporary-database update only after backup evidence and manual approval;
- no product writes, no SyncLog writes, no tested-success writes, no timeline event writes, and formal sync remaining closed.

## Still Not Approved

- Real batch order refresh write.
- Public endpoint wiring.
- Automatic backup creation from the refresh endpoint.
- Platform write operations.
- Formal Naver order sync.

