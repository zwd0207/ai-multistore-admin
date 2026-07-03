# Phase Naver-ERP-14D - Order Status Events Schema Proposal

## Summary

Phase 14D proposes the future persistence model for Naver order status history. This phase is proposal-only: it does not modify SQLAlchemy models, does not run migrations, does not change database schema, does not call Naver, does not execute `real_sync=true`, does not write local data, does not modify Codex2 runtime code, and does not open formal Naver order sync.

This proposal follows the production v1 roadmap in the workspace root route document and the 14A/14B/14C timeline work:

- 14A planned the status timeline concept.
- 14B added a private mock mapper for planned events.
- 14C planned Orders UI display.
- 14D now proposes the schema shape only.

## Design Decision

Use a separate `order_status_events` table.

Do not store status history inside `orders.raw_data`.

Reasons:

- `orders` should remain the latest sanitized snapshot.
- status history needs independent ordering, dedupe, and display.
- future audit and restore checks are easier with one row per observed event.
- schema-level uniqueness is clearer than nested JSON history.
- sensitive-field gates can be enforced per event.

## Proposed Table

Table name:

```text
order_status_events
```

Proposed columns:

```text
id                         integer primary key
store_id                   integer not null, foreign key stores.id, indexed
order_id                   integer not null, foreign key orders.id, indexed
platform                   string(50) not null, indexed
external_order_id_hash     string(120) nullable, indexed
external_product_order_id_hash string(120) not null, indexed
event_type                 string(50) not null, indexed
status_raw                 string(60) nullable
status_label_zh            string(120) nullable
payment_status_raw         string(60) nullable
payment_status_label_zh    string(120) nullable
delivery_status_raw        string(60) nullable
delivery_status_label_zh   string(120) nullable
claim_status_raw           string(60) nullable
claim_status_label_zh      string(120) nullable
observed_at                datetime timezone nullable, indexed
source_phase               string(80) not null
source_type                string(80) not null, indexed
mapping_version            string(100) not null
dedupe_key                 string(320) not null
raw_response_saved         boolean not null default false
privacy_fields_redacted    boolean not null default true
address_saved              boolean not null default false
safe_metadata              json nullable
created_at                 datetime timezone not null
updated_at                 datetime timezone not null
```

Recommended SQLAlchemy model name:

```text
OrderStatusEvent
```

## Constraints

Recommended unique constraint:

```text
UniqueConstraint("store_id", "platform", "dedupe_key", name="uq_order_status_event_dedupe")
```

Recommended indexes:

```text
ix_order_status_events_store_platform_observed
  (store_id, platform, observed_at)

ix_order_status_events_order_observed
  (order_id, observed_at)

ix_order_status_events_store_event_type
  (store_id, platform, event_type)

ix_order_status_events_product_order_hash
  (external_product_order_id_hash)
```

Rationale:

- `store_id/platform/dedupe_key` prevents duplicate status events.
- `order_id/observed_at` supports detail-page timeline display.
- `store_id/platform/event_type` supports dashboard counts and claim/delivery filters.
- product-order hash supports refresh write readback and troubleshooting without full IDs.

## Dedupe Key

Use the same logical shape as the 14B mock mapper:

```text
store_id + platform + external_product_order_id_hash + event_type + status_raw + delivery_status_raw + claim_status_raw
```

Store the computed string in `dedupe_key`.

Do not include:

- full order id.
- full product order id.
- buyer fields.
- receiver fields.
- address fields.
- raw response fragments.

## Event Types

Allowed `event_type` values:

```text
order_paid
order_confirmed
dispatch_ready
dispatched
delivering
delivered
cancel_requested
canceled
return_requested
returned
exchange_requested
exchanged
purchase_decided
unknown_status_observed
manual_review_required
```

Unknown statuses should not be inserted by a real write path unless the phase explicitly records a manual-review event. Unknown status must continue to block normal refresh write approval.

## Safe Metadata

`safe_metadata` may contain only:

- `source_window`.
- `candidate_classification`.
- `refresh_gate_phase`.
- `timeline_mapper_phase`.
- `unknown_status_observed`.
- `deduped_event_count`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.

`safe_metadata` must not contain:

- raw Naver response body.
- complete-field preview payload.
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
- token values.
- `Authorization`.
- request or response headers.
- signature or bcrypt output.
- client secret.

## Relationship To Orders

The future model should point to the existing local order row:

```text
order_status_events.order_id -> orders.id
```

The event should also store safe hashes redundantly:

- `external_order_id_hash`.
- `external_product_order_id_hash`.

Reason:

- `order_id` gives stable local joins.
- safe hashes make readback and debugging possible without exposing full IDs.
- if an event is viewed in isolation, it still has enough safe context.

The event must always be bound to `store_id`; no cross-store timeline record is allowed.

## Migration Direction

14D does not migrate.

Future schema implementation should be split:

1. 14E: mock schema gate using a temporary verification database.
2. 14F: real schema approval plan with backup and rollback steps.
3. 14G: actual schema migration after explicit approval.

For SQLite, future migration should:

- back up `backend/codex1.db`.
- create table only if missing.
- create indexes only if missing.
- verify `PRAGMA table_info(order_status_events)`.
- verify unique constraint behavior in a temporary test or controlled migration check.
- avoid dropping or rewriting `orders`.
- keep existing `orders_store8`, `products_store8`, `sync_logs_store8`, and `tested_success_store8` unchanged.

For future PostgreSQL, the same model should move to Alembic rather than ad hoc create-table logic.

## Write Gate Requirements

A future event write may happen only after:

- explicit user approval.
- clean git worktrees.
- database backup.
- fresh readonly preview.
- selected order identity match.
- exactly one local `orders` row for the selected hash.
- privacy gate success.
- status mapping success or explicit manual-review event approval.
- dedupe check confirms no existing equivalent event.

The write must:

- insert at most one event row per approved operation.
- not create or delete orders.
- not write products.
- not write `SyncLog`.
- not add `ApiCapabilityTestResult tested_success`.
- not execute any Naver platform write action.
- not open formal order sync.

## Read API Direction

Future read endpoint can be planned later.

Suggested route:

```text
GET /api/v1/orders/{order_id}/status-events
```

Alternative store-scoped query:

```text
GET /api/v1/orders/status-events?store_id=8&platform=naver&order_id=...
```

Read response must:

- be store-scoped.
- return safe labels and timestamps.
- include safe technical details only when requested or inside a technical payload.
- not return full IDs or privacy fields.

No public route is added in 14D.

## Rollback Direction

Future rollback for schema migration:

- if table creation fails before data insertion, restore DB backup.
- if indexes fail after table creation, either complete index creation or restore backup.
- if event insert later fails validation, delete only the inserted event row or restore backup depending on blast radius.
- never modify existing order rows as part of timeline schema rollback unless that later phase explicitly changed them.

## Acceptance Criteria For Future 14G

Before 14G can be considered complete:

- `order_status_events` table exists.
- indexes and unique constraint exist.
- `orders` table row count unchanged.
- `products` row count unchanged.
- `SyncLog` count unchanged unless a later approved audit phase changes that.
- `tested_success` count unchanged.
- no raw response, token, Authorization, headers, signature, full order id, full product order id, buyer privacy, phone, address, or zip code appears in event rows.
- `verify_all.py` passes.
- encoding scan passes.
- git status is clean after commit.

## Next Stage

Recommended next phase: `Phase Naver-ERP-14E: Order status events mock schema gate`.

Purpose:

- Create mock/test-only coverage for the proposed table shape in a temporary database.
- Verify dedupe, safety fields, privacy scan, and no side effects before touching the real schema.
