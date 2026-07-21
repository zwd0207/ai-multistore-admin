# Phase ERP-UX-1H - Production Usability Mock Walkthrough

## Summary

Phase ERP-UX-1H performs a mock-data walkthrough of the current production usability direction.

This phase does not modify runtime frontend code, does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

The walkthrough used `VITE_DATA_SOURCE=mock` and checked whether primary pages load, use business-facing Chinese, avoid mojibake, avoid misleading formal-sync claims, and keep technical fields out of the visible main area.

## Scope

Checked mock routes:

- `/dashboard`
- `/orders`
- `/products`
- `/sales`
- `/api-capabilities`
- `/accounts`
- `/logs`
- `/settings`

Additional interaction:

- Opened one Logs detail modal.
- Confirmed before/after JSON details are not expanded by default.

## Results

### Dashboard

Result: pass.

Observed:

- The page loads into `运营工作台`.
- It shows `今日经营摘要`.
- It separates connection, products, orders, inventory, delivery/claims, and sales summary.
- It clearly states formal product/order batch sync and platform write operations are not open.
- No mojibake was observed.
- No console errors were observed.

Note:

- Initial sampling can briefly catch `正在加载工作台...`; after waiting for mock data to settle, the page renders normally.

### Orders

Result: pass.

Observed:

- The page loads into `订单管理`.
- It states formal order batch sync is still not open.
- It explains local operational orders, fulfillment, delivery, claim status, and detail visibility in business language.
- No visible technical enum or guardrail wording was observed in the main area.
- No mojibake was observed.
- No console errors were observed.

### Products

Result: pass.

Observed:

- The page loads into `商品管理`.
- It shows Naver product summary, local product count, inventory reminders, and price/stock change hints.
- It states formal product batch sync is still not open.
- No visible technical enum or raw sync wording was observed in the main area.
- No mojibake was observed.
- No console errors were observed.

### Sales

Result: pass.

Observed:

- The page loads into `销售额统计`.
- It labels Naver sales as local order amount aggregation.
- It explicitly avoids treating order amount as platform settlement, profit, or withdrawable balance.
- No mojibake was observed.
- No console errors were observed.

### API Capabilities

Result: pass.

Observed:

- The page loads into `平台连接状态`.
- It displays platform authorization, seller account, store connection, product reading, order reading, and formal batch sync status in business Chinese.
- Technical details remain folded.
- No visible technical enum was observed in the main area.
- No mojibake was observed.
- No console errors were observed.

### Accounts

Result: pass.

Observed:

- In mock mode the route shows mock account management rather than backend credentials.
- The page loads into `账号管理`.
- Account, role, status, and risk filters are readable.
- No mojibake was observed.
- No console errors were observed.

Note:

- Backend credential wording was covered in `ERP-UX-1F` and is mounted only in backend-source accounts routing.

### Logs

Result: pass with follow-up planned.

Observed:

- The page loads into `高级日志与审计`.
- It explains this is an administrator page and ordinary sellers do not need to inspect technical details.
- Operation log rows are readable.
- One detail modal opens successfully.
- Before/after JSON is behind a folded details section and is not visible by default.
- No mojibake was observed.
- No console errors were observed.

Follow-up:

- `ERP-UX-1G` already recommends a runtime cleanup to frame `SyncLog` as `同步记录` and split operation, sync, backup, and restore records. That remains the best next UX implementation stage.

### Settings

Result: pass.

Observed:

- The page loads into `系统设置`.
- The form sections are readable.
- No mojibake was observed.
- No console errors were observed.

## Technical Field Check

The walkthrough checked the main visible area for common technical leakage:

- `store_id`
- `credential_id`
- `real_sync`
- `real_preview`
- `tested_success`
- `safe_keyword_flags`
- `business_error_hint`
- `capability_scope`
- `path_kind`
- `raw_response`
- `auth_failed`
- `ip_not_allowed`
- `token_auth_failed`
- `product_api_not_allowed`
- `guardrail`
- `dedupe_key`
- `SyncLog`

No blocking visible leakage was observed in the checked mock pages. Technical detail sections remain available where appropriate and folded by default.

## Misleading Copy Check

The walkthrough checked for misleading production claims such as:

- formal batch sync being open.
- product sync being fully available.
- all Naver products already synced.
- order sync being fully available.

No such misleading claim was observed.

## Verification

Completed:

- `VITE_DATA_SOURCE=mock npm.cmd run build`.
- `npm.cmd run encoding:scan`.
- Browser walkthrough of the mock frontend.

Recommended after any runtime change:

- `npm.cmd run build`.
- `VITE_DATA_SOURCE=mock npm.cmd run build`.
- `npm.cmd run encoding:scan`.
- browser walkthrough of changed pages.

## Decision

The mock production usability baseline is acceptable for the current stage.

Recommended next stage:

```text
Phase ERP-UX-1I: Logs runtime readability cleanup
```

This should implement the 1G plan in `Logs.jsx` without Codex1 changes:

- make `同步记录` the seller-facing label for sync logs.
- add a short administrator summary.
- keep JSON and technical details folded.
- avoid claiming full audit coverage until the audit schema is live.
