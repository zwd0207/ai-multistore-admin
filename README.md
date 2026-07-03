# AI 多店铺运营与环境管理系统（Codex2）

React + Vite 后台前端，已完成 13 个业务路由、第一至第四阶段页面，以及第五阶段 A 的 Codex1 后端接口适配准备。默认继续使用本地 mock 数据，切换后端数据源不会要求重写页面字段。

## 环境要求

- Node.js 18 或更高版本
- npm 9 或更高版本
- 正式联调时启动 Codex1 FastAPI 后端

## 安装、启动与构建

```bash
npm install
npm run dev
```

开发地址通常为 `http://localhost:5173`。

```bash
npm run build
npm run preview
```

## 数据源配置

Codex1 默认接口：`http://127.0.0.1:8000/api/v1`

当前 Codex2 联调建议接口：`http://127.0.0.1:8011/api/v1`

当前联调 Swagger：`http://127.0.0.1:8011/docs`

在本机创建不提交 Git 的 `.env.local`，按需要设置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8011/api/v1
VITE_DATA_SOURCE=backend
```

`VITE_DATA_SOURCE` 可选值：

- `mock`：默认值，所有已完成页面继续使用本地 Promise mock 接口。
- `backend`：Dashboard、店铺、商品、订单、客服咨询与同步日志读取 Codex1；其他页面继续使用 mock。

修改环境变量后需要重新启动 Vite。商品、订单与客服咨询接口需要 `store_id`；当前 provider 会使用显式传入的 `storeId`，未传时自动选择 Codex1 返回的首个店铺。后续全局店铺选择器接入后可直接覆盖该参数。

## 第五阶段 B 只读联调范围

- Dashboard Summary：后端总览卡片、风险、最近订单及同步日志兼容映射。
- Stores：后端店铺列表。
- Products：按 `store_id` 读取商品列表。
- Orders：按 `store_id` 读取订单，展示脱敏手机号、金额和币种。
- Customer Service：按 `store_id` 读取咨询，详情使用后端只读结构。
- Sync Logs：操作日志页增加 Codex1 同步日志区块，原操作审计 mock 保留。
- AI Daily Context：Dashboard 只展示结构化聚合数据，不调用模型，不生成日报文案。

backend 模式下，上述业务列表隐藏新增、编辑、删除或回复入口，避免把后端读取与 mock 写入混用。接口失败时显示中文错误空状态；mock 模式保留第一至第四阶段的完整交互。

## 服务层职责

- `src/services/mockApi.js`：第一至第四阶段的稳定 mock 数据源，保留完整查询和前端交互能力。
- `src/services/http.js`：统一 base URL、查询参数、JSON、超时、Token 预留及脱敏错误处理。
- `src/services/backendApi.js`：严格封装 Codex1 `/api/v1` 合同与统一响应格式。
- `src/services/adapters.js`：将 Codex1 snake_case 字段转换为现有页面字段。
- `src/services/dataProvider.js`：根据 `VITE_DATA_SOURCE` 选择数据源，页面无需散落数据源判断。

## 项目结构

```text
src/
├── components/common/  通用页面、表格、弹窗、表单与状态组件
├── data/               UTF-8 中韩文 mock 数据
├── layouts/            后台管理布局
├── pages/              13 个业务页面
├── routes/             集中路由配置
├── services/           mock、HTTP、Codex1 API、adapter 与 provider
└── styles/             全局及布局样式
```

## 本地自用敏感字段规则

本地业务页面允许展示运营地址、运营 IP、设备环境标签和明确标记为测试数据的手机号。真实客户数据仍应使用脱敏显示。

前端、mock、README、阶段文档及 Git 中不得写入或显示平台密钥、邮箱凭证、代理凭证、远程桌面凭证、银行卡号、身份证号或真实商家后台登录凭证。凭证页面只能展示“已配置/未配置”、到期时间、绑定状态和最后验证时间。HTTP 错误对象会按字段名隐藏凭证类值，也不会将请求或响应写入控制台。

本阶段不连接真实 Naver/Coupang API，不读取或发送真实邮件，也不调用 OpenAI、DeepSeek 或其他模型。

## 编码

HTML 明确声明 UTF-8，源码文件均以 UTF-8 保存。字体栈包含 `Microsoft YaHei`、`Noto Sans KR` 和 `Malgun Gothic`，用于兼容中文与韩文。

## Phase 5C - Store Context and Remaining Read-only Integration

Current formal integration target:

```text
VITE_API_BASE_URL=http://127.0.0.1:8012/api/v1
VITE_DATA_SOURCE=backend
```

Do not switch this phase back to port 8011. Codex1 Swagger is available at `http://127.0.0.1:8012/docs`.

