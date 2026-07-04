# AI 多店铺运营与环境管理系统（Codex2）

React + Vite 后台前端，已完成 13 个业务路由、第一至第四阶段页面，以及第五阶段 A 的 Codex1 后端接口适配准备。默认继续使用本地 mock 数据，切换后端数据源不会要求重写页面字段。

## 当前项目进度

最新项目进度、当前定位、未完成阶段和后续计划记录在：

```text
PROJECT_PROGRESS.md
```

当前固定进度口径：

- 项目总体规划进度：约 `72% - 78%`
- Naver 基础 ERP 闭环进度：约 `80% - 85%`
- ERP 给真实用户落地使用进度：约 `74% - 80%`
- 可交给非技术人员长期稳定使用的生产版进度：约 `68% - 74%`

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

## Phase Naver-ERP-11F - Selected Candidate Post-Write Verification

The selected candidate post-write verification is documented in `PHASE_NAVER_ERP_11F_SELECTED_CANDIDATE_POST_WRITE_VERIFICATION.md`.

11F performed local database readback only. It did not call Naver, did not write local data, did not modify Codex1 or Codex2 runtime behavior, and did not open formal Naver order sync. The selected candidate `id-hash-ab176f5db1` exists exactly once with `source_type=naver_real_order_sync`, `order_status=DELIVERED`, `quantity=1`, `order_amount=330000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Current counts remain `orders_store8=5`, real Naver local orders 2, mock Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`.

## Phase Naver-ERP-12A - Orders and Dashboard Real-Order Count Display Check

The Naver Orders and Dashboard display check is documented in `PHASE_NAVER_ERP_12A_ORDER_DASHBOARD_REAL_COUNT_DISPLAY_CHECK.md`.

12A fixed Codex2 display filtering so backend rows with display platform `Naver` still match the `naver` platform filter, removed stale one-order wording, and confirmed Orders/Dashboard now show 2 real Naver operational orders while 3 mock/test orders stay isolated. Dashboard shows `5 商品 / 2 订单`, local order amount `829000 KRW`, and keeps formal order sync, product batch sync, and platform delivery/claim writes closed.

## Phase Naver-ERP-12B - Orders UI Manual Approval Affordance Plan

The Orders UI manual approval affordance plan is documented in `PHASE_NAVER_ERP_12B_ORDERS_UI_MANUAL_APPROVAL_AFFORDANCE_PLAN.md`.

12B adds a display-only manual approval status area to the Naver Orders detail panel. It shows the future approval boundary, required preconditions, disabled approval/write placeholders, and the continued closure of formal order sync and platform write operations. The disabled buttons do not call Codex1 or Naver, no local data is written, and no real API request is triggered by this phase.

## Phase Naver-ERP-13A - Naver Order Local Refresh Mock Gate

The Naver order local refresh mock gate is documented in `PHASE_NAVER_ERP_13A_ORDER_LOCAL_REFRESH_MOCK_GATE.md`.

13A adds a private Codex1 mock-testable gate for future local order refresh planning. It is not wired to a public endpoint and does not call Naver. `verify_all.py` covers readonly not-requested, stale preview, identity mismatch, missing local order, privacy-blocked, manual-approval-required, one-row temporary mock refresh success, no-change repeat refresh, and sensitive field scanning while keeping products, SyncLog, tested_success, raw response saving, platform writes, and formal order sync closed.

## Phase Naver-ERP-13B - Naver Order Readonly Refresh Repeat

The Naver order readonly refresh repeat is documented in `PHASE_NAVER_ERP_13B_ORDER_READONLY_REFRESH_REPEAT.md`.

13B re-ran the existing Codex1 order preview endpoint with `real_preview=true`, `include_detail=true`, `complete_field_preview=true`, and `real_sync=false` over a recent 3-day KST window. The backend returned HTTP 200 with `preview_status=success`, feed/detail HTTP 200, and safe hash `id-hash-ab176f5db1`, which matched an existing real local Naver order. The observed status is `DELIVERED / 配送完成`, amount is `330000 KRW`, and quantity is 1. Local counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, and `tested_success_store8=8`. This is not refresh write approval; formal Naver order sync and all platform write operations remain closed.

## Phase Naver-ERP-13C - Naver Selected Order Refresh Approval Plan

The Naver selected order refresh approval plan is documented in `PHASE_NAVER_ERP_13C_SELECTED_ORDER_REFRESH_APPROVAL_PLAN.md`.

13C is documentation-only. It records the future gate for refreshing one existing local Naver order with selected safe hash `id-hash-ab176f5db1`: explicit user approval, clean worktrees, database backup, fresh readonly preview, exact hash match, exactly one existing local real Naver order, privacy gate pass, one-row update limit, post-write readback, no product writes, no SyncLog, no tested_success, no raw response saving, and no Naver platform write operation. It does not call Naver, does not write local data, and does not approve formal order sync.

## Phase Naver-ERP-13D - Selected Naver Order Single Local Refresh Write

The selected Naver order single local refresh write attempt is documented in `PHASE_NAVER_ERP_13D_SELECTED_ORDER_SINGLE_LOCAL_REFRESH_WRITE.md`.

13D backed up the real database and ran fresh readonly Naver order previews, but it did not update the selected local order because the fresh preview hashes did not match approved hash `id-hash-ab176f5db1`. The 3-day window returned `id-hash-0c36f22281`, and the targeted narrow probe returned `id-hash-a5870c77c2`. The refresh gate blocked on selected-hash mismatch, leaving orders, products, SyncLog, tested_success, and order status events unchanged. Formal Naver order sync remains closed.

## Phase Naver-ERP-14A - Naver Order Status Timeline Plan

The Naver order status timeline plan is documented in `PHASE_NAVER_ERP_14A_ORDER_STATUS_TIMELINE_PLAN.md`.

14A is planning-only. It separates the latest local order snapshot from future status-history events so a later refresh does not hide transitions such as `PAYED -> DELIVERED`. The plan defines safe timeline event fields, forbidden privacy/raw-response fields, status-to-event mapping, dedupe rules, no-change refresh behavior, and a future preference for a separate `order_status_events` table in a later approved schema phase. It does not call Naver, does not write local data, does not change schema, and does not open formal order sync.

## Phase Naver-ERP-14B - Naver Order Status Timeline Mock Mapper

The Naver order status timeline mock mapper is documented in `PHASE_NAVER_ERP_14B_ORDER_STATUS_TIMELINE_MOCK_MAPPER.md`.

14B adds a private Codex1 helper that maps sanitized previous/current Naver order status snapshots into planned timeline events for mock verification only. It covers delivered, delivery, cancel, return, exchange, unknown-status, privacy-blocked, identity-mismatch, no-change, and deduped refresh cases while keeping `orders`, products, SyncLog, tested_success, raw responses, platform writes, schema changes, and formal order sync closed. The helper is not wired to any public endpoint.

## Phase Naver-ERP-14C - Orders UI Status Timeline Display Plan

The Orders UI status timeline display plan is documented in `PHASE_NAVER_ERP_14C_ORDERS_UI_STATUS_TIMELINE_DISPLAY_PLAN.md`.

14C is display-planning only. It defines how Orders UI should separate current status, future status history, refresh gate state, complete-field readonly preview, and TechnicalDetails. The plan keeps seller-facing text on the main page, puts safe raw enums and hashes only in TechnicalDetails, keeps timeline history collapsed by default, and forbids wording that implies timeline persistence, automatic refresh, or formal Naver order sync is already open. It does not modify runtime frontend code.

## Phase Naver-ERP-14D - Order Status Events Schema Proposal

The order status events schema proposal is documented in `PHASE_NAVER_ERP_14D_ORDER_STATUS_EVENTS_SCHEMA_PROPOSAL.md`.

14D is proposal-only. It recommends a future `order_status_events` table linked to `orders.id`, with safe order hashes, event type, status labels, observed time, source metadata, a dedupe key, and safety booleans. It defines unique/index strategy, forbidden privacy/raw-response fields, migration and rollback direction, and future read API boundaries. It does not modify models, run migrations, write data, or open formal order sync.

## Phase Naver-ERP-14E - Order Status Events Mock Schema Gate

The order status events mock schema gate is documented in `PHASE_NAVER_ERP_14E_ORDER_STATUS_EVENTS_MOCK_SCHEMA_GATE.md`.

14E adds mock-only verification in Codex1 `verify_all.py` using the temporary verification SQLite database. It creates a temporary `order_status_events` table shape, verifies proposed columns, required indexes, the `store_id/platform/dedupe_key` uniqueness boundary, safe metadata, one-row mock insertion, duplicate rejection, and sensitive-field scanning. It does not modify the real database schema, add a model or migration, call Naver, write real orders, modify Codex2 runtime UI, or open formal order sync. Real schema approval remains deferred to a later 14F plan.

## Phase Naver-ERP-14F - Order Status Timeline Schema Approval Plan

The order status timeline schema approval plan is documented in `PHASE_NAVER_ERP_14F_ORDER_STATUS_TIMELINE_SCHEMA_APPROVAL_PLAN.md`.

14F is planning-only. It defines the approval boundary, backup path, rollback steps, preflight checks, migration shape, post-migration verification, and future event-write boundary for a later `order_status_events` schema migration. It does not create the table, add a model or migration, call Naver, write local data, modify runtime UI, or open formal order sync. The actual schema migration remains deferred to a separately approved 14G phase.

## Phase Naver-ERP-14G - Order Status Timeline Schema Migration

The order status timeline schema migration is documented in `PHASE_NAVER_ERP_14G_ORDER_STATUS_TIMELINE_SCHEMA_MIGRATION.md`.

14G creates the real `order_status_events` table in `backend/codex1.db` with the approved safe columns and dedupe/index strategy. The migration leaves the table empty, keeps existing order/product/log/capability counts unchanged, and still does not approve event writes, order refresh writes, platform writes, UI timeline display, or formal Naver order sync.

## Phase Naver-ERP-14H - Timeline Event Single Local Write Mock Gate

The timeline event single local write mock gate is documented in `PHASE_NAVER_ERP_14H_TIMELINE_EVENT_SINGLE_LOCAL_WRITE_MOCK_GATE.md`.

14H adds a private Codex1 helper and verify_all coverage for a single timeline event write gate in the temporary verification database only. It checks fresh preview, selected hash identity, exactly one planned event, local order uniqueness, known event type, dedupe key, safety booleans, sensitive fields, and manual approval before a mock event row can be inserted. It does not write the real event table, call Naver, modify runtime UI, or open formal order sync.

## Phase Naver-ERP-14I - Post-Refresh Timeline Verification

The post-refresh timeline verification is documented in `PHASE_NAVER_ERP_14I_POST_REFRESH_TIMELINE_VERIFICATION.md`.

14I is local readback only after the blocked 13D refresh attempt. It confirms selected hash `id-hash-ab176f5db1` remains `DELIVERED`, `orders_refreshed=false`, `order_status_events_rows=0`, and selected-hash timeline events `0`. Because 13D did not pass the fresh selected-hash gate, no timeline event should exist. Formal Naver order sync and real timeline event writes remain closed.

