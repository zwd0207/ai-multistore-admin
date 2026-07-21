# Phase ERP-Audit-1S: Audit writer local runtime integration approval plan

## Scope

This phase is an approval plan only. It defines the boundary for a future local runtime audit-writer integration, but does not connect the writer to any runtime route, service, button, middleware, sync flow, backup flow, restore flow, or migration flow.

It does not write `operation_audit_logs`, does not modify `backend/codex1.db`, does not change schema, does not call Naver or Coupang APIs, does not execute backup/restore, and does not open formal product or order sync.

## Current Baseline

- `operation_audit_logs` schema exists in the real local database.
- Real `operation_audit_logs` count remains zero.
- Read-only audit list and summary API are implemented.
- Codex2 Logs/Audit read-only UI integration is implemented.
- A local audit writer helper exists behind explicit internal gates.
- Phase 1R proved safe multi-row audit correlation chains only in the temporary `verify_all.py` database.
- Runtime business-flow writer wiring remains closed.

## Approved Future Direction

The first future runtime integration should remain narrow and local:

1. Controlled Naver selected-order local write evidence.
2. Controlled Naver selected-order local refresh evidence.
3. Pre-write database backup evidence when a local business write is involved.
4. Post-write verification evidence after the local operation completes.

Backup-only, restore dry-run, and schema migration audit wiring should remain separate follow-up phases unless they are directly attached to an explicitly approved write or migration task.

## Not Approved In This Phase

- No automatic audit middleware.
- No blanket audit logging for all requests.
- No audit writer call from every endpoint.
- No public audit write endpoint.
- No audit delete/export/raw detail endpoint.
- No platform API auditing of request or response bodies.
- No storage of raw request or response data.
- No formal Naver product/order batch sync.
- No shipment, cancel, return, exchange, refund, sales, settlement, customer-service, mail, appeal, or AI automation write flow.

## Required Runtime Gate For A Later Phase

A future runtime integration phase must require all of the following before a real audit row can be written:

- Clean Codex1 and Codex2 worktrees before execution.
- Explicit user approval naming the target phase and operation.
- A successful database backup when the operation writes local business data or changes schema.
- A single generated `correlation_id` shared by approval, backup, attempted write, write result, and post-write verification rows.
- Unique `request_id` values per audit row.
- Store-scoped operation, initially `store_id=8` only.
- Operation type allowlist, initially only controlled Naver selected-order local write/refresh.
- Safe row whitelist matching the existing `operation_audit_logs` schema.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.
- Sensitive scan passed for every row.
- Blocked operations must record `blocked_payload_written=false`.
- Post-write readback must prove business row counts and target row state.
- Audit write failure must not roll forward a business write without reporting the failure.

## Safe Audit Row Chain

The first real integration should produce a small correlation chain:

1. `approval_planned`
2. `pre_write_backup_verified`
3. `local_write_attempted`
4. One terminal result:
   - `local_write_succeeded`
   - `local_write_blocked`
   - `local_write_failed`
5. One verification result:
   - `post_write_verification_succeeded`
   - `post_write_verification_failed`

The chain should be append-only. It should not overwrite or delete previous audit rows.

## Allowed Metadata

Future runtime audit rows may include:

- Store id and platform.
- Actor type, safe actor label, and role.
- Operation phase and action.
- Correlation id and request id.
- Status and safe reason code.
- Target type and safe target hash.
- Safe changed field names.
- Safe count summaries.
- Backup path and SHA-256 evidence.
- Restore-source SHA-256 if relevant.
- Safety booleans and a short business note.

## Forbidden Metadata

Future runtime audit rows must not contain:

- Token, refresh token, access token, or Authorization value.
- Request or response headers.
- Signature, bcrypt input, or client secret.
- Raw request or raw response body.
- Full channel number.
- Full order id or product-order id.
- Full product id when it is a sensitive platform identifier.
- Buyer or receiver full name.
- Buyer or receiver phone.
- Full address, detailed address, zip code, or delivery memo.
- Raw platform payload snapshots.

## Failure Handling

- If pre-write backup is missing or fails, business write and audit runtime integration must stop.
- If sensitive scan fails, no audit row containing the payload may be written.
- If the business operation is blocked, write only safe blocked evidence with `blocked_payload_written=false`.
- If the audit writer fails after a local business write, post-write verification must report the audit failure as a production-readiness blocker before any wider rollout.
- No failed audit integration may trigger a platform write.

## Verification Required For The Next Phase

The next phase should still be mock-only and should not write the real database. It should prove the exact call site shape for one selected local operation using fake services and a temporary database:

- Selected-operation approval present.
- Backup evidence present.
- One local write attempt represented.
- One terminal result represented.
- Post-write verification represented.
- Business row counts unchanged in the mock.
- No public audit write route added.
- Sensitive field scan covers serialized audit rows and blocked payloads.

## Recommended Next Stage

`Phase ERP-Audit-1T: Selected operation audit runtime wiring mock plan`

The next phase should design and mock the first specific call site, likely the selected Naver order local write/refresh flow, without enabling runtime production audit writes yet.
