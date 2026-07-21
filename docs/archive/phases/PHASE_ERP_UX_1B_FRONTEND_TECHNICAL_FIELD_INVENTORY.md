# Phase ERP-UX-1B - Frontend Technical Field Inventory

## Summary

Phase ERP-UX-1B inventories frontend technical fields that can confuse non-technical operators.

This phase is inventory-only. It does not modify runtime frontend code, does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Inventory Method

The scan covered:

- `src/pages/Dashboard.jsx`.
- `src/pages/Orders.jsx`.
- `src/pages/Products.jsx`.
- `src/pages/ApiCapabilities.jsx`.
- `src/pages/BackendCredentialPage.jsx`.
- `src/pages/Logs.jsx`.
- `src/pages/Sales.jsx`.
- `src/components/common/TechnicalDetails.jsx`.
- `src/utils/capabilityStatusMapper.js`.
- `src/services/adapters.js`.
- `src/services/dataProvider.js`.
- `src/services/backendApi.js`.

Search terms included:

- `error_code`, `errorCode`, `http_status`, `httpStatus`.
- `safe_keyword_flags`, `business_error_hint`, `capability_scope`, `path_kind`.
- `store_id`, `storeId`, `credential_id`, `credentialId`.
- `real_preview`, `real_sync`.
- `raw_response_saved`, `raw_data`, `raw_`.
- `mapping_version`, `source_phase`, `dedupe_key`.
- `safe_hash`, `candidate_`, `guardrail`.
- `tested_success`, `SyncLog`.

## Current Boundary

The frontend already has a useful boundary:

- `TechnicalDetails` renders as a collapsed `<details>` block by default.
- Many technical fields are already placed inside `TechnicalDetails`.
- `capabilityStatusMapper.js` maps Naver API errors into business copy before page display.
- Adapters keep technical backend fields available for diagnostics without requiring every page to render them.

This is a good foundation, but several main-page surfaces still show technical wording or ids.

## High-Priority Main-Page Findings

### Orders

File:

```text
src/pages/Orders.jsx
```

Main-page technical leakage:

- `store #{selectedStoreId}` appears in visible period chips.
- `store_id=8` appears in the user-facing complete-field preview restriction message.
- Some visible notes still reference `orders`, `SyncLog`, and `tested_success`.
- Manual approval and refresh-gate panels still expose too much gate mechanics in business cards.
- Coupang order controls still show operator-facing "write local" actions with technical sync framing.

Recommended production cleanup:

- Replace `store #8 · pxg球包店` with the store name only.
- Replace `store_id=8` with "当前仅限 pxg球包店".
- Replace `不写 orders / 不写 SyncLog / 不新增 tested_success` with "本次不会写入业务数据或变更系统记录".
- Replace gate mechanics with "可预览 / 需人工批准 / 暂不可操作 / 已完成".
- Keep raw gate data in `TechnicalDetails`.

### Products

File:

```text
src/pages/Products.jsx
```

Main-page technical leakage:

- `store #{selectedStoreId}` appears in the Coupang product panel.
- Source labels such as `naver_real_sync` and `coupang_real_sync` exist in page-level mappings and should not reach seller-facing text as raw values.
- Naver product technical preview fields are currently mostly inside `TechnicalDetails`, which is acceptable.

Recommended production cleanup:

- Replace visible store id chips with store name only.
- Keep `real_preview`, `real_sync`, `credential_id`, `raw_response_saved`, preview diff counters, and platform comparison flags inside `TechnicalDetails`.
- Use business labels: "小批量测试完成", "正式批量同步未开放", "本次只是预览".

### API Capabilities

File:

```text
src/pages/ApiCapabilities.jsx
```

Current state:

- The result table showing `errorCode` and `httpStatus` is inside `TechnicalDetails`, which is acceptable for now.
- Store readiness cards use business copy for Naver connection issues.
- `credential_id`, `real_api_test_enabled`, `real_api_write_enabled`, and low-level Naver issue details are inside `TechnicalDetails`.

Production risk:

- The page is still conceptually an API capability workbench, so non-technical operators may not understand why it exists.
- If this page remains visible to operators, it needs a business-first summary above the technical table.

Recommended production cleanup:

- Keep the technical table collapsed.
- Rename main page language toward "平台连接检查" rather than "API Capabilities" for operator routes.
- Show business cards first: connection normal, IP not allowed, credentials invalid, permission missing, formal sync not open.

### API Credentials

File:

```text
src/pages/BackendCredentialPage.jsx
```

