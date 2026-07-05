# Phase Shipping-2J: Tracking-Number Import Contract Plan

## Purpose

Plan the future tracking-number import contract without opening Naver shipment writeback.

## Proposed Future File Type

`file_type=tracking_upload`

Suggested columns:

- `store_id`
- `platform`
- `order_reference`
- `product_order_reference`
- `logistics_inventory_code`
- `carrier`
- `tracking_number`
- `shipped_at`
- `row_status`
- `operator_note`

## Boundary

Tracking-number import is not open yet. This phase does not parse real files, write tracking numbers, update orders, call Naver shipment APIs, or execute shipment/cancel/return/exchange write operations.
