# Phase ERP-UX-1E - Products Business Display Cleanup

## Summary

Phase ERP-UX-1E cleans up the Products page for production usability.

This phase modifies Codex2 frontend display only. It does not modify Codex1, does not call platform APIs during validation, does not write local data, does not change database schema, and does not open formal Naver product sync.

## Changes

- The Naver Products page now starts with a business-first product overview:
  - local Naver product count.
  - stock alerts.
  - price / stock change hints.
  - local price / stock visibility.
  - would-create / would-update business counts.
  - refresh-only count.
  - skipped count.
  - formal product sync status.
- The main Products view no longer shows `store #...`, `store_id`, `real_sync`, `SyncLog`, or `tested_success`.
- Product preview, inventory, and price/stock diagnostic fields remain folded in `TechnicalDetails`.
- Product identifiers remain masked in summary and list views.
- The list copy now uses business labels such as `商品名称`, `售价`, `库存`, `平台状态`, `数据来源`, and `最近同步`.
- Coupang product controls no longer show a `store #...` chip.

## Business Copy Direction

Seller-facing copy now uses business language:

- `商品小批量写入测试` became local product status.
- `只读检查` became local business summary wording.
- `dry-run` became preview / observation wording.
- `would_refresh_only` is shown as `仅同步时间刷新`, not a business update.
- Formal batch sync remains clearly marked as not open.

## Safety Boundary

The page still states that:

- formal Naver product batch sync is not open.
- price and stock changes require separate review before any write.
- the page does not display platform secrets, temporary authorization, request signatures, full channel numbers, or raw responses.
- platform product identifiers are masked in summary/list views.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.
- `git diff --check`.

Page checks should confirm:

- Products opens in mock mode.
- Naver product summary uses business copy.
- Main Products page does not show `store #...`, `store_id`, `real_sync`, `SyncLog`, or `tested_success`.
- Technical fields remain folded in `TechnicalDetails`.
- The page does not claim formal Naver product batch sync is open.
