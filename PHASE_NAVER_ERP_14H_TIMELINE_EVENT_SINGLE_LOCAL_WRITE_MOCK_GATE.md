# Phase Naver-ERP-14H - Timeline Event Single Local Write Mock Gate

## Summary

Phase 14H adds a private mock-testable gate for inserting one Naver order status timeline event. This phase does not call Naver, does not execute `real_sync=true`, does not write the real `backend/codex1.db` event table, does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult`, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

The gate is exercised only inside `backend/scripts/verify_all.py` against the temporary verification database.

## Gate Purpose

14G created the real `order_status_events` schema, but the table remained empty. 14H proves the next write path can be safely gated before any real event insert is approved.

The helper accepts a selected local order safe hash and exactly one planned event from the 14B timeline mapper. It verifies:

- fresh readonly preview flag.
- selected order hash shape.
- exactly one planned event.
- `store_id=8`.
- `platform=naver`.
- event identity matches the selected local order hash.
- exactly one matching local Naver order exists.
- event type is known and not `unknown_status_observed`.
- `source_type=naver_order_preview`.
- expected mapping version.
- dedupe key matches the approved event shape.
- no existing event row has the same `store_id/platform/dedupe_key`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- manual approval is present before writing.

## Mock Write Result

In the temporary verification database only, the gate can insert one `OrderStatusEvent` row when:

- `write_enabled=true`.
- `manual_approval=true`.
- all gates pass.

The inserted mock row uses:

- `source_phase=Naver-ERP-14H`.
- safe hashes only.
- status enums and Chinese labels.
- approved safety booleans.
- safe metadata containing gate phases only.

Repeated execution with the same dedupe key returns `timeline_event_already_exists` and does not insert a second row.

## Blocked Cases Covered

`verify_all.py` covers:

- write not requested.
- manual approval missing.
- more than one planned event.
- selected hash / event identity mismatch.
- sensitive event fields.
- unknown status event.
- successful one-row mock insert.
- duplicate dedupe key.
- no writes to orders, products, SyncLog, or tested_success.
- sensitive-field scan of gate result and event row.

## Still Closed

14H does not approve:

- real `order_status_events` inserts.
- order refresh writes.
- event write API endpoints.
- platform write operations.
- delivery/cancel/return/exchange writes.
- Codex2 timeline display.
- formal Naver order sync.

## Next Phase Direction

Recommended next phase:

```text
Phase Naver-ERP-14I: Timeline event real write approval plan
```

14I should define the explicit approval checklist, backup requirement, selected-event source, post-write readback, duplicate handling, and rollback steps for a future single real event insert.
