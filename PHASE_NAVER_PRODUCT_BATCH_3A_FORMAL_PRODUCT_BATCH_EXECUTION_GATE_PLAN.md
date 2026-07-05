# Phase Naver-Product-Batch-3A: Formal Product Batch Execution Gate Plan

Purpose: define the final operator-facing gate before any future formal Naver product batch write.

Current state:

- Codex1 already exposes `POST /api/v1/batch/naver/products/execution-approval/readonly-check`.
- Codex2 Products already shows product batch execution approval readiness.
- The common formal batch execution chain already exists through preflight, dry-run, final approval, write-boundary, and pre-execution refresh readonly routes.

This phase is a gate plan only. It does not open formal product batch sync.

Required evidence before a later execution phase:

- latest readonly product candidates,
- product field whitelist,
- price/stock/status mapping review,
- duplicate protection,
- store-scoped permission evidence,
- human approval evidence,
- verified database backup,
- rollback report and restore-dry-run reference,
- post-write readback plan,
- sensitive scan evidence,
- audit correlation plan.

Product write boundary:

- Allowed future local fields must stay in the approved product business whitelist.
- Product platform write APIs remain excluded.
- Raw responses, tokens, Authorization, headers, signatures, client secrets, and complete sensitive identifiers must not be saved.
- `SyncLog` and `ApiCapabilityTestResult tested_success` must not be written by the formal product batch execution gate unless a separate phase explicitly approves that behavior.

Operator rule:

Passing readonly approval evidence only means the materials can be reviewed. It is not execution approval. A later explicit execution phase must still re-check backup, permissions, dry-run, audit, readback, rollback, and sensitive scan evidence.

Closed in this phase:

- `formal_product_sync_open=false`
- `products_written=false`
- `operation_audit_rows_written=false`
- `real_api_called=false`
- `real_database_written=false`
- `platform_product_writes_enabled=false`

Recommended next product phase: `Phase Naver-Product-Batch-3B: Product batch execution dry-run evidence runtime repeat`.