Phase 5C adds global store context in `src/context/StoreContext.jsx` and the topbar `StoreSelector`. The selected store id is persisted as `codex2.selectedStoreId` in `localStorage`; backend read requests that depend on a store explicitly pass `storeId` through `dataProvider`, and `backendApi` converts it to Codex1 `store_id`.

Updated Phase 5B backend reads:

- Dashboard summary: `/dashboard/summary?store_id={selectedStoreId}`
- Products: `/products?store_id={selectedStoreId}`
- Orders: `/orders?store_id={selectedStoreId}`
- Customer inquiries: `/customer-inquiries?store_id={selectedStoreId}`
- Sync logs: `/sync-logs?store_id={selectedStoreId}`
- AI daily context: `/ai/daily-context?store_id={selectedStoreId}`

New Phase 5C read-only backend modules:

- Devices and Environment: `/device-environments?store_id={selectedStoreId}`
- Emails: `/email-accounts?store_id={selectedStoreId}` and `/important-emails?store_id={selectedStoreId}`
- Appeals: `/appeal-cases?store_id={selectedStoreId}`
- Accounts / Credentials: `/credentials?store_id={selectedStoreId}`

Credentials and email account pages show only configuration states and never show credential values. Codex1 snake_case response fields stay centralized in `src/services/adapters.js`; page JSX should use adapted frontend fields.

Verification record: see `PHASE_5C_STORE_CONTEXT.md`.

## Phase 6B-2 - API Capability Matrix Frontend

Phase 6B-2 adds the `/api-capabilities` workspace page and sidebar entry `API 能力确认`.

The page maintains two record types from Codex1:

- Platform-level API capability definitions through `/api-capabilities`.
- Current store-level manual/docs/mock/sandbox result records through `/api-capability-results`.

This page is an API capability confirmation workbench, not a platform connection page. `docs_only` and `manual` records mean documentation review or operator-entered notes only. The frontend does not call Naver or Coupang APIs, does not use real keys, does not refresh tokens, and does not run real sync. Store-level result creation uses the current `StoreContext` selected store and only displays API Credential metadata such as platform, label, auth status, and `has_*` configuration states; secret, token, password, and encrypted values are never displayed.

Time fields on the page use the shared KST display helpers from `src/utils/time.js`. Mock mode keeps the page reachable with an empty-state notice and does not pretend to maintain Codex1 API capability records.

## Phase 6B-3B - Dashboard API Capability Summary

Dashboard now reads Codex1 `api_capability_summary` and AI Daily Context `api_capability_context` in backend mode. The summary card shows platform-level capability counts, current store-level result counts, attention items, and a link to `/api-capabilities`.

The UI labels `tested_success_count` as `记录为通过`; it does not describe docs-only/manual/mock/sandbox records as real platform connection or real sync coverage. `real_readonly_count` is displayed only as a future reserved count. Mock mode shows an empty-state notice instead of fabricating capability data.

## Phase 5D-1 - Store and Device Environment Writes

Phase 5D-1 keeps `VITE_API_BASE_URL=http://127.0.0.1:8012/api/v1` and `VITE_DATA_SOURCE=backend`.