## Phase Naver-ERP-14J - Orders UI Timeline Readonly Display

The Orders UI timeline readonly display is documented in `PHASE_NAVER_ERP_14J_ORDERS_UI_TIMELINE_READONLY_DISPLAY.md`.

14J adds a read-only Naver order status timeline section to Codex2 Orders detail. The main panel shows the current local order status snapshot and safe future timeline events when present; if no event rows are available, it explicitly shows that no local status history has been recorded yet. Raw enums, source phase, dedupe key, mapping version, and safe hashes stay in TechnicalDetails. This phase does not call Naver, does not write local data, does not modify Codex1 schema or APIs, and does not open formal Naver order sync.

## Phase Naver-ERP-15A - Naver Order Refresh Batch Gate Plan

The Naver order refresh batch gate plan is documented in `PHASE_NAVER_ERP_15A_ORDER_REFRESH_BATCH_GATE_PLAN.md`.

15A is planning-only. It defines the future gate for refreshing multiple already-existing local Naver orders while keeping the current public real preview cap at `page=1,size=1`. It separates existing-order refresh from new-order creation, timeline event insertion, shipment/claim platform writes, and formal order sync. A future batch gate must start with readonly candidate discovery, reject mixed new/refresh candidates, require exact safe-hash matches to existing local real Naver orders, block partial writes in the first batch, and require explicit approval plus database backup before any later local write phase.

## Phase Naver-ERP-15B - Naver Order Refresh Batch Mock Gate

The Naver order refresh batch mock gate is documented in `PHASE_NAVER_ERP_15B_ORDER_REFRESH_BATCH_MOCK_GATE.md`.

15B adds a private Codex1 mock gate for a future existing-order refresh batch. It is exercised only by `verify_all.py` against the temporary verification database. The gate defaults to at most two candidates, rejects stale previews, duplicate safe hashes, new-order candidates, privacy failures, unknown statuses, sensitive/raw-response fields, and unapproved writes, and can update two temporary existing local orders only when `write_enabled=true` and `manual_approval=true`. It does not change the public endpoint, call Naver, write the real database, insert timeline events, modify runtime UI, or open formal order sync.

## Phase Naver-ERP-15C - Naver Order Refresh Readonly Candidate Batch

The Naver order refresh readonly candidate batch result is documented in `PHASE_NAVER_ERP_15C_ORDER_REFRESH_READONLY_CANDIDATE_BATCH.md`.

15C runs a controlled real readonly candidate discovery under the existing public guardrail, so the request remains `page=1,size=1`, `real_preview=true`, `include_detail=true`, and `real_sync=false`. The preview returned HTTP 200 with feed/detail HTTP 200 and one safe candidate hash, `id-hash-67b5fc1c97`, but that hash did not match an existing local real Naver order. It is therefore a new-order candidate, not an existing-order batch refresh candidate. Counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. `DELIVERY_COMPLETION` is now recognized as `配送完成`. True multi-candidate probing, local batch refresh writing, timeline event insertion, new-order writing, platform writes, and formal Naver order sync remain closed.

## Phase Naver-ERP-15D - Naver Order Refresh Batch Approval Plan

The Naver order refresh batch approval plan is documented in `PHASE_NAVER_ERP_15D_ORDER_REFRESH_BATCH_APPROVAL_PLAN.md`.

15D is planning-only. It defines the human approval checklist for a future batch refresh of already-existing local Naver orders after 15B mock coverage. It does not run a real readonly batch probe, does not change the current `page=1,size=1` public guardrail, and does not write local data. A later write phase would require clean worktrees, a database backup, explicit approved safe hashes, a fresh readonly candidate batch result, no mixed new-order candidates, no duplicate hashes, every hash matching exactly one existing local real Naver order, privacy/status gates passing, and post-write readback.

## Phase Naver-ERP-15E - Naver Order Refresh Batch Readonly Expansion Approval Plan

The Naver order refresh readonly expansion approval plan is documented in `PHASE_NAVER_ERP_15E_ORDER_REFRESH_READONLY_EXPANSION_APPROVAL_PLAN.md`.

