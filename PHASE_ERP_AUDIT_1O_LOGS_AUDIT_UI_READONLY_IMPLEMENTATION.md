# Phase ERP-Audit-1O - Logs/Audit UI Readonly Implementation

## Summary

Phase ERP-Audit-1O implements the Codex2 read-only Logs/Audit UI integration planned in 1N.

This phase modifies Codex2 frontend runtime only. It does not modify Codex1 runtime code, database schema, local data, audit rows, products, orders, SyncLog, ApiCapabilityTestResult, platform APIs, backup execution, restore execution, or formal product/order sync gates.

## Implemented

Added read-only frontend API methods:

```text
backendApi.getOperationAuditLogs
backendApi.getOperationAuditLogSummary
dataProvider.getOperationAuditLogs
dataProvider.getOperationAuditLogSummary
```

Allowed backend calls:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
```

No frontend method was added for audit POST, PUT, PATCH, DELETE, export, or detail routes.

## Logs Page Behavior

`src/pages/Logs.jsx` now separates:

```text
审计可读性摘要
操作审计
同步记录
折叠高级详情
```

Backend mode:

- reads the verified local audit API through GET only.
- shows `operation_audit_logs=0` as a normal Chinese empty state.
- keeps SyncLog in a separate `同步记录` section.
- removes the sync-write panel from the Logs page.
- does not show a risk-marking write action for backend audit rows.
- keeps audit diagnostics folded in `TechnicalDetails`.

Mock mode:

- continues to show existing demo operation logs.
- keeps the risk-marking demo action in mock mode only.
- labels the rows as `演示操作记录` so operators do not confuse them with the real audit table.

## Safe Adapter Shape

The new audit adapters map backend rows to UI-safe fields:

```text
time
objectName
module
actionType
operator
status
riskLevel
summary
nextStep
backupEvidence
recoveryEvidence
safetyLabel
changedFields
advancedDetails
```

Main page does not display raw `before_summary`, raw `after_summary`, raw `counts_summary`, raw `safety_flags`, raw JSON payloads, full hashes, full request ids, full platform ids, tokens, Authorization values, headers, signatures, client secrets, buyer/receiver privacy, phones, addresses, or zip codes.

## Readability Cleanup

The visible labels in these shared components were cleaned so the Logs page no longer inherits mojibake-like labels for table loading, empty rows, pagination, table actions, and common status badges:

```text
src/components/common/DataTable.jsx
src/components/common/EmptyState.jsx
src/components/common/Pagination.jsx
src/components/common/StatusBadge.jsx
```

## Runtime Walkthrough

Backend walkthrough:

```text
http://127.0.0.1:5177/logs
```

Observed:

- `审计可读性摘要` visible.
- `操作审计` visible.
- `当前还没有操作审计记录` visible.
- `同步记录` visible.
- no mock sync panel text.
- no raw JSON keywords.
- console errors: 0.

Mock walkthrough:

```text
http://127.0.0.1:5179/logs
```

Observed:

- `审计可读性摘要` visible.
- `演示操作记录` visible.
- backend audit table wording absent.
- mock-only `风险标记` button visible.
- no raw JSON keywords.
- console errors: 0.

Temporary Vite walkthrough servers were stopped after verification.

## Verification

Passed:

```text
npm.cmd run build
VITE_DATA_SOURCE=mock npm.cmd run build
VITE_DATA_SOURCE=backend npm.cmd run build
npm.cmd run encoding:scan
git diff --check
```

Safety scans passed for:

- no audit write/delete/export/detail frontend route.
- no misleading formal sync wording.
- no sensitive marker added in changed lines.
- no mojibake marker in changed files.

Real database read-only count check remained unchanged:

```text
operation_audit_logs=0
products=9
orders=9
sync_logs=47
tested_success_store8=8
order_status_events=0
```

## Still Not Approved

Still closed:

- audit writer integration.
- audit rows for real business operations.
- audit export/delete/detail routes.
- backup execution.
- restore execution.
- formal Naver product/order batch sync.
- Naver shipment, cancel, return, exchange, refund, settlement, or other platform writes.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1P: Logs/Audit UI readonly post-implementation verification
```

1P should re-check the new UI after commit using backend and mock modes, then decide whether to move toward audit writer integration approval or backup manifest implementation.
