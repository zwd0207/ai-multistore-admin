# Phase ERP-Batch-2N - Approval Decision Readonly API Frontend Integration

## Goal

Connect the Orders formal batch approval decision panel to the readonly API through `dataProvider`.

## Completed

- Added `backendApi.checkBatchApprovalDecisionReadonly(...)`.
- Added data-provider adaptation for the approval-decision readonly result.
- Added mock fallback for mock data mode.
- Added runtime Orders panel loading:
  - local Naver order count,
  - batch readonly evidence,
  - approval audit evidence,
  - approval decision readonly result.

## User-Facing Behavior

The main Orders page now states that approval decision materials are ready for review when the readonly API passes, while clearly keeping execution closed.

## Safety Result

- No Naver API call.
- No local order/product write.
- No SyncLog/tested-success/audit-row write.
- No formal batch execution approval.
- Technical fields stay folded in `TechnicalDetails`.
