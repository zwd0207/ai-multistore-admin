# Phase ERP-Batch-1R: Batch Approval Audit Evidence Readonly Route Mock Gate

Purpose: close the mock-gate boundary before exposing the local readonly batch approval audit-evidence route.

Scope:

- Reuse the existing batch approval audit evidence gate.
- Require readonly evidence, approval context, and audit evidence plan.
- Keep the future route readonly.
- Do not write audit rows, orders, products, SyncLog, or tested-success rows.
- Do not call platform APIs.
- Keep formal product and order batch sync closed.

Gate result:

- `operation_audit_rows_planned=true`
- `operation_audit_rows_written=false`
- `orders_written=false`
- `products_written=false`
- `formal_sync_open=false`

This phase is completed by the Codex1 service-level mock gate and verify_all coverage.