15E is planning-only. It does not call Naver, does not change the current public `page=1,size=1` guardrail, does not write local data, and does not open formal order sync. It decides that the 15C safe hash `id-hash-67b5fc1c97` remains a new-order candidate, not an existing-order refresh candidate, so no batch refresh write is approved. A future readonly expansion would require a separate guarded implementation phase, first limited to `page=1,size=2`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`, with strict candidate classification and stop conditions. The recommended next stage is the new-order candidate approval path.

## Phase Naver-ERP-16A - New-Order Candidate Approval Plan

The Naver new-order candidate approval plan is documented in `PHASE_NAVER_ERP_16A_NEW_ORDER_CANDIDATE_APPROVAL_PLAN.md`.

16A is planning-only. It does not call Naver, does not write local data, does not change schema or runtime UI, and does not open formal order sync. It routes the 15C safe hash `id-hash-67b5fc1c97` into the selected new-order path, not the existing-order refresh batch path. A later write still requires a fresh 16B readonly repeat, duplicate checks, privacy/status gates, explicit write approval, database backup, one-order limit, no products/SyncLog/tested_success/timeline writes, and no Naver platform write action.

## Phase Naver-ERP-16B - Selected New-Order Readonly Repeat Check

The Naver selected new-order readonly repeat result is documented in `PHASE_NAVER_ERP_16B_SELECTED_NEW_ORDER_READONLY_REPEAT_CHECK.md`.

16B repeats the real readonly preview under the existing `page=1,size=1` guardrail with `real_sync=false`. It returned HTTP 200 with feed/detail HTTP 200 and the same selected safe hash, `id-hash-67b5fc1c97`. Duplicate checks found 0 real local matches and 0 mock/test matches, so the candidate remains `candidate_new`. Status and privacy gates passed, required business fields were present, and counts stayed unchanged: `orders_store8=5`, real Naver local orders 2, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. 16B does not approve a write; it only allows a later 16C approval plan to be considered.

## Phase Naver-ERP-16C - Selected New-Order Single Local Write Approval

The Naver selected new-order single local write approval is documented in `PHASE_NAVER_ERP_16C_SELECTED_NEW_ORDER_SINGLE_LOCAL_WRITE_APPROVAL.md`.

16C is approval and documentation only. It does not call Naver, does not back up or write the database, does not modify schema or runtime UI, and does not open formal order sync. It approves only the plan for a later 16D single local write of selected safe hash `id-hash-67b5fc1c97`. 16D must still re-check clean worktrees, back up `backend/codex1.db`, rerun a fresh readonly preview, verify the selected hash and duplicate counts, write at most one sanitized local order, keep products/SyncLog/tested_success/timeline counts unchanged, and perform post-write readback plus sensitive scans.

## Phase Naver-ERP-16C2 - Current 24h Candidate Write Approval Plan

The current 24-hour candidate write approval plan is documented in `PHASE_NAVER_ERP_16C2_CURRENT_24H_CANDIDATE_WRITE_APPROVAL_PLAN.md`.

16C2 is approval and documentation only. It does not call Naver, execute `real_sync=true`, back up or write `backend/codex1.db`, change schema, modify runtime UI, or open formal order sync. It exists because the stopped 16D gate saw the 3-day readonly candidate `id-hash-67b5fc1c97`, but the writeable 24-hour guardrail returned a different current candidate, `id-hash-bc5528d093`. Since the 24-hour candidate was not approved by 16C, no order was written. 16C2 approves only the plan for a later one-row retry targeting `id-hash-bc5528d093`; that retry must still back up the database, rerun fresh readonly preview, confirm duplicate counts are zero, pass privacy and required-field gates, write no products/SyncLog/tested_success/timeline rows, and keep all Naver platform write operations plus formal order sync closed.

## Phase Naver-ERP-16D-Retry - Approved Current Candidate Single Local Write

The approved current candidate single local write is documented in `PHASE_NAVER_ERP_16D_RETRY_APPROVED_CURRENT_CANDIDATE_SINGLE_LOCAL_WRITE.md`.

16D-Retry performed one controlled local write for safe hash `id-hash-bc5528d093` after backing up `backend/codex1.db` and rerunning the 24-hour readonly preview. The fresh gate returned HTTP 200 with token/feed/detail HTTP 200, the approved safe hash, zero local duplicate matches, privacy gate passed, and required fields present. Post-write counts are `orders_store8=6`, real Naver local orders 3, mock/test Naver orders 3, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, and `order_status_events_rows=0`. The written row is sanitized with `source_type=naver_real_order_sync`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Formal Naver order sync, batch writes, timeline insertion, and all Naver platform write operations remain closed.

## Phase Naver-ERP-16E - New-Order Post-Write Verification

The new-order post-write verification is documented in `PHASE_NAVER_ERP_16E_NEW_ORDER_POST_WRITE_VERIFICATION.md`.

16E is local verification only. It does not call Naver, execute `real_sync=true`, write local rows, modify schema, change runtime UI, or open formal order sync. It verified safe hash `id-hash-bc5528d093` through direct database readback, Orders API, Dashboard summary, and order-based sales summary. The local real Naver order count is now 3, default Orders API excludes 3 mock/test rows, Dashboard reports `order_count=3`, and order-based sales summary reports `total_orders=3` with `total_sales_amount=1159000.00 KRW`. Sensitive scans found no token, secret, Authorization, header, signature, raw platform response, full id key, address key, or plain phone pattern.

## Phase Naver-ERP-17A - Claim Status Mapping Expansion

The claim status mapping expansion is documented in `PHASE_NAVER_ERP_17A_CLAIM_STATUS_MAPPING_EXPANSION.md`.

17A does not call Naver, write local data, change schema, modify runtime UI, or open formal order sync. It expands backend readonly mapping so `COLLECT_DONE` now displays as `售后取件完成` instead of an unknown status, and adds related safe mappings for claim pickup, return completion, and exchange completion states. Timeline mock mapping now recognizes `COLLECT_DONE` as `claim_collected`. Existing persisted rows are not rewritten; UI display cleanup or a later approved refresh should handle historical sanitized labels separately. Naver after-sales platform actions remain closed.

## Phase Naver-ERP-17B - Orders UI Claim/Delivery Wording Check

The Orders UI claim/delivery wording check is documented in `PHASE_NAVER_ERP_17B_ORDERS_UI_CLAIM_DELIVERY_WORDING_CHECK.md`.

17B updates Codex2 display mapping so Orders and Dashboard main areas show business Chinese wording for Naver delivery and claim states, even when older sanitized rows contain stale labels. `DELIVERY_COMPLETION` is normalized to delivered wording, `COLLECT_DONE` is shown as after-sales pickup completed wording, and return/exchange completed states use operator-friendly labels. The main UI no longer surfaces raw Naver enums such as `DELIVERY_COMPLETION` or `COLLECT_DONE`; technical enum values remain limited to folded diagnostic details. This phase does not modify Codex1, call Naver, write local data, change schema, or open formal order sync.

## Phase ERP-Audit-1A - Local Operation Audit Log Plan

The local operation audit log plan is documented in `PHASE_ERP_AUDIT_1A_LOCAL_OPERATION_AUDIT_LOG_PLAN.md`.

ERP-Audit-1A is planning-only. It defines a future `operation_audit_logs` trail separate from `SyncLog` so production operators can answer who approved or performed a local operation, what object/store was affected, when it happened, what safe fields changed, whether backup/restore evidence exists, and whether sensitive scans passed. It also defines the sensitive-data boundary for audit logs: no tokens, Authorization, headers, signatures, client secrets, raw platform responses, full order ids, full product-order ids, buyer/receiver privacy, phones, addresses, or zip codes. This phase does not create schema, write audit rows, modify runtime UI, or change backup/restore behavior.

## Phase ERP-Audit-1B - Audit Log Schema Proposal

The audit log schema proposal is documented in `PHASE_ERP_AUDIT_1B_AUDIT_LOG_SCHEMA_PROPOSAL.md`.

ERP-Audit-1B is proposal-only. It defines the future `operation_audit_logs` table shape, column types, status/action/target enum direction, indexes, SHA-256 backup/restore fields, safety booleans, JSON summary boundaries, and sensitive-field ban. It keeps audit logging separate from `SyncLog`, proposes no uniqueness constraint for normal audit rows because correlation chains need multiple rows, and recommends a later mock schema gate before any real migration. It does not create a table, run a migration, add a model, write audit rows, or modify runtime UI.

## Phase ERP-Audit-1C - Audit Log Mock Write Gate

The audit log mock write gate is documented in `PHASE_ERP_AUDIT_1C_AUDIT_LOG_MOCK_WRITE_GATE.md`.

ERP-Audit-1C adds private `verify_all.py` coverage for the future `operation_audit_logs` write gate. It creates the proposed table only inside the temporary verification SQLite database, validates columns/defaults/indexes, blocks unapproved writes, rejects invalid SHA-256 and sensitive JSON, writes safe mock audit rows, records blocked-operation evidence without sensitive payloads, and confirms multiple rows can share a `correlation_id`. It does not create a real schema, add a model, run a migration, write real audit rows, call platform APIs, modify runtime UI, or change backup/restore behavior.

## Phase ERP-Audit-1D - Audit Log Schema Migration Approval Plan

The audit log schema migration approval plan is documented in `PHASE_ERP_AUDIT_1D_AUDIT_LOG_SCHEMA_MIGRATION_APPROVAL_PLAN.md`.

ERP-Audit-1D is planning-only. It approves no real schema change by itself; instead, it defines the required pre-checks, explicit operator approval, database backup metadata, zero-row migration rule, post-migration verification, rollback boundary, and sensitive-data ban for a future `operation_audit_logs` migration. The future real migration must be a separate phase and must create only the table and indexes, insert zero audit rows, keep business table counts unchanged, and continue blocking tokens, Authorization, headers, signatures, client secrets, raw platform responses, full platform identifiers, buyer/receiver privacy, phones, and addresses.

## Phase ERP-Audit-1E - Audit Log Schema Migration

The audit log schema migration is documented in `PHASE_ERP_AUDIT_1E_AUDIT_LOG_SCHEMA_MIGRATION.md`.

ERP-Audit-1E creates the real local `operation_audit_logs` table and approved indexes in `backend/codex1.db` after backing up the database. The migration inserted zero audit rows and left business table counts unchanged: stores 8, products 9, orders 9, sync logs 47, tested success results 8, order status events 0, and operation audit logs 0. It adds no runtime audit writer, no public audit endpoint, no frontend audit reader, no restore execution, no platform API call, and no formal product/order sync approval.

## Phase ERP-Audit-1F - Audit Log Post-Migration Verification

The audit log post-migration verification is documented in `PHASE_ERP_AUDIT_1F_AUDIT_LOG_POST_MIGRATION_VERIFICATION.md`.

ERP-Audit-1F is verification-only. It opens the real `backend/codex1.db` in SQLite read-only mode and confirms the `operation_audit_logs` table still has 34 approved columns, 10 approved non-unique indexes, safe defaults, no forbidden columns, zero rows, and unchanged business counts. It also confirms no public audit route exists and runtime audit writing remains disabled. This phase changes no schema, writes no audit or business rows, calls no platform APIs, and opens no formal sync.

## Phase ERP-Audit-1G - Audit Writer Service Mock Gate

The audit writer service mock gate is documented in `PHASE_ERP_AUDIT_1G_AUDIT_WRITER_SERVICE_MOCK_GATE.md`.

ERP-Audit-1G adds a private backend audit writer gate and verifies it only inside the temporary `verify_all.py` database. The helper stays blocked unless write intent, manual approval, and the private verification scope are all present. Tests cover safe mock audit rows, blocked-operation evidence rows, sensitive JSON rejection, invalid SHA-256 rejection, privacy flag rejection, and unchanged business counts. The real `backend/codex1.db` remains `operation_audit_logs=0`; no public audit endpoint, frontend reader, runtime writer, platform API call, or formal sync is opened.

## Phase ERP-Audit-1H - Audit Writer Local Implementation

The audit writer local implementation is documented in `PHASE_ERP_AUDIT_1H_AUDIT_WRITER_LOCAL_IMPLEMENTATION.md`.

ERP-Audit-1H adds a controlled backend local writer helper for future approved internal operations. It requires explicit write intent, manual approval, a private local scope, valid timestamps, valid SHA-256 values, safe flags, and sensitive JSON blocking. `verify_all.py` proves safe local audit rows and blocked-operation evidence rows can be written to the temporary database only. The real `backend/codex1.db` remains `operation_audit_logs=0`; no public audit endpoint, frontend reader, automatic order/product instrumentation, platform API call, or formal sync is opened.

## Phase ERP-Audit-1I - Audit Logs API Readonly Plan

The audit logs API readonly plan is documented in `PHASE_ERP_AUDIT_1I_AUDIT_LOGS_API_READONLY_PLAN.md`.

ERP-Audit-1I is planning-only. It defines the future read-only `operation_audit_logs` API shape, bounded filters, business-first list response, empty-state message, summary endpoint direction, advanced-detail boundary, store/permission boundary, and sensitive-field ban. It does not add a route, expose a public audit API, query real audit rows from the UI, write audit rows, modify schema, call platform APIs, or open formal sync. The real `backend/codex1.db` remains `operation_audit_logs=0`.

## Phase ERP-Audit-1J - Audit Logs API Readonly Mock Gate

The audit logs API readonly mock gate is documented in `PHASE_ERP_AUDIT_1J_AUDIT_LOGS_API_READONLY_MOCK_GATE.md`.

ERP-Audit-1J adds private backend mock-gate coverage for future read-only audit log list and summary responses. The helpers require the private verification scope, return business-first Chinese labels, enforce bounded filters and pagination, keep raw summaries out of the default response, and restrict advanced details to safe enums, abbreviated hashes, abbreviated SHA-256 values, and safe field labels. `verify_all.py` proves the read gate writes no business rows and exposes no public endpoint. The real `backend/codex1.db` remains `operation_audit_logs=0`.

## Phase ERP-Audit-1K - Audit Logs API Readonly Implementation Approval Plan

The audit logs API readonly implementation approval plan is documented in `PHASE_ERP_AUDIT_1K_AUDIT_LOGS_API_READONLY_IMPLEMENTATION_APPROVAL_PLAN.md`.

ERP-Audit-1K is documentation-only. It approves the boundary for a future local read-only audit logs route implementation, limited to list and summary endpoints, bounded filters, business-first responses, opt-in advanced details, and strict sensitive-field bans. It does not add routes, register routers, query audit logs from runtime UI, write audit rows, modify schema, call platform APIs, or open formal sync. The real `backend/codex1.db` remains `operation_audit_logs=0`.

## Phase ERP-Audit-1L - Audit Logs API Readonly Local Implementation

The audit logs API readonly local implementation is documented in `PHASE_ERP_AUDIT_1L_AUDIT_LOGS_API_READONLY_LOCAL_IMPLEMENTATION.md`.

ERP-Audit-1L implements local read-only audit list and summary routes: `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`. The routes use the 1J business-first response shape, enforce bounded filters and capped pagination, keep advanced details opt-in, reject unsupported or unsafe filters, and expose no write/export/delete/detail routes. `verify_all.py` proves read calls write no audit rows or business rows. The real `backend/codex1.db` remains `operation_audit_logs=0`, so an empty response is currently expected.

## Phase ERP-Audit-1M - Audit Logs API Post-Implementation Verification

The audit logs API post-implementation verification is documented in `PHASE_ERP_AUDIT_1M_AUDIT_LOGS_API_POST_IMPLEMENTATION_VERIFICATION.md`.

ERP-Audit-1M verifies the 1L read-only audit routes against the real local backend database. `GET /api/v1/operation-audit-logs?store_id=8` and `GET /api/v1/operation-audit-logs/summary?store_id=8` return HTTP 200 with an empty business state because `operation_audit_logs=0`. `POST`, `PUT`, `PATCH`, and `DELETE` remain 405. Unsupported filters return a safe Chinese business message without echoing raw unsupported names. Real database counts stayed unchanged: `operation_audit_logs=0`, `products=9`, `orders=9`, `sync_logs=47`, `tested_success_store8=8`, and `order_status_events=0`. This phase does not add frontend readers, audit writers, schema changes, platform API calls, backups, restores, or formal product/order sync approval.

## Phase ERP-Audit-1N - Logs/Audit UI Readonly Integration Plan

The Logs/Audit UI readonly integration plan is documented in `PHASE_ERP_AUDIT_1N_LOGS_AUDIT_UI_READONLY_INTEGRATION_PLAN.md`.

ERP-Audit-1N is planning-only. It defines how Codex2 should connect the verified read-only audit API to the Logs page in a later runtime phase: backend mode should call only `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`, show `operation_audit_logs=0` as a normal Chinese empty state, keep SyncLog as a separate `同步记录` section, and keep audit diagnostics folded through `TechnicalDetails`. The plan forbids audit write/delete/export/detail calls, raw JSON display, full hashes or platform ids on the main page, frontend claims that audit writing is live, platform API calls, local data writes, and formal product/order sync approval.

## Phase ERP-Audit-1O - Logs/Audit UI Readonly Implementation

The Logs/Audit UI readonly implementation is documented in `PHASE_ERP_AUDIT_1O_LOGS_AUDIT_UI_READONLY_IMPLEMENTATION.md`.

ERP-Audit-1O implements the Codex2 read-only Logs/Audit UI integration. Backend mode now calls only `GET /api/v1/operation-audit-logs` and `GET /api/v1/operation-audit-logs/summary`, renders `operation_audit_logs=0` as a normal Chinese empty state, keeps SyncLog in a separate `同步记录` section, removes write-like sync controls from the Logs page, and keeps audit diagnostics folded in `TechnicalDetails`. Mock mode continues to show demo operation logs. Shared table, empty-state, pagination, and status badge labels were cleaned for readability. This phase does not modify Codex1 runtime code, write local data, call platform APIs, add audit write/delete/export/detail calls, or open formal product/order sync.

## Phase ERP-Audit-1Q - Audit Writer Integration Approval Plan

The audit writer integration approval plan is documented in `PHASE_ERP_AUDIT_1Q_AUDIT_WRITER_INTEGRATION_APPROVAL_PLAN.md`.

ERP-Audit-1Q is planning-only. It defines how the existing controlled local audit writer may later be connected to selected runtime operations through a separate mock gate first. The first approved target direction is narrow local accountability for controlled Naver order writes/refreshes, backup creation, restore dry-run evidence, and schema migration evidence. Any future real audit write must require explicit approval, clean worktrees, database backup when applicable, safe correlation-chain rows, sensitive scans, and post-write verification. This phase does not write `operation_audit_logs`, change schema, modify Codex2 runtime behavior, call platform APIs, execute backups/restores, or open formal product/order sync.

## Phase ERP-Audit-1R - Audit Writer Integration Mock Gate

The audit writer integration mock gate is documented in `PHASE_ERP_AUDIT_1R_AUDIT_WRITER_INTEGRATION_MOCK_GATE.md`.

ERP-Audit-1R adds a private Codex1 service mock gate for complete safe audit correlation chains, verified only in the temporary `verify_all.py` database. It covers controlled Naver order local write/refresh evidence, database backup evidence, restore dry-run evidence, and schema migration evidence. The gate requires explicit write intent, manual approval, the private verification scope, one shared correlation id, unique request ids, complete required action chains, safe flags, privacy redaction, valid SHA-256 evidence, and sensitive-field blocking. It does not write the real `operation_audit_logs` table, connect runtime business flows, add public audit write/delete/export/detail routes, call platform APIs, execute backup/restore, change schema, or open formal sync.

## Phase ERP-Audit-1S - Audit Writer Runtime Integration Approval Plan

The audit writer runtime integration approval plan is documented in `PHASE_ERP_AUDIT_1S_AUDIT_WRITER_RUNTIME_INTEGRATION_APPROVAL_PLAN.md`.

ERP-Audit-1S is planning-only. It approves only the future direction for a narrow local runtime integration: controlled Naver selected-order local write/refresh evidence, linked pre-write backup evidence, and post-write verification evidence. It keeps automatic middleware, blanket endpoint logging, public audit write/delete/export/detail routes, backup/restore execution, schema changes, platform API calls, and formal product/order sync closed. A later mock-only phase must still prove the exact selected-operation call site before any real runtime audit writer is connected.

## Phase ERP-Audit-1T - Selected Operation Runtime Wiring Mock Plan

The selected-operation runtime wiring mock plan is documented in `PHASE_ERP_AUDIT_1T_SELECTED_OPERATION_RUNTIME_WIRING_MOCK_PLAN.md`.

ERP-Audit-1T is planning-only. It selects `controlled_naver_order_local_refresh` as the first future mock wiring target and defines the fake call-site shape, required five-row audit chain, success criteria, block cases, safe flags, forbidden data, and public API boundary. It does not add code, connect audit writer calls to runtime order flows, write audit or business rows, modify schema, call platform APIs, execute backup/restore, add public audit write routes, or open formal sync.

## Phase ERP-Audit-1U - Selected Operation Runtime Wiring Mock Gate

The selected-operation runtime wiring mock gate is documented in `PHASE_ERP_AUDIT_1U_SELECTED_OPERATION_RUNTIME_WIRING_MOCK_GATE.md`.

ERP-Audit-1U adds a private Codex1 mock helper for `controlled_naver_order_local_refresh` and verifies it only in the temporary `verify_all.py` database. It requires store 8, platform Naver, a safe target order hash, manual approval, backup evidence, fake write result, fake post-write readback, audit write intent, and private verification scope. It writes a five-row audit chain only in the temporary verification database and confirms business counts remain unchanged. It does not connect real runtime order flows, write the real `operation_audit_logs` table, call platform APIs, modify schema, execute backup/restore, add public audit write routes, or open formal sync.

## Phase ERP-Audit-1V - Selected Operation Runtime Wiring Implementation Approval Plan

The selected-operation runtime wiring implementation approval plan is documented in `PHASE_ERP_AUDIT_1V_SELECTED_OPERATION_RUNTIME_WIRING_IMPLEMENTATION_APPROVAL_PLAN.md`.

ERP-Audit-1V is planning-only. It defines the approval boundary for a later local implementation that may connect audit writing to only `controlled_naver_order_local_refresh`. A later implementation must start from clean worktrees, create and verify a database backup, record baseline counts, require explicit user approval, remain limited to store 8 and Naver, write only safe append-only audit rows, and prove readback and sensitive scans. This phase does not add code, connect runtime order flows, write audit or business rows, modify schema, call platform APIs, execute backup/restore, add public audit write routes, or open formal sync.

## Phase ERP-Backup-1A - Database Backup and Restore Drill Plan

The database backup and restore drill plan is documented in `PHASE_ERP_BACKUP_1A_DATABASE_BACKUP_RESTORE_DRILL_PLAN.md`.

ERP-Backup-1A is planning-only. It defines the future backup filename and manifest convention, SHA-256 verification, SQLite integrity checks, temporary restore drill workflow, real restore approval boundary, and phases that must require a backup before writes or migrations. It does not create a backup, restore a database, modify `backend/codex1.db`, change schema, write business data, call platform APIs, modify runtime UI, or change backup/restore behavior.

## Phase ERP-Backup-1B - Backup Metadata and Retention Plan

The backup metadata and retention plan is documented in `PHASE_ERP_BACKUP_1B_BACKUP_METADATA_RETENTION_PLAN.md`.

ERP-Backup-1B is planning-only. It defines future backup manifest metadata, retention classes, retention windows, protected-from-auto-delete rules, cleanup approval gates, restore metadata checks, and future audit-log relationships. It does not create backups, delete backups, restore a database, modify `backend/codex1.db`, change schema, write business data, call platform APIs, modify runtime UI, or change backup/restore behavior. The first cleanup implementation must be report-only and must not delete files automatically.

## Phase ERP-Backup-1C - Restore Verification Dry-Run

The restore verification dry-run is documented in `PHASE_ERP_BACKUP_1C_RESTORE_VERIFICATION_DRY_RUN.md`.

ERP-Backup-1C adds private `verify_all.py` coverage for a future restore verification workflow. It creates a temporary SQLite fixture, temporary backup copy, safe manifest, and temporary restore target, then verifies SHA-256, file size, retention class, safety flags, sensitive-field rejection, `PRAGMA integrity_check`, expected tables, and restored row counts. It blocks the production database path as a restore target and confirms the real `backend/codex1.db` is unchanged. It does not create production backups, restore the real database, delete backups, modify schema, write business data, call platform APIs, modify runtime UI, or open any formal sync.

## Phase ERP-Backup-1D - Real Backup Manifest Implementation Plan

The real backup manifest implementation plan is documented in `PHASE_ERP_BACKUP_1D_REAL_BACKUP_MANIFEST_IMPLEMENTATION_PLAN.md`.

ERP-Backup-1D is planning-only. It defines the future manifest writer contract for real `backend/codex1.db` backups: required fields, computed hash/size/integrity data, path safety, atomic UTF-8 JSON writes, baseline counts, retention defaults, sensitive-field boundaries, and future audit correlation. It does not create backup files, write manifest files, restore a database, delete backups, modify schema, write local data, call platform APIs, modify runtime UI, or open formal sync.

## Phase ERP-Backup-1E - Backup Manifest Mock Implementation Gate

The backup manifest mock implementation gate is documented in `PHASE_ERP_BACKUP_1E_BACKUP_MANIFEST_MOCK_IMPLEMENTATION_GATE.md`.

ERP-Backup-1E adds temporary-file `verify_all.py` coverage for a future backup manifest writer. The mock gate writes only temporary fixture manifests, computes SHA-256/size/integrity/counts from fixture backup files, validates retention and path safety, blocks sensitive fields, blocks manifest overwrite, and proves the real `backend/codex1.db` hash and size remain unchanged. It does not create production backups, write production manifest files, restore a database, delete backups, modify schema, write local data, call platform APIs, modify runtime UI, or open formal sync.

## Phase ERP-Backup-1F - Real Local Backup Implementation Approval Plan

The real local backup implementation approval plan is documented in `PHASE_ERP_BACKUP_1F_REAL_LOCAL_BACKUP_IMPLEMENTATION_APPROVAL_PLAN.md`.

ERP-Backup-1F is planning-only. It defines the approval boundary for a later manual local backup helper for `backend/codex1.db`, including the approved backup root, source/path checks, SQLite backup method expectation, manifest generation, integrity checks, baseline counts, overwrite blocking, sensitive boundaries, and failure handling. It does not create backup files, write production manifest files, restore a database, delete backups, modify schema, write local data, call platform APIs, modify runtime UI, or open formal sync.

## Phase ERP-Backup-1G - Real Local Backup Helper Implementation

The real local backup helper implementation is documented in `PHASE_ERP_BACKUP_1G_REAL_LOCAL_BACKUP_HELPER_IMPLEMENTATION.md`.

ERP-Backup-1G implements `backend/scripts/create_local_backup.py` for manual local backups of `backend/codex1.db`. The helper uses SQLite online backup, validates the temporary backup before finalizing, writes a side-by-side UTF-8 manifest, records safe SHA-256/size/integrity/count metadata, blocks unsupported paths/retention/sensitive inputs/overwrites, and is covered by `verify_all.py` fixture tests. This phase creates one real local backup file and manifest under the approved local backup root, but it does not restore a database, delete backups, modify schema, write business rows, write `operation_audit_logs`, call platform APIs, modify runtime UI, or open formal sync.

## Phase ERP-UX-1A - Frontend Production Usability Plan

The frontend production usability plan is documented in `PHASE_ERP_UX_1A_FRONTEND_PRODUCTION_USABILITY_PLAN.md`.

ERP-UX-1A is planning-only. It defines how the frontend should become usable for non-technical operators by making Dashboard, Orders, Products, Credentials, API status, Logs, Audit, Backup, and Restore screens business-first. Main pages should show Chinese business copy, daily tasks, safe next actions, and formal-sync status without exposing raw enums, safe hashes, guardrail wording, `real_sync`, `store_id`, `credential_id`, HTTP details, or other technical fields. Those fields belong only in collapsed `TechnicalDetails` or diagnostic views. This phase does not modify runtime frontend code, Codex1, database schema, local data, platform APIs, or formal sync gates.

## Phase ERP-UX-1B - Frontend Technical Field Inventory

The frontend technical field inventory is documented in `PHASE_ERP_UX_1B_FRONTEND_TECHNICAL_FIELD_INVENTORY.md`.

ERP-UX-1B is inventory-only. It scans Codex2 pages, adapters, service helpers, and `TechnicalDetails` usage for technical fields that can confuse non-technical operators. The main findings are visible `store #...` chips in Orders, Products, and Sales; a visible `store_id=8` Orders restriction message; seller-facing no-write wording that mentions `orders`, `SyncLog`, and `tested_success`; and the need to keep API capability result codes collapsed. It does not modify runtime code, Codex1, schema, local data, platform APIs, or formal sync gates.