Implemented backend writes:

- Store create/update through Codex1 `POST /stores` and `PUT /stores/{store_id}`.
- Device Environment create/update through Codex1 `POST /device-environments` and `PUT /device-environments/{environment_id}`.
- Store saves refresh `StoreContext` and the topbar `StoreSelector`.

Still excluded in 5D-1:

- Credential writes.
- Email account writes.
- mock sync buttons.
- real Naver/Coupang APIs.
- real mailbox connections.
- AI model calls.

Details and validation notes: see `PHASE_5D_WRITE_INTEGRATION.md`.

## Phase 5D-2 - API Credential and Email Account Writes

Phase 5D-2 adds local Codex1 backend writes for API Credentials and Email Accounts while keeping mock mode intact.

Implemented:

- API Credential create/update through `POST /credentials` and `PUT /credentials/{credential_id}`.
- API Credential disable through `PUT /credentials/{credential_id}` with `status: inactive`.
- Email Account create/update through `POST /email-accounts` and `PUT /email-accounts/{email_account_id}`.
- Credential and Email Account saves refresh the current `selectedStoreId` list.
- Test connection buttons are local-only notices and do not claim real Naver, Coupang, or mailbox validation.

Sensitive field names may exist in service and adapter payload mapping where required by Codex1 contracts, but pages, notices, errors, and console output must not display credential plaintext or encrypted credential fields. Edit forms leave sensitive inputs blank; blank values are not sent as updates.

## Phase 5D-3 - Local Mock Sync

Phase 5D-3 adds local mock sync buttons for backend mode while keeping mock mode intact:

- Products: `POST /sync/products/mock`
- Orders: `POST /sync/orders/mock`
- Customer inquiries: `POST /sync/customer-inquiries/mock`

All sync controls are explicitly labeled as local mock sync. They write to the local Codex1 backend and refresh the relevant page data, sync logs, Dashboard Summary, and AI Daily Context where applicable. They do not connect to real Naver, Coupang, mailbox, or AI services.

## Phase 6A-2 - Platform Login Frontend Boundary

Phase 6A-2 connects the backend-mode Accounts page to Codex1 Platform Login endpoints while keeping API Credentials separate.

Implemented frontend behavior:

- Platform Login Information section for manual Naver SmartStore / Coupang Wing backend login configuration.
- API Development Credentials section for existing API Credential create/update/inactive behavior.
- Platform Login list/create/edit/inactive through `/platform-logins`.
- Current-store Email Account and Device Environment binding selectors.
- Password inputs are never prefilled; blank password on edit means no update.
- `loginStatus` is shown only as local configuration status, not real platform login verification.

Still excluded:

- Real Naver or Coupang login.
- Verification code reading.
- Real mailbox connections.
- Real API credential validation.
- AI model calls.

## Phase 6B-0B - Frontend KST Time Display

Phase 6B-0B keeps Codex1 unchanged and fixes Codex2 display semantics for business time:

- Business dates and operational timestamps are displayed in `Asia/Seoul` / `KST`.
- Browser or Windows local display timezone is not used as the business-time source.
- Backend UTC timestamps are formatted for display only; payload values are not rewritten.
- Dashboard shows the Korean business day returned by Codex1 and no longer labels backend range totals as today-only totals.
- Mock-generated `today` and `now` values use the same KST utility as backend display paths.

Details and validation notes: see `PHASE_6A_PLATFORM_LOGIN.md`.

## Phase 6A-3 - API Credential Structured Fields

Phase 6A-3 adds structured API credential fields for future Naver / Coupang API capability validation.

Implemented:

- Coupang-oriented metadata: Vendor ID, Market, API local status, API remark.
- Naver-oriented metadata: Client ID, Access Token status, Refresh Token status, Token expiry, API local status, API remark.
- Sensitive key/secret/token values are accepted only through blank-on-edit password inputs and are never displayed.
- The existing Access Key / Secret Key flow remains compatible with 5D-2 and 5D-3 mock sync.
- Test connection remains a local-only notice and does not claim real API validation.

