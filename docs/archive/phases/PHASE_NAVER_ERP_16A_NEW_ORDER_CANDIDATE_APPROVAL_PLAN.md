# Phase Naver-ERP-16A - New-Order Candidate Approval Plan

## Summary

Phase 16A defines the approval plan for the latest Naver new-order candidate discovered in Phase 15C.

This phase is planning-only. It does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not insert `order_status_events`, does not write products, SyncLog, or ApiCapabilityTestResult rows, does not change database schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Current Baseline

- Phase 15C ran a controlled readonly candidate discovery under the existing public `page=1,size=1` guardrail.
- 15C returned HTTP 200, feed HTTP 200, detail HTTP 200, and one safe candidate hash: `id-hash-67b5fc1c97`.
- The candidate did not match any existing local real Naver order.
- Therefore it is classified as a `new_order_candidate`, not an `existing_refresh_candidate`.
- Current database counts remain:
  - `orders_store8=5`.
  - `naver_real_orders_store8=2`.
  - `products_store8=5`.
  - `sync_logs_store8=1`.
  - `tested_success_store8=8`.
  - `order_status_events_rows=0`.
- The latest observed delivery enum `DELIVERY_COMPLETION` maps to `配送完成`.
- Formal order sync, automatic refresh, batch writes, timeline event insertion, and all Naver platform write APIs remain closed.

## Approval Decision

16A does not approve an immediate local write.

16A approves only the planning direction:

- route `id-hash-67b5fc1c97` into the selected new-order candidate path.
- require a fresh readonly repeat before any later write approval.
- require a separate explicit write approval phase after the readonly repeat.
- do not use existing-order refresh batch gates for this candidate.
- do not combine this candidate with existing-order refresh candidates.

## Candidate Approval Scope

The future selected new-order path may consider only:

- `store_id=8`.
- `credential_id=7`.
- `platform=naver`.
- candidate safe hash `id-hash-67b5fc1c97`.
- one selected candidate only.
- fresh readonly preview from the public endpoint.
- `page=1`.
- `size=1`.
- `real_preview=true`.
- `include_detail=true`.
- `complete_field_preview=false` for persistence planning.
- `real_sync=false` until a later explicitly approved write phase.

It must not approve:

- formal Naver order sync.
- batch order sync.
- automatic scheduled refresh.
- existing-order refresh from this candidate.
- timeline event insertion.
- shipment, cancel, return, exchange, refund, delivery, settlement, sales, customer-service, or any other Naver platform write API.
- storing complete-field preview payloads as persistence source.

## Required Evidence Before Future Write Approval

Before any future 16C/16D write approval can be considered, the operator must have a fresh 16B readonly repeat showing:

- HTTP 200.
- `preview_status=success`.
- feed HTTP 200.
- detail HTTP 200.
- exactly one selected safe hash.
- selected safe hash equals `id-hash-67b5fc1c97`, or the operator explicitly approves a new selected hash from the fresh preview.
- duplicate check across local real Naver orders returns 0 matches for the selected hash.
- duplicate check across mock/test Naver rows returns 0 matches, or any mock/test match is manually reviewed and blocked from operational write.
- privacy gate passes.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- `unknown_status_observed=false`.
- required business fields are present: status, quantity, amount, currency, safe product text or safe option text.
- no orders, products, SyncLog, ApiCapabilityTestResult, or timeline events change during the readonly repeat.

If the fresh readonly preview returns a different safe hash, 16A approval does not automatically transfer. The new hash must be reported and re-approved.

## Future Single-Order Write Gate

A later selected new-order single local write may proceed only after a separate explicit user request naming the write phase and only if:

- Codex1 and Codex2 worktrees are clean.
- `backend/codex1.db` is backed up before the write.
- the selected candidate comes from a fresh readonly repeat.
- the selected candidate is still classified as `candidate_new`.
- the selected safe hash has no existing local operational duplicate.
- only one order is written.
- no products are written.
- no SyncLog is written.
- no ApiCapabilityTestResult `tested_success` row is added.
- no `order_status_events` row is inserted unless a separate timeline event write phase approves it.
- no Naver platform write action is executed.
- formal Naver order sync remains closed.

## Allowed Persistence Fields For Later Write

If a later phase writes the selected order, it may persist only the existing safe whitelist:

- `store_id`.
- `platform=naver`.
- safe external order hash.
- safe external product-order hash.
- `order_status`.
- `order_status_label_zh`.
- `payment_status` if safely observed.
- safe `product_name`.
- safe `option_name`.
- `quantity`.
- `order_amount`.
- `currency=KRW`.
- `ordered_at`.
- `paid_at`.
- `last_changed_at`.
- `delivery_status`.
- `delivery_status_label_zh`.
- `claim_status`.
- `claim_status_label_zh`.
- `source_type=naver_real_order_sync`.
- `last_synced_at`.
- `mapping_version`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- masked buyer/receiver display fields only if already supported by the safe local schema.

## Forbidden Persistence Fields

The later write must not persist:

- raw Naver response.
- request headers.
- Authorization.
- token values.
- signature or bcrypt output.
- client secret.
- full channel number.
- full order id.
- full product-order id.
- full buyer name.
- full buyer phone.
- full receiver name.
- full receiver phone.
- full address.
- zip code.
- detailed address.
- complete-field preview payload.

## Stop Conditions

Stop and do not proceed to write approval if:

- readonly repeat fails.
- preview is `success_empty`.
- detail is not called.
- selected hash is missing.
- selected hash differs from the approved hash without a new approval.
- selected hash already exists in a local real Naver order.
- duplicate/ambiguous local match is observed.
- privacy gate fails.
- `unknown_status_observed=true`.
- forbidden fields appear.
- any database count changes during readonly repeat.
- operator asks to combine this with batch refresh, formal sync, or platform write actions.

## Operator Message

Seller-facing wording should be:

```text
发现 1 条可能的新 Naver 订单候选。当前只进入人工复核与审批计划，不会写入订单，也不会开放正式订单同步。
```

Do not say:

- `Naver 订单同步已开放`.
- `订单已全部同步`.
- `自动同步已启用`.
- `批量写入已批准`.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-16B: Selected new-order readonly repeat check
```

16B may call the real readonly preview again with the existing public `page=1,size=1` guardrail, but it must keep `real_sync=false`, write no local data, and stop after producing a fresh safe duplicate/privacy/status summary for the selected candidate.
