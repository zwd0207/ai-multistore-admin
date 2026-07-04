# Phase Naver-Product-Batch-1Q: Product Rollback Readonly Report Backend Route Plan

Purpose: plan the local backend route that exposes product rollback readiness as a readonly report.

Planned route:

```text
POST /api/v1/batch/naver/products/rollback-readonly-report
```

Safety boundary:

- The route may show backup evidence, stock-only impact, rollback checklist, temporary restore planning, readback planning, and sensitive-scan planning.
- It must not execute restore.
- It must not touch the production database.
- It must not write products, orders, audit rows, SyncLog, or tested-success rows.
- It must not open formal product batch sync.

This phase is plan-only; implementation is handled by `Naver-Product-Batch-1R`.
