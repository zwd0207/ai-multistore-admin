# Phase ERP-UX-1A - Frontend Production Usability Plan

## Summary

Phase ERP-UX-1A defines the frontend production usability direction for ERP v1.0.

This phase is planning-only. It does not modify runtime frontend code, does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Goal

The frontend must become usable by non-technical operators.

Operators should be able to understand:

- What needs attention today.
- Which orders need action.
- Which products or inventory items are risky.
- Whether platform connection problems affect daily work.
- Whether a local write or refresh is available, blocked, or awaiting approval.
- What is safe to do next.

They should not need to understand:

- backend enum names.
- safe hashes.
- raw status fields.
- HTTP status codes.
- credential ids.
- store ids.
- `real_preview`.
- `real_sync`.
- guardrail internals.
- migration or dry-run mechanics.

## User Types

Primary user:

- Daily store operator.
- Needs clear tasks, business status, and safe manual actions.
- Should see Chinese business language first.

Secondary user:

- Owner or manager.
- Needs totals, risk summary, sales amount, backup/audit confidence, and manual approval status.

Technical user:

- Needs raw enums, ids, safe hashes, gate details, and backend diagnostics.
- These details should stay in `TechnicalDetails`, advanced panels, or diagnostic-only views.

## Page Principles

Main page content should answer business questions:

- Is the store connected?
- Are there new orders?
- Are any orders waiting for shipment?
- Are there cancel, return, or exchange requests?
- Are products out of stock or low stock?
- Did price or stock change?
- Is formal sync open or still closed?
- Is there a manual approval action waiting?

Main page content should not show technical mechanisms by default:

- `error_code`.
- `http_status`.
- `safe_keyword_flags`.
- `business_error_hint` raw object.
- `capability_scope`.
- `path_kind`.
- `real_preview`.
- `real_sync`.
- `store_id`.
- `credential_id`.
- `external_product_id`.
- `productOrderId`.
- safe hashes.
- `dedupe_key`.
- `mapping_version`.
- `source_phase`.
- raw enum fields.

## Page Plan

### Dashboard

Production goal:

- Show a daily action summary.
- Prioritize work: connection issue, new orders, pending shipment, claims, low stock, sales, backup/audit confidence.
- Avoid turning the Dashboard into a technical status board.

Main display should include:

- Store connection state in business language.
- Naver product small-batch status.
- Operational order count.
- New orders.
- Pending shipment.
- Delivery issues.
- Cancel / return / exchange requests.
- Low stock and out-of-stock count.
- Local order-based sales summary.
- Formal sync status as a plain safety note.

Advanced details:

- backend source.
- raw capability result.
- technical error enum.
- sync gate status.

### Orders

Production goal:

- Operators should see which orders need action and what state each order is in.
- Order details can show complete business fields when allowed, but technical routing stays hidden.

Main display should include:

- Order status label.
- Payment status.
- Delivery status.
- Claim status.
- Product and option text.
- Quantity.
- Amount.
- Buyer/receiver business fields according to the current privacy policy.
- Timeline summary.
- Manual approval status in plain language.

Advanced details:

- raw Naver enums.
- safe hashes.
- source phase.
- mapping version.
- refresh gate result.
- readonly preview metadata.

### Products and Inventory

Production goal:

- Operators should understand product health and inventory urgency.

Main display should include:

- Product name.
- Status label.
- Price.
- Stock.
- Out-of-stock or low-stock tag.
- Price/stock change hint.
- Latest local sync time.
- Formal product batch sync closed note.

Advanced details:

- platform ids.
- sanitized raw metadata.
- preview counts.
- would-create/update/refresh-only categories.

### Credentials and API Status

Production goal:

- Operators should know whether the platform connection is healthy and what to fix.

Main display should include:

- "Naver API request IP is not allowed" as business copy.
- "Naver credentials may be invalid" as business copy.
- "Naver API permission is insufficient" as business copy.
- "Naver product API is not available or not enabled" as business copy.
- Last checked time.
- Next recommended action.

Advanced details:

