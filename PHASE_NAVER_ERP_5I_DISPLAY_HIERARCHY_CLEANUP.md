# Phase Naver-ERP-5I - Naver Order Display Hierarchy Cleanup

## Scope

This phase cleans up the display hierarchy for Naver orders after complete-field readonly preview and status mapping polish.

It does not call Naver, does not write orders, does not change Codex1, does not change database schema, and does not open formal Naver order sync.

## Implemented

- Orders detail panel remains the only normal page area where complete order fields can appear after explicit readonly preview.
- Orders list now focuses on operational local Naver orders and isolates `mock_sync` test rows.
- Dashboard fulfillment and order amount summaries use operational Naver orders only.
- The Naver order status panel reports how many `mock_sync` rows were isolated from seller-facing operational summaries.
- Orders table now includes a lightweight `数据层级` column so the visible row is clearly an operational order.

## Display Boundaries

- Detail panel: may show complete order number, product order number, platform product id, buyer/receiver fields, zip code, and address after manual readonly preview.
- Orders list: shows summary fields only and keeps Naver customer/phone display bounded to local safe values.
- Dashboard: shows aggregate counts and amounts only; it does not expand complete buyer or address fields.
- TechnicalDetails: may show source and count metadata, collapsed by default.

## Safety Boundary

- No automatic Naver request on page load.
- No new real API request in this phase.
- No `real_sync=true`.
- No local write from Codex2.
- No `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success` write.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Formal Naver order sync remains closed.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
- Browser walkthrough:
  - Orders page opens without `订单数据加载失败`
  - Orders list shows operational Naver order summaries only
  - Dashboard keeps complete buyer/address fields out of top-level cards
  - no `[object Object]`
  - no misleading formal-sync-open wording