Codex1 uses an idempotent SQLite schema upgrade script for existing local databases. This phase still excludes real Naver/Coupang API calls, token refresh, and real API connection tests.

## Phase Naver-ERP-5B - Order Detail Complete Field Strategy

Naver ERP Dashboard summary is in place, and the next order-detail boundary is documented in `PHASE_NAVER_ERP_5B_ORDER_DETAIL_FIELD_STRATEGY.md`.

This strategy allows complete order number, product number, buyer information, receiver information, and address to appear in controlled internal order-detail views. Dashboard remains summary-only and should not expand complete buyer phone or address into top-level cards.

This phase is documentation-only. It does not call Naver, does not write Codex1 data, does not change database schema, and does not open formal Naver order sync.

## Phase Naver-ERP-5C - Order Detail Mock Display

Codex2 Orders now includes a Naver order detail section for controlled internal display of complete mock business fields. See `PHASE_NAVER_ERP_5C_ORDER_DETAIL_MOCK_DISPLAY.md`.

The `pxg球包店` mock order includes complete order number, product order number, platform product number, buyer information, receiver information, address, payment status, delivery status, and claim status. Dashboard remains summary-only.

This phase still does not call Naver, does not write Codex1 data, does not change database schema, and does not open formal Naver order sync. Backend mode remains tolerant when complete fields are not yet present.

## Phase Naver-ERP-5E - Complete Field Readonly Preview Integration

Codex2 Orders now has a manual `读取完整字段只读预览` action backed by Codex1 `POST /api/v1/sync/orders/naver/preview` with `complete_field_preview=true`, `include_detail=true`, and `real_sync=false`. See `PHASE_NAVER_ERP_5E_COMPLETE_FIELD_PREVIEW_INTEGRATION.md`.

The Orders page does not auto-run this preview on load. Local sanitized order data remains visible first; complete order number, product order number, product id, buyer/receiver names, phones, and address are displayed only in the Orders detail panel after an explicit readonly preview. The phase does not write orders, does not modify Codex1, does not change schema, does not save raw response data, and does not open formal Naver order sync.

## Phase Naver-ERP-5G - Controlled Complete Field Preview Window

Codex2 Orders now lets an operator choose a bounded readonly preview window before clicking `读取完整字段只读预览`: `最近 24 小时`, `最近 3 天`, or `最近 7 天`. See `PHASE_NAVER_ERP_5G_CONTROLLED_PREVIEW_WINDOW.md`.

The selected window only changes `start_datetime` / `end_datetime` for the existing Codex1 preview call. The request remains `store_id=8`, `credential_id=7`, `page=1`, `size=1`, `include_detail=true`, `complete_field_preview=true`, and `real_sync=false`. The page still does not auto-run Naver requests, does not write orders, does not save raw response data, and does not open formal Naver order sync.

## Phase Naver-ERP-5H - Order Complete Field Status Mapping Polish

Codex2 Orders now keeps delivery display aligned with complete-field order status when Naver returns a clear delivery-stage order status but a missing or unknown delivery status. See `PHASE_NAVER_ERP_5H_STATUS_MAPPING_POLISH.md`.

The Orders detail panel can show `配送完成` instead of an unnecessary unknown warning when the complete-field readonly preview proves the order is delivered. Dashboard remains summary-only, and formal Naver order sync remains closed.

## Phase Naver-ERP-5I - Order Display Hierarchy Cleanup

Codex2 now separates Naver order display levels: the Orders detail panel can show complete readonly preview fields, the Orders list shows operational order summaries, and Dashboard uses aggregate counts only. See `PHASE_NAVER_ERP_5I_DISPLAY_HIERARCHY_CLEANUP.md`.

