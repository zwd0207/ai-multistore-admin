# Phase Naver-ERP-15D - Naver Order Refresh Batch Approval Plan

## Summary

Phase 15D defines the human approval plan for a future local batch refresh of already-existing Naver orders.

This phase is planning-only. It does not call Naver, does not run a readonly batch probe, does not execute `real_sync=true`, does not write `orders`, does not insert `order_status_events`, does not modify schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Current Baseline

- Phase 15A documented the batch-refresh gate direction.
- Phase 15B added a private mock gate in Codex1 and `verify_all.py` coverage.
- Phase 15C ran a controlled real readonly candidate discovery under the current `page=1,size=1` public guardrail.
- 15C returned HTTP 200 and one safe hash, `id-hash-67b5fc1c97`, but it did not match an existing local real Naver order.
- The public real Naver order preview endpoint still remains capped at `page=1,size=1`.
- Current real write behavior remains single-order only.
- No true multi-candidate batch readonly probe has been executed.
- No existing-order batch refresh candidate is currently approved.
- Formal order sync, automatic refresh, timeline event writes, shipment writes, cancel/return/exchange writes, SyncLog writes, and tested_success writes remain closed.

## Approval Scope

The future approval can cover only:

- refreshing existing local real Naver orders.
- `store_id=8`.
- `credential_id=7`.
- `platform=naver`.
- at most 2 approved local order refreshes for the first batch write phase.
- sanitized status/amount/quantity/timestamp/product-option fields already covered by the refresh whitelist.

It must not approve:

- new-order creation.
- formal order sync.
- automatic scheduled refresh.
- timeline event insertion.
- complete-field preview persistence.
- shipment, cancel, return, exchange, refund, delivery, settlement, sales, customer-service, or any other Naver platform write API.

## Required Evidence Before Approval

Before a later batch write phase can be approved, the operator must have:

- a clean Codex1 worktree.
- a clean Codex2 worktree.
- `verify_all.py` passing after the 15B mock gate.
- a fresh readonly candidate batch result from a separately approved phase.
- no real write in the readonly candidate phase.
- explicit candidate safe hashes.
- candidate count within the first-batch limit.
- no duplicate safe hashes.
- every candidate matched to exactly one existing local real Naver order.
- no new-order candidate mixed into the batch.
- no mock/test order candidate.
- no unknown status observation.
- privacy gate passed for every candidate.
- only whitelisted fields changed.
- no complete-field payload used as persistence source.
- no raw response, token, Authorization, header, signature, bcrypt output, client secret, full order id, full product-order id, full buyer/receiver data, phone, address, or zip code in the candidate payload.

## Approval Record Shape

The future approval record should be operator-readable and safe:

- phase name.
- requested action: `naver_existing_order_batch_refresh`.
- `store_id=8`.
- `credential_id=7`.
- approved safe hashes.
- candidate count.
- per-candidate changed field names only.
- per-candidate current local status label.
- per-candidate preview status label.
- backup path.
- approval timestamp.
- approver note.
- `real_sync_allowed=false` until the later write phase actually starts.
- `formal_order_sync_open=false`.

It must not contain raw responses, full order ids, buyer privacy, addresses, tokens, headers, signatures, bcrypt output, client secrets, or complete-field preview payloads.

## First Batch Write Rules For A Later Phase

The later write phase must:

- require an explicit user request naming the write phase.
- re-check clean worktrees.
- back up `backend/codex1.db` before any write.
- use only the approved safe hashes.
- update at most 2 existing local orders.
- create zero new orders.
- block the entire batch if any candidate fails.
- write no products.
- write no SyncLog.
- add no ApiCapabilityTestResult tested_success.
- insert no timeline events unless a separate event-write phase approves it.
- execute no Naver platform write operation.
- keep formal Naver order sync closed.

## Post-Write Readback Required For A Later Phase

After a future approved write, the agent must immediately read back:

- total local order count unchanged.
- approved hashes still exist exactly once.
- changed rows remain `store_id=8`, `platform=naver`, `source_type=naver_real_order_sync`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- products count unchanged.
- SyncLog count unchanged.
- tested_success count unchanged.
- timeline event count unchanged unless separately approved.
- sensitive-field scan passes across updated rows and gate output.

If any readback fails, stop and restore from the database backup.

## Blockers

Approval must be denied if:

- the latest readonly candidate is still `id-hash-67b5fc1c97` and still does not match an existing local real Naver order.
- current endpoint still cannot produce a safe readonly batch candidate result.
- candidate batch is larger than the approved first-batch limit.
- any candidate is a new order.
- any candidate is missing a safe hash.
- any safe hash is duplicated.
- any safe hash matches zero or multiple local real orders.
- any candidate is a mock/test order.
- unknown status is observed.
- privacy gate fails.
- forbidden sensitive/raw fields appear.
- the operator asks for partial success.
- the operator asks to open formal order sync or platform write actions.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-15E: Naver order refresh batch readonly expansion approval plan
```

15E should still avoid writes. It should decide whether to temporarily expand the readonly candidate probe beyond `page=1,size=1`, define the exact probe parameters and stop conditions before any real request is made, and explicitly separate new-order candidates from existing-order refresh candidates.
