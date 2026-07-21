# Phase Shipping-1F: Logistics Inventory Mapping Mock Gate

## Purpose

Add the first mock gate for logistics inventory-code matching. The gate checks whether Naver unshipped-order candidates can be matched to logistics-provider inventory codes by product name plus option name.

## Implemented

- Added `src/utils/shippingAssistant.js`.
- Added `buildUnshippedOrderCandidates(...)`.
- Added `buildLogisticsInventoryMappingMockGate(...)`.
- Added clean Shipping mock data in `src/data/shippingMockData.js`.

## Gate Behavior

The gate returns business counts:

- unshipped candidate count
- matched inventory-code count
- unmatched mapping count
- stock attention count
- export-ready count

The first matching key is:

```text
normalized_product_name + normalized_option_name
```

The helper keeps the future extension path open for platform product ids, option ids, internal SKU, logistics SKU, and manual override.

## Boundary

- No real Naver API call.
- No database write.
- No schema migration.
- No SyncLog write.
- No tested-success write.
- No operation-audit row write.
- No formal order sync.
- No platform shipment write.

