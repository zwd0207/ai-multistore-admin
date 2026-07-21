# Phase Naver-ERP-14B - Naver Order Status Timeline Mock Mapper

## Summary

Phase 14B adds a private Codex1 mock-testable mapper for future Naver order status timeline events. It is not wired to a public endpoint, does not call Naver, does not write real local data, does not create a timeline table, does not change database schema, does not modify Codex2 runtime behavior, and does not open formal Naver order sync.

The mapper is exercised only inside `verify_all.py` with the temporary verification database.

## Helper

New private helper:

```text
_evaluate_naver_order_status_timeline_mock_mapper(...)
```

Inputs:

- selected safe local order hash.
- previous sanitized local snapshot.
- fresh sanitized refresh preview.
- optional existing timeline dedupe keys.
- freshness and identity flags.

Outputs:

- whether a timeline event would be planned.
- planned safe event payloads.
- dedupe counts.
- changed status fields.
- unknown-status/manual-review flags.
- safety flags proving no local writes or platform writes.

The helper is intentionally private and planning-only. It does not persist events.

## Event Mapping

The mock mapper supports these event types:

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

It reuses the existing Naver status label mapping so the event label remains consistent with order preview/detail display.

## Safe Event Payload

Planned event payloads contain only safe fields:

- `store_id`.
- `platform=naver`.
- safe order hash.
- safe product-order hash.
- `event_type`.
- raw status enum and Chinese label.
- safe payment/delivery/claim status enum and Chinese label.
- `observed_at`.
- `source_phase=Naver-ERP-14B`.
- `source_type=naver_order_preview`.
- `mapping_version=naver_order_status_timeline_mock_mapper_v1`.
- `dedupe_key`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.

It does not include complete-field preview values or buyer/receiver privacy data.

## Gate Behavior

The mapper blocks or returns no planned event when:

- the readonly preview is stale.
- the selected order hash is missing.
- the refresh preview is missing.
- the refresh preview hash does not match the selected order hash.
- privacy gate fails.
- an unknown status is observed.
- the status did not change.
- an equivalent event already exists by dedupe key.

Unknown status observations return `blocked_unknown_status` with a safe `unknown_status_observed` event and `manual_review_required=true`; they do not approve refresh writes.

## Dedupe Rules

The dedupe key uses:

```text
store_id + platform + external_product_order_id_hash + event_type + status_raw + delivery_status_raw + claim_status_raw
```

Repeated `DELIVERED` refreshes do not create duplicate delivered events. A `last_synced_at`-only refresh creates no event.

## Verification

`verify_all.py` covers:

- `PAYED -> DELIVERED` creates one planned `delivered` event.
- repeated delivered refresh is deduped.
- no-change refresh creates no event.
- delivery status change creates a delivery event.
- cancel request creates a claim event.
- return request creates a claim event.
- exchange request creates a claim event.
- unknown status returns manual review metadata and does not write.
- privacy failure creates no event.
- identity mismatch creates no event.
- sensitive field scan over serialized mapper output.
- `orders`, `products`, `SyncLog`, and `tested_success` counts stay unchanged.

## Safety Boundary

14B does not:

- call Naver.
- execute `real_sync=true`.
- write `orders`.
- write products.
- write `SyncLog`.
- add `ApiCapabilityTestResult tested_success`.
- create a timeline table.
- save raw response data.
- save tokens, headers, signatures, bcrypt output, or client secrets.
- save full order ids, product-order ids, buyer/receiver names, phone numbers, addresses, or zip codes.
- open formal Naver order sync.
- execute any Naver platform write action.

## Next Stage

Recommended next phase: `Phase Naver-ERP-14C: Orders UI status timeline display plan`.

Purpose:

- Plan how Orders UI should show current status versus future status history.
- Keep it display-planning only before schema changes.
- Avoid making users think timeline persistence or formal order sync is already open.
