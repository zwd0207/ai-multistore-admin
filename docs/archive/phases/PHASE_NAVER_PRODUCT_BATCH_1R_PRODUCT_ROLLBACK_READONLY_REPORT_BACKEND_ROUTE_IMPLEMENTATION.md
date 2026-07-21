# Phase Naver-Product-Batch-1R: Product Rollback Readonly Report Backend Route Implementation

Purpose: expose the Naver product rollback readonly report as a local backend route.

Route:

```text
POST /api/v1/batch/naver/products/rollback-readonly-report
```

Behavior:

- Wraps the existing rollback readonly report gate.
- Returns local review readiness for backup, rollback checklist, readback, and sensitive scan.
- Rejects sensitive markers.
- Executes no restore.
- Writes no products, orders, audit rows, SyncLog, or tested-success rows.
- Keeps formal product batch sync closed.

Verification:

- OpenAPI contains the route as POST-only.
- verify_all covers ready and sensitive-marker blocked responses.
- Database counts remain unchanged.
