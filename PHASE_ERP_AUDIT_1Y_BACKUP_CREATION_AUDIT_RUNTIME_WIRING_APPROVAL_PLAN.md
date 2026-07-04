# Phase ERP-Audit-1Y: Backup creation audit runtime wiring approval plan

## Scope

ERP-Audit-1Y plans the future runtime wiring between the real local backup helper and append-only audit rows.

This phase is planning-only. It does not modify runtime writer calls, does not create backups, does not write audit rows, does not restore databases, does not delete backups, does not write business data, does not call platform APIs, does not change schema, and does not open formal sync.

## Future Approved Direction

A later implementation may connect successful manual local backup creation to the existing audit writer, using this chain:

```text
backup_planned
backup_created
backup_hash_verified
backup_integrity_verified
backup_manifest_verified
```

The runtime wiring must require:

- explicit user approval;
- clean worktrees;
- successful backup helper result;
- safe backup path inside the approved backup root;
- valid SHA-256;
- `sqlite_integrity_check=ok`;
- `manifest_written=true`;
- `raw_response_saved=false`;
- `secrets_saved=false`;
- `privacy_fields_redacted=true`;
- append-only audit rows;
- post-write audit readback;
- sensitive-field scan.

## Still Blocked

- Audit writing for failed or partial backup attempts without a separate blocked-evidence design.
- Automatic scheduled backup audit writes.
- Restore audit runtime wiring.
- Backup deletion audit runtime wiring.
- Public audit write routes.

