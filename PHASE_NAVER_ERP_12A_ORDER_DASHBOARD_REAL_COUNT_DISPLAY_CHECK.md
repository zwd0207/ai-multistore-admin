# Phase Naver-ERP-12A - Naver Orders and Dashboard Real-Order Count Display Check

## Summary

Phase 12A verified and fixed the Codex2 display path for the current Naver local order state. This phase did not modify Codex1, did not call Naver, did not write local business data, did not execute `real_sync=true`, and did not open formal Naver order sync.

Current backend readonly state:

- `orders_store8=5`.
- Real Naver local orders: 2.
- Isolated mock/test Naver orders: 3.
- `products_store8=5`.
- Dashboard summary order count: 2.
- Dashboard summary local order amount: `829000 KRW`.

## Fixes

- Fixed frontend backend-row platform filtering so adapted rows with display platform `Naver` still match request platform `naver` through `rawPlatform`.
- Removed stale "1 order" wording from Naver order status text.
- Updated Orders page status panel to show the current operational Naver order count dynamically.
- Updated Dashboard Naver cards and todo wording to show controlled order write completion without implying formal batch sync.
- Updated Dashboard todo wording so delivered orders are not described as pending shipment.

## Page Check

Orders page:

- Shows 2 operational Naver orders.
- Shows 3 isolated test orders.
- Shows 1 new order and 1 delivered order.
- Table total is 2 rows.
- Formal order sync remains shown as not open.

Dashboard:

- Shows `订单数=2` with detail `Naver 运营订单`.
- Shows `5 商品 / 2 订单`.
- Shows `订单管理=2 条运营订单`.
- Shows local Naver order amount `829000 KRW`.
- Shows formal product/order batch sync and platform delivery/claim writes as not open.
- The generic todo now uses `新订单 / 待发货` for Naver and notes that delivered orders are not counted as pending shipment.

## Safety Boundary

12A kept all sensitive and write boundaries closed:

- No Naver real API request.
- No `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult` write.
- No Codex1 schema or runtime change.
- No raw response, token, Authorization, request headers, signature, bcrypt output, or client secret exposure.
- No platform dispatch, cancel, return, exchange, refund, sales, settlement, or delivery write.

## Recommended Next Stage

Recommended next phase: `Phase Naver-ERP-12B: Naver order refresh gate UI wording review`.

Purpose:

- Review the existing order refresh gate panel now that there are 2 real Naver local orders.
- Keep it display-only.
- Keep formal order sync and platform writes closed.
