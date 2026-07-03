# Phase Naver-ERP-14E - Order Status Events Mock Schema Gate

## Summary

Phase 14E adds a mock-only schema gate for the proposed future `order_status_events` table. It does not modify the real database schema, does not add a SQLAlchemy model or migration, does not call Naver, does not execute `real_sync=true`, does not write real business data, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

The gate runs inside `backend/scripts/verify_all.py` against the temporary verification SQLite database only. That temporary table is deleted with the verify database cleanup.

## What The Gate Verifies

- The temporary table has the proposed safe columns from 14D.
- Required event fields are non-null.
- `store_id/platform/dedupe_key` has a unique dedupe boundary.
- The planned indexes exist for store/time, order/time, store/event type, and product-order hash lookups.
- One safe event from the 14B timeline mock mapper can be inserted.
- Re-inserting the same dedupe key is rejected.
- The inserted row keeps `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`.
- `safe_metadata` contains only phase/gate metadata and safety booleans.
- `orders`, `products`, `SyncLog`, and `ApiCapabilityTestResult tested_success` counts remain unchanged.
- Sensitive sentinel values do not appear in serialized event rows.

## Boundaries

14E is not schema approval and not migration approval.

It must not persist:

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

## Next Phase Direction

Recommended next phase: `Phase Naver-ERP-14F: Order status events schema approval and rollback plan`.

14F should remain planning-only and define:

- database backup path.
- rollback steps.
- migration approval checklist.
- real table creation gate.
- post-migration readback checks.
- sensitive-field scan requirements.

Actual schema migration should stay deferred to a separately approved phase after 14F.
