# Phase Naver-ERP-16C - Selected New-Order Single Local Write Approval

## Summary

Phase 16C documents the approval gate for a future single local write of the selected Naver new-order candidate.

This phase is approval and documentation only. It does not call Naver, does not execute `real_sync=true`, does not back up or write `backend/codex1.db`, does not write `orders`, does not insert `order_status_events`, does not write products, SyncLog, or ApiCapabilityTestResult rows, does not change database schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Current Evidence

The latest eligible candidate comes from Phase 16B:

- selected safe product-order hash: `id-hash-67b5fc1c97`.
- selected hash matched the 16A approved candidate.
- candidate classification: `candidate_new`.
- real local Naver order match count: 0.
- mock/test Naver order match count: 0.
- all local Naver order match count: 0.
- order status: `PURCHASE_DECIDED` -> `已确认购买`.
- delivery status: `DELIVERY_COMPLETION` -> `配送完成`.
- quantity: 1.
- amount: `499000 KRW`.
- required business fields were present.
- status gate passed.
- privacy gate passed.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- `unknown_status_observed=false`.

Counts stayed unchanged in 16B:

- `orders_store8=5`.
- `naver_real_orders_store8=2`.
- `naver_mock_orders_store8=3`.
- `products_store8=5`.
- `sync_logs_store8=1`.
- `tested_success_store8=8`.
- `order_status_events_rows=0`.

## Approval Decision

16C approves only the plan for entering a later single-write phase.

It does not perform the write. It does not itself approve formal order sync, batch sync, automatic refresh, timeline event insertion, or any Naver platform write operation.

A later `Phase Naver-ERP-16D: Selected new-order single local write` may be requested only for this selected safe hash:

```text
id-hash-67b5fc1c97
```

If a fresh preview in 16D returns a different safe hash, the approval must stop and return to a new approval phase.

## Required 16D Entry Conditions

Before any 16D write attempt, all conditions must be true:

- user explicitly requests `Phase Naver-ERP-16D`.
- Codex1 worktree is clean.
- Codex2 worktree is clean.
- `backend/codex1.db` is backed up before any write.
- backup path is printed.
- backup SHA-256 is computed if practical.
- baseline counts are recorded before the write.
- selected safe hash is still `id-hash-67b5fc1c97`.
- a fresh readonly preview is executed in 16D immediately before write.
- fresh preview uses `store_id=8`, `credential_id=7`, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false` first.
- fresh preview returns HTTP 200, feed HTTP 200, detail HTTP 200, and `preview_status=success`.
- candidate remains `candidate_new`.
- duplicate checks return zero local real matches and zero mock/test matches.
- privacy gate passes.
- status gate passes.
- required business fields are present.
- proposed write payload contains only approved safe fields.
- no sensitive values appear in the proposed payload.

## Allowed Future Persistence Fields

16D may persist only:

- `store_id=8`.
- `platform=naver`.
- hashed external order id.
- hashed external product-order id.
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
- masked buyer/receiver fields only if already produced by the approved sanitized preview.

## Forbidden Future Persistence Fields

16D must not persist or print:

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

## Write Limits

The later 16D write phase must:

- write at most one local order row.
- create exactly one local order only if all gates pass.
- create zero orders if any gate fails.
- update zero existing orders.
- write zero products.
- write zero SyncLog rows.
- add zero ApiCapabilityTestResult `tested_success` rows.
- insert zero `order_status_events` rows unless a separate timeline event write phase later approves it.
- execute zero Naver platform write operations.
- keep formal Naver order sync closed.

## Post-Write Readback Required For 16D

If 16D writes one order, it must immediately verify:

- `orders_store8` increases by exactly 1.
- `naver_real_orders_store8` increases by exactly 1.
- `products_store8` is unchanged.
- `sync_logs_store8` is unchanged.
- `tested_success_store8` is unchanged.
- `order_status_events_rows` is unchanged.
- the written row has `store_id=8`.
- the written row has `platform=naver`.
- the written row has `source_type=naver_real_order_sync`.
- the written row uses safe hashed external identifiers only.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- `currency=KRW`.
- no full order id, full product-order id, full buyer/receiver data, phone, address, zip code, raw response, token, Authorization, header, signature, bcrypt output, or client secret appears in the written row or serialized readback.

If any readback check fails, stop and restore from the database backup before proceeding.

## Stop Conditions

Stop and write nothing in 16D if:

- worktree is not clean.
- backup fails.
- backup path cannot be verified.
- fresh readonly preview fails.
- preview is `success_empty`.
- detail is not called.
- selected safe hash is missing.
- selected safe hash differs from `id-hash-67b5fc1c97`.
- duplicate match count is greater than 0.
- candidate is no longer `candidate_new`.
- privacy gate fails.
- `unknown_status_observed=true`.
- required business fields are missing.
- forbidden fields appear.
- proposed write would affect more than one row.
- operator asks to combine this write with batch sync, refresh sync, timeline event writes, or Naver platform write actions.

## Operator Message

Seller-facing wording should be:

```text
已通过单条新订单写入前审批。下一阶段仍需先备份数据库并复查候选，成功后最多只写入 1 条本地 Naver 订单。正式订单同步仍未开放。
```

Do not say:

- `Naver 订单同步已开放`.
- `订单已全部同步`.
- `自动同步已启用`.
- `批量写入已批准`.
- `平台发货或售后处理已开放`.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-16D: Selected new-order single local write
```

16D is the first phase that may write one local order, but only after backing up `backend/codex1.db`, re-running the fresh readonly preview, confirming the selected hash, and passing all gates above.
