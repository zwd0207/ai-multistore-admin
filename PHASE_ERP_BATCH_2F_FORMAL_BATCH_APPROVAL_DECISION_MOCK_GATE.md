# Phase ERP-Batch-2F: Formal Batch Approval Decision Mock Gate

## Purpose

固化正式商品/订单批量写入前的最终审批决策 mock 门禁。它只判断审批材料是否足够进入人工复核，不批准执行、不写库、不调用平台。

## Implemented

- Added `evaluate_formal_batch_approval_decision_mock_gate(...)` in Codex1 sync service.
- The gate requires fresh readonly evidence, approval-audit evidence, backup manifest evidence, rollback readiness, permission gate evidence, field whitelist, duplicate check, sensitive scan, readback planning, and audit correlation planning.
- The gate blocks sensitive markers and any payload that already wrote business rows, audit rows, SyncLog rows, tested-success rows, or platform writes.
- `verify_all.py` covers success, missing backup evidence, stale readonly evidence, missing audit evidence, sensitive marker blocking, and no-write invariants.

## Boundary

- No real API call.
- No order/product write.
- No SyncLog or tested-success write.
- No audit-row write.
- No formal product or order batch execution.

## Result

The system can now prove that a future formal batch decision has enough safe evidence to enter manual review while keeping execution closed.
