# Phase Naver-ERP-11D - Selected Candidate Real Write Approval Plan

## Summary

Phase 11D documents the approval plan for a possible future selected-candidate Naver order local write. It does not call Naver, does not write local data, does not modify Codex1 runtime behavior, does not modify Codex2 runtime behavior, and does not open formal Naver order sync.

Based on 11C-Retry, the candidate can be considered for a later single-row write phase, but 11D itself is not a write approval and does not execute `real_sync=true`.

## Current Candidate

Safe candidate from 11C-Retry:

- selected safe product-order hash: `id-hash-ab176f5db1`.
- classification: `candidate_new`.
- order status: `DELIVERED / 配送完成`.
- amount: `330000 KRW`.
- quantity: 1.
- product text present: true.
- option text present: true.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- local duplicate match count: 0.
- real Naver local match count: 0.
- mock/test Naver match count: 0.

This candidate is eligible for manual review in a later phase, but it is not yet approved for persistence.

## 11E Entry Conditions

A future `Phase Naver-ERP-11E: Selected candidate single local write` may proceed only if all conditions are met:

- The user explicitly requests 11E.
- `git status` is clean in Codex1 and Codex2.
- `backend/codex1.db` is backed up before any write attempt.
- The backup path is printed.
- Baseline counts are recorded before the write.
- The selected candidate safe hash remains explicit: `id-hash-ab176f5db1`.
- The fresh selected candidate still classifies as `candidate_new`.
- Duplicate checks return zero matches for real and mock/test Naver orders immediately before write.
- Privacy gate passes.
- The write limit is exactly one local order row.
- `store_id=8` and `credential_id=7`.
- `products`, `SyncLog`, and `tested_success` must remain unchanged.
- Naver platform order writes remain disabled.
- Formal Naver order sync remains closed.

## Allowed Future Persistence Fields

11E may persist only sanitized fields already accepted by the Naver order privacy gate:

- `store_id=8`.
- `platform=naver`.
- hashed external order identifiers.
- order status and Chinese label.
- safe delivery and claim status labels when available.
- safe product and option text.
- quantity.
- order amount.
- `currency=KRW`.
- ordered, paid, and last-changed timestamps when available.
- `source_type=naver_real_order_sync`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- mapping version and sanitized metadata.

## Explicitly Forbidden

11E must not persist or print:

- full order id.
- full product order id.
- full buyer name.
- full buyer phone.
- full receiver name.
- full receiver phone.
- address or zip code.
- raw response.
- request headers.
- Authorization value.
- token.
- signature or bcrypt output.
- client secret.

11E must not:

- write products.
- write SyncLog.
- add `ApiCapabilityTestResult tested_success`.
- execute dispatch, cancel, return, exchange, delivery, refund, sales, settlement, or customer-service writes.
- open formal Naver order sync.

## Stop Conditions

Stop and write nothing if any of the following occurs:

- selected candidate hash is missing or changed.
- candidate is no longer `candidate_new`.
- candidate is not unique.
- duplicate match count is greater than 0.
- privacy gate fails.
- feed or detail preview fails.
- database backup is missing.
- baseline counts are unexpected.
- any sensitive field appears in the proposed payload.

## Recommended Next Phase

Recommended next phase: `Phase Naver-ERP-11E: Selected candidate single local write`.

Purpose:

- Back up the database.
- Recheck the selected candidate and duplicate state.
- If all gates pass, write exactly one sanitized local Naver order.
- Verify readback and sensitive scans.
- Keep formal order sync closed.
