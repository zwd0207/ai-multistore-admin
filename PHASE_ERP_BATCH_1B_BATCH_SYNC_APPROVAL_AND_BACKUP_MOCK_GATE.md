# Phase ERP-Batch-1B: Batch sync approval and backup mock gate

## Purpose

Implement a private mock gate for future formal batch sync readiness.

The gate checks:

- sync kind is allowed: Naver order batch, Naver order refresh batch, or Naver product batch
- batch size is inside a conservative limit
- readonly preview evidence is fresh and safe
- raw response is not saved
- privacy fields are redacted
- duplicate checks and field whitelist checks passed
- backup evidence is verified
- audit, rollback, duplicate-protection, failure-isolation, and multi-store-isolation plans are ready
- every target store passes store-scoped permission and sensitive-action approval

## Result

The mock gate can return `formal_batch_gate_ready_for_later_execution`, but it still keeps:

- `formal_sync_open=false`
- `formal_order_sync_open=false`
- `formal_product_sync_open=false`
- `platform_writes_enabled=false`
- `orders_written=false`
- `products_written=false`
- `sync_log_written=false`

This is readiness evidence only, not a production sync opening.

