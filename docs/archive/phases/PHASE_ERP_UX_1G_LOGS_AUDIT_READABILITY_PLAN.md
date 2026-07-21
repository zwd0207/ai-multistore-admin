# Phase ERP-UX-1G - Logs and Audit Readability Plan

## Summary

Phase ERP-UX-1G defines how Logs and Audit should read in the production ERP UI.

This phase is planning-only. It does not modify runtime frontend code, does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

The production goal is:

```text
Let operators understand what happened, who did it, whether it succeeded, and whether recovery evidence exists.
```

## Current State

The current Logs page already has a reasonable administrator boundary:

- The page title is `高级日志与审计`.
- Backend mode shows a SyncLog summary block.
- SyncLog technical metadata such as `selected_store_id` and `sync_log_total` is inside folded `TechnicalDetails`.
- Mock operation log detail keeps JSON before/after payloads inside folded `TechnicalDetails`.
- Daily operator pages should not depend on this screen for normal work.

Related backend planning already exists:

- `ERP-Audit-1A` defines the local operation audit log purpose.
- `ERP-Audit-1B` proposes the future `operation_audit_logs` schema.
- `ERP-Audit-1C` adds temporary mock verification for future safe audit writes.
- `ERP-Backup-1A/1B/1C` define backup metadata, retention, and restore dry-run boundaries.

## Readability Problem

The page should not become a raw technical dump for non-technical operators.

High-risk wording and fields for the main visible area:

- `SyncLog`.
- `operation_audit_logs`.
- `store_id`.
- `credential_id`.
- `correlation_id`.
- `request_id`.
- safe hashes.
- raw JSON payloads.
- backend enum names.
- backup SHA-256 values.
- schema or migration terminology.
- raw platform identifiers.
- token, Authorization, headers, signature, client secret, or raw response wording.

These fields can remain in administrator-only technical details after upstream payloads are sanitized.

## Audience Split

### Daily Operator

Needs to know:

- what changed.
- who performed or approved it.
- whether it succeeded.
- whether it affects orders, products, inventory, credentials, backup, or restore.
- what should be done next.

Should not need:

- raw ids.
- hashes.
- HTTP status codes.
- JSON payloads.
- schema details.

### Manager

Needs to know:

- who approved risky actions.
- whether backup evidence exists.
- whether recovery was tested.
- which store and business object were affected.
- whether a blocked operation needs follow-up.

### Administrator

Needs access to:

- safe technical details.
- correlation chain.
- safe reason codes.
- sanitized changed field names.
- backup metadata.
- restore verification results.

## Target Page Shape

Future Logs / Audit should be split into clear business sections:

1. `操作记录`
   - local user/system operations.
   - approvals.
   - blocked actions.
   - credential changes.
   - order/product local writes.

2. `同步记录`
   - sync-style jobs and platform data refreshes.
   - current `SyncLog` can remain here.
   - main text should say `同步记录`, not require users to understand `SyncLog`.

3. `备份与恢复记录`
   - backup created.
   - restore dry-run verified.
   - restore executed, only after explicit approval in a future phase.
   - recoverability status.

4. `高级详情`
   - technical ids.
   - safe hashes.
   - correlation id.
   - request id.
   - safe JSON summaries.
   - backup SHA-256.

## Main Table Columns

Recommended business-first columns:

- `时间`.
- `店铺`.
- `业务对象`.
- `操作`.
- `操作人`.
- `结果`.
- `风险`.
- `恢复证据`.
- `下一步`.

Avoid main columns like:

- `store_id`.
- `correlation_id`.
- `request_id`.
- `raw_status`.
- `reason_code`.
- `source_phase`.
- `SyncLog id`.

## Business Status Labels

Recommended visible labels:

- `已完成`.
- `失败，需要处理`.
- `已阻止，保护数据安全`.
- `等待人工批准`.
- `已创建备份`.
- `恢复演练通过`.
- `不可恢复，需管理员确认`.
- `仅预览，未写入`.

Avoid visible labels:

- `tested_success`.
- `guardrail_blocked`.
- `real_sync=false`.
- `write_enabled=false`.
- `raw_response_saved=false`.
- `sync_log_total`.

## Detail Drawer Plan

Each log detail should answer:

- `发生了什么`.
- `谁操作或批准`.
- `影响哪个店铺`.
- `影响哪个业务对象`.
- `结果是什么`.
- `是否有备份`.
- `是否可恢复`.
- `下一步建议`.

Collapsed advanced details may include:

- safe local ids.
- `correlation_id`.
- `request_id`.
- sanitized changed field names.
- safe counts.
- backup path.
- backup SHA-256.
- safe reason code.
- source phase.

## Sensitive Data Boundary

Logs and audit UI must not display:

- token.
- Authorization.
- request or response headers.
- signature or bcrypt inputs.
- client secret.
- raw platform response.
- full channel number.
- full private platform ids unless a later approved business detail view explicitly allows them.
- buyer/receiver privacy outside approved order detail context.
- full phone number outside approved order detail context.
- full address outside approved order detail context.

The audit view should prefer safe labels, safe hashes, local ids, counts, and field names.

## Interaction Plan

Future runtime cleanup should:

- Rename seller-facing SyncLog wording to `同步记录`.
- Keep `高级日志与审计` as an administrator page.
- Add a short top summary:
  - operations needing review.
  - failed or blocked operations.
  - latest backup evidence.
  - latest restore drill status.
- Add filter presets:
  - `需要处理`.
  - `写入操作`.
  - `备份与恢复`.
  - `连接资料变更`.
  - `Naver 订单`.
  - `Naver 商品`.
- Keep JSON before/after data folded by default.
- Make destructive or restore-related records visually distinct.

## Dependency On Audit Schema

The production audit UI should not pretend full audit coverage exists before the backend table is live.

Until `operation_audit_logs` is implemented:

- show existing operation mock logs as demo/admin records.
- show current sync logs as `同步记录`.
- label future audit sections as `待接入` when data is unavailable.
- do not claim full production audit coverage.

## Recommended Next UX Stages

1. `Phase ERP-UX-1H: Logs runtime readability cleanup`
   - Update Logs page wording and visible columns.
   - Keep technical details folded.
   - No Codex1 changes.

2. `Phase ERP-UX-1I: Backup and restore UI readability plan`
   - Define backup/restore page copy, status labels, and recovery evidence display.
   - Planning-only.

3. `Phase ERP-UX-1J: TechnicalDetails safety hardening plan`
   - Define a frontend deny-list/redaction layer for advanced details.
   - Planning-only before implementation.

4. `Phase ERP-Audit-1D: Audit timeline schema approval plan`
   - Continue backend audit implementation only after UX wording is clear.

## Acceptance Criteria For This Plan

- Logs/Audit main page language is business-first.
- Sync logs are framed as `同步记录`.
- Audit logs are framed around accountability and recoverability.
- Technical ids and raw details stay folded.
- The UI does not imply full audit coverage before backend audit schema exists.
- Formal Naver product/order sync remains closed.
- No runtime code, platform API, local data, schema, or Codex1 changes are made in this phase.
