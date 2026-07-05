# Phase Shipping-6B: Tracking-number to local order matching mock gate

Purpose: implement a readonly gate that compares tracking rows with local orders.

The gate returns:

- total tracking rows
- matched order count
- unmatched order count
- duplicate tracking row count
- row-level match status

Safety boundary:

- `shipment_writeback_called=false`
- `orders_updated=false`
- `real_database_written=false`
- `real_api_called=false`
- `platform_writes_enabled=false`

This phase is evidence-only.
