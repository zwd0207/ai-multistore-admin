# Phase Naver-ERP-8B - Naver Dashboard ERP Summary

## Scope

This phase adds a seller-facing Naver ERP summary to the Codex2 Dashboard using existing local frontend/backend data only.

It does not call Naver, does not write orders or products, does not write sales or settlement rows, does not change Codex1, does not change database schema, does not run `real_sync=true`, and does not open formal product or order sync.

## Implemented

- Dashboard `Naver ERP 工作台摘要` now starts with a daily summary strip:
  - daily priority
  - local product and order counts
  - pending delivery and claim attention counts
  - local order amount
- Daily priority is selected from:
  - connection issue
  - claim attention
  - pending delivery
  - inventory attention
  - product price/stock change hint
  - no high-priority blocker
- The summary keeps the existing detailed cards for:
  - connection
  - product management
  - price / stock change hints
  - order management
  - inventory alerts
  - delivery / claim
  - order amount
- Dashboard guardrails explicitly show that product batch sync, order batch sync, platform delivery/claim writes, and Naver sales/settlement APIs remain closed.
- Technical fields remain folded in `TechnicalDetails`.

## Seller-Facing Boundary

- Dashboard uses local products, local operational orders, local capability results, and local dry-run summaries.
- Order amount is a local order amount summary only.
- It is not Naver settlement amount, profit, withdrawable balance, confirmed refund amount, or net sales.
- Delivery and claim sections are readonly classification only.
- Product and order formal batch sync remain closed.

## Safety Boundary

- No real Naver API request in this phase.
- No order write.
- No product write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No sales or settlement write.
- No cancel, return, exchange, refund, dispatch, or delivery write operation.
- No raw response, token, Authorization, headers, signature, bcrypt output, client secret, full order id, full product id, buyer phone, or buyer address display in summary cards.

## Deferred

- Dedicated backend ERP summary endpoint.
- Naver official sales/statistics readonly probe.
- Naver settlement readonly probe.
- Dashboard actions for human-approved follow-up workflows.
- Formal Naver product or order synchronization.

## Validation

- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
