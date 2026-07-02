# Phase Naver-ERP-6B - Naver Product Price / Stock Change Hints

## Scope

This phase adds seller-facing hints for Naver product price and stock changes in Codex2.

It does not call Naver, does not write products or orders, does not change Codex1, does not change database schema, does not run `real_sync=true`, and does not open formal Naver product batch sync.

## Implemented

- Added a product change hint builder for Naver products.
- Products page now shows:
  - current price / stock change status
  - local price / stock coverage counts
  - folded technical fields for changed field names and readonly boundaries
- Dashboard now shows:
  - a Naver ERP workbench card for price / stock change hints
  - a seller todo item for price / stock changes
  - folded technical fields for `would_update`, changed fields, and write protection state

## Current Baseline

- The latest known Naver product dry-run has `would_update=0`.
- Price and stock business fields currently have no detected platform-side changes.
- Local products can still surface operational alerts such as out-of-stock or low-stock from local rows.
- Local inventory alerts are not the same as a platform price / stock difference.

## Seller-Facing Behavior

- When no price or stock business change is detected, the UI says no price / stock change is currently observed.
- If a future dry-run exposes safe changed field names such as `price`, `currency`, or `stock_quantity`, the UI will ask the operator to manually verify before any write.
- The UI does not show raw response data, complete platform product ids, complete channel numbers, tokens, Authorization, headers, signatures, or secrets.

## Safety Boundary

- No real Naver API request in this phase.
- No product write.
- No order write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No raw response persistence or display.
- Formal Naver product batch sync remains closed.

## Deferred

- Platform-vs-local price comparison with newly fetched Naver data.
- Price / stock change history.
- Product-level audit trail for price / stock diffs.
- Any automatic product write or inventory update.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`