Backend-mode Naver order lists isolate `mock_sync` test rows from operational summaries. Those rows are not deleted; they are simply excluded from the main seller-facing list, Dashboard fulfillment counts, and local order amount summaries. Formal Naver order sync remains closed.

## Phase Naver-ERP-5J - Order Local List Cleanup

Codex1 `/orders`, sales stats, and Dashboard summary now exclude local order test rows such as `mock_sync` and `local_frontend_mock` by default. The rows are retained in the database for audit/testing and can be inspected only with the explicit readonly diagnostic flag `include_test_orders=true`. See `PHASE_NAVER_ERP_5J_LOCAL_LIST_CLEANUP.md`.

Codex2 preserves the backend `test_orders_excluded` metadata for technical/status display while keeping the seller-facing Orders list and Dashboard on operational-order counts. This phase does not call Naver, does not write orders, and does not open formal Naver order sync.

## Phase Naver-ERP-6A - Inventory Basic Alerts

Codex2 now shows basic Naver inventory alerts from local product records only. See `PHASE_NAVER_ERP_6A_INVENTORY_BASIC_ALERTS.md`.

The Products page and Dashboard classify local Naver products as out of stock, low stock, normal, or invalid stock. The low-stock rule is `0 < stock < 5`, so stock equal to 5 remains normal. This phase does not call Naver, does not compare platform inventory, does not write products or orders, and does not open formal Naver product batch sync.

## Phase Naver-ERP-6B - Product Price / Stock Change Hints

Codex2 now separates local inventory alerts from Naver product price / stock change hints. See `PHASE_NAVER_ERP_6B_PRODUCT_PRICE_STOCK_CHANGE_HINTS.md`.

The Products page and Dashboard show that the latest known Naver product dry-run has no price or stock business-field changes, while still showing local out-of-stock or low-stock alerts separately. Future safe changed-field names such as `price`, `currency`, or `stock_quantity` can be surfaced as manual review hints, but this phase does not call Naver, does not write products, and does not open formal Naver product batch sync.

## Phase Naver-ERP-7A - Delivery Status Dashboard Summary

Codex2 Dashboard now has a dedicated Naver delivery status summary. See `PHASE_NAVER_ERP_7A_DELIVERY_STATUS_DASHBOARD_SUMMARY.md`.

The summary uses local Naver operational orders only and separates pending delivery, in-delivery, delivered, and unknown delivery states. It does not call Naver, does not write orders, does not execute dispatch/cancel/return/exchange writes, and does not open formal Naver order sync.

## Phase Naver-ERP-7B - Claim Readonly Classification

Codex2 now has a dedicated Naver claim readonly classification summary. See `PHASE_NAVER_ERP_7B_CLAIM_READONLY_CLASSIFICATION.md`.

The Dashboard and Orders page classify local Naver operational orders into cancel requests, return requests, exchange requests, already canceled orders, and unknown claim/order states. This phase does not call Naver, does not write orders, does not execute cancel/return/exchange/refund writes, and does not open formal Naver order sync.

## Phase Naver-ERP-8A - Order-Based Sales Summary

Codex2 now has a richer Naver order-based sales summary. See `PHASE_NAVER_ERP_8A_ORDER_BASED_SALES_SUMMARY.md`.

The Dashboard and Sales page summarize local Naver operational order amounts by total, today, week, month, store, and product. The displayed amount comes only from local orders and is not Naver settlement, profit, withdrawable balance, confirmed refund amount, or net sales. This phase does not call Naver sales/statistics/settlement APIs, does not write orders or financial rows, and does not open formal Naver order sync.

## Phase Naver-ERP-8B - Dashboard ERP Summary

Codex2 Dashboard now has a seller-facing Naver ERP daily summary. See `PHASE_NAVER_ERP_8B_DASHBOARD_ERP_SUMMARY.md`.

