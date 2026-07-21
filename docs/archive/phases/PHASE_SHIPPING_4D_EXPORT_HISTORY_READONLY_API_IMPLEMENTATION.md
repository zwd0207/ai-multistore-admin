# Phase Shipping-4D: Export History Readonly API Implementation

## Purpose

Implement the local export-history read-only route.

## Implemented Route

`GET /api/v1/shipping/export-history`

Supported filters:

- `store_id`
- `platform`
- `limit`
- `offset`
- `include_rows`

## Safety

The route is read-only and returns `tracking_number_import_open=false`, `shipment_writeback_open=false`, and `real_database_written=false`.
