# Phase Naver-ERP-14G - Order Status Timeline Schema Migration

## Summary

Phase 14G creates the real `order_status_events` schema in `backend/codex1.db`. This phase is schema-only: it does not call Naver, does not execute `real_sync=true`, does not insert timeline events, does not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult`, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

The schema is created after the 14F approval plan and after backing up the real database.

## Real Database Result

The real database now contains:

```text
order_status_events
```

The table has 0 rows after migration. No historical event has been backfilled.

Existing baseline counts stayed unchanged:

- `orders_store8=5`.
- real Naver local orders `2`.
- mock/test Naver orders `3`.
- `products_store8=5`.
- `sync_logs_store8=1`.
- `tested_success_store8=8`.

## Schema Shape

Approved columns:

```text
id
store_id
order_id
platform
external_order_id_hash
external_product_order_id_hash
event_type
status_raw
status_label_zh
payment_status_raw
payment_status_label_zh
delivery_status_raw
delivery_status_label_zh
claim_status_raw
claim_status_label_zh
observed_at
source_phase
source_type
mapping_version
dedupe_key
raw_response_saved
privacy_fields_redacted
address_saved
safe_metadata
created_at
updated_at
```

Approved indexes:

```text
uq_order_status_event_dedupe
ix_order_status_events_store_platform_observed
ix_order_status_events_order_observed
ix_order_status_events_store_event_type
ix_order_status_events_product_order_hash
```

The migration intentionally keeps only the approved composite/product-hash indexes. It does not keep extra single-column SQLAlchemy convenience indexes.

## Safety Boundary

The schema must not persist:

- raw Naver responses.
- complete-field preview payloads.
- tokens.
- Authorization values.
- request or response headers.
- signatures or bcrypt output.
- client secrets.
- full order ids.
- full product-order ids.
- buyer or receiver names.
- phone numbers.
- addresses or zip codes.

The table includes safety booleans:

- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.

## What Is Still Closed

14G does not approve:

- event row writes.
- order refresh writes.
- formal Naver order sync.
- platform write operations.
- delivery, cancel, return, or exchange write operations.
- UI display of persisted timelines.

## Next Phase Direction

Recommended next phase:

```text
Phase Naver-ERP-14H: Order status event write gate plan
```

14H should remain planning/mock-first and define the gate for inserting at most one status event after a fresh readonly preview, identity match, privacy gate success, known status mapping, dedupe check, and explicit approval.