The summary prioritizes connection issues, claim attention, pending delivery, inventory attention, and product price/stock change hints, then shows local products, local operational orders, pending delivery, claims, and local order amount. It uses existing local data only, does not call Naver, does not write orders/products/financial rows, and keeps product batch sync, order batch sync, platform delivery/claim writes, and Naver sales/settlement APIs closed.

## Phase Naver-ERP-9A - Controlled Order Refresh Write Gate Plan

Codex2 Orders now shows a controlled Naver order refresh write gate plan beside the complete-field readonly preview. See `PHASE_NAVER_ERP_9A_CONTROLLED_ORDER_REFRESH_WRITE_GATE_PLAN.md`.

This phase is a planning and display gate only. It does not add a write button, does not call a new API, does not change Codex1, does not write orders, and does not open formal Naver order sync. The gate explains that a later refresh write would require a usable readonly complete-field preview, one selected local operational order, a database backup, explicit manual approval, a safe field whitelist, no SyncLog write, no tested_success write, no platform order write operation, and no saved raw response or platform secret.

## Phase Naver-ERP-9B - Order Refresh Gate Mock Verification

The Naver order refresh write gate has been verified in both backend-source and mock-source Orders pages. See `PHASE_NAVER_ERP_9B_ORDER_REFRESH_GATE_MOCK_VERIFICATION.md`.

Backend mode shows the gate as `待只读预览` without white screen or console errors. Mock mode can move the gate to `可进入人工审核，不会自行写库` after the existing mock complete-field readonly preview, while still showing that orders, SyncLog, tested_success, and platform write operations remain closed. This phase does not call Naver, does not write local data, and does not open formal Naver order sync.

## Phase Naver-ERP-9C - Controlled Order Readonly Preview Repeat

The controlled Naver order complete-field readonly preview was repeated through Codex1 with `real_sync=false`. See `PHASE_NAVER_ERP_9C_CONTROLLED_ORDER_READONLY_PREVIEW_REPEAT.md`.