## Phase ERP-UX-1C - Dashboard Business Summary Cleanup

The Dashboard business summary cleanup is documented in `PHASE_ERP_UX_1C_DASHBOARD_BUSINESS_SUMMARY_CLEANUP.md`.

ERP-UX-1C updates Codex2 Dashboard runtime UI so Naver stores show a business-first `今日经营摘要` before generic statistics. Backend mode no longer shows a visible `数据源 backend` chip; mock mode still shows `演示数据`. Main Dashboard copy now avoids `store #...`, `store_id`, `real_sync`, `SyncLog`, and `tested_success`, while technical diagnostics stay folded in `TechnicalDetails`. This phase does not modify Codex1, call platform APIs, write data, change schema, or open formal product/order sync.

## Phase ERP-UX-1D - Orders Business Display Cleanup

The Orders business display cleanup is documented in `PHASE_ERP_UX_1D_ORDERS_BUSINESS_DISPLAY_CLEANUP.md`.

ERP-UX-1D updates Codex2 Orders runtime UI so Naver order summaries are business-first: local operational orders, fulfillment, delivery, claims, detail visibility, and formal-sync status are separated from technical gate fields. Main Orders copy no longer shows `store #...`, `store_id=8`, `real_sync`, `SyncLog`, or `tested_success`; refresh protection details stay folded in `TechnicalDetails`. The order detail section may show full order number, product number, buyer, receiver, phone, and address information, while Dashboard and list summaries remain concise. This phase does not modify Codex1, call platform APIs during validation, write data, change schema, or open formal order sync.

