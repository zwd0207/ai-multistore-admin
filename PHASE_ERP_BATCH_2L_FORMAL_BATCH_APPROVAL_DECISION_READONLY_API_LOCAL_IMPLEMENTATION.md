# Phase ERP-Batch-2L: Formal Batch Approval Decision Readonly API Local Implementation

## Purpose

Expose a local readonly endpoint for formal batch approval-decision review.

## Implemented

```text
POST /api/v1/batch/approval-decision/readonly-check
```

The route returns business-readable decision readiness and safety flags for manual review.

## Boundary

- No Naver call.
- No product/order write.
- No SyncLog, tested-success, timeline, or audit-row write.
- No execution approval.
- No platform write.

## Result

Administrators can review formal batch decision readiness through a local readonly API without opening any batch execution path.
