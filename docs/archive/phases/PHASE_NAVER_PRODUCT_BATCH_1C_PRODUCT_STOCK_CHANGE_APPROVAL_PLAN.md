# Phase Naver-Product-Batch-1C: Product stock-change approval plan

## Purpose

Plan the approval boundary for the 3 Naver product stock changes observed in readonly preview.

## Observed Evidence

The protected readonly product preview returned:

```text
page=1,size=5
matched_existing_count=5
would_create=0
would_update=3
would_refresh_only=2
would_skip=0
changed_fields=stock_quantity
```

`page=2,size=5` returned `success_empty`.

## Approval Boundary

The next writable phase must require:

- exact readonly evidence repeat
- only `stock_quantity` in changed fields
- no product creation
- no skipped candidates
- verified database backup
- admin approval for `products.batch_sync_write`
- audit plan
- rollback plan
- post-write readback
- sensitive scan

This phase does not approve local writes and does not open formal product batch sync.

