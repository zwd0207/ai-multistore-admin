# Phase ERP-Audit-1W: Backup creation audit integration approval plan

## Scope

ERP-Audit-1W is planning-only. It defines how future real backup creation should be represented in the operation audit log.

This phase does not write audit rows, does not create backups, does not restore databases, does not modify schema, does not write business data, does not call platform APIs, and does not open formal sync.

## Planned Audit Chain

A later real integration may write an append-only audit chain only after separate approval:

```text
backup_planned
backup_created
backup_hash_verified
backup_integrity_verified
backup_manifest_verified
```

Each row should use safe evidence only:

- operation phase;
- operation type `database_backup`;
- actor type and safe actor label;
- backup path inside the approved backup root;
- SHA-256 and integrity status;
- counts summary;
- retention metadata;
- safe booleans such as `raw_response_saved=false`, `secrets_saved=false`, and `privacy_fields_redacted=true`.

## Safety Boundary

Future audit rows must not store tokens, Authorization values, request or response headers, signatures, bcrypt inputs, client secrets, raw external responses, complete channel ids, complete order/product-order ids, complete buyer/receiver names, phones, addresses, or zip codes.

## Approval Gate For Future Real Wiring

A later implementation must require:

- clean worktrees;
- explicit user approval;
- a completed backup with verified manifest;
- `PRAGMA integrity_check=ok`;
- append-only audit writes;
- readback verification;
- no business-table writes;
- no platform API calls;
- no formal sync opening.

