# Phase ERP-Audit-1V: Selected operation audit runtime wiring implementation approval plan

## Scope

This phase is an implementation approval plan only. It defines the approval boundary for a later phase that may connect the mock-proven selected-operation audit writer to one real local runtime operation.

It does not add code, does not connect runtime order flows, does not write `operation_audit_logs`, does not write orders/products/SyncLog, does not modify schema, does not call Naver or Coupang APIs, does not execute backup/restore, and does not open formal sync.

## Current Baseline

- The real `operation_audit_logs` table exists and remains empty.
- Read-only audit list and summary APIs exist.
- Logs/Audit UI can read audit logs.
- Phase 1R verified generic integration chains in the temporary verification database.
- Phase 1U verified a private selected-operation mock gate for `controlled_naver_order_local_refresh`.
- No real runtime order-flow audit writer is connected.

## Approved Future Implementation Target

A later implementation phase may connect audit writing only to:

`controlled_naver_order_local_refresh`

The target must be a selected local Naver order refresh/write path that already has:

- explicit manual approval,
- selected target order identity,
- pre-write backup evidence,
- local write result,
- post-write readback verification,
- and no platform write operation.

It must not audit formal batch sync, automatic sync, shipment writes, cancel/return/exchange writes, settlement writes, customer-service actions, mail, appeals, or AI automation.

## Required Preconditions For The Later Implementation Phase

Before any real runtime writer is connected:

- Codex1 and Codex2 worktrees must be clean.
- A fresh backup of `backend/codex1.db` must be created and SHA-256 verified.
- Real database baseline counts must be recorded:
  - `operation_audit_logs`
  - orders
  - products
  - SyncLog
  - `ApiCapabilityTestResult tested_success`
  - `order_status_events`
- The selected local order operation must be explicitly approved by the user.
- The implementation must be limited to `store_id=8` and platform `naver`.
- The implementation must not introduce public audit write/delete/export/raw detail routes.
- The implementation must not introduce automatic middleware or blanket endpoint logging.
- The implementation must not call Naver or Coupang APIs.

## Required Runtime Behavior

The future implementation should write audit evidence only after the selected local operation reaches defined checkpoints:

1. approval evidence prepared,
2. pre-write backup verified,
3. local write attempt begins,
4. local write result is known,
5. post-write verification is complete.

The audit rows must share one `correlation_id` and use unique `request_id` values. The chain must be append-only.

## Allowed Audit Data

Future real audit rows may store:

- `store_id=8`
- `platform=naver`
- safe actor type and label
- action and operation phase
- correlation id and request id
- status and safe reason code
- target type `order`
- safe target hash
- safe changed field names
- safe count summary
- backup path and SHA-256
- safety flags
- short business note

## Forbidden Audit Data

Future real audit rows must not store or echo:

- token, refresh token, access token, or Authorization value
- request or response headers
- signature, bcrypt input, or client secret
- raw request or raw response body
- full channel number
- full order id or product-order id
- buyer or receiver full name
- buyer or receiver phone
- address, detailed address, zip code, or delivery memo
- raw platform payload snapshots

## Failure And Rollback Boundary

- If backup creation or verification fails, do not run the selected local write and do not write audit rows beyond a safe blocked record.
- If sensitive scan fails, do not persist the unsafe payload.
- If the selected local operation is blocked before writing business data, write only safe blocked evidence.
- If the selected local operation writes business data but audit writing fails, the phase must stop, report audit integration failure, and block any wider rollout.
- The later implementation must not try to restore the database automatically. Restore remains a separate approval flow.
- No audit failure may trigger a platform API write.

## Required Verification For The Later Implementation Phase

The later implementation phase must prove:

- The real `operation_audit_logs` count increases only by the expected chain length.
- The selected local order operation result is verified by readback.
- Orders/products/SyncLog/tested_success/order_status_events counts match the approved operation expectation.
- No public audit write/delete/export/raw detail route exists.
- Existing read-only audit APIs can read the new rows safely.
- Main UI remains business-readable and does not show raw technical payloads.
- Sensitive scan finds no token, Authorization, headers, signatures, client secrets, raw response, full platform id, buyer privacy, phone, address, or zip code.

## Not Yet Approved

The following remain closed:

- audit writer instrumentation for all routes,
- middleware-based audit logging,
- public audit write API,
- audit export/delete/raw detail API,
- formal Naver product or order batch sync,
- Naver shipment/cancel/return/exchange write operations,
- backup scheduler,
- restore execution,
- role-based approval workflow,
- multi-store rollout.

## Recommended Next Stage

`Phase ERP-Audit-1W: Selected operation audit runtime wiring local implementation`

That phase may connect the audit writer to the single selected local operation only if the user explicitly approves it and the pre-write backup is completed first.
