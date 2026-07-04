# Phase ERP-Audit-1Q - Audit Writer Integration Approval Plan

## Summary

Phase ERP-Audit-1Q defines the approval boundary for connecting the existing local audit writer to selected runtime operations in later phases.

This phase is planning-only. It does not modify runtime code, does not call Naver or Coupang, does not write `operation_audit_logs`, does not write business tables, does not change schema, does not execute backup or restore, and does not open formal product or order sync.

## Current Baseline

The audit foundation is now in place:

- `operation_audit_logs` table exists in the real local database.
- The table currently has zero rows.
- `write_operation_audit_log_local(...)` exists as a controlled backend helper.
- The helper is not wired into public routes or business flows.
- Read-only audit routes exist:
  - `GET /api/v1/operation-audit-logs`
  - `GET /api/v1/operation-audit-logs/summary`
- Codex2 Logs/Audit UI reads only those GET routes.
- The local 8012 backend runtime has been refreshed and the read-only audit UI sanity check passed.

## Approved Direction For The Next Implementation Chain

The next implementation must start with a mock gate:

```text
Phase ERP-Audit-1R: Audit writer integration mock gate
```

1R may add temporary verification-only tests that simulate how selected operations would produce audit rows. It must write only to the temporary `verify_all.py` database and must not write real `backend/codex1.db`.

Only after 1R passes may a later local implementation phase be considered.

## First Integration Targets

The first real runtime audit integration should be narrow and local-only. Preferred target order:

1. Controlled Naver order local writes and refreshes.
2. Database backup creation and backup manifest verification.
3. Restore dry-run evidence.
4. Schema migration approval and post-migration verification.

These are preferred because they already have explicit approval gates, database safety checks, and readback verification.

Not approved yet:

- automatic audit writing from every page load.
- automatic audit writing from read-only GET calls.
- audit writing for platform API probes.
- audit writing for broad product or order batch sync.
- audit writing from frontend buttons directly.

## Required Audit Chain

Future audited local write operations should produce a correlation chain, not a single vague row.

Minimum chain for a future local write:

```text
approval_planned
pre_write_backup_verified
local_write_attempted
local_write_succeeded | local_write_blocked | local_write_failed
post_write_verification_succeeded | post_write_verification_failed
```

Minimum chain for a future backup operation:

```text
backup_planned
backup_created
backup_hash_verified
backup_integrity_verified
```

Minimum chain for a future restore dry-run:

```text
restore_dry_run_planned
restore_source_verified
restore_temp_copy_verified
restore_integrity_verified
```

All rows in one operation chain must share a safe `correlation_id`.

## Required Fields For Future Audit Rows

Future integration rows must include only safe accountability metadata:

- `store_id`, when the operation is store-bound.
- `platform`, when relevant.
- `actor_type`.
- `actor_label`.
- `action`.
- `operation_phase`.
- `correlation_id`.
- `status`.
- `reason_code`, when blocked or failed.
- safe `target_type`.
- local numeric `target_id`, when safe.
- safe `target_hash`, when referencing platform-origin objects.
- changed field names, not raw values.
- safe count summaries.
- backup path and SHA-256 metadata, when applicable.
- restore source path and SHA-256 metadata, when applicable.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.
- `sensitive_scan_passed=true` for successful rows.

## Sensitive Data Ban

Future audit rows, route responses, logs, tests, and docs must not contain:

- token.
- access token or refresh token.
- Authorization.
- request headers.
- response headers.
- signature.
- bcrypt inputs.
- client secret.
- raw request body.
- raw response body.
- full channel number.
- full order id.
- full product-order id.
- full product id when sensitive.
- buyer or receiver full name.
- full phone number.
- address.
- zip code.
- raw platform payloads.

Blocked-operation evidence must record only the safe reason and safe field labels. It must not persist the blocked payload.

## Approval Requirements For Any Future Real Audit Write

A later real audit writer integration phase must require:

- explicit user approval for that phase.
- clean Codex1 and Codex2 worktrees before the write phase starts.
- database backup before any business write that will be audited.
- a fresh pre-write count snapshot.
- a post-write count snapshot.
- proof that the audit rows match the same operation correlation id.
- proof that no products, orders, SyncLog, tested_success, or timeline rows were written unless that exact operation phase explicitly allowed them.
- proof that formal product/order sync remains closed.
- sensitive-field scan of serialized audit rows and API responses.
- `verify_all.py` coverage before any real runtime wiring is accepted.

## Route And UI Boundary

Still closed:

- `POST /api/v1/operation-audit-logs`.
- `PUT /api/v1/operation-audit-logs`.
- `PATCH /api/v1/operation-audit-logs`.
- `DELETE /api/v1/operation-audit-logs`.
- audit export route.
- full raw audit detail route.
- frontend audit write button.
- automatic audit writer activation from Codex2.

Codex2 Logs/Audit may continue to read audit rows through the existing GET routes only.

## Verification Required In 1R

1R must prove with mock/private tests:

- approval chain rows can be planned safely.
- backup evidence rows can be planned safely.
- blocked-operation rows do not store blocked payloads.
- successful-operation rows require safe flags.
- one correlation id may have multiple ordered rows.
- duplicate or missing correlation ids are rejected where unsafe.
- unsupported operation types are blocked.
- sensitive JSON keys and values are rejected.
- read-only calls do not create audit rows.
- real `backend/codex1.db` remains unchanged.
- no platform API is called.

## Current Counts Must Remain Unchanged

This 1Q planning phase must leave the real database unchanged:

```text
operation_audit_logs=0
products=9
orders=9
sync_logs=47
tested_success_store8=8
order_status_events=0
```

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1R: Audit writer integration mock gate
```

1R should add temporary verification coverage for the selected audit writer integration patterns while keeping the real database and runtime behavior unchanged.
