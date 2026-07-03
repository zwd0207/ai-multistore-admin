# Phase Naver-ERP-16C2 - Current 24h Candidate Write Approval Plan

## Summary

Phase 16C2 documents a new approval plan for the current 24-hour Naver new-order candidate.

This phase is approval and documentation only. It does not call Naver, does not execute `real_sync=true`, does not back up or write `backend/codex1.db`, does not write `orders`, does not insert `order_status_events`, does not write products, SyncLog, or ApiCapabilityTestResult rows, does not change database schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Why 16C2 Is Needed

Phase 16D was stopped before any local write because the writeable 24-hour window did not return the same safe hash approved in Phase 16C.

Observed during the stopped 16D gate:

- 3-day readonly preview returned the previously approved safe hash: `id-hash-67b5fc1c97`.
- the existing single-write guardrail still limits `real_sync=true` to a 24-hour window.
- the 24-hour readonly preview returned a different safe hash: `id-hash-bc5528d093`.
- because `id-hash-bc5528d093` was not approved by Phase 16C, no local order was written.
- post-stop readback confirmed `orders_store8=5`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`.

16C2 exists to approve only the plan for the current 24-hour candidate. It does not itself perform the write.

## Current Candidate Evidence

The current candidate safe product-order hash is:

```text
id-hash-bc5528d093
```

Readonly evidence observed in the 24-hour gate:

- HTTP 200.
- `preview_status=success`.
- token HTTP 200.
- feed HTTP 200.
- detail HTTP 200.
- privacy gate passed.
- required business fields were present.
- real local match count: 0.
- mock/test local match count: 0.
- order status: `DELIVERED` / delivery complete.
- delivery status: `DELIVERY_COMPLETION` / delivery complete.
- claim status: `COLLECT_DONE`, currently treated as an unknown status requiring mapping review.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.

The unknown claim status does not approve timeline event insertion or claim automation. It only means a later write phase may persist the sanitized order row if all other gates pass, while a separate mapping phase should add a user-facing label for `COLLECT_DONE`.

## Approval Decision

16C2 approves only the plan for entering a later single-write retry phase for this safe hash:

```text
id-hash-bc5528d093
```

If a fresh preview in the write phase returns any other safe hash, the write must stop and return to a new approval phase.

This approval does not open:

- formal Naver order sync.
- batch order sync.
- existing-order refresh batch writes.
- timeline event insertion.
- shipment, cancel, return, exchange, refund, delivery, settlement, sales, customer-service, or any other Naver platform write operation.

## Required Next Write Entry Conditions

A later write retry phase may write at most one sanitized local order only if all conditions are true:

- user explicitly requests the write retry phase.
- Codex1 worktree is clean.
- Codex2 worktree is clean.
- `backend/codex1.db` is backed up before any write.
- backup path is printed.
- backup integrity is checked.
- baseline counts are recorded before the write.
- selected safe hash is still `id-hash-bc5528d093`.
- a fresh readonly preview is executed immediately before write.
- fresh preview uses `store_id=8`, `credential_id=7`, recent 24-hour KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false` first.
- fresh preview returns HTTP 200, feed HTTP 200, detail HTTP 200, and `preview_status=success`.
- duplicate checks return zero local real matches and zero mock/test matches.
- privacy gate passes.
- required business fields are present.
- proposed write payload contains only approved safe fields.
- no sensitive values appear in the proposed payload.

## Allowed Future Persistence Fields

The future write may persist only:

- `store_id=8`.
- `platform=naver`.
- hashed external order id.
- hashed external product-order id.
- `order_status`.
- safe status labels or sanitized status metadata.
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
- safe delivery labels or sanitized delivery metadata.
- `claim_status`.
- safe claim labels or sanitized claim metadata.
- `source_type=naver_real_order_sync`.
- `last_synced_at`.
- `mapping_version`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- masked buyer/receiver fields only if already produced by the sanitized preview.

## Forbidden Future Persistence Fields

The future write must not persist or print:

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

## Post-Write Readback Required

If the later write phase writes one order, it must immediately verify:

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

Stop and write nothing in the later write phase if:

- worktree is not clean.
- backup fails.
- backup path cannot be verified.
- fresh readonly preview fails.
- preview is `success_empty`.
- detail is not called.
- selected safe hash is missing.
- selected safe hash differs from `id-hash-bc5528d093`.
- duplicate match count is greater than 0.
- privacy gate fails.
- required business fields are missing.
- forbidden fields appear.
- proposed write would affect more than one row.
- operator asks to combine this write with batch sync, refresh sync, timeline event writes, or Naver platform write actions.

## Operator Message

Seller-facing wording should be:

```text
已通过当前 24 小时窗口候选订单的单条写入前审批。下一阶段仍需先备份数据库并重新复核候选，成功后最多只写入 1 条本地 Naver 订单。正式订单同步仍未开放。
```

Do not say:

- do not claim formal Naver order sync is open.
- do not claim all orders are synced.
- do not claim automatic sync is enabled.
- do not claim batch write approval.
- do not claim shipment or after-sales platform operations are open.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-16D-Retry: Approved current candidate single local write
```

That phase is the next one that may write one local order, but only after backing up `backend/codex1.db`, re-running the fresh readonly preview, confirming `id-hash-bc5528d093`, and passing all gates above.