The 3-day KST window returned HTTP 200 with `preview_status=success`, feed and detail both called, and complete-field preview available. The observed readonly detail status was `DELIVERED / 配送完成` with amount `330000 KRW`. No local counters changed: `orders_store8=4`, operational Naver orders remain 1, mock/test Naver orders remain 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`.

This success does not approve refresh writing. The local operational Naver order currently remains `PAYED` with amount `499000 KRW`, so the next gate must prove that the previewed product-order identity matches the selected local operational order before any future one-row refresh write is considered.

## Phase Naver-ERP-9D - Order Refresh Candidate Match Gate

Codex2 now requires the complete-field readonly preview identity to match the selected local operational Naver order before the refresh gate can enter manual review. See `PHASE_NAVER_ERP_9D_ORDER_REFRESH_CANDIDATE_MATCH_GATE.md`.

The gate prefers safe product-order hash matching from `detail_preview`; it falls back to full product order number comparison only when both sides have comparable full values. If the identity differs or cannot be confirmed, the Orders page blocks refresh-write review. This phase does not call Naver, does not change Codex1, does not write local data, and does not open formal Naver order sync.

## Phase Naver-ERP-9E - Order Refresh Match Walkthrough

The 9D identity gate has been walked through in backend-source and mock-source Orders pages. See `PHASE_NAVER_ERP_9E_ORDER_REFRESH_MATCH_WALKTHROUGH.md`.

Backend mode used the existing 3-day complete-field readonly preview with `real_sync=false`. The preview succeeded, but the product-order safe hash did not match the selected local operational order, so the gate stayed `不可写库` and did not enter manual review. Mock mode demonstrated the matched path and moved to `可进入人工审核，不会自行写库`. No local counters changed, no Codex1 files changed, and formal Naver order sync remains closed.

## Phase Naver-ERP-9F - Order Refresh Write Deferral And Next-Candidate Plan

Naver order refresh writing is formally deferred because the real readonly preview does not match the selected local operational order. See `PHASE_NAVER_ERP_9F_ORDER_REFRESH_WRITE_DEFERRAL_AND_NEXT_CANDIDATE_PLAN.md`.

The current local operational order remains `PAYED / 499000 KRW`, while the latest controlled readonly preview observed `DELIVERED / 配送完成` with `330000 KRW`. Since the product-order safe hash mismatches, the previewed detail must not update the existing local row. The safer next path is to classify the previewed detail as a possible new order candidate under a separate phase, still with preview-first, duplicate checks, one-order limits, and formal sync closed.

## Phase Naver-ERP-10A - New Order Candidate Classification Plan

The mismatched Naver readonly preview is now treated only as a possible new-order candidate, not as a refresh payload for the existing local order. See `PHASE_NAVER_ERP_10A_NEW_ORDER_CANDIDATE_CLASSIFICATION_PLAN.md`.

10A defines candidate states such as `no_candidate`, `candidate_new`, `candidate_duplicate`, `candidate_ambiguous`, `candidate_blocked_privacy`, and `candidate_stale_preview`. A future new-order write can only be considered after a fresh readonly preview, safe product-order hash duplicate checks across local Naver orders, one-order limits, database backup, explicit approval, and privacy/raw-response gates. This phase does not call Naver, does not write local data, and does not open formal Naver order sync.

## Phase Naver-ERP-10B - New Order Candidate Readonly Repeat

The Naver new-order candidate readonly preview was repeated through Codex1 with `real_sync=false`. See `PHASE_NAVER_ERP_10B_NEW_ORDER_CANDIDATE_READONLY_REPEAT.md`.

The 3-day KST window returned HTTP 200 with `preview_status=success` and classified the candidate as `candidate_new`. The candidate status is `DELIVERED / 配送完成`, amount `330000 KRW`, product and option text are present, and local duplicate checks found zero operational or mock/test matches. No local counters changed: `orders_store8=4`, operational Naver orders remain 1, mock/test Naver orders remain 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. This is not a write approval; a one-row new-order write requires a separate phase, database backup, and explicit approval.

## Phase Naver-ERP-10C - Single New-Order Write Gate

The controlled one-order Naver local write gate was executed after a database backup. See `PHASE_NAVER_ERP_10C_SINGLE_NEW_ORDER_WRITE_GATE.md`.

Codex1 caps `real_sync=true` order writes to a 24-hour window. The 10C write gate returned HTTP 200 and `preview_status=success`, but the 24-hour detail matched an existing local Naver order, so `local_sync_result.status=already_exists`, `no_duplicate_created=true`, and `orders_written=false`. No local counters changed: `orders_store8=4`, operational Naver orders remain 1, mock/test Naver orders remain 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. The 3-day `candidate_new` from 10B was not force-written, and formal Naver order sync remains closed.

## Phase Naver-ERP-10D - New-Order Write Window Decision

The Naver new-order write window decision is documented in `PHASE_NAVER_ERP_10D_NEW_ORDER_WRITE_WINDOW_DECISION.md`.

10D keeps the existing Codex1 `real_sync=true` order write gate capped to a 24-hour window. The 3-day `candidate_new` from 10B must not be forced through the current 24-hour gate or reused from a stale readonly response. If that candidate should be considered for persistence, it needs a separate selected-candidate write path with a fresh readonly preview, database backup, duplicate checks, privacy gates, and explicit approval. This phase does not call Naver, does not write local data, does not change Codex1, and does not open formal Naver order sync.

## Phase Naver-ERP-11A - Selected New-Order Write Path Plan

The selected Naver new-order write path is documented in `PHASE_NAVER_ERP_11A_SELECTED_NEW_ORDER_WRITE_PATH_PLAN.md`.

11A keeps the existing 24-hour write gate unchanged and defines a separate future selected-candidate path for any manually approved older new-order candidate. The future path must re-run a fresh readonly preview, recompute safe hashes server-side, match exactly one selected candidate, pass duplicate and privacy gates, back up the database, write at most one order, and keep `products`, `SyncLog`, and `tested_success` unchanged. This phase does not call Naver, does not write local data, does not change Codex1, and does not open formal Naver order sync.

## Phase Naver-ERP-11B - Selected New-Order Write Mock Gate

The selected Naver new-order write mock gate is documented in `PHASE_NAVER_ERP_11B_SELECTED_NEW_ORDER_WRITE_MOCK_GATE.md`.

11B adds a private Codex1 mock-testable gate for future selected-candidate persistence. It is not wired to the public preview endpoint and does not call Naver. `verify_all.py` now covers readonly not-requested, stale, missing, changed, duplicate, not-unique, privacy-blocked, and one-row temporary mock success paths while keeping `products`, `SyncLog`, `tested_success`, raw response saving, platform writes, and formal order sync closed.

## Phase Naver-ERP-11C - Selected New-Order Readonly Candidate Refresh

The selected Naver new-order readonly candidate refresh is documented in `PHASE_NAVER_ERP_11C_SELECTED_NEW_ORDER_READONLY_CANDIDATE_REFRESH.md`.

11C re-ran the existing Codex1 order preview endpoint with `real_preview=true`, `include_detail=true`, `complete_field_preview=true`, and `real_sync=false` over a recent 3-day KST window. The backend returned HTTP 200 with `preview_status=failed` and `error_code=ip_not_allowed`, so feed/detail were not called and the older `candidate_new` could not be refreshed. Local counts stayed unchanged: `orders_store8=4`, real Naver local orders remain 1, mock Naver orders remain 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. The next step is to confirm the Naver Commerce API allowed IP setting before retrying 11C; selected-candidate write approval remains blocked.

## Phase Naver-ERP-11C-Retry - Selected New-Order Readonly Candidate Refresh

The selected Naver new-order readonly retry is documented in `PHASE_NAVER_ERP_11C_RETRY_SELECTED_NEW_ORDER_READONLY_REFRESH.md`.

After the Naver API allowed IP setting was updated, the same readonly preview boundary succeeded with HTTP 200, `preview_status=success`, feed/detail HTTP 200, and `real_sync=false`. The candidate safe hash is `id-hash-ab176f5db1`, status is `DELIVERED / 配送完成`, amount is `330000 KRW`, quantity is 1, and local duplicate checks returned zero matches across real and mock Naver orders. Local counts stayed unchanged: `orders_store8=4`, real Naver local orders remain 1, mock Naver orders remain 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. The candidate is `candidate_new`, but this is not a write approval and formal Naver order sync remains closed.

## Phase Naver-ERP-11D - Selected Candidate Real Write Approval Plan

The selected candidate real write approval plan is documented in `PHASE_NAVER_ERP_11D_SELECTED_CANDIDATE_REAL_WRITE_APPROVAL_PLAN.md`.

11D does not call Naver, does not write local data, and does not execute `real_sync=true`. It records that candidate `id-hash-ab176f5db1` may enter a later 11E manual review only after explicit user approval, database backup, fresh candidate validation, duplicate checks, privacy gate success, and a one-row write limit. Formal Naver order sync remains closed.

## Phase Naver-ERP-11E - Selected Candidate Single Local Write

The selected candidate single local write is documented in `PHASE_NAVER_ERP_11E_SELECTED_CANDIDATE_SINGLE_LOCAL_WRITE.md`.

11E backed up `backend/codex1.db`, re-ran a fresh readonly sanitized preview, confirmed candidate `id-hash-ab176f5db1` still matched `candidate_new` with duplicate count 0, and wrote exactly one sanitized local Naver order. `orders_store8` moved from 4 to 5, real Naver local orders moved from 1 to 2, mock Naver orders remained 3, `products_store8` stayed 5, `sync_logs_store8` stayed 1, and `tested_success_store8` stayed 8. The row keeps `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Formal Naver order sync remains closed.
