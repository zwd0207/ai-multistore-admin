# Phase Naver-ERP-12B - Orders UI Manual Approval Affordance Plan

## Summary

Phase 12B adds a display-only manual approval affordance to the Codex2 Orders page. It makes the future approval boundary visible to a seller/operator without enabling any write path.

This phase did not modify Codex1, did not call Naver, did not write local business data, did not execute `real_sync=true`, and did not open formal Naver order sync.

## UI Behavior

The Orders detail panel now shows a dedicated manual approval status area below the existing Naver order refresh write gate:

- `人工批准入口` explains whether the order can prepare for manual review.
- `批准前置条件` lists the required readonly preview, identity match, database backup, whitelist, and sensitive-field checks.
- `按钮行为` explains that approval and write buttons are placeholders only.
- `同步边界` keeps formal order sync and platform write operations closed.

Two disabled buttons are shown as affordances:

- `人工批准未开放` or `等待单独批准阶段`.
- `刷新写库未开放`.

These buttons have no click handler and cannot call Codex1 or Naver.

## Page Check

Backend-source Orders page check confirmed:

- The page still shows 2 real Naver operational orders.
- The formal order sync card still shows `未开放`.
- The manual approval affordance is visible.
- The approval/write affordance buttons are disabled.
- No complete-field readonly preview was clicked during this phase.
- No real Naver request was triggered by this phase.

## Safety Boundary

12B keeps all write and sensitive-data boundaries closed:

- No `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult` write.
- No Codex1 schema or runtime change.
- No raw response, token, Authorization, request headers, signature, bcrypt output, or client secret exposure.
- No platform dispatch, cancel, return, exchange, refund, sales, settlement, or delivery write.
- Formal Naver order sync remains closed.

## Recommended Next Stage

Recommended next phase: `Phase Naver-ERP-12C: Naver order approval affordance mock walkthrough`.

Purpose:

- Verify the same manual approval affordance in mock mode.
- Demonstrate both blocked and review-ready UI states without calling Naver or writing data.
- Keep all write operations closed.
