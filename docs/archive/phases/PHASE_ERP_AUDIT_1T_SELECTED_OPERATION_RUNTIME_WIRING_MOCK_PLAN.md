# Phase ERP-Audit-1T: Selected operation audit runtime wiring mock plan

## Scope

This phase is a mock-wiring plan only. It describes the first selected runtime operation shape that may later be tested with fake services and a temporary database.

It does not add code, does not connect an audit writer to runtime routes, does not write `operation_audit_logs`, does not write orders/products/SyncLog, does not modify schema, does not call Naver or Coupang APIs, does not execute backup/restore, and does not open formal sync.

## Selected Operation

The first selected operation for mock wiring should be:

`controlled_naver_order_local_refresh`

This means a future mock phase should model the audit wrapper around a selected local Naver order refresh/write path that is already constrained by earlier order gates. It must not represent formal batch sync.

## Why This Operation First

- Naver orders are already the most mature ERP write path.
- The project has completed selected-order preview, selected-order local writes, refresh gate planning, refresh mock gates, readonly candidate checks, small-batch write gates, and post-write verification phases.
- A selected local order write/refresh is small enough to audit with a five-row chain.
- It exercises the important production pattern: approval -> backup -> local write attempt -> result -> post-write verification.
- It does not require platform write APIs, shipment actions, claim actions, settlement APIs, mail, appeals, or AI automation.

## Mock Wiring Shape

A later 1U mock gate should introduce a private helper or test-local adapter that accepts:

- `operation_type="controlled_naver_order_local_refresh"`
- `store_id=8`
- `platform="naver"`
- `target_order_hash`
- `manual_approval=true`
- `backup_verified=true`
- `post_write_verification_required=true`
- `audit_write_enabled=true`
- private verification scope only
- fake selected-order write result
- fake post-write readback result

The mock must use fake services or temporary database fixtures only. It must not call the real Naver preview endpoint and must not write the real `backend/codex1.db`.

## Required Mock Audit Chain

The mock wiring should create the same safe correlation chain proven in 1R:

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

All rows must share one generated `correlation_id` and must have unique `request_id` values.

## Mock Success Criteria

A later 1U test should pass only if:

- The operation is explicitly allowlisted.
- Manual approval is present.
- Backup evidence is present before the fake write attempt.
- The fake write attempt is represented once.
- The terminal result is represented once.
- Post-write verification is represented once.
- The full audit chain is written only to the temporary verification database.
- Business counts remain unchanged in the mock unless the fixture intentionally simulates a fake business write inside the temporary database.
- No public audit write endpoint is added.
- Runtime routes remain unchanged.
- Formal sync remains closed.

## Mock Block Cases

The later mock gate should block:

- Missing manual approval.
- Missing pre-write backup evidence.
- Unsupported operation type.
- `store_id` other than the approved test store.
- Platform other than Naver.
- Missing target hash.
- Mixed correlation ids.
- Duplicate request ids.
- Missing terminal action.
- Missing post-write verification action.
- Any blocked row without `blocked_payload_written=false`.
- Any row containing unsafe keys or unsafe values.

## Safety Fields

Every mock audit row must keep:

- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `sensitive_scan_passed=true` for success rows
- `blocked_payload_written=false` for blocked rows
- `formal_sync_open=false`
- `real_api_called=false`
- `runtime_writer_enabled=false` during the mock phase

## Forbidden Data

The mock must not store or echo:

- Token, refresh token, access token, Authorization value.
- Request or response headers.
- Signature, bcrypt input, client secret.
- Raw request or raw response body.
- Full channel number.
- Full order id or product-order id.
- Full buyer or receiver name.
- Buyer or receiver phone.
- Full address, detailed address, zip code, or delivery memo.
- Raw platform payload.

## Public API Boundary

1T does not approve a public write API. The existing audit read-only APIs may remain:

- `GET /api/v1/operation-audit-logs`
- `GET /api/v1/operation-audit-logs/summary`

The following remain closed:

- `POST /api/v1/operation-audit-logs`
- audit log update/delete/export endpoints
- raw audit detail endpoint
- automatic audit middleware
- blanket route instrumentation

## Expected Documentation Update For 1U

If 1U is executed, it should document:

- the fake selected operation input,
- the generated safe audit chain,
- blocked-case coverage,
- unchanged real database counts,
- no public route changes,
- no platform API calls,
- and why runtime production wiring remains closed.

## Recommended Next Stage

`Phase ERP-Audit-1U: Selected operation audit runtime wiring mock gate`

That phase may add mock-only test helpers and `verify_all.py` coverage, but should still not connect the writer to real runtime order flows.
