# Phase Naver-ERP-15A - Naver Order Refresh Batch Gate Plan

## Summary

Phase 15A defines the gate for a future controlled batch refresh of existing local Naver orders.

This phase is planning-only. It does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not insert `order_status_events`, does not write products, SyncLog, or ApiCapabilityTestResult rows, does not change Codex1 schema, does not change Codex2 runtime UI, and does not open formal Naver order sync.

## Current Baseline

- Naver ERP priority remains Naver-first normal ERP operations.
- Product line is staged and formal product batch sync remains closed.
- Local Naver orders for `store_id=8` exist, but formal order sync remains closed.
- Current public Naver order preview guardrail still allows only `page=1,size=1` for real preview.
- Current real single-order write gate remains limited to a 24-hour window.
- Phase 13D attempted a selected local order refresh but did not write because fresh readonly previews did not match the approved selected hash.
- Phase 14G created the `order_status_events` schema, but Phase 14I confirmed `order_status_events_rows=0`.
- Phase 14J added Codex2 read-only Orders UI timeline display, but it does not create events or open refresh automation.

## Goal

The future batch refresh gate should update multiple already-existing local Naver orders only after a safe readonly candidate pass and explicit user approval.

It must not combine these workflows:

- existing-order refresh.
- new-order creation.
- timeline event insertion.
- shipment, cancel, return, exchange, refund, or other platform write actions.
- formal batch order sync.

If a feed result contains a safe hash that does not match an existing local real Naver order, it is a new-order candidate and must be routed to the new-order gate, not the refresh-batch gate.

## Proposed Future Batch Shape

The first future batch refresh implementation should be smaller than production sync:

- `store_id=8`.
- `credential_id=7`.
- `platform=naver`.
- `real_preview=true` before any write.
- `include_detail=true`.
- `complete_field_preview=false` for persistence.
- `real_sync=false` for readonly batch candidate discovery.
- future readonly batch candidate limit: at most 3 feed/detail candidates.
- future write limit: at most 2 existing local order refreshes in one approved phase.
- recent bounded KST window only.
- no `lastChangedTo` unless separately approved.
- no order-status filter expansion beyond the current safe contract unless separately approved.

The current public endpoint must remain capped at `page=1,size=1` until a later mock gate and implementation phase explicitly changes it.

## Batch Readiness Gate

A future batch refresh can become writable only if all candidates pass:

- the worktrees are clean.
- `backend/codex1.db` is backed up.
- the readonly request is fresh, HTTP 200, and `preview_status=success`.
- feed/detail candidate count is within the approved batch limit.
- every detail payload produces a safe product-order hash.
- there are no duplicate safe hashes in the same batch.
- every safe hash matches exactly one existing local real Naver order.
- no candidate is a new-order candidate.
- no candidate is a mock/test order.
- privacy gate passes for every candidate.
- unknown status is not observed.
- only whitelisted refresh fields changed.
- no complete-field preview payload is used for persistence.
- no raw response, token, Authorization, header, signature, bcrypt output, client secret, full order id, full product-order id, full buyer/receiver data, phone, address, or zip code appears in the write payload.

## Allowed Batch Refresh Fields

Future batch refresh may update only these sanitized fields on existing local `orders` rows:

- `order_status`.
- `order_status_label_zh`.
- `payment_status`.
- `delivery_status`.
- `delivery_status_label_zh`.
- `claim_status`.
- `claim_status_label_zh`.
- safe `product_name`.
- safe `option_name`.
- `quantity`.
- `order_amount`.
- `currency=KRW`.
- `ordered_at`.
- `paid_at`.
- `last_synced_at`.
- sanitized `raw_data` whitelist with safe hashes, status labels, mapping version, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`.

## Batch Blockers

The future batch gate must block the entire write, not partially write, when any candidate has:

- missing safe product-order hash.
- duplicate safe hash in the batch.
- zero matching local real Naver orders.
- more than one matching local real Naver order.
- unknown order, delivery, or claim status.
- privacy gate failure.
- complete-field payload selected as persistence source.
- forbidden field in candidate payload.
- raw response or sensitive credential/header/signature data.
- a candidate that should be created as a new order instead of refreshed.
- platform write action requested or implied.

Partial success should stay out of the first batch refresh write. A later production-grade design may revisit partial processing only after audit, rollback, and operator review are mature.

## Timeline Event Boundary

Order status timeline events remain a separate gate.

A future batch refresh may calculate planned timeline events for review, but real event insertion must not happen unless a later phase explicitly approves batch event writes. A no-change refresh or `last_synced_at`-only refresh must not create an event.

## Post-Write Readback For Future Phase

If a later approved phase writes a refresh batch, it must immediately verify:

- updated local order count is unchanged.
- exactly the approved existing rows were updated.
- no new orders were created.
- no products were changed.
- no SyncLog row was written.
- no ApiCapabilityTestResult tested_success was added.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- all updated rows remain `store_id=8`, `platform=naver`, and `source_type=naver_real_order_sync`.
- sensitive scans pass across serialized updated rows.
- any planned timeline events remain uninserted unless separately approved.

## Recommended Next Stages

1. `Phase Naver-ERP-15B: Order refresh batch mock gate`
   - Add private mock-only verification for a batch of existing local order refresh candidates.
   - No real API and no real database writes.

2. `Phase Naver-ERP-15C: Order refresh batch readonly candidate probe plan`
   - Plan how to safely expand readonly candidate discovery beyond `size=1`.
   - Still no implementation and no real request.

3. `Phase Naver-ERP-15D: Order refresh batch readonly probe`
   - Only after explicit approval, run a real readonly probe with a small candidate limit.
   - No write.

4. `Phase Naver-ERP-15E: Order refresh batch write approval plan`
   - Convert the readonly batch result into an operator approval checklist.
   - No write.

5. `Phase Naver-ERP-15F: Order refresh batch local write`
   - Only after explicit approval and backup, refresh at most the approved existing local orders.
   - Still not formal order sync.

## Operator Message

Seller-facing wording should stay conservative:

> 当前只是规划 Naver 已有本地订单的小批量刷新门禁。正式订单同步、自动刷新、发货、取消、退货、换货等平台写操作仍未开放。

## Why Not Open Formal Sync

Formal Naver order sync is still not ready because:

- current real preview remains capped at one candidate.
- selected-order refresh already showed hash mismatch risk in 13D.
- batch duplicate and mixed new/refresh candidate behavior is not yet mock-verified.
- timeline event writes are not approved.
- partial failure, audit trail, rollback, and operator approval UX are not production-complete.
- platform write actions remain out of scope.
