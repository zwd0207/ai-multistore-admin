# Phase Shipping-2A: Logistics Inventory Mapping Schema Approval Plan

## Purpose

Approve the local schema boundary for the first Shipping Assistant production feature.

## Decision

Use two local tables:

- `logistics_inventory_mappings`: product name plus option name to logistics inventory code.
- `logistics_inventory_items`: logistics inventory code plus manually maintained stock.

Both tables require `store_id` and `platform`. The platform field remains extensible for `naver`, `coupang`, and `future_platform`.

## Safety

Do not store token, Authorization, headers, signature, client secret, raw response, full order id, full product order id, buyer information, receiver information, address, or zip code.

## Status

Approved for local schema migration in Shipping-2B.
