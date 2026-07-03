# Phase Naver-ERP-11B - Naver Selected New-Order Write Mock Gate

## Summary

Phase 11B implements and verifies a private selected new-order write gate in Codex1 mock/fake tests. It does not call Naver, does not write the real local business database, does not change Codex2 runtime behavior, and does not open formal Naver order sync.

The purpose is to prove the future selected-candidate path can distinguish safe one-row persistence from stale, missing, duplicate, ambiguous, and privacy-blocked candidates before any real selected-candidate write is considered.

## Implementation

Codex1 now has a private helper:

- `_evaluate_naver_selected_new_order_write_gate`.

This helper is not wired to `POST /api/v1/sync/orders/naver/preview` and does not add any public API parameter. It is used by `verify_all.py` with synthetic sanitized `detail_preview` data.

The helper requires:

- a selected safe product-order hash;
- fresh readonly preview confirmation;
- exactly one matching candidate;
- `candidate_classification` absent or `candidate_new`;
- the existing Naver order privacy gate to pass;
- duplicate checks against local Naver order hashes.

## Verified Mock Paths

`verify_all.py` now covers:

- readonly selected candidate with `write_enabled=false`, returning `selected_candidate_write_not_requested`;
- missing selected candidate, writing nothing;
- stale preview, writing nothing;
- changed candidate classification, writing nothing;
- non-unique matching candidates, writing nothing;
- privacy-blocked candidate, writing nothing;
- one-row selected mock success in the temporary verification database;
- duplicate selected candidate after the mock success, writing no second row.

The mock success path still verifies:

- at most one order row is created;
- `products` remain unchanged;
- `SyncLog` remains unchanged;
- `tested_success` remains unchanged;
- `raw_response_saved=false`;
- `privacy_fields_redacted=true`;
- `address_saved=false`;
- formal order sync remains closed;
- platform write operations remain closed.

## Safety Boundary

11B does not:

- execute a real Naver API request;
- write `backend/codex1.db`;
- add a public selected-candidate API;
- widen the existing 24-hour `real_sync=true` write gate;
- write products;
- write SyncLog;
- add `ApiCapabilityTestResult tested_success`;
- execute dispatch, cancel, return, exchange, delivery, refund, sales, settlement, or customer-service writes;
- save raw responses, tokens, request headers, Authorization values, signatures, bcrypt output, client secrets, full order ids, full product order ids, full buyer names, full phones, or addresses.

## Recommended Next Phase

Recommended next phase: `Phase Naver-ERP-11C: Selected new-order readonly candidate refresh`.

Purpose:

- Re-run a real readonly preview only.
- Confirm whether the previously observed older candidate is still visible and still classifies as `candidate_new`.
- Continue `real_sync=false`.
- Continue no local write and no formal order sync.
