# Phase ERP-Batch-2S - Approval Decision Audit Linkage Readonly API Local Implementation Plan

## Goal

Plan a future local readonly route for reviewing approval-decision audit linkage.

## Planned Route

```text
POST /api/v1/batch/approval-decision/audit-linkage/readonly-check
```

## Boundary

This phase is plan-only. It does not add the route, does not write audit rows, does not approve execution, and does not open product/order batch sync.

Any later route must stay readonly and show business-readable review readiness only.
