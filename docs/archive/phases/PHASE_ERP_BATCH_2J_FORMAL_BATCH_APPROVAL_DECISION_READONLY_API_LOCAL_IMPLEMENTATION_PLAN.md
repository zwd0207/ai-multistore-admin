# Phase ERP-Batch-2J: Formal Batch Approval Decision Readonly API Local Implementation Plan

## Purpose

Plan a future local readonly API for formal batch approval decision review. This phase does not implement the route.

## Planned Route

```text
POST /api/v1/batch/approval-decision/readonly-check
```

## Planned Behavior

The route should return:

- Business decision status.
- Store and target scope.
- Readonly evidence readiness.
- Approval-audit evidence readiness.
- Backup and rollback evidence.
- Permission and manual approval requirements.
- Sensitive scan and readback requirements.
- Safety flags showing no execution is approved.

## Boundary

- No route in this phase.
- No schema change.
- No product/order write.
- No SyncLog, tested-success, timeline, or audit-row write.
- No platform write.

## Next Step

A later phase may implement the route after the mock gate contract is approved.
