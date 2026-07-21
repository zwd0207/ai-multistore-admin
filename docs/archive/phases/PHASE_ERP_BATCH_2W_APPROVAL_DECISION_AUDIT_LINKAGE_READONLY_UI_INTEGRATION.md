# Phase ERP-Batch-2W: Approval Decision Audit Linkage Readonly UI Integration

## Goal

Integrate Codex2 Orders with the approval-decision audit-linkage readonly API.

## Implemented

- Added `backendApi.checkBatchApprovalDecisionAuditLinkageReadonly(...)`.
- Added `dataProvider.checkBatchApprovalDecisionAuditLinkageReadonly(...)` with backend and mock data-source support.
- Added an Orders readonly panel for approval-decision audit linkage.
- The panel shows business wording for audit-linkage readiness and keeps route/phase/write flags folded.

## Safety Boundary

The UI does not add an execution button, does not call Naver, does not execute `real_sync`, does not write products or orders, and does not write audit rows.

