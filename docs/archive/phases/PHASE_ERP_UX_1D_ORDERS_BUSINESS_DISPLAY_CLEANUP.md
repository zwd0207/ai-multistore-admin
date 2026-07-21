# Phase ERP-UX-1D - Orders Business Display Cleanup

## Summary

Phase ERP-UX-1D cleans up the Orders page for production usability.

This phase modifies Codex2 frontend display only. It does not modify Codex1, does not call platform APIs during validation, does not write local data, does not change database schema, and does not open formal Naver order sync.

## Changes

- The Naver Orders page now starts with a business-first order overview:
  - local operational order count.
  - fulfillment and after-sales status.
  - new order and pending dispatch counts.
  - delivery status.
  - claim request status.
  - abnormal / unknown order count.
  - detail visibility and formal-sync boundary.
- The main Naver order overview no longer shows `store #...`, `store_id=8`, `real_sync`, `SyncLog`, or `tested_success`.
- Refresh protection details are moved under folded `TechnicalDetails` instead of large seller-facing gate cards.
- The order detail section keeps full order number, product order number, platform product number, buyer, receiver, phone, and address information in the controlled detail area.
- Dashboard and order summary cards remain concise and do not expand full buyer or platform identifiers.
- Orders list controls now show readable Chinese labels for search, refresh, empty state, read-only state, and pagination.

## Business Copy Direction

Seller-facing copy now uses business language:

- `受控写入测试` became local operational order status.
- `完整字段只读预览` became recent order complete information.
- `刷新写库门禁` became refresh protection.
- `不可写库` became not refreshable / requires separate approval.
- Technical write boundaries remain available only in collapsed details.

## Safety Boundary

The page still states that:

- formal Naver order batch sync is not open.
- local order refresh requires a separate phase and explicit approval.
- platform shipment, cancel, return, exchange, and refund writes are not open.
- platform tokens, temporary authorization, request headers, signatures, and raw responses are not displayed.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.
- `git diff --check`.

Page checks should confirm:

- Orders opens in mock mode.
- Naver order summary uses business copy.
- Main Orders page does not show `store #...`, `store_id=8`, `real_sync`, `SyncLog`, or `tested_success`.
- Technical fields remain folded in `TechnicalDetails`.
