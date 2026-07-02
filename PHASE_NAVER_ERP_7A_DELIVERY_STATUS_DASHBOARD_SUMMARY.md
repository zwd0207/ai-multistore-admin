# Phase Naver-ERP-7A - Naver Delivery Status Dashboard Summary

## Scope

This phase adds a Naver delivery status summary to the Codex2 Dashboard using local Naver operational orders only.

It does not call Naver, does not write orders or products, does not change Codex1, does not change database schema, does not run `real_sync=true`, and does not open formal Naver order sync or delivery write operations.

## Implemented

- Added a delivery-specific summary builder on top of the existing Naver order fulfillment summary.
- Dashboard now shows a dedicated `Naver 配送状态摘要` section with:
  - delivery overview
  - pending delivery
  - in delivery
  - delivered
  - delivery exception / unknown status
  - delivery write protection
- Dashboard seller todos now include a delivery status item.
- Technical fields remain folded in `TechnicalDetails`.

## Seller-Facing Behavior

- Delivery status is summarized from local Naver operational order rows.
- `PAYED` and `PLACE_PRODUCT_ORDER` are treated as pending delivery work.
- `DISPATCHED`, `DELIVERING`, and equivalent states are treated as in delivery.
- `DELIVERED` and equivalent states are treated as delivered.
- Unknown statuses are shown as needing manual review and do not trigger platform writes.

## Safety Boundary

- No real Naver API request in this phase.
- No order write.
- No product write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No dispatch, cancel, return, exchange, or delivery write operation.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Formal Naver order sync remains closed.

## Deferred

- Naver delivery API readonly probe.
- Naver dispatch/write integration.
- Delivery history timeline.
- Delivery carrier and tracking number workflows.
- Automated cancel / return / exchange handling.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`

