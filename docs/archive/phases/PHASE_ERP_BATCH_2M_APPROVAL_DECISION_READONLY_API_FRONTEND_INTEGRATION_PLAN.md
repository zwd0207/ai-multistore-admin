# Phase ERP-Batch-2M - Approval Decision Readonly API Frontend Integration Plan

## Goal

Plan how Codex2 Orders should consume the local readonly approval-decision API before any future formal product/order batch execution.

## Scope

- Use the existing local readonly API contract: `POST /api/v1/batch/approval-decision/readonly-check`.
- Keep the Orders page business-first: show review readiness, evidence status, and closed execution boundary in seller-readable wording.
- Keep `decision_status`, route flags, write flags, and phase names inside `TechnicalDetails`.
- Provide a mock fallback for `VITE_DATA_SOURCE=mock`.

## Safety Boundary

- No Naver API call.
- No order or product write.
- No SyncLog write.
- No tested-success write.
- No audit-row write.
- No execution button.
- No formal product/order batch sync opening.

## Implementation Target

The next phase may add a `dataProvider.checkBatchApprovalDecisionReadonly(...)` method and route-backed Orders panel state, but it must remain readonly and review-only.
