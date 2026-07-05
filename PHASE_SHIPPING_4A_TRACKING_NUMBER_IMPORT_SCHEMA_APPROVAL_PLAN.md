# Phase Shipping-4A: Tracking-Number Import Schema Approval Plan

## Purpose

Approve the next safe direction for tracking-number import without changing the database schema yet.

## Decision

The future tracking import flow should stay store-scoped and platform-aware:

- `store_id`
- `platform`
- `file_type=tracking_upload`
- `file_format=xlsx`
- `order_reference`
- `product_order_reference`
- `logistics_inventory_code`
- `carrier`
- `tracking_number`
- `shipped_at`
- `row_status`
- `operator_note`

## Boundary

This phase does not migrate schema, parse real files, write tracking numbers, update orders, call Naver shipment APIs, or execute shipment/cancel/return/exchange write operations.
