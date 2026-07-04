# Phase ERP-Batch-2P - Approval Decision Audit Linkage Mock Gate

## Goal

Add a Codex1 mock gate that proves a future formal batch approval decision can be linked to append-only audit evidence before any execution phase.

## Completed

Codex1 now validates that a future batch approval decision has planned references for:

- Approval decision id.
- Readonly evidence hash.
- Backup manifest.
- Permission evidence.
- Sensitive scan evidence.
- Readback result.
- Rollback report.
- Operator identity hash.
- Store scope.
- Audit correlation id.
- Append-only audit rows.

## Safety Result

- No real API call.
- No product write.
- No order write.
- No SyncLog/tested-success write.
- No timeline write.
- No audit row write.
- No execution approval.
- Formal product/order batch sync remains closed.

Passing the mock gate only means the future audit linkage shape is ready for review.
