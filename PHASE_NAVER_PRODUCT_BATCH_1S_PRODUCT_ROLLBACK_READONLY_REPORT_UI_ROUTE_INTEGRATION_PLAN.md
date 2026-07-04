# Phase Naver-Product-Batch-1S: Product Rollback Readonly Report UI Route Integration Plan

Purpose: plan how the Products rollback report panel should consume the local readonly rollback-report route.

Planned route:

```text
POST /api/v1/batch/naver/products/rollback-readonly-report
```

UI boundary:

- The Products page may show backup, readback, restore-plan, and sensitive-scan readiness in business wording.
- Restore, database touch, product write, and audit write flags stay folded.
- The UI must not execute restore.
- The UI must not write products.
- Formal product batch sync remains closed.

This phase is a plan for a readonly UI integration only.
