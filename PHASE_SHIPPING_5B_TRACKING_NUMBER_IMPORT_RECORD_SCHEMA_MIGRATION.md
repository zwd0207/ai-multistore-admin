# Phase Shipping-5B: Tracking-number import record schema migration

Purpose: migrate local SQLite schema for tracking import records.

New local tables:

- `shipping_tracking_import_batches`
- `shipping_tracking_import_rows`

Required safety fields:

- `tracking_number_import_open=false`
- `shipment_writeback_called=false`
- `orders_updated=false`
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`

Migration rules:

- Back up `codex1.db` before migration.
- Create tables and indexes only.
- Do not create fake import rows.
- Do not write `orders`, `products`, `SyncLog`, or tested-success rows.

Approved next step: Shipping-5C local write mock gate.
