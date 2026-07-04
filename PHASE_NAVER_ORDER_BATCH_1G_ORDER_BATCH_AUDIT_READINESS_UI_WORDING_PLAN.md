# Phase Naver-Order-Batch-1G: Order Batch Audit Readiness UI Wording Plan

## Purpose

Define the seller-facing wording for future Naver order batch audit-readiness evidence.

## UI Wording Direction

The main UI should say:

- "订单批量审批材料已整理。"
- "当前不会写入订单。"
- "正式订单批量同步仍未开放。"
- "后续写入前需要备份、权限、审计和回读校验。"

## Technical Details Boundary

Keep these folded:

```text
phase
sync_kind
would_create
would_update
would_refresh_only
changed_fields
operation_audit_rows_planned
operation_audit_rows_written
formal_order_sync_open
```

## Result

This phase is wording planning only. It does not call Naver, write orders, or open formal order batch sync.

