# Phase ERP-Batch-2U: Approval Decision Audit Linkage Readonly API Local Implementation

## Goal

Expose a local readonly API for reviewing whether a formal batch approval decision can be linked to sanitized audit-evidence references.

## Implemented Route

```text
POST /api/v1/batch/approval-decision/audit-linkage/readonly-check
```

The route accepts:

- `approval_decision`
- `audit_linkage_context`
- `readonly_api_context`

## Completed

- Added the request schema.
- Added the FastAPI route.
- Added the local service helper.
- Added verification coverage for success and sensitive-field blocking.

## Safety Boundary

The route is review-only. It does not approve execution, write audit rows, write products, write orders, write SyncLog, write tested-success rows, call Naver, or open formal product/order batch sync.