## Phase ERP-UX-1E - Products Business Display Cleanup

The Products business display cleanup is documented in `PHASE_ERP_UX_1E_PRODUCTS_BUSINESS_DISPLAY_CLEANUP.md`.

ERP-UX-1E updates Codex2 Products runtime UI so Naver product summaries are business-first: local products, stock alerts, price/stock change hints, refresh-only count, skipped count, and formal-sync status are separated from technical preview fields. Main Products copy no longer shows `store #...`, `store_id`, `real_sync`, `SyncLog`, or `tested_success`; product preview and inventory diagnostics stay folded in `TechnicalDetails`. Product identifiers remain masked in summary/list views, and formal Naver product batch sync remains closed. This phase does not modify Codex1, call platform APIs during validation, write data, change schema, or open formal product sync.

## Phase ERP-UX-1F - Credentials and API Status Wording Cleanup

The Credentials and API status wording cleanup is documented in `PHASE_ERP_UX_1F_CREDENTIALS_API_STATUS_WORDING_CLEANUP.md`.

ERP-UX-1F updates Codex2 API Credentials and API Capabilities runtime UI so connection status, authorization issues, IP allowlist problems, product/order access, and formal-sync boundaries are shown in business Chinese. Main pages no longer surface raw technical enums such as `ip_not_allowed`, `token_auth_failed`, `product_api_not_allowed`, `http_status`, `safe_keyword_flags`, `credential_id`, or channel identifiers; those diagnostics remain folded in `TechnicalDetails`. This phase does not modify Codex1, call platform APIs during validation, write data, change schema, or open formal product/order sync.

## Phase ERP-UX-1G - Logs and Audit Readability Plan

The Logs and Audit readability plan is documented in `PHASE_ERP_UX_1G_LOGS_AUDIT_READABILITY_PLAN.md`.

ERP-UX-1G is planning-only. It defines how Logs and Audit should read for production operators: main pages should explain what happened, who did it, whether it succeeded, whether backup/restore evidence exists, and what to do next. Sync logs should be framed as `同步记录`, future audit logs should focus on accountability and recoverability, and raw ids, hashes, JSON payloads, backend enums, SHA-256 values, and other technical details should stay in folded advanced details. This phase does not modify runtime frontend code, Codex1, platform APIs, local data, database schema, or formal sync gates.

## Phase ERP-UX-1H - Production Usability Mock Walkthrough

The production usability mock walkthrough is documented in `PHASE_ERP_UX_1H_PRODUCTION_USABILITY_MOCK_WALKTHROUGH.md`.

ERP-UX-1H checks the current Codex2 mock frontend across Dashboard, Orders, Products, Sales, API Capabilities, Accounts, Logs, and Settings. The mock pages load without console errors or mojibake, use business-facing Chinese, keep technical details folded, and do not claim formal Naver product/order sync is open. The Logs detail modal also keeps before/after JSON folded by default. This phase does not modify runtime frontend code, Codex1, platform APIs, local data, database schema, or formal sync gates.

## Phase ERP-UX-1I - Logs Runtime Readability Cleanup

The Logs runtime readability cleanup is documented in `PHASE_ERP_UX_1I_LOGS_RUNTIME_READABILITY_CLEANUP.md`.

ERP-UX-1I updates Codex2 Logs runtime UI so administrator-facing audit pages are easier to read: the page now starts with an `审计可读性摘要`, frames sync jobs as `同步记录`, frames local history as `操作记录`, shows business columns such as object/action/actor/result/risk/next step, and keeps internal log numbers, raw status, raw risk level, IP/device/source, and JSON before/after payloads folded in advanced details. It does not claim full production audit coverage because the real audit-log service is not live yet. This phase does not modify Codex1, call platform APIs, write local data, change schema, or open formal sync gates.

## Phase ERP-UX-1J - TechnicalDetails Safety Hardening Plan

The TechnicalDetails safety hardening plan is documented in `PHASE_ERP_UX_1J_TECHNICALDETAILS_SAFETY_HARDENING_PLAN.md`.

ERP-UX-1J is planning-only. It defines a frontend last-line-of-defense redaction plan for folded technical details: labels and values related to tokens, Authorization, headers, signatures, client secrets, raw responses, full platform ids, buyer/receiver privacy, phones, and addresses must be hidden, while safe diagnostics such as error codes, http status, safe keyword flags, mapping versions, source phases, safe hashes, counts, and booleans may remain visible only inside folded administrator details. This phase does not modify runtime frontend code, Codex1, platform APIs, local data, schema, or formal sync gates.

## Phase ERP-UX-1K - TechnicalDetails Safety Hardening Implementation

The TechnicalDetails safety hardening implementation is documented in `PHASE_ERP_UX_1K_TECHNICALDETAILS_SAFETY_HARDENING_IMPLEMENTATION.md`.

ERP-UX-1K updates Codex2 runtime `TechnicalDetails` with strict default redaction. Folded administrator details now hide token, Authorization, headers, signatures, bcrypt/sign values, client secrets, raw response/body fields, full channel/product/order identifiers, buyer/receiver names and phones, and address-like fields. Safe diagnostics such as error codes, HTTP status, business hints, safe keyword flags, hashes, mapping versions, counts, booleans, source phases, and backup metadata can still appear in folded details. Logs before/after JSON is passed through the same redaction helper before rendering. This phase does not modify Codex1, call platform APIs, write local data, change database schema, or open formal product/order sync.

## Phase ERP-Backup-1H - Backup Restore Drill Using 1G Manifest

The backup restore drill using the 1G manifest is documented in `PHASE_ERP_BACKUP_1H_BACKUP_RESTORE_DRILL_USING_1G_MANIFEST.md`.

ERP-Backup-1H adds `backend/scripts/restore_backup_dry_run.py` and verifies the existing 1G backup by copying it only to a temporary restore file, checking SHA-256, SQLite integrity, and baseline counts, then deleting the temporary copy. The real drill completed with `status=restore_dry_run_verified`, `real_restore_executed=false`, `production_db_touched=false`, and `backup_deleted=false`. This phase does not restore the real database, delete backups, write business data, call platform APIs, change schema, or open formal sync.

## Phase ERP-Backup-1I - Backup List/Report Readonly Helper

The backup list/report readonly helper is documented in `PHASE_ERP_BACKUP_1I_BACKUP_LIST_REPORT_READONLY_HELPER.md`.

ERP-Backup-1I adds `backend/scripts/list_local_backups.py` for safe readonly backup manifest reporting. It lists approved-root manifests, validates required fields, reports existence and size match, abbreviates SHA-256, and returns safe counts, retention metadata, and safety booleans. The real report returned one valid manifest from ERP-Backup-1G with sensitive scan passed. It does not delete backups, restore databases, write audit rows, write business data, call platform APIs, change schema, or open formal sync.

## Phase ERP-Audit-1W - Backup Creation Audit Integration Approval Plan

The backup creation audit integration approval plan is documented in `PHASE_ERP_AUDIT_1W_BACKUP_CREATION_AUDIT_INTEGRATION_APPROVAL_PLAN.md`.

ERP-Audit-1W is planning-only. It defines the future safe audit chain for real backup creation: `backup_planned`, `backup_created`, `backup_hash_verified`, `backup_integrity_verified`, and `backup_manifest_verified`. It does not write audit rows, create backups, restore databases, modify schema, write business data, call platform APIs, or open formal sync.

## Phase ERP-Audit-1X - Backup Creation Audit Mock Gate

The backup creation audit mock gate is documented in `PHASE_ERP_AUDIT_1X_BACKUP_CREATION_AUDIT_MOCK_GATE.md`.

ERP-Audit-1X adds a private `write_backup_creation_audit_mock_gate(...)` helper in Codex1. It writes a five-row backup audit chain only inside the temporary `verify_all.py` database after private scope, manual approval, verified SHA-256, integrity, manifest, and safety flags pass. It does not write the real `operation_audit_logs` table, create backups, restore databases, write business data, call platform APIs, change schema, or open formal sync.

## Phase Naver-ERP-18A - Controlled Order Refresh Backup Evidence Gate

The controlled order refresh backup evidence gate is documented in `PHASE_NAVER_ERP_18A_ORDER_REFRESH_BACKUP_EVIDENCE_GATE.md`.

Naver-ERP-18A adds a private backup-evidence wrapper around the existing Naver order refresh batch mock gate. Write-enabled paths are blocked unless safe backup evidence verifies SHA-256, SQLite integrity, manifest presence, and safety flags; readonly paths remain allowed without backup evidence because they do not write data. Verification runs only in the temporary database and proves no `products`, `SyncLog`, `ApiCapabilityTestResult`, or timeline event writes occur. It does not call Naver, write the real database, wire a public endpoint, or open formal Naver order sync.

## Phase ERP-Backup-1J - Backup Report Readonly API Approval Plan

The backup report readonly API approval plan is documented in `PHASE_ERP_BACKUP_1J_BACKUP_REPORT_READONLY_API_APPROVAL_PLAN.md`.

ERP-Backup-1J is planning-only. It approves only `GET /api/v1/backups/local-report` and `GET /api/v1/backups/local-report/summary` as future readonly endpoints. The future route must not accept filesystem paths, restore targets, delete flags, or cleanup controls. This phase does not add code, write data, restore or delete backups, call platform APIs, change schema, modify Codex2 runtime UI, or open formal sync.

