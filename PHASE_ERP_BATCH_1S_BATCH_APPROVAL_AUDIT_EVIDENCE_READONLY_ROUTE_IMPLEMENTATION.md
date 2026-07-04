# Phase ERP-Batch-1S: Batch Approval Audit Evidence Readonly Route Implementation

Purpose: expose a local readonly route for batch approval audit evidence review.

Route:

```text
POST /api/v1/batch/approval-audit-evidence
```

Behavior:

- Accepts normalized readonly evidence, approval context, and audit evidence plan.
- Returns business readiness wording for local review.
- Rejects sensitive markers through the existing gate.
- Writes no audit rows.
- Writes no orders or products.
- Writes no SyncLog or tested-success rows.
- Calls no platform APIs.
- Keeps formal product and order batch sync closed.

Verification:

- OpenAPI contains the route as POST-only.
- verify_all covers success and sensitive-marker blocked responses.
- Database counts remain unchanged.
