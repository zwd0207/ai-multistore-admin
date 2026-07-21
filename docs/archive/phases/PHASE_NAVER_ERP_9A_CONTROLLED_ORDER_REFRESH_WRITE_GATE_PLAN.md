# Phase Naver-ERP-9A - Controlled Order Refresh Write Gate Plan

## Summary

Codex2 Orders now shows a seller-facing Naver order refresh write gate plan next to the controlled complete-field readonly preview. This phase is planning and gate display only: it does not add a write button, does not call any new backend API, does not modify Codex1, does not write orders, and does not open formal Naver order sync.

The goal is to make the later controlled refresh write path auditable before any database write is approved. Operators can see whether the current selected Naver order has a usable complete-field readonly preview and which manual gates still need approval.

## UI Behavior

- The Orders detail panel now includes `Naver 订单刷新写库门禁计划`.
- The main message remains business-facing:
  - no technical raw response
  - no platform token or request signature
  - no backend stack detail
  - no claim that formal order sync is open
- Before a complete-field readonly preview is available, the gate status stays `待只读预览`.
- If the preview is unavailable or the selected order is not an operational Naver order, the gate status stays `不可写库`.
- If the preview is available, the gate only says the order can enter manual review. It still does not write orders.

## Gate Checklist

The displayed plan requires:

- pxg球包店 verified Naver configuration only.
- One selected local operational Naver order.
- A complete-field readonly preview first.
- A database backup before any later refresh write phase.
- Explicit manual approval before any later refresh write phase.
- A safe refresh whitelist only: order status, payment, delivery, claim, amount, time, and safe product fields.
- No SyncLog write.
- No tested_success write.
- No Naver platform order write operations, including dispatch, cancel, return, exchange, or refund.
- No raw response, token, request headers, Authorization value, client secret, or request signature saved.

## Technical Details Boundary

The technical details accordion may show safe gate metadata only:

- `order_refresh_write_gate_phase=Naver-ERP-9A`
- `planned_only=true`
- selected store and credential identifiers
- preview availability and selected preview window
- `requires_user_approval=true`
- `requires_db_backup=true`
- write capability flags all false
- `raw_response_saved=false`
- `formal_order_sync_open=false`

The main page does not display raw error bodies, platform secrets, request headers, full sync payloads, or backend-only diagnostic structures.

## Later Phase Sketch

- `Phase Naver-ERP-9B`: mock and UI review of the refresh gate checklist, still no real API and no database write.
- `Phase Naver-ERP-9C`: repeat the readonly complete-field preview for the selected order window, still no database write.
- `Phase Naver-ERP-9D`: only if separately approved, backup the database and refresh one selected local Naver order using the safe whitelist.

## Safety Statement

This phase does not execute a real Naver request, does not write `orders`, does not write `products`, does not write `SyncLog`, does not add `tested_success`, does not change database schema, and does not change Codex1. Formal Naver order sync remains closed.