## Phase ERP-Backup-1K - Backup Report Readonly API Mock Gate

The backup report readonly API mock gate is documented in `PHASE_ERP_BACKUP_1K_BACKUP_REPORT_READONLY_API_MOCK_GATE.md`.

ERP-Backup-1K adds `backend/app/services/backup_service.py` with a private mock gate for backup report API behavior. It reads only temporary fixture backup manifests under private verification scope, returns safe business metadata, blocks unsupported or sensitive cases, and confirms no restore, delete, production database touch, audit write, business write, platform API call, or formal sync occurs.

## Phase ERP-Backup-1L - Backup Report Readonly Local API Implementation

The backup report readonly local API implementation is documented in `PHASE_ERP_BACKUP_1L_BACKUP_REPORT_READONLY_LOCAL_API_IMPLEMENTATION.md`.

ERP-Backup-1L implements `GET /api/v1/backups/local-report` and `GET /api/v1/backups/local-report/summary`. The endpoints read only the approved local backup root, accept only `limit`, reject unsupported query parameters without echoing raw values, return safe backup evidence and business messages, and keep `backup_deleted=false`, `real_restore_executed=false`, `production_db_touched=false`, and `rows_written=0`. They do not create/restore/delete backups, write audit or business rows, call platform APIs, change schema, modify Codex2 runtime UI, or open formal sync.

## Phase ERP-Audit-1Y - Backup Creation Audit Runtime Wiring Approval Plan

The backup creation audit runtime wiring approval plan is documented in `PHASE_ERP_AUDIT_1Y_BACKUP_CREATION_AUDIT_RUNTIME_WIRING_APPROVAL_PLAN.md`.

ERP-Audit-1Y is planning-only. It defines the future narrow runtime connection from successful manual backup creation to append-only audit rows: `backup_planned`, `backup_created`, `backup_hash_verified`, `backup_integrity_verified`, and `backup_manifest_verified`. It does not write audit rows, create backups, restore/delete backups, call platform APIs, change schema, or open formal sync.

## Phase ERP-Audit-1Z - Backup Creation Audit Runtime Wiring Mock Gate

The backup creation audit runtime wiring mock gate is documented in `PHASE_ERP_AUDIT_1Z_BACKUP_CREATION_AUDIT_RUNTIME_WIRING_MOCK_GATE.md`.

ERP-Audit-1Z adds a private Codex1 mock gate that proves a successful backup helper result can be converted into the five-row backup audit chain in the temporary verification database only. It does not write the real audit table, create backups, restore/delete backups, write business rows, call platform APIs, change schema, or open formal sync.

## Phase ERP-Audit-2A - Backup Creation Audit Local Implementation

The backup creation audit local implementation is documented in `PHASE_ERP_AUDIT_2A_BACKUP_CREATION_AUDIT_LOCAL_IMPLEMENTATION.md`.

ERP-Audit-2A creates a real local backup and writes five append-only rows to `operation_audit_logs` for the backup evidence chain. Only audit rows are written; products, orders, SyncLog, tested-success records, order timeline rows, schema, platform APIs, restore/delete actions, and formal sync remain untouched.

## Phase ERP-Audit-2B - Backup Audit Post-Write Verification

The backup audit post-write verification is documented in `PHASE_ERP_AUDIT_2B_BACKUP_AUDIT_POST_WRITE_VERIFICATION.md`.

ERP-Audit-2B verifies the 2A audit chain by readback only: five actions, one correlation id, backup target type, safe backup hash evidence, false raw/secret flags, privacy redaction, sensitive scan pass, and unchanged business counts. It does not write new rows.

## Phase Naver-ERP-18B - Controlled Order Refresh With Real Backup Evidence Approval Plan

The controlled order refresh with real backup evidence approval plan is documented in `PHASE_NAVER_ERP_18B_CONTROLLED_ORDER_REFRESH_WITH_REAL_BACKUP_EVIDENCE_APPROVAL_PLAN.md`.

Naver-ERP-18B is planning-only. It defines the approval gate for a later controlled Naver order refresh write that must use fresh real backup evidence before any local update. The future write remains capped, manually approved, privacy-gated, and limited to existing local real Naver orders. This phase does not call Naver, execute `real_sync=true`, write local data, create timeline events, write SyncLog or tested-success records, change schema, modify Codex2 runtime UI, or open formal Naver order sync.

## Phase ERP-Backup-1M - Backup Report Frontend Readonly Display Plan

The backup report frontend readonly display plan is documented in `PHASE_ERP_BACKUP_1M_BACKUP_REPORT_FRONTEND_READONLY_DISPLAY_PLAN.md`.

ERP-Backup-1M defines how the Logs/Audit administrator page should show backup evidence in business language while keeping restore/delete/cleanup actions out of scope.

## Phase ERP-Backup-1N - Backup Report Frontend Readonly Implementation

The backup report frontend readonly implementation is documented in `PHASE_ERP_BACKUP_1N_BACKUP_REPORT_FRONTEND_READONLY_IMPLEMENTATION.md`.

ERP-Backup-1N connects Codex2 to the existing readonly backup report APIs and adds a `本地备份报告` section to Logs/Audit. It shows backup counts, manifest safety, latest backup evidence, and folded diagnostics, without restore/delete/cleanup controls and without any platform API or business-data write.

## Phase ERP-Audit-2C - Selected Operation Audit Local Implementation Approval Plan

The selected operation audit local implementation approval plan is documented in `PHASE_ERP_AUDIT_2C_SELECTED_OPERATION_AUDIT_LOCAL_IMPLEMENTATION_APPROVAL_PLAN.md`.

ERP-Audit-2C is planning-only. It approves only the future audit coverage boundary for `controlled_naver_order_local_refresh`: manual approval, verified pre-write backup evidence, selected local Naver order target, append-only audit rows, post-write verification, and strict sensitive-data exclusion. It does not modify runtime code, write audit rows, write business rows, create or restore backups, call platform APIs, change schema, or open formal Naver order sync.

## Phase ERP-Audit-2D - Selected Operation Audit Local Implementation Mock Gate

The selected operation audit local implementation mock gate is documented in `PHASE_ERP_AUDIT_2D_SELECTED_OPERATION_AUDIT_LOCAL_IMPLEMENTATION_MOCK_GATE.md`.

ERP-Audit-2D adds a private Codex1 mock gate for the production-shaped selected-operation audit chain: `approval_verified`, `pre_write_backup_verified`, `selected_operation_started`, `selected_operation_finished`, and `post_write_verification_finished`. It writes only to the temporary `verify_all.py` database, requires manual approval, verified backup evidence, formal sync closed, platform writes disabled, privacy redaction, and safe target hashes. It does not write the real database, call platform APIs, change schema, or open formal Naver order sync.

## Phase Naver-ERP-18C - Controlled Order Refresh Readonly Repeat With Backup Evidence

The controlled order refresh readonly repeat is documented in `PHASE_NAVER_ERP_18C_ORDER_REFRESH_READONLY_REPEAT_WITH_BACKUP_EVIDENCE.md`.

Naver-ERP-18C reruns the real Naver order preview in readonly mode after the current outbound IP was allowlisted. The request used `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail all returned HTTP 200, with safe hash `id-hash-192b9c67e8`, status `DELIVERED / 配送完成`, amount `499000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Counts stayed unchanged: `orders_store8=6`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=5`, and `order_status_events=0`. Formal order sync remains closed.

## Phase Naver-ERP-18D - Controlled Order Refresh Small Write Approval

The controlled order refresh small write approval review is documented in `PHASE_NAVER_ERP_18D_CONTROLLED_ORDER_REFRESH_SMALL_WRITE_APPROVAL.md`.

Naver-ERP-18D does not approve a refresh write for the 18C candidate. Local readback showed that safe hash `id-hash-192b9c67e8` does not match an existing real local Naver order, while refresh writes are only for existing local orders. This phase did not call Naver, execute `real_sync=true`, write local data, write audit rows, change schema, or open formal order sync. The safe next direction is a separate selected new-order candidate approval plan if the operator wants to consider writing this candidate.

## Phase Naver-ERP-19A - Selected New-Order Candidate Approval Plan

The selected new-order candidate approval plan is documented in `PHASE_NAVER_ERP_19A_SELECTED_NEW_ORDER_CANDIDATE_APPROVAL_PLAN.md`.

Naver-ERP-19A is planning-only. It approves safe hash `id-hash-192b9c67e8` only for a fresh readonly repeat as a selected new-order candidate, not as an existing-order refresh candidate. Any later write requires exact hash repeat, duplicate count zero, privacy gate pass, fresh database backup, one-order limit, post-write readback, audit evidence, no SyncLog write, no tested-success write, no product write, no platform write, and no formal order sync opening.

## Phase Naver-ERP-19B - Selected New-Order Readonly Repeat

The selected new-order readonly repeat is documented in `PHASE_NAVER_ERP_19B_SELECTED_NEW_ORDER_READONLY_REPEAT.md`.

Naver-ERP-19B calls the existing Naver order preview endpoint in readonly mode over a recent 3-day KST window. Token, feed, and detail returned HTTP 200. The observed safe hash matched `id-hash-192b9c67e8`, remained `candidate_new`, and had `配送完成`, amount `499000 KRW`, `raw_response_saved=false`, `privacy_fields_redacted=true`, and `address_saved=false`. Counts stayed unchanged: `orders_store8=6`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=5`, and `order_status_events=0`. Formal order sync remains closed.

## Phase Naver-ERP-19C - Selected New-Order Single Local Write Approval

The selected new-order single local write approval is documented in `PHASE_NAVER_ERP_19C_SELECTED_NEW_ORDER_SINGLE_LOCAL_WRITE_APPROVAL.md`.

Naver-ERP-19C approves only a later one-order local write for safe hash `id-hash-192b9c67e8`, after clean worktrees, fresh database backup, fresh readonly preview, duplicate count zero, privacy gate, one-candidate limit, post-write readback, and five-row operation audit evidence. This phase does not call Naver, execute `real_sync=true`, write local data, write audit rows, create backups, change schema, or open formal order sync.

## Phase Naver-ERP-19D - Selected New-Order Single Local Write With Audit Evidence

The selected new-order single local write with audit evidence is documented in `PHASE_NAVER_ERP_19D_SELECTED_NEW_ORDER_SINGLE_LOCAL_WRITE_WITH_AUDIT_EVIDENCE.md`.

Naver-ERP-19D creates a fresh database backup, repeats the selected Naver order readonly preview, confirms safe hash `id-hash-192b9c67e8`, passes the privacy gate, and writes exactly one local Naver order. Counts changed as expected: `orders_store8=6 -> 7`, `products_store8=5 -> 5`, `sync_logs_store8=1 -> 1`, `tested_success_store8=8 -> 8`, and `order_status_events=0 -> 0`. Five append-only audit rows were written for approval, backup, operation start, operation finish, and post-write verification. Formal order sync and all Naver platform write operations remain closed.

