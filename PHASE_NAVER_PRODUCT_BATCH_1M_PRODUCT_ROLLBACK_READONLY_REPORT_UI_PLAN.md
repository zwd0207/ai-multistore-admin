# Phase Naver-Product-Batch-1M: Product Rollback Readonly Report UI Plan

## Purpose

Plan a future operator-facing UI surface for the product rollback readonly report created by the rollback report mock gate.

## UI Direction

The UI should show a simple business report:

- Backup evidence status.
- Stock-only write summary.
- Changed product count.
- Rollback checklist readiness.
- Temporary restore drill plan.
- Readback verification plan.
- Sensitive scan plan.
- Formal product batch sync remains closed.

## Technical Details Boundary

The main UI must not show raw technical payloads. Fold these fields into TechnicalDetails or an advanced diagnostics section:

```text
phase
skip_reason
updated_count
created_count
rollback_drill_ready
backup_evidence_verified
operation_audit_rows_written
formal_product_sync_open
```

## Not Approved

- Real restore.
- Production database restore target.
- Product writes.
- Product formal batch sync.
- Platform write calls.

## Result

This phase is a UI plan only. No Codex2 runtime implementation is required yet.
