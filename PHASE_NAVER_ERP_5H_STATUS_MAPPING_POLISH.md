# Phase Naver-ERP-5H - Naver Order Complete Field Status Mapping Polish

## Scope

This phase polishes Naver order status presentation after the controlled complete-field readonly preview succeeded with a recent 3-day window.

It does not add automatic Naver requests, does not write orders, does not change database schema, and does not open formal Naver order sync.

## Implemented

- Kept the complete-field preview manual-only on the Orders page.
- Added frontend status aliases for Naver delivery-stage values such as `READY`, `DELIVERING`, and delivery-complete aliases.
- Added an Orders detail fallback so delivery display can use a clearly mapped order status when the delivery status field is missing or unknown.
- Kept complete order number, product order number, product id, buyer/receiver names, phones, zip code, and address limited to the Orders detail panel.
- Kept Dashboard summary-only.

## Backend Mapping Boundary

Codex1 status mapping now recognizes common delivery aliases and can set `delivery_status_derived_from_order_status=true` in readonly complete-field preview metadata when needed. This flag is display-only and must not be used as a platform write instruction.

## Safety Boundary

- No automatic preview on page load.
- No `real_sync=true`.
- No local write from Codex2.
- No `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success` write.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Formal Naver order sync remains closed.

## Validation

- Codex1 `python scripts/verify_all.py`
- Codex2 `npm.cmd run build`
- Codex2 `VITE_DATA_SOURCE=mock npm.cmd run build`
- Codex2 `npm.cmd run encoding:scan`
- Browser walkthrough for backend Orders page:
  - recent 3-day complete-field preview remains manual
  - delivered order shows `配送完成` in the delivery area
  - no `订单数据加载失败`
  - no `[object Object]`
  - no misleading formal-sync-open wording
