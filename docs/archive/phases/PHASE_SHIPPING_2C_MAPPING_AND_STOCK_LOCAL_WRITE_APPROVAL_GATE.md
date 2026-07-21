# Phase Shipping-2C: Mapping and Stock Local Write Approval Gate

## Purpose

Validate mapping and stock write requests before any local database write.

## Gate Rules

- `manual_approval=true` is required.
- `store_id` and `platform` are required.
- Product name, option name, logistics inventory code, provider name, and stock quantity must be safe business fields.
- Full platform order ids, buyer or receiver privacy, address, token, Authorization, headers, signature, client secret, and raw response are blocked.

## Result

The gate can return `mapping_stock_write_gate_ready`, but it does not write rows itself.
