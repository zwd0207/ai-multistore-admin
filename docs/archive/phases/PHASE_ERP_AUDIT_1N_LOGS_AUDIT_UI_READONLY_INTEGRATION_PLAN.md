# Phase ERP-Audit-1N - Logs/Audit UI Readonly Integration Plan

## Summary

Phase ERP-Audit-1N defines how Codex2 should integrate the verified read-only audit logs API into the Logs/Audit page.

This phase is planning-only. It does not modify runtime frontend code, Codex1 runtime code, database schema, local data, audit rows, products, orders, SyncLog, ApiCapabilityTestResult, platform APIs, backup execution, restore execution, or formal product/order sync gates.

The backend baseline from 1M is:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
operation_audit_logs=0
POST/PUT/PATCH/DELETE remain 405
```

An empty audit-log response is currently expected and should be shown as a normal business empty state.

## Current Logs Page State

Codex2 already has a business-oriented Logs page:

```text
src/pages/Logs.jsx
```

Current behavior:

- mock mode reads `mockApi.getOperationLogs`.
- backend mode reads backend `SyncLog` through `dataProvider.getSyncLogs`.
- the page separates business-facing summary cards, sync records, operation records, and folded `TechnicalDetails`.
- `TechnicalDetails` already has strict redaction for tokens, Authorization, headers, signatures, raw response fields, full platform ids, buyer/receiver privacy, phones, and addresses.

Current gap:

- backend mode does not yet read `GET /api/v1/operation-audit-logs`.
- backend mode therefore cannot show the real local `operation_audit_logs` empty state.
- mock operation logs and backend SyncLog are still separate from the new read-only audit API.

## Integration Goal

The future runtime implementation should make the Logs/Audit page useful to a non-technical operator:

- show whether any operation audit records exist.
- explain empty audit state in business Chinese.
- keep SyncLog as `同步记录`.
- show operation audit rows as `操作审计`.
- avoid exposing backend enums, raw hashes, JSON summaries, request ids, SHA-256 values, `store_id`, `real_sync`, or other technical gate fields on the main page.
- keep advanced diagnostics folded and redacted.

## Proposed Frontend API Layer

Future Codex2 implementation should add only read methods:

```text
backendApi.getOperationAuditLogs(params)
backendApi.getOperationAuditLogSummary(params)
dataProvider.getOperationAuditLogs(params)
dataProvider.getOperationAuditLogSummary(params)
```

Allowed backend paths:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
```

Forbidden frontend calls:

```text
POST /api/v1/operation-audit-logs
PUT /api/v1/operation-audit-logs
PATCH /api/v1/operation-audit-logs
DELETE /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/{id}
export/download audit logs
```

The first runtime implementation should not add audit write buttons, delete buttons, export buttons, or raw detail endpoints.

## Proposed Adapter Shape

Future adapters should convert backend audit rows into UI-safe rows before rendering.

Main page row fields:

```text
time
businessObject
operation
actor
result
riskOrAttention
summary
nextStep
backupEvidenceLabel
restoreEvidenceLabel
```

Allowed folded advanced fields:

```text
operation_phase
correlation_id_abbrev
request_id_abbrev
target_hash_abbrev
changed_field_labels
safe_summary_labels
backup_sha256_abbrev
restore_sha256_abbrev
status
reason_code
```

Main page must not show:

```text
raw before_summary
raw after_summary
raw counts_summary
raw safety_flags
raw JSON payloads
full correlation_id
full request_id
full target_hash
full platform ids
store_id
real_sync
headers
Authorization
tokens
signatures
raw responses
buyer/receiver names
phones
addresses
zip codes
```

## Empty State

Because the real table is currently empty, the first UI implementation should treat this as a normal state:

Main message:

```text
当前还没有操作审计记录。
```

Description:

```text
后续受控写入、备份、恢复等操作接入后，会在这里显示谁操作了什么、什么时候操作、结果如何，以及是否有备份或恢复证据。
```

The empty state must not read as a failure and must not say that audit writing is already live.

## Page Hierarchy

Recommended `Logs.jsx` structure:

1. `审计可读性摘要`
   - operation audit count
   - needs attention count
   - backup evidence count
   - restore evidence count
2. `操作审计`
   - real backend audit rows in backend mode.
   - mock rows only in mock mode.
   - empty state when backend returns zero rows.
3. `同步记录`
   - existing SyncLog list remains separate.
   - keep sync job details folded.
4. `高级详情`
   - folded and redacted through `TechnicalDetails`.

This order makes accountability first, then sync-history context.

## Error Handling

If the audit API returns a safe backend error, the main page should show business Chinese:

- filter unsupported: `审计记录筛选条件不支持，请使用页面提供的筛选项。`
- filter invalid: `审计记录筛选条件无效，请调整筛选范围后重试。`
- backend unavailable: `操作审计暂时无法加载，请稍后重试或联系管理员。`

Technical details such as `error_code`, HTTP status, and safe diagnostic flags may be folded in `TechnicalDetails`.

## Mock Mode

Mock mode may keep the existing mock operation logs, but labels should clarify:

```text
演示操作记录
```

Mock mode should not imply that real operation audit rows exist in `operation_audit_logs`.

## Safety Gates For Future Implementation

The next runtime phase must verify:

- backend mode calls only the two GET audit endpoints.
- no audit POST/PUT/PATCH/DELETE/export/detail calls are added.
- empty real backend audit table renders as a normal empty state.
- mock mode still works.
- main page does not display raw technical fields.
- `TechnicalDetails` redaction remains active.
- no platform API is called.
- no local database write is triggered.
- no formal product/order sync is opened.

## Acceptance Criteria For 1O

The future `Phase ERP-Audit-1O: Logs/Audit UI readonly implementation` should pass:

```text
npm.cmd run build
VITE_DATA_SOURCE=mock npm.cmd run build
npm.cmd run encoding:scan
```

Manual/backend walkthrough should confirm:

- backend Logs page loads.
- backend audit empty state is business-readable.
- backend SyncLog still displays separately.
- mock Logs page still displays mock operation records.
- no raw audit JSON appears on the main page.
- no sensitive field leaks through folded details.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1O: Logs/Audit UI readonly implementation
```

1O may modify Codex2 runtime frontend only, using the already verified backend read-only audit API. It should not modify Codex1 unless a small API mismatch is discovered and explicitly approved.
