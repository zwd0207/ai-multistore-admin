# Phase Naver-ERP-14A - Naver Order Status Timeline Plan

## Summary

Phase 14A plans the Naver order status timeline before any selected-order refresh write. This phase is planning-only: it does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not create timeline rows, does not change database schema, does not modify Codex1 runtime code, does not modify Codex2 runtime code, and does not open formal Naver order sync.

Current baseline:

- `orders_store8=5`.
- real Naver local orders: 2.
- mock/test Naver orders: 3.
- `products_store8=5`.
- `sync_logs_store8=1`.
- `tested_success_store8=8`.
- selected refresh candidate from 13B/13C: `id-hash-ab176f5db1`.
- latest observed candidate status: `DELIVERED / 配送完成`.

## Problem

The current local `orders` row stores the latest safe status snapshot. A future refresh write could update that snapshot, but without a timeline the system cannot explain how the order moved through states such as `PAYED -> DELIVERED`.

That matters because ERP users need to know both:

- the current state: what needs action now.
- the status history: what changed, when it was observed, and whether it was a real business transition or only a no-change refresh.

## Timeline Goals

The timeline should support:

- payment/new-order events.
- order confirmation events.
- dispatch and delivery-stage events.
- delivery completion events.
- cancel, return, and exchange request events.
- refund or claim completion events when safely observed.
- unknown status observations that need manual review.
- no-change refresh detection without creating fake events.

The timeline must not become a platform action log. It is local readonly observation history only.

## Safe Event Shape

A future timeline event may persist only sanitized business metadata:

- `store_id`.
- `platform=naver`.
- `external_order_id_hash`.
- `external_product_order_id_hash`.
- `event_type`.
- `status_raw`.
- `status_label_zh`.
- `payment_status_raw`, if safely observed.
- `payment_status_label_zh`, if safely mapped.
- `delivery_status_raw`, if safely observed.
- `delivery_status_label_zh`, if safely mapped.
- `claim_status_raw`, if safely observed.
- `claim_status_label_zh`, if safely mapped.
- `observed_at`.
- `source_phase`.
- `source_type`.
- `mapping_version`.
- `dedupe_key`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.

Recommended `event_type` values:

- `order_paid`.
- `order_confirmed`.
- `dispatch_ready`.
- `dispatched`.
- `delivering`.
- `delivered`.
- `cancel_requested`.
- `canceled`.
- `return_requested`.
- `returned`.
- `exchange_requested`.
- `exchanged`.
- `purchase_decided`.
- `unknown_status_observed`.
- `manual_review_required`.

## Forbidden Event Data

Timeline events must not persist:

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
- complete-field preview payload.
- token values.
- `Authorization`.
- request or response headers.
- signature or bcrypt output.
- client secret.

## Status Mapping

The timeline should reuse the existing Naver order mapping:

- `PAYED` / `결제완료` -> `order_paid`, `已付款 / 新订单`.
- `PLACE_PRODUCT_ORDER` / `발주확인` -> `order_confirmed`, `已确认订单`.
- `READY` / `DELIVERY_READY` -> `dispatch_ready`, `待发货`.
- `DISPATCHED` -> `dispatched`, `已发货 / 配送中`.
- `DELIVERING` / `배송중` -> `delivering`, `配送中`.
- `DELIVERED` / `DELIVERY_COMPLETION` / `배송완료` -> `delivered`, `配送完成`.
- `CANCEL_REQUEST` / `취소요청` -> `cancel_requested`, `取消请求`.
- `CANCELED` / `취소` -> `canceled`, `已取消`.
- `RETURN_REQUEST` / `반품요청` -> `return_requested`, `退货请求`.
- `EXCHANGE_REQUEST` / `교환요청` -> `exchange_requested`, `换货请求`.
- `PURCHASE_DECIDED` / `구매확정` -> `purchase_decided`, `已确认购买`.

If a status does not match the mapping:

- do not guess.
- set `unknown_status_observed=true`.
- create only a safe `unknown_status_observed` planning event in mock tests.
- block real refresh write until manual review confirms the mapping.

## Dedupe Rules

The future timeline must avoid duplicate events.

Recommended dedupe key:

```text
store_id + platform + external_product_order_id_hash + event_type + status_raw + delivery_status_raw + claim_status_raw
```

Rules:

- A no-change refresh must not create a new timeline event.
- A `last_synced_at` refresh alone must not create a new timeline event.
- A status label remap without raw status change should be treated as metadata correction, not a business event.
- A transition from `PAYED` to `DELIVERED` should create a single delivered event if no delivered event exists.
- Claim events should be separate from delivery events because cancel/return/exchange actions can overlap delivery state.

## Storage Direction

14A does not add schema.

For later implementation, the safer direction is a separate `order_status_events` table rather than stuffing history into `orders.raw_data`.

Reason:

- `orders` should remain the latest snapshot.
- timeline rows need independent ordering, dedupe, and display.
- separate rows make later UI filtering and audit easier.
- raw response and privacy boundaries can be enforced per event.

The future table should be introduced only in a separately approved schema phase.

## Refresh Interaction

Before 13D or any later local refresh write updates a selected order, it should compare:

- previous `order_status`.
- previous delivery status from sanitized metadata.
- previous claim status from sanitized metadata.
- fresh preview `order_status`.
- fresh preview delivery status.
- fresh preview claim status.

Decision:

- no status/delivery/claim/payment change: update only allowed snapshot fields and `last_synced_at`; no timeline event.
- safe status change: update the latest snapshot and create or plan one deduped timeline event.
- unknown status: stop and require manual mapping.
- privacy gate failure: stop and write nothing.
- identity mismatch: stop and write nothing.

Until the timeline implementation exists, 13D should still be allowed only as a one-row snapshot refresh after explicit approval, but it should report whether a timeline event would have been created.

## Frontend Direction

Future Orders UI should display:

- current status as the primary badge.
- latest observed delivery/claim labels.
- a collapsed "status history" section.
- timeline entries in business language.
- unknown-status entries as manual-review warnings.

Main pages must not show:

- raw `event_type`.
- raw `status_raw` as the primary text.
- `store_id`.
- `credential_id`.
- raw response markers.
- full order ids or buyer privacy data.

TechnicalDetails may show safe enum fields and hashes if needed.

## Verification Plan

Future mock tests should cover:

- `PAYED -> DELIVERED` creates one planned delivered event.
- repeated `DELIVERED` refresh creates no duplicate event.
- delivery status changed but order status unchanged creates a delivery event.
- cancel request creates a claim event and does not overwrite delivery history.
- return request creates a claim event.
- exchange request creates a claim event.
- unknown status blocks write and produces manual-review metadata.
- privacy gate failure creates no event.
- identity mismatch creates no event.
- sensitive scan over serialized event payload finds no token, client secret, Authorization, headers, signature, bcrypt, raw response body, full order id, full product order id, full buyer/receiver data, phone, or address.

## Gate Decision

Do not move directly from 14A into schema changes or real refresh writes.

Recommended next phases:

1. `Phase Naver-ERP-14B: Naver order status timeline mock mapper`.
2. `Phase Naver-ERP-14C: Orders UI status timeline display plan`.
3. `Phase Naver-ERP-14D: Order status events schema proposal`.
4. `Phase Naver-ERP-13D: Selected Naver order single local refresh write`, only if explicitly approved and still needed.

This keeps timeline design, UI expectations, schema risk, and real local writes separated.