Current state:

- Business cards already hide secrets and expose Naver connection messages.
- `credential_id`, auth status, configured flags, and connection issue technical items are inside `TechnicalDetails`.

Production risk:

- Credential wording should emphasize what the operator can fix, not how the backend classified the issue.

Recommended production cleanup:

- Keep technical ids in `TechnicalDetails`.
- Main cards should show: "连接资料已配置 / 当前连接异常 / 请检查允许 IP / 请检查 Client ID 和 Secret".

### Sales

File:

```text
src/pages/Sales.jsx
```

Main-page technical leakage:

- `store #{selectedStoreId}` appears in a visible period chip.
- Some preview panels can show technical result labels such as page count and sample ids, but these are inside `TechnicalDetails`.

Recommended production cleanup:

- Replace visible store id chip with store name only.
- Keep `sample_ids`, `store_id`, page count, cursor flags, and API route diagnostics inside `TechnicalDetails`.
- Continue warning that order amount is not settlement, profit, or withdrawable balance.

### Dashboard

File:

```text
src/pages/Dashboard.jsx
```

Current state:

- Most technical Naver ERP fields appear inside `TechnicalDetails`.
- Main sections are already business-oriented: product status, inventory, delivery, claims, sales, and formal sync boundary.

Production risk:

- Dashboard has many sections and can still feel like a verification dashboard instead of a daily workbench.
- Technical details should remain collapsed and not become the primary way operators understand state.

Recommended production cleanup:

- Reorder into daily action hierarchy:
  - connection issue.
  - new orders.
  - pending shipment.
  - claims.
  - low stock.
  - sales summary.
  - sync safety status.
- Keep inventory raw flags, platform API flags, capability details, and source metadata in `TechnicalDetails`.

### Logs

File:

```text
src/pages/Logs.jsx
```

Current state:

- Logs is an administrator/audit-style page.
- It intentionally allows `SyncLog` and JSON before/after data in collapsed technical sections.
- `selected_store_id` and `sync_log_total` are inside `TechnicalDetails`.

Production risk:

- If exposed to daily operators, "SyncLog" and JSON before/after payloads are too technical.

Recommended production cleanup:

- Split future logs into:
  - operator activity timeline.
  - technical audit details.
- Keep JSON payloads collapsed.
- For operator views, show action label, actor, time, result, recoverability, and next step.

## Data-Layer Fields To Keep But Not Render Directly

These fields are useful in adapters/services and can remain available:

- `storeId`, `credentialId`.
- `errorCode`, `httpStatus`.
- `businessErrorHint`, `safeKeywordFlags`.
- `capabilityScope`, `pathKind`.
- `rawResponseSaved`.
- `mappingVersion`.
- `sourcePhase`.
- `dedupeKey`.
- `testedSuccessWritten`.
- `real_preview`, `real_sync` request payload fields.

Rule:

```text
Allowed in data layer and TechnicalDetails; not allowed in primary cards, page headings, empty states, or seller-facing table columns.
```

## TechnicalDetails Findings

`src/components/common/TechnicalDetails.jsx` currently:

- renders a collapsed `<details>` block.
- stringifies object values.
- does not itself redact sensitive values.

This is acceptable only because upstream payloads are expected to be sanitized.

Future hardening should:

- add a small deny-list redaction pass for labels and values.
- prevent accidental rendering of token, Authorization, headers, signature, client_secret, raw response, full private ids, phone, and address values.
- optionally label the component as "高级详情" in operator-facing routes.

## Priority Cleanup List

P0:

- Remove visible `store #...` chips from Orders, Products, and Sales.
- Replace `store_id=8` visible copy in Orders.
- Keep `errorCode` / `httpStatus` result tables collapsed.

P1:

- Rewrite Orders gate wording from technical write blockers to business-safe statuses.
- Clean up visible `SyncLog` / `tested_success` references in seller-facing order copy.
- Clarify API Capabilities as platform connection status for non-technical users.

P2:

- Add TechnicalDetails redaction hardening.
- Split Logs into operator timeline vs technical audit view.
- Normalize source labels such as `naver_real_sync` into business labels everywhere.

## Recommended Next Phase

Recommended next phase:

```text
Phase UX-ERP-1A: Orders production usability cleanup
```

Reason:

Orders has the highest operator impact and the clearest main-page technical leakage: visible store ids, `store_id=8`, write-gate mechanics, and technical no-write counters. Cleaning Orders first will make the ERP feel less like a test console and more like a daily operations tool.
