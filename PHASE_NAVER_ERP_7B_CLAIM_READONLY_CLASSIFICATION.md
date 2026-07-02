# Phase Naver-ERP-7B - Naver Claim Readonly Classification

## Scope

This phase adds readonly Naver claim classification to Codex2 using local Naver operational orders only.

It does not call Naver, does not write orders or products, does not change Codex1, does not change database schema, does not run `real_sync=true`, and does not open formal Naver order sync or claim write operations.

## Implemented

- Added a claim-specific readonly summary builder on top of the existing Naver order fulfillment summary.
- Dashboard now shows a dedicated `Naver 售后请求只读分类` section with:
  - cancel requests
  - return requests
  - exchange requests
  - canceled orders
  - unknown claim/order statuses
- Dashboard seller todos now include a claim item.
- Orders page uses the same claim summary for the `取消 / 退货 / 换货` card.
- Technical fields remain folded in `TechnicalDetails`.

## Seller-Facing Behavior

- `CANCEL_REQUEST` is shown as a cancel request.
- `RETURN_REQUEST` is shown as a return request.
- `EXCHANGE_REQUEST` is shown as an exchange request.
- `CANCELED` is shown as an already canceled order.
- Unknown claim/order statuses are shown as needing manual review.
- Canceled orders are not treated as confirmed refund amount.

## Safety Boundary

- No real Naver API request in this phase.
- No order write.
- No product write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No cancel, return, exchange, refund, dispatch, or delivery write operation.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Formal Naver order sync remains closed.

## Deferred

- Naver claim API readonly probe.
- Claim detail timeline.
- Refund amount split.
- Automatic cancel / return / exchange handling.
- Any platform claim write operation.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
