# Phase ERP-Batch-2H: Formal Batch Approval Decision Readonly UI Implementation

## Purpose

Add an Orders page readonly panel that explains formal batch approval decisions in language an operator can understand.

## Implemented

- Added an Orders panel named `正式批量审批决策只读记录`.
- The panel shows decision status, execution switch status, readonly candidate evidence, backup manifest, permission gate, rollback report, sensitive scan, and post-write readback.
- The panel has no execute button and does not call Naver.
- Technical fields are folded in `TechnicalDetails`.

## Boundary

- No real API call.
- No product/order write.
- No SyncLog, tested-success, or audit-row write.
- No formal product/order batch execution.

## Result

Non-technical operators can see what is still required before formal batch writes without mistaking the page for an execution approval screen.
