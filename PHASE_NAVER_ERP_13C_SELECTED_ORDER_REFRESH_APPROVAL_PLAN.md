# Phase Naver-ERP-13C - Naver Selected Order Refresh Approval Plan

## Summary

Phase 13C documents the approval gate for a future selected Naver order local refresh. This phase is planning-only: it does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not modify Codex1 runtime code, does not modify Codex2 runtime code, and does not open formal Naver order sync.

Current refresh candidate baseline:

- selected safe product-order hash: `id-hash-ab176f5db1`.
- latest readonly repeat phase: 13B.
- latest readonly repeat result: HTTP 200, `preview_status=success`.
- latest observed status: `DELIVERED / 配送完成`.
- latest observed amount: `330000 KRW`.
- latest observed quantity: 1.
- local match: exactly one existing real local Naver order.
- current local counts: `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`.

13B proves the readonly feed-to-detail path and identity match are healthy. It does not approve a refresh write.

## Future 13D Approval Boundary

A future `Phase Naver-ERP-13D: Selected Naver order single local refresh write` may be considered only after a separate explicit user request.

Before any write is allowed, the operator must confirm:

- the requested phase name is explicit and write-scoped.
- the target is still `store_id=8`, `credential_id=7`, `platform=naver`.
- the selected local hash is explicit: `id-hash-ab176f5db1`.
- both Codex1 and Codex2 worktrees are clean.
- `backend/codex1.db` has been backed up to the approved local backup directory.
- the local database contains exactly one real Naver order for the selected hash.
- a fresh readonly preview has just been executed.
- the fresh readonly preview returns HTTP 200 and `preview_status=success`.
- the fresh preview detail hash exactly matches the selected local hash.
- the privacy gate passes.
- no platform write action is requested or implied.

Do not reuse 13B as the write payload. 13B may be used only as historical evidence that the selected order was refreshable at that time.

## Required Fresh Preview Gate

The future write phase must first run a fresh readonly request with:

- `POST /api/v1/sync/orders/naver/preview`.
- `store_id=8`.
- `credential_id=7`.
- recent bounded KST window.
- `order_status=ALL`.
- `page=1`.
- `size=1`.
- `real_preview=true`.
- `include_detail=true`.
- `complete_field_preview=false` for the persistence payload.
- `real_sync=false`.

If a complete-field operator display is needed, it may be requested separately with `complete_field_preview=true`, but those complete fields must remain display-only and must not be used as the persistence payload.

The future write must stop if:

- feed returns `success_empty`.
- detail is not called.
- detail HTTP is not 200.
- preview status is not `success`.
- the safe product-order hash is missing.
- the safe hash differs from the selected local hash.
- more than one local real Naver order matches the selected hash.
- no local real Naver order matches the selected hash.
- `unknown_status_observed=true`.
- privacy gate fails.
- any sensitive value appears in the write candidate.

## Allowed Refresh Fields

The future refresh write may update only one existing local `orders` row and only with sanitized fields:

- `order_status`.
- `order_status_label_zh`.
- `payment_status`, if safely observed.
- `delivery_status`.
- `delivery_status_label_zh`.
- `claim_status`.
- `claim_status_label_zh`.
- safe `product_name`, if still non-private.
- safe `option_name`, if still non-private.
- `quantity`.
- `order_amount`.
- `currency=KRW`.
- `ordered_at`, if safely observed.
- `paid_at`, if safely observed.
- `last_synced_at`.
- sanitized `raw_data` whitelist.

The sanitized `raw_data` whitelist must keep:

- `external_order_id_hash`.
- `external_product_order_id_hash`.
- `mapping_version`.
- `source_type=naver_real_order_sync`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- safe status samples only.
- boolean observation flags such as `address_observed`.

## Forbidden Refresh Fields

The future refresh write must not persist:

- full order id.
- full product order id.
- full platform product id.
- full buyer name.
- full buyer phone.
- full receiver name.
- full receiver phone.
- receiver address.
- zip code.
- detailed address.
- raw Naver response body.
- token values.
- `Authorization`.
- request or response headers.
- signature or bcrypt output.
- client secret.
- complete-field preview payload.

## Write Limits

The future refresh write must:

- update exactly one existing local order.
- create zero new orders.
- keep `orders_store8` unchanged at 5 unless a separate approved new-order write happens first.
- keep real Naver local order count unchanged at 2 unless a separate approved new-order write happens first.
- not write `products`.
- not write `SyncLog`.
- not add `ApiCapabilityTestResult tested_success`.
- not change database schema.
- not execute dispatch, cancel, return, exchange, refund, delivery, sales, settlement, customer-service, or any other Naver platform write API.
- not open batch refresh, automated refresh, or formal order sync.

## Post-Write Readback Gate

If a later 13D write is approved and executed, it must immediately read back the target row and verify:

- exactly one row exists for the selected safe hash.
- row still belongs to `store_id=8` and `platform=naver`.
- `source_type=naver_real_order_sync`.
- `currency=KRW`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- no full order id, product order id, buyer/receiver name, phone, address, raw response, token, header, signature, bcrypt output, or client secret appears in the row.
- `products_store8` is unchanged.
- `sync_logs_store8` is unchanged.
- `tested_success_store8` is unchanged.

If any readback check fails, stop immediately and recover from the database backup.

## Operator Message

The user-facing wording for this gate should be:

> 当前可以考虑刷新 1 条已存在的 Naver 本地订单，但这不是正式订单同步。执行前必须重新只读预览、备份数据库、确认订单 hash 匹配，并且只允许更新 1 条已存在订单的安全字段。

## Next Stage

Recommended next phase: `Phase Naver-ERP-13D: Selected Naver order single local refresh write`.

13D should run only if the user explicitly approves a real local refresh write. Otherwise, the safer next step is frontend-only: show the selected order refresh gate as disabled/manual-review status in Orders UI.