- `error_code`.
- `http_status`.
- `safe_keyword_flags`.
- capability scope.
- path kind.

### Logs, Audit, Backup, and Restore

Production goal:

- Operators should see what happened without needing to read raw technical payloads.

Main display should include:

- Action label.
- Actor label.
- Time.
- Store.
- Result.
- Recoverability status.
- Backup available or not.
- Restore drill verified or not.

Advanced details:

- correlation id.
- request id.
- safe changed field names.
- safe counts.
- backup SHA-256.
- technical reason code.

## Business Copy Rules

Use business-first Chinese text.

Examples:

- "当前连接异常，请检查平台连接资料或 API 设置。"
- "当前有新订单需要处理。"
- "有订单等待发货。"
- "发现退货请求，请进入订单查看。"
- "库存不足，请检查补货。"
- "该操作需要人工批准后才能执行。"
- "正式批量同步仍未开放。"
- "本次只是预览，不会写入数据。"

Avoid exposing these phrases on main pages:

- `auth_failed`.
- `ip_not_allowed`.
- `token_auth_failed`.
- `product_api_not_allowed`.
- `real_sync=true`.
- `candidate_new`.
- `guardrail`.
- `safe_hash`.
- `dedupe_key`.
- `tested_success`.

## Safety Messaging

Safety notes should be short and operator-readable.

Preferred:

```text
正式批量同步未开放。
```

```text
该操作需要人工批准，并会先创建数据库备份。
```

Avoid:

```text
real_sync=true is blocked by guardrail.
```

```text
candidate_new requires selected hash approval.
```

## Technical Details Boundary

`TechnicalDetails` should be:

- collapsed by default.
- clearly labeled as technical details.
- absent from top-level summary cards unless opened.
- safe-scanned for secrets and raw response values.

Allowed in `TechnicalDetails`:

- error code.
- HTTP status.
- safe keyword flags.
- raw enum.
- safe hash.
- source phase.
- mapping version.
- dedupe key.
- count summaries.

Not allowed anywhere:

- tokens.
- Authorization values.
- headers.
- signatures.
- bcrypt inputs.
- client secrets.
- raw platform responses.
- unsafe full ids where current page policy forbids them.
- buyer/receiver privacy outside approved detail contexts.

## Recommended Execution Order

1. `Phase UX-ERP-1A: Orders production usability cleanup`.
2. `Phase UX-ERP-1B: Dashboard production todo hierarchy`.
3. `Phase UX-ERP-1C: Inventory and order action center`.
4. `Phase UX-ERP-1D: Manual approval workflow display`.
5. `Phase UX-ERP-1E: Error and empty-state production polish`.
6. `Phase UX-ERP-1F: TechnicalDetails boundary hardening`.
7. `Phase UX-ERP-1G: Logs and audit readability plan`.
8. `Phase UX-ERP-1H: Backup and restore status display plan`.
9. `Phase UX-ERP-1I: Production mock walkthrough`.
10. `Phase UX-ERP-1J: Operator handoff checklist`.

## Acceptance Criteria For Later Implementation

Each implementation phase should verify:

- Main pages use business Chinese copy.
- Technical enums do not appear in primary cards, tables, or empty states.
- Advanced details are collapsed by default.
- No misleading copy says formal batch sync is open.
- No raw response, token, secret, header, or signature appears.
- Error states include a next action.
- Empty states explain whether there is nothing to do or data is not connected yet.
- Mock and backend data sources both render without blank screens.
- Encoding scan passes.
- Build passes when runtime code changes.

## Non-Goals

This phase does not:

- implement UI changes.
- add buttons.
- add write operations.
- change Codex1 APIs.
- change database schema.
- call Naver or Coupang.
- open formal product sync.
- open formal order sync.
- implement email, appeals, or deep AI automation.

## Recommended Next Phase

Recommended next phase:

```text
Phase UX-ERP-1A: Orders production usability cleanup
```

Reason:

Orders are the most operator-facing workflow. Cleaning order list/detail language first gives the largest usability gain and reduces confusion around safe hashes, preview gates, status timelines, and manual approval states.
