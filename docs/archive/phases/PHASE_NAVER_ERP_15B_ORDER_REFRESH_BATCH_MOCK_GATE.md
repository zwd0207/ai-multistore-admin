# Phase Naver-ERP-15B - Naver Order Refresh Batch Mock Gate

## Summary

Phase 15B adds a private mock-testable Codex1 gate for a future Naver existing-order refresh batch.

This phase does not call Naver, does not change the public preview endpoint, does not execute `real_sync=true`, does not write the real `backend/codex1.db`, does not modify schema, does not modify Codex2 runtime UI, does not insert real timeline events, and does not open formal Naver order sync.

## Implemented Gate

Codex1 now has a private helper:

```text
_evaluate_naver_order_refresh_batch_mock_gate(...)
```

It is used only by `verify_all.py` against the temporary verification database.

The gate validates a small batch of existing local Naver order refresh candidates:

- default batch limit: 2 candidates.
- requires fresh readonly preview input.
- requires safe product-order hashes.
- rejects duplicate safe hashes in the same batch.
- optionally checks explicit approved safe hashes.
- requires every safe hash to match exactly one local real Naver order.
- rejects new-order candidates.
- rejects mock/test orders.
- rejects privacy failures.
- rejects unknown status observations.
- rejects complete-field/raw-response/sensitive field names.
- blocks partial writes in the first batch design.
- writes nothing unless `write_enabled=true` and `manual_approval=true`.

## Mock Write Behavior

When the mock gate is approved inside `verify_all.py`, it may update at most the matched existing local order rows in the temporary database.

It still must not:

- create new orders.
- write products.
- write SyncLog.
- add ApiCapabilityTestResult tested_success.
- insert timeline events.
- save raw response payloads.
- save tokens, Authorization values, headers, signatures, bcrypt output, or client secrets.
- save full order ids, full product-order ids, full buyer or receiver data, phone numbers, addresses, or zip codes.
- execute any Naver platform write action.
- open formal order sync.

## Verify Coverage

`verify_all.py` covers:

- readonly batch not requested.
- stale preview blocked.
- candidate limit exceeded.
- duplicate safe hash blocked.
- new-order candidate blocked.
- privacy failure blocked.
- unknown status blocked.
- sensitive/raw-response field blocked.
- manual approval required.
- approved two-row temporary mock update.
- no-change repeat.
- products, SyncLog, tested_success, and timeline event counts unchanged.
- sensitive-field scan over gate output and updated rows.
- temporary batch rows removed after the test so later verification stays stable.

## Current Runtime Boundary

The public Naver order preview endpoint is unchanged.

Current real preview remains capped at:

```text
page=1,size=1
```

Current real write behavior remains single-order only. 15B does not approve a real batch readonly probe or a real batch write.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-15D: Naver order refresh batch approval plan
```

15D should remain planning-only and convert the mock gate into a human approval checklist before any later real readonly batch probe or local write phase is considered.
