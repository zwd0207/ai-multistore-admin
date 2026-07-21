# Phase Naver-Product-Batch-1T: Product Rollback Readonly Report UI Route Integration

Purpose: connect the Products rollback report panel to the local readonly rollback-report route.

Implemented behavior:

- `dataProvider.getNaverProductRollbackReadonlyReport(...)` calls the backend route in backend mode.
- Mock mode returns an equivalent readonly response without platform calls.
- The Products page shows the report as local review evidence.
- Technical route and write flags remain folded in `TechnicalDetails`.

Safety boundary:

- No restore is executed.
- No product, order, audit, SyncLog, or tested-success row is written.
- No Naver API call is made.
- Formal product batch sync remains closed.
