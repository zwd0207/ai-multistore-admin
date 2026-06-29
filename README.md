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
