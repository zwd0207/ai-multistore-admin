# Phase Naver-ERP-8A - Naver Order-Based Sales Summary

## Scope

This phase adds a readonly Naver sales summary based only on local Naver operational orders.

It does not call Naver sales, statistics, settlement, order, delivery, claim, cancel, return, exchange, or refund APIs. It does not write orders, products, SyncLog, capability results, sales rows, settlement rows, or database schema. Formal Naver order sync remains closed.

## Implemented

- Extended the local Naver order amount summary with:
  - total local order amount
  - today order amount and order count
  - current-week and current-month order amount
  - store breakdown
  - product breakdown
  - observed canceled-order amount
  - explicit refund, net sales, settlement, profit, and withdrawable-balance boundaries
- Dashboard now shows the richer `Naver 订单金额摘要`.
- Sales page now shows the same Naver order-based summary and local-only boundaries.
- Technical fields stay folded in `TechnicalDetails`.

## Seller-Facing Boundary

- The displayed amount comes from local `orders.order_amount` only.
- It is not Naver settlement amount.
- It is not profit.
- It is not withdrawable balance.
- Canceled-order amount is only an observed order amount tied to canceled orders, not a confirmed refund amount.
- Refund amount and net sales remain unavailable until later fields are verified.

## Safety Boundary

- No real Naver API request in this phase.
- No order write.
- No product write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No sales or settlement table write.
- No cancel, return, exchange, refund, dispatch, or delivery write operation.
- No raw response, token, Authorization, headers, signature, bcrypt output, client secret, full order id, full product id, buyer phone, or buyer address display in summary cards.

## Deferred

- Naver official sales/statistics API preview.
- Naver settlement API preview.
- Confirmed refund amount split.
- Net sales calculation.
- Profit and withdrawable-balance calculation.
- Formal order or sales synchronization.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
