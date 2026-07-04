# Phase Naver-Product-Batch-1D: Product stock-change mock write gate

## Purpose

Add a private mock gate for future stock-only Naver product updates.

## Implemented Gate

Codex1 now has:

```text
_evaluate_naver_product_stock_change_mock_write_gate(...)
```

The helper verifies:

- private verification scope
- `store_id=8`
- dry-run evidence is present and safe
- changed fields are exactly `stock_quantity`
- approved changed fields match observed changed fields
- `would_update > 0`
- `would_create = 0`
- `would_skip = 0`
- backup evidence is verified
- audit and rollback plans are ready
- admin role has `products.batch_sync_write` approval

## Boundary

The mock gate never writes products, orders, SyncLog, tested-success rows, audit rows, or timeline events. Passing status only means the stock-only update is ready for a later separately approved write phase.

