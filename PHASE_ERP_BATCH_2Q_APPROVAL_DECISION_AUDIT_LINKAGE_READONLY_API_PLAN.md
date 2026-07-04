# Phase ERP-Batch-2Q - Approval Decision Audit Linkage Readonly API Plan

## Goal

Plan a future readonly API for reviewing approval-decision audit linkage.

## Planned Route

```text
POST /api/v1/batch/approval-decision/audit-linkage/readonly-check
```

## Readonly Contract

The route should accept only sanitized approval-decision evidence and audit-linkage context. It should return business-readable readiness and folded technical details.

It must not:

- Approve execution.
- Write products or orders.
- Write SyncLog or tested-success records.
- Write operation audit rows.
- Call Naver or any platform API.
- Store raw responses, tokens, headers, signatures, or secrets.

## Next Boundary

This phase is plan-only. A separate implementation phase is required before adding the route.
