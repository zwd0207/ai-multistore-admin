# Phase ERP-Audit-1U: Selected operation audit runtime wiring mock gate

## Scope

This phase implements a private mock gate for the selected-operation audit wiring shape planned in 1T.

It writes safe audit rows only to the temporary `verify_all.py` database. It does not connect the audit writer to real runtime order flows, does not write the real `backend/codex1.db`, does not write real `operation_audit_logs`, does not write orders/products/SyncLog, does not modify schema, does not call Naver or Coupang APIs, does not execute backup/restore, and does not open formal sync.

## Implemented

- Added `SELECTED_OPERATION_MOCK_SCOPE=verify_all_temp_db`.
- Added private helper `write_selected_operation_audit_runtime_wiring_mock_gate`.
- The helper only accepts `operation_type="controlled_naver_order_local_refresh"`.
- It requires:
  - `store_id=8`
  - `platform="naver"`
  - safe `target_order_hash`
  - `manual_approval=true`
  - `backup_verified=true`
  - fake selected-order write result
  - fake post-write readback result
  - `audit_write_enabled=true`
  - private verification scope
- It generates the five-row safe audit chain:
  - `approval_planned`
  - `pre_write_backup_verified`
  - `local_write_attempted`
  - `local_write_succeeded`, `local_write_blocked`, or `local_write_failed`
  - `post_write_verification_succeeded` or `post_write_verification_failed`
- It delegates chain persistence to the existing 1R integration mock gate.
- Runtime writer remains disabled in the result.

## Verified

`verify_all.py` now covers:

- Audit write disabled returns no write.
- Missing private scope blocks.
- Unsupported operation type blocks.
- Unsupported store blocks.
- Unsupported platform blocks.
- Missing target hash blocks.
- Missing manual approval blocks.
- Missing backup evidence blocks.
- Missing fake write result blocks.
- Missing fake post-write readback blocks.
- Invalid fake write status blocks.
- Invalid fake verification status blocks.
- Sensitive fake payload blocks without echoing sensitive markers.
- Successful fake selected-order refresh writes five audit rows to the temporary database only.
- Blocked fake selected-order refresh writes safe blocked evidence with `blocked_payload_written=false`.
- Orders, products, SyncLog, tested_success, and order_status_events counts remain unchanged in the verification database.

## Closed Boundaries

- No public audit write route.
- No audit delete/export/raw detail route.
- No automatic audit middleware.
- No runtime order-flow audit writer call.
- No platform API call.
- No real database write.
- No schema change.
- No backup/restore execution.
- No formal Naver product/order sync approval.

## Safety Boundary

The mock rows keep:

- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `formal_sync_open=false`
- `real_api_called=false`
- `runtime_writer_enabled=false`

Blocked rows must include `blocked_payload_written=false`.

Rows must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw request/response bodies, full channel/order/product-order identifiers, buyer/receiver privacy, phones, addresses, zip codes, or raw platform payload snapshots.

## Next Step

The next phase should be an implementation approval plan before connecting this mock-proven selected operation to any real runtime order flow.