## Phase Naver-ERP-19E - Selected New-Order Post-Write Audit Verification

The selected new-order post-write audit verification is documented in `PHASE_NAVER_ERP_19E_SELECTED_NEW_ORDER_POST_WRITE_AUDIT_VERIFICATION.md`.

Naver-ERP-19E is readback-only. It confirms the selected safe hash exists exactly once, `orders_store8=7`, `operation_audit_logs=10`, and the 19D audit chain has exactly five safe rows with one correlation id. It does not call Naver, write local data, change schema, modify Codex2 runtime code, or open formal order sync.

## Phase ERP-Auth-1A - Role and Permission Model Plan

The role and permission model plan is documented in `PHASE_ERP_AUTH_1A_ROLE_PERMISSION_MODEL_PLAN.md`.

ERP-Auth-1A is planning-only. It defines the first local ERP roles (`owner`, `admin`, `operator`, `auditor`, `viewer`), store-scoped permission groups, and sensitive actions that need explicit approval. It does not add user tables, public auth routes, schema changes, local writes, platform calls, or Codex2 runtime behavior.

## Phase ERP-Auth-1B - Store-Scoped Access Gate Mock

The store-scoped access gate mock is documented in `PHASE_ERP_AUTH_1B_STORE_SCOPED_ACCESS_GATE_MOCK.md`.

ERP-Auth-1B adds a private Codex1 permission mock gate that verifies role, store scope, operation permission, and sensitive actor-context blocking. It is covered by `verify_all.py` only and is not connected to runtime routes or frontend behavior.

## Phase ERP-Auth-1C - Sensitive Action Approval Roles

The sensitive action approval roles phase is documented in `PHASE_ERP_AUTH_1C_SENSITIVE_ACTION_APPROVAL_ROLES.md`.

ERP-Auth-1C extends the private mock gate for sensitive actions such as `orders.local_write`, `orders.refresh_batch_write`, backup creation, restore, credential updates, schema migrations, and formal sync opening. It verifies manual approval and role approval in mock only, with no business writes and no public API surface.

## Phase ERP-Auth-1D - Frontend Role-Aware Action Visibility Plan

The frontend role-aware action visibility plan is documented in `PHASE_ERP_AUTH_1D_FRONTEND_ROLE_AWARE_ACTION_VISIBILITY_PLAN.md`.

ERP-Auth-1D is planning-only. It defines how Codex2 should eventually hide, disable, or explain sensitive actions using business wording while keeping permission keys and gate diagnostics inside folded technical details.

## Phase Naver-ERP-20A - Controlled Order Refresh Batch With Audit Approval Plan

The controlled order refresh batch with audit approval plan is documented in `PHASE_NAVER_ERP_20A_CONTROLLED_ORDER_REFRESH_BATCH_WITH_AUDIT_APPROVAL_PLAN.md`.

Naver-ERP-20A is planning-only. It defines the next controlled order refresh batch path after the selected new-order write: backup, readonly candidate repeat, store-scoped role gate, sensitive action approval, audit chain, post-write readback, and sensitive scan. It does not call Naver, execute `real_sync=true`, write data, write audit rows, change schema, or open formal order sync.

## Phase Naver-ERP-20B - Controlled Order Refresh Batch Readonly Repeat

The controlled order refresh batch readonly repeat is documented in `PHASE_NAVER_ERP_20B_CONTROLLED_ORDER_REFRESH_BATCH_READONLY_REPEAT.md`.

Naver-ERP-20B reruns the real Naver order preview in readonly mode with `store_id=8`, `credential_id=7`, a recent 3-day KST window, `page=1`, `size=1`, `real_preview=true`, `include_detail=true`, `complete_field_preview=false`, and `real_sync=false`. Token, feed, and detail returned HTTP 200. The observed safe hash was `id-hash-192b9c67e8`, matched exactly one existing local Naver order, and is classified as an existing local refresh candidate. Counts stayed unchanged: `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=10`, and `order_status_events=0`.

## Phase Naver-ERP-20C - Controlled Order Refresh Batch Write Approval

The controlled order refresh batch write approval plan is documented in `PHASE_NAVER_ERP_20C_CONTROLLED_ORDER_REFRESH_BATCH_WRITE_APPROVAL.md`.

Naver-ERP-20C is planning-only. It does not write the candidate. A later refresh write still requires clean worktrees, a fresh backup, a fresh readonly repeat, exact identity match, store-scoped role permission, sensitive-action approval, audit evidence, post-write readback, and sensitive scan. Formal order sync and platform order writes remain closed.

## Phase ERP-Auth-1E - Runtime Permission API Approval Plan

The runtime permission API approval plan is documented in `PHASE_ERP_AUTH_1E_RUNTIME_PERMISSION_API_APPROVAL_PLAN.md`.

ERP-Auth-1E approves only a mock-gate public API surface for safe role inventory, store-scoped permission checks, and sensitive-action approval checks. It does not create a production auth session, user table, schema migration, platform API call, business write, or formal sync approval.

## Phase ERP-Auth-1F - Runtime Permission API Mock Gate

The runtime permission API mock gate is documented in `PHASE_ERP_AUTH_1F_RUNTIME_PERMISSION_API_MOCK_GATE.md`.

ERP-Auth-1F adds `GET /api/v1/permissions/role-inventory`, `POST /api/v1/permissions/mock-check`, and `POST /api/v1/permissions/sensitive-action/mock-check`. The routes expose only safe mock permission results and business messages, with `real_auth_session_created=false`, `real_database_written=false`, `raw_response_saved=false`, `formal_sync_open=false`, and `platform_writes_enabled=false`.

## Phase ERP-UX-2A - Role-Aware Action Visibility Implementation

The role-aware action visibility implementation is documented in `PHASE_ERP_UX_2A_ROLE_AWARE_ACTION_VISIBILITY_IMPLEMENTATION.md`.

ERP-UX-2A updates the Codex2 Orders page to show business-first role/action visibility for Naver orders: current role can view orders, order refresh writes require administrator approval, backup/readonly/audit gates remain required, and formal order batch sync remains closed. Permission keys and mock diagnostics stay inside folded `TechnicalDetails`.

## Phase Naver-ERP-20D - Controlled Order Refresh Write Execution Approval With Permission Evidence

The controlled order refresh write execution approval is documented in `PHASE_NAVER_ERP_20D_CONTROLLED_ORDER_REFRESH_WRITE_EXECUTION_APPROVAL_WITH_PERMISSION_EVIDENCE.md`.

Naver-ERP-20D approves only one controlled existing-order refresh attempt for safe hash `id-hash-192b9c67e8`. Runtime permission evidence confirmed store-scoped access and sensitive-action approval in the mock permission API. The approval still requires backup, fresh readonly preview, exact identity match, privacy gate, audit chain, readback, and sensitive scan.

## Phase Naver-ERP-20E - Controlled Existing-Order Refresh Single Local Write With Audit Evidence

The controlled existing-order refresh execution is documented in `PHASE_NAVER_ERP_20E_CONTROLLED_EXISTING_ORDER_REFRESH_SINGLE_LOCAL_WRITE_WITH_AUDIT_EVIDENCE.md`.

Naver-ERP-20E created a pre-write backup, repeated the readonly Naver preview, and executed the controlled refresh gate for safe hash `id-hash-192b9c67e8`. The gate found no business-field changes, so it correctly did not update the order. Five audit evidence rows were written with terminal action `local_write_blocked` and reason `no_business_field_change`. Orders, products, SyncLog, tested-success rows, and order timeline events were not changed.

## Phase Naver-ERP-20F - Controlled Refresh Post-Write Verification

The controlled refresh post-write verification is documented in `PHASE_NAVER_ERP_20F_CONTROLLED_REFRESH_POST_WRITE_VERIFICATION.md`.

Naver-ERP-20F verified the no-change refresh outcome by readback. Current counts are `orders_total=10`, `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=15`, and `order_status_events=0`. The selected safe hash exists exactly once and the 20E audit chain has five rows under one correlation id.

## Phase ERP-Auth-1G - Permission API Frontend-Wide Visibility Plan

The frontend-wide permission visibility plan is documented in `PHASE_ERP_AUTH_1G_PERMISSION_API_FRONTEND_WIDE_VISIBILITY_PLAN.md`.

ERP-Auth-1G is planning-only. It defines how Dashboard, Products, Orders, Sales, Credentials/API, Logs/Audit, Backups, and Settings should use business wording for permission states while keeping permission keys and gate diagnostics folded.

## Phase ERP-Auth-1H - Runtime Permission API Production Auth Boundary Plan

The production auth boundary plan is documented in `PHASE_ERP_AUTH_1H_RUNTIME_PERMISSION_API_PRODUCTION_AUTH_BOUNDARY_PLAN.md`.

ERP-Auth-1H is planning-only. It records that the current permission API is a mock visibility and approval-planning API, not a production authentication system. Future production auth still needs user/session/role/store-membership schema, route dependencies, role assignment UI, cross-store isolation tests, backups, and rollback plans.

## Phase ERP-Auth-1I - User and Role Schema Proposal

The user and role schema proposal is documented in `PHASE_ERP_AUTH_1I_USER_ROLE_SCHEMA_PROPOSAL.md`.

ERP-Auth-1I defines the future production-auth shape for `erp_users`, `erp_roles`, `erp_permissions`, and `erp_role_permissions`. It is proposal-only and does not create real auth sessions, migrate schema, write production rows, call platform APIs, or open formal sync.

## Phase ERP-Auth-1J - Store Membership Schema Proposal

The store membership schema proposal is documented in `PHASE_ERP_AUTH_1J_STORE_MEMBERSHIP_SCHEMA_PROPOSAL.md`.

ERP-Auth-1J defines the future `erp_store_memberships` boundary so every permission decision can prove store scope. It remains proposal-only with no database write and no runtime UI change.

## Phase ERP-Auth-1K - Auth Schema Mock Migration Gate

The auth schema mock migration gate is documented in `PHASE_ERP_AUTH_1K_AUTH_SCHEMA_MOCK_MIGRATION_GATE.md`.

ERP-Auth-1K adds a `verify_all.py` temporary-database gate for the proposed auth tables. It verifies roles, permissions, store membership, sensitive-column exclusions, and unchanged business counts without touching `backend/codex1.db`.

## Phase ERP-Backup-2A - Restore Runbook and Operator Checklist Plan

The restore runbook and operator checklist plan is documented in `PHASE_ERP_BACKUP_2A_RESTORE_RUNBOOK_OPERATOR_CHECKLIST_PLAN.md`.

ERP-Backup-2A defines the checklist for a future real restore: source backup manifest, SHA-256, temp restore dry-run, baseline counts, pre-restore backup, approval, audit evidence, and rollback plan. Real restore remains closed.

## Phase Naver-ERP-21A - Existing-Order Refresh No-Change UI/Audit Display Check

