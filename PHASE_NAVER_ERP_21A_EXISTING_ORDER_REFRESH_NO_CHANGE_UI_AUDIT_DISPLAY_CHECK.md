# Phase Naver-ERP-21A: Existing-order refresh no-change UI/audit display check

## Purpose

Check that the 20E/20F no-change refresh outcome can be explained to operators without implying formal order sync is open.

This phase is a display and wording check. No runtime UI code is changed.

## Checked Outcome

The current no-change refresh evidence should be presented as:

- "The order was checked against Naver again."
- "No business fields changed."
- "No local order update was forced."
- "The blocked/no-change result was recorded in audit logs."
- "Formal Naver order batch sync remains closed."

It must not be presented as:

- formal order batch sync opened
- order sync fully available
- platform order write executed
- shipment/cancel/return/exchange operation executed
- failed operation requiring seller action

## UI Placement

Recommended display:

- Orders detail: business notice that refresh requires separate approval and backup
- Logs/Audit: audit row summary should show the operation was blocked/no-change with safe next step
- TechnicalDetails: keep correlation id, reason code, route names, permission keys, and safety flags folded

## Current Evidence

The 20E audit chain used correlation id `audit-corr-20e-192b9c67e8` and ended with `local_write_blocked` because `no_business_field_change`.

Counts after 20F:

- `orders_total=10`
- `orders_store8=7`
- `products_store8=5`
- `sync_logs_store8=1`
- `tested_success_store8=8`
- `operation_audit_logs=15`
- `order_status_events=0`

## Boundary

No Naver API call, no local order write, no SyncLog write, no tested-success write, no schema change, no Codex2 runtime change, and no formal sync opening are performed in this phase.

