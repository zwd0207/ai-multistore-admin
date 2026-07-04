# Phase ERP-Batch-2B: Formal Batch Sync Checklist UI Display

## Goal

Display the formal batch sync operator checklist in Codex2.

## Implementation

The Orders page now shows a readonly panel named:

`正式批量同步操作员检查清单`

The panel lists the core gates:

- human approval
- store permission
- database backup
- readonly candidates
- field whitelist
- duplicate protection
- rollback plan
- audit evidence

## Safety Boundary

The panel is display-only.

It keeps:

- `real_api_called=false`
- `real_database_written=false`
- `products_written=false`
- `orders_written=false`
- `sync_log_written=false`
- `tested_success_written=false`
- `operation_audit_rows_written=false`
- `formal_product_sync_open=false`
- `formal_order_sync_open=false`
- `platform_writes_enabled=false`

## Result

Operators can see what must be completed before formal batch sync, without confusing the checklist with approval or execution.