The no-change refresh UI/audit display check is documented in `PHASE_NAVER_ERP_21A_EXISTING_ORDER_REFRESH_NO_CHANGE_UI_AUDIT_DISPLAY_CHECK.md`.

Naver-ERP-21A records how to explain the 20E/20F no-change refresh: the selected order was checked, no business fields changed, no local update was forced, and audit evidence was recorded. It must not be displayed as formal order sync availability.

## Phase ERP-Auth-1L - Auth Schema Migration Approval Plan

The auth schema migration approval plan is documented in `PHASE_ERP_AUTH_1L_AUTH_SCHEMA_MIGRATION_APPROVAL_PLAN.md`.

ERP-Auth-1L approves only the local auth foundation migration: auth tables plus safe role/permission metadata. It does not approve real users, store memberships, login sessions, public auth routes, business writes, platform APIs, restore execution, or formal sync opening.

## Phase ERP-Auth-1M - Auth Schema Migration Implementation

The auth schema migration implementation is documented in `PHASE_ERP_AUTH_1M_AUTH_SCHEMA_MIGRATION_IMPLEMENTATION.md`.

ERP-Auth-1M adds Codex1 auth models and `backend/scripts/upgrade_auth_schema.py`, creates a pre-migration backup, and applies the local schema. The real local database now has 5 auth foundation tables plus safe system role/permission metadata. It keeps `erp_users=0` and `erp_store_memberships=0`, so production login remains closed.

## Phase ERP-Auth-1N - Auth Schema Post-Migration Verification

The auth schema post-migration verification is documented in `PHASE_ERP_AUTH_1N_AUTH_SCHEMA_POST_MIGRATION_VERIFICATION.md`.

ERP-Auth-1N verifies `erp_roles=5`, `erp_permissions=10`, `erp_role_permissions=35`, `erp_users=0`, and `erp_store_memberships=0`. Business counts stay stable, admin can approve `orders.refresh_batch_write`, and operator cannot receive that permission.

## Phase ERP-Backup-2B - Restore Runbook Mock Drill Gate

The restore runbook mock drill gate is documented in `PHASE_ERP_BACKUP_2B_RESTORE_RUNBOOK_MOCK_DRILL_GATE.md`.

ERP-Backup-2B adds a private restore checklist gate to Codex1. It verifies a future restore request has manifest, hash, dry-run, approval, audit, rollback, and post-restore evidence before any real restore can be considered. It does not execute restore or expose a public restore API.

## Phase Naver-ERP-21B - Existing-Order No-Change Audit UI Runtime Walkthrough

The existing-order no-change audit UI walkthrough is documented in `PHASE_NAVER_ERP_21B_EXISTING_ORDER_NO_CHANGE_AUDIT_UI_RUNTIME_WALKTHROUGH.md`.

Naver-ERP-21B confirms the expected UI wording for the 20E/20F no-change refresh: checked again, no business fields changed, no forced local update, audit evidence recorded, formal order sync still closed.

## Phase ERP-Batch-1A - Formal Batch Sync Production Gate Plan

The formal batch sync production gate plan is documented in `PHASE_ERP_BATCH_1A_FORMAL_BATCH_SYNC_PRODUCTION_GATE_PLAN.md`.

ERP-Batch-1A shifts the next priority toward formal product/order batch sync readiness. It defines the required production gates: human approval, store-scoped permission, sensitive-action approval, fresh readonly evidence, verified backup, duplicate protection, field whitelist, rollback plan, failure isolation, append-only audit, readback, and sensitive scan. Formal product and order batch sync remain closed.

## Phase ERP-Batch-1B - Batch Sync Approval and Backup Mock Gate

The batch sync approval and backup mock gate is documented in `PHASE_ERP_BATCH_1B_BATCH_SYNC_APPROVAL_AND_BACKUP_MOCK_GATE.md`.

ERP-Batch-1B adds a private Codex1 mock gate for future formal batch sync readiness. It supports Naver order batch, Naver order refresh batch, and Naver product batch gate checks. A passing result can only say the gate is ready for a later execution phase; it still returns `formal_sync_open=false`, `formal_order_sync_open=false`, `formal_product_sync_open=false`, `orders_written=false`, and `products_written=false`.

The local auth permission metadata now includes `products.batch_sync_write`, `orders.batch_sync_write`, and `store_membership.assign`, with `erp_permissions=13`, `erp_role_permissions=41`, `erp_users=0`, and `erp_store_memberships=0`.

## Phase Naver-Order-Batch-1A - Naver Order Batch Refresh Production Plan

The Naver order batch refresh production plan is documented in `PHASE_NAVER_ORDER_BATCH_1A_NAVER_ORDER_BATCH_REFRESH_PRODUCTION_PLAN.md`.

Naver-Order-Batch-1A defines how selected-order and small-batch refresh evidence can evolve into a controlled production order batch path. The path requires fresh readonly feed/detail evidence, exact hash matching, privacy/status gates, whitelist-only changes, backup evidence, role permission, sensitive approval, audit chain, and post-write readback. Shipment, cancel, return, exchange, refund, settlement, customer service, mail, appeal, and AI automation writes remain closed.

## Phase Naver-Product-Batch-1A - Naver Product Batch Sync Production Plan

The Naver product batch sync production plan is documented in `PHASE_NAVER_PRODUCT_BATCH_1A_NAVER_PRODUCT_BATCH_SYNC_PRODUCTION_PLAN.md`.

Naver-Product-Batch-1A defines the path from the current 5-row product proof toward future batch sync: page/window preview, duplicate detection, field whitelist, price/stock/status change classification, backup, role permission, sensitive approval, audit chain, rollback plan, and readback. The existing `products_store8=5` result remains a small-batch proof, not a formal opening.

## Phase ERP-Multistore-1A - Multi-Store Production Operation Model Plan

The multi-store production operation model plan is documented in `PHASE_ERP_MULTISTORE_1A_MULTI_STORE_PRODUCTION_OPERATION_MODEL_PLAN.md`.

ERP-Multistore-1A defines the production model for large-scale multi-store operations: known actor identity, active store membership, role scope, per-store task state, failure isolation, audit evidence, backup/restore evidence, and business-safe dashboard summaries. Auth foundation tables exist, but real users and store memberships are still not active.

## Phase ERP-Batch-1C - Formal Batch Sync Readonly Evidence API Plan

The formal batch sync readonly evidence API plan is documented in `PHASE_ERP_BATCH_1C_FORMAL_BATCH_SYNC_READONLY_EVIDENCE_API_PLAN.md`.

ERP-Batch-1C plans a future readonly evidence API for formal batch approval screens. It remains planning-only: no public execution endpoint, no formal sync opening, and no business writes.

## Phase ERP-Batch-1D - Batch Sync Approval UI Plan

The batch sync approval UI plan is documented in `PHASE_ERP_BATCH_1D_BATCH_SYNC_APPROVAL_UI_PLAN.md`.

ERP-Batch-1D plans the future operator-facing approval UI. It should show candidate counts, changed fields, backup evidence, permission approval, audit readiness, and rollback readiness in business language while keeping technical diagnostics folded.

## Phase Naver-Order-Batch-1B - Order Batch Readonly Candidate Window

The Naver order batch readonly candidate window is documented in `PHASE_NAVER_ORDER_BATCH_1B_ORDER_BATCH_READONLY_CANDIDATE_WINDOW.md`.

Naver-Order-Batch-1B ran a recent 3-day KST readonly window through the existing protected order preview endpoint. HTTP returned `200`, preview status was `success`, safe hash `id-hash-192b9c67e8` was observed, and the local sync status remained `not_requested`. No orders, products, SyncLog rows, tested-success rows, audit rows, or timeline events were written. Formal order batch sync remains closed.

## Phase Naver-Product-Batch-1B - Product Batch Page Expansion Readonly Repeat

The Naver product batch page expansion readonly repeat is documented in `PHASE_NAVER_PRODUCT_BATCH_1B_PRODUCT_BATCH_PAGE_EXPANSION_READONLY_REPEAT.md`.

Naver-Product-Batch-1B ran protected readonly product previews for `page=1,size=5` and `page=2,size=5`. Page 1 returned `would_update=3`, `would_refresh_only=2`, and changed field name `stock_quantity`; page 2 returned `success_empty`. No product writes were performed. The new stock-change signal requires manual review before any later write phase.

## Phase ERP-Multistore-1B - Store Membership Assignment Approval Plan

The store membership assignment approval plan is documented in `PHASE_ERP_MULTISTORE_1B_STORE_MEMBERSHIP_ASSIGNMENT_APPROVAL_PLAN.md`.

ERP-Multistore-1B plans the first production-safe store membership assignment flow. It does not create users, assign memberships, activate login, or enable large-scale multi-store production operation.

## Phase Naver-Product-Batch-1C - Product Stock-Change Approval Plan

The product stock-change approval plan is documented in `PHASE_NAVER_PRODUCT_BATCH_1C_PRODUCT_STOCK_CHANGE_APPROVAL_PLAN.md`.

Naver-Product-Batch-1C plans the approval boundary for the 3 stock-only Naver product changes observed in readonly preview. It does not approve local writes and does not open formal product batch sync.

## Phase Naver-Product-Batch-1D - Product Stock-Change Mock Write Gate

The product stock-change mock write gate is documented in `PHASE_NAVER_PRODUCT_BATCH_1D_PRODUCT_STOCK_CHANGE_MOCK_WRITE_GATE.md`.

Naver-Product-Batch-1D adds a private Codex1 helper for stock-only product update readiness: `_evaluate_naver_product_stock_change_mock_write_gate(...)`. It verifies exact `stock_quantity` changes, backup evidence, audit/rollback readiness, and admin approval for `products.batch_sync_write`. It never writes products.

## Phase ERP-Batch-1E - Readonly Evidence API Mock Gate

The readonly evidence API mock gate is documented in `PHASE_ERP_BATCH_1E_READONLY_EVIDENCE_API_MOCK_GATE.md`.

ERP-Batch-1E adds `_evaluate_batch_readonly_evidence_api_mock_gate(...)` for future batch approval screens. It normalizes safe evidence while keeping `public_endpoint_enabled=false`, `formal_sync_open=false`, `orders_written=false`, and `products_written=false`.

## Phase ERP-Multistore-1C - Store Membership Mock Assignment Gate

The store membership mock assignment gate is documented in `PHASE_ERP_MULTISTORE_1C_STORE_MEMBERSHIP_MOCK_ASSIGNMENT_GATE.md`.

ERP-Multistore-1C adds `evaluate_store_membership_assignment_mock_gate(...)`. It checks safe target user hash, target store, target role, assignment reason, admin approval for `store_membership.assign`, and duplicate active membership. It does not create users or memberships.

## Phase ERP-Auth-1O - Auth Role Assignment Approval Plan

The auth role assignment approval plan is documented in `PHASE_ERP_AUTH_1O_AUTH_ROLE_ASSIGNMENT_APPROVAL_PLAN.md`.

ERP-Auth-1O documents the future role assignment approval flow. Production login, user creation, role assignment UI, route-level authorization, and real store memberships remain closed.
