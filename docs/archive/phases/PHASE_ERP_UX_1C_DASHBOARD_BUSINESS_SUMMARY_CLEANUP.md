# Phase ERP-UX-1C - Dashboard Business Summary Cleanup

## Summary

Phase ERP-UX-1C cleans up the Dashboard business summary hierarchy for production usability.

This phase modifies Codex2 frontend only. It does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Changes

- The Naver Dashboard now puts the business-first daily summary before generic statistics.
- The top Naver summary title is now `今日经营摘要`.
- The summary focuses on daily operator priorities:
  - connection health.
  - local products.
  - local operational orders.
  - inventory alerts.
  - delivery and claims.
  - local order amount.
- Generic `StatGrid` is still available, but for Naver stores it appears after the daily business summary and todo/risk blocks.
- Backend mode no longer shows a visible `数据源 backend` chip in the Dashboard header.
- Mock mode still indicates `演示数据`.
- Main Dashboard copy no longer exposes `store #...`, `store_id`, `real_sync`, `SyncLog`, or `tested_success`.
- Technical fields remain available only inside collapsed `TechnicalDetails`.

## Business Copy Adjustments

Seller-facing text was softened from validation language to operations language:

- `商品小批量写入测试` became product stability / local product status in the main Dashboard.
- `订单受控写入测试` became local operational order status.
- `只读检测无阻断` became `连接检查无阻断`.
- `Naver 销售 / 结算接口未接入` became `Naver 销售 / 结算数据待接入`.

## Safety Boundary

The Dashboard still states that:

- formal product batch sync is not open.
- formal order batch sync is not open.
- Naver shipment / claim platform writes are not open.
- local order amount is not settlement, profit, or withdrawable balance.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.

Manual page checks should confirm:

- Dashboard opens in backend and mock mode.
- Naver store starts with business summary, not technical statistics.
- Main Dashboard does not show technical ids or sync gate internals.
- Technical diagnostics remain folded in `TechnicalDetails`.
