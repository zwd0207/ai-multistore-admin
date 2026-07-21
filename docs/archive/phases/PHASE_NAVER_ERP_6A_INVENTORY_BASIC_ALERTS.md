# Phase Naver-ERP-6A - Naver Inventory Basic Alerts

## Scope

This phase adds basic Naver inventory alerts to Codex2 using local product records only.

It does not call Naver, does not write products or orders, does not change Codex1, does not change database schema, does not run `real_sync=true`, and does not open formal Naver product batch sync.

## Implemented

- Naver product inventory summary now classifies local products into:
  - out of stock: `stock = 0`
  - low stock: `0 < stock < 5`
  - normal stock: `stock >= 5`
  - invalid stock: missing, negative, or non-numeric stock
- Products page shows:
  - total local Naver product inventory coverage
  - out-of-stock / low-stock / normal counts
  - a short attention list for products that need stock review
  - a clear readonly boundary that no Naver inventory write is performed
- Dashboard shows:
  - inventory status inside Naver ERP workbench
  - inventory action in today's seller todo list
  - folded technical fields for threshold rule and readonly boundaries

## Seller-Facing Behavior

- Inventory alerts use local Naver product rows already stored in the system.
- The low-stock threshold is 5 pieces, but stock equal to 5 is treated as normal.
- The page does not claim platform inventory was checked.
- The page does not modify Naver platform stock.
- Formal Naver product batch sync remains closed.

## Safety Boundary

- No real Naver API request.
- No product write.
- No order write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- No complete channel number or sensitive platform identifier is exposed in inventory cards.

## Deferred

- Platform-vs-local inventory comparison.
- Inventory change history.
- Product-level low-stock threshold settings.
- Purchase, warehouse, or replenishment workflows.
- Any platform inventory write operation.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`

