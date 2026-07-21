# AI 多店铺运营系统目标对齐审计

审计日期：2026-07-19
审计分支：`release/operator-v1`
审计提交：`4027e761f53b1eef80e32eb1542aa7c83305e713`
生产代码基线：`62e49ba9cfdd19a6f6b026c25d53fc3f2ad98401`
审计性质：只读代码、测试和 Git 证据审计；未修改业务代码、模型、数据库或部署。

> 本文件是一次性审计证据，不是日常当前状态入口。原始分类和原始结论保留用于追溯；本文末尾的“审计校准说明”与 `docs/PROJECT_CONTROL.md` 的当前分类优先。

## 1. 调整后的项目目标

项目定位调整为公司内部自用的 AI 多店铺运营系统。当前主目标不是建设商业 SaaS，而是让内部运营人员在同一个系统中完成以下工作：

1. 管理公司业务空间、店铺、平台账号、API 凭证、紫鸟设备和店铺邮箱。
2. 自动读取并统一展示商品、订单、库存/SKU、发货、物流、客服咨询、销售数据、平台邮件和风险。
3. 通过今日工作台回答“现在需要处理什么”，并让任务深链到唯一业务页面。
4. 使用 AI 做总结、分类、建议和异常分析；AI 不绕过人工确认执行平台写入。
5. 对客服回复和发货回填采用单次人工确认、幂等、失败关闭、未知结果对账和完整审计。

当前不优先建设开放注册、商业租户、套餐收费、完整移动端、无人值守写入、自动申诉、广告自动化或市场情报平台。已有相关代码不删除，按“内部复用、冻结或未来兼容”处理。

## 2. 审计口径与当前代码事实摘要

### 2.1 审计口径

- “代码存在”不等于“业务完成”。只有进入生产主路由、具备真实数据合同并有测试或生产证据，才判定为完成。
- Mock、preview、readonly-check、dry-run 和历史 Phase 文档只证明门禁或设计，不证明真实运营闭环。
- 当前生产事实优先取 `docs/archive/governance/COMMANDER_DECISIONS.md` 的 D044-D049 和 `docs/archive/governance/COMMANDER_STATE.md` 尾部的 Current Release Gate；文件顶部的旧状态不作为当前事实。
- 本次未连接生产服务器、未读取生产客户数据、未调用 Naver/紫鸟真实接口。

### 2.2 当前事实

- 仓库有 755 个跟踪文件，其中 397 个 Markdown、351 个根目录 `PHASE_*` 文档、29 个 `.codex-handoff` 文档。
- 后端包含 23 个模型文件、约 40 个服务、30 个端点模块和 41 个 `verify_*.py` 脚本。
- 前端包含 17 条主要业务路由、91 个 `src` 文件和 28 个合同/构建/浏览器验证脚本。
- 生产基础已完成 PostgreSQL 16、Alembic、HTTPS、MFA 会话、小时级加密 OSS 备份和恢复演练；证据见 D044-D045。
- 两个获批 Naver 店铺的订单、咨询、商品和物流只读自动同步已完成首轮真实验证；物流共保存 44 条受保护记录，证据见 D048-D049。
- 平台写入、客服回复、发货回填、商品/库存修改和 AI 自动操作仍关闭。
- AI 端点当前只返回结构化上下文，没有模型调用，见 `backend/app/api/v1/endpoints/ai.py:12`。

### 2.3 本次验证结果

- 前端编码、会话、全部合同测试、生产构建和 Bundle 门禁通过。
- 构建产物为 38 个 JavaScript chunk，入口 273,629 字节，`bundle:verify` 通过。
- 后端 `verify_all.py` 在运行到 T24 双店自动读取验证前，T13-T24、物流、发货、紫鸟、会话和备份专项均通过。
- 全量后端验证最终失败：`verify_t24_dual_store_automatic_read.py:63` 固定 `NOW=2026-07-17`，但准备代码在 `prepare_t24_dual_store_automatic_read.py:187` 调用的清理健康检查使用真实当前时间，导致 2026-07-19 被判定为过期。该结果是测试时钟不一致，不能据此认定生产同步失败，但当前 HEAD 不能宣称“今天 verify_all 全部通过”。
- 本地 PostgreSQL 并发验证因未设置一次性 `T22_TEST_POSTGRES_URL` 而跳过；历史 GitHub CI 的 PostgreSQL 16 任务通过，证据见 D049。

## 3. 已完成能力清单

以下能力有实现和验证证据，可直接保留：

1. PostgreSQL/Alembic 生产基线、HTTPS、CI、加密 OSS 备份与恢复演练。
2. 登录、密码、TOTP MFA、恢复码、会话、CSRF、近期认证和安全响应头。
3. 店铺成员关系、店铺级权限、跨店隔离和平台管理员跨空间审计。
4. `Store` 主数据、全局店铺选择器、双店切换和归档状态。
5. Naver API 凭证加密、验证、一键开店、最近 30 天初始读取和历史订单回填。
6. 商品读取、精确平台商品 ID、受控本地缩略图。
7. 当前/历史订单、商品订单号、订单状态时间线、隐私字段门禁。
8. Naver 物流只读快照、脱敏运单、过期控制和订单/客服上下文。
9. 受保护 Naver 咨询读取、已回复/未回复分类、客户与店铺历史对话展示。
10. `SyncCheckpoint` 租约、重试、错峰、过期状态和 T16 验证恢复。
11. `SyncLog`、`OperationAuditLog` 和隐私字段扫描边界。
12. 后端生成的今日工作台任务、异常优先展示和现有页面深链。

## 4. 模块分类表

分类统计以“主要能力切片”为单位，不以文件数为单位：A 12 项、B 8 项、C 5 项、D 4 项、E 8 项、F 3 项，共 40 项。

| # | 主要模块/能力 | 分类 | 当前事实 | 处理建议 | 主要证据 |
|---:|---|:---:|---|---|---|
| 1 | PostgreSQL、Alembic、HTTPS、备份与 CI | A | 已生产迁移并恢复演练 | 直接保留 | `ops/`, `.github/workflows/ci.yml`, D044-D045 |
| 2 | 会话、MFA、CSRF、近期认证 | A | 生产验证完成 | 保留，停止重复开发 | `models/auth.py`, `session_service.py`, `verify_production_sessions.py` |
| 3 | 店铺权限、成员关系、审计 | A | 店铺隔离和敏感操作门禁已验证 | 保留为内部权限底座 | `operator_access_service.py`, `operation_audit_log.py` |
| 4 | 店铺主数据与选择器 | A | 双店生产数据切换通过 | 保留唯一 `Store` | `models/store.py`, `StoreContext.jsx`, `StoreSelector.jsx` |
| 5 | Naver API 凭证与一键开店 | A | 凭证加密、验证、30 天导入和历史回填已实现 | 保留现有 onboarding | `api_credential.py`, `store_onboarding_service.py`, T13 tests |
| 6 | 商品读取与缩略图 | A | 精确商品 ID、本地 WebP 合同通过 | 保留 `Product` 和缩略图服务 | `product.py`, `product_thumbnail_service.py` |
| 7 | 订单、历史订单和状态事件 | A | 当前/历史视图、时间线、分页和隐私门禁已实现 | 保留 `Order` + `OrderStatusEvent` | `orders.py`, `order_service.py`, `Orders.jsx` |
| 8 | Naver 物流只读 | A | 双店 44 条受保护物流记录验证通过 | 保留唯一物流快照实现 | `pxg_naver_readonly.py:93`, D049 |
| 9 | Naver 受保护咨询和聊天展示 | A | 30 天咨询、分类、历史问答展示完成 | 保留受保护表为 Naver 主实现 | `naver_readonly_inquiry_service.py`, `CustomerService.jsx` |
| 10 | 自动读取、租约、重试、恢复 | A | 两店四资源 `SyncCheckpoint` 主流程完成 | 保留唯一调度状态 | `automatic_read_sync_service.py`, `sync_checkpoint.py` |
| 11 | 同步日志和操作审计 | A | 唯一同步日志和审计链已投入生产 | 保留，不建第二套日志 | `sync_log.py`, `operation_audit_log.py` |
| 12 | 今日工作台任务中心 | A | 后端任务分区和前端深链已完成 | 保留后端为唯一计算源 | `stats_service.py:675`, `Dashboard.jsx:118` |
| 13 | 公司主体和营业执照 | B | 没有独立公司/证照数据合同 | 先定义最小内部主体字段，再决定是否扩展 `Tenant` | 全仓无 Company/License 模型 |
| 14 | 平台账号统一关系 | B | `Store`、平台登录和 API 凭证可用，但缺统一业务定义 | 先定义聚合口径，不立即加表 | `store.py`, `platform_login_credential.py`, `api_credential.py` |
| 15 | SKU 映射和库存口径 | B | 平台库存与物流库存均存在，但页面口径未统一 | 明确两个库存来源和 SKU 主键 | `product.py:22`, `shipping.py:10`, `shipping.py:64` |
| 16 | 仓库发货和平台回填 | B | 五阶段批次和安全 attempt 已实现；未真实授权 | 继续复用，保持写入关闭到单记录验收 | `WarehouseShippingBatch`, T18 tests |
| 17 | 人工客服回复 | B | 旧回复服务存在，但当前受保护咨询明确禁用回复 | 先统一咨询主键和 attempt 合同 | `sync_service.py:1608`, `customer_inquiry_service.py:188` |
| 18 | 销售与结算 | B | 订单金额汇总可用；平台销售/结算主要为 Coupang 结构 | 当前只认订单运营销售，结算冻结 | `financial.py`, `stats_service.py:277` |
| 19 | 店铺邮箱、平台邮件和风险 | B | 邮箱/重要邮件 CRUD 有，真实收信和分类器没有 | 复用模型和页面，后续接一个批准的收信适配器 | `email_account.py`, `important_email.py` |
| 20 | AI 总结、分类、建议、异常分析 | B | 只有结构化 `daily-context`，没有模型调用 | 复用上下文合同，AI 层后置 | `ai.py`, `stats_service.py:1382` |
| 21 | 邀请、密码重置和租户管理扩展 | C | T23 已完成，但当前不做外部 SaaS 开放 | 保留生产安全能力，冻结商业化扩展 | `tenant.py`, `tenant_auth_service.py`, `TenantPages.jsx` |
| 22 | Coupang 同步和财务适配 | C | 代码较多但未进入当前生产业务主线 | 保留、关闭入口、停止扩展 | `sync_service.py` 的 Coupang 函数、`financial.py` |
| 23 | 申诉案件和自动申诉方向 | C | 本地 CRUD/页面存在，自动提交禁用 | 保留资料壳，冻结自动申诉 | `appeal_case.py`, `Appeals.jsx` |
| 24 | 正式批量审批/证据工作台 | C | 大量 readonly-check/mock gate 已完成 | 保留审计经验，冻结继续堆门禁 | `batch.py`, `sync_service.py:7985+` |
| 25 | 完整手机端操作 | C | 390px 响应式通过，写操作边界已有合同 | 仅保留手机只读，冻结完整操作端 | `t23-t26-auth-boundary.contract.test.mjs` |
| 26 | `Tenant` 语义 | D | 目前是 SaaS 租户，但可作为内部公司/业务空间 | 只改产品语义，不改模型名和表名 | `tenant.py:10`, `auth.py:33`, `store.py:22` |
| 27 | 用户/角色/成员关系语义 | D | 可直接作为内部员工和店铺权限 | 将 owner/admin 解释为内部职责，冻结客户套餐语义 | `auth.py:126-228` |
| 28 | 紫鸟目录、设备和打开后台 | D | Windows 本地 T19/T20 已验证；Linux 生产关闭 | 重定义为每台员工电脑的 Windows 助手 | `ziniao_directory_sync_service.py`, `platform_login_service.py` |
| 29 | API 能力矩阵 | D | 适合内部连接诊断，不适合普通运营主流程 | 降级为管理员诊断来源，不继续建设独立工作台 | `api_capability.py`, `ApiCapabilities.jsx` |
| 30 | 通用咨询表与受保护 Naver 咨询表 | E | 两套表、两套写入/读取逻辑并存 | Naver 以受保护表为主，通用表仅兼容非 Naver/历史 | `customer_inquiry.py`, `pxg_naver_readonly.py:123` |
| 31 | 旧发货导出/导入与仓库批次 | E | 旧 `ShippingExport/TrackingImport` 与新 `WarehouseShippingBatch` 并存 | 仓库批次为主，旧接口冻结只读兼容 | `shipping.py:105-377`, `shipping.py` endpoints |
| 32 | 平台库存与物流库存 | E | `Product.stock_quantity` 与 `LogisticsInventoryItem` 都被称为库存 | 保留两者但强制标注来源，禁止相互覆盖 | `product.py:28`, `shipping.py:83` |
| 33 | 设备页和环境页 | E | 后端模式都渲染同一 `BackendDeviceEnvironmentPage` | 选一个主入口，另一个保留重定向/兼容 | `Devices.jsx`, `Environment.jsx` |
| 34 | 后端待办与前端派生状态 | E | 主工作台用后端任务，但前端仍有多套订单/库存工具计算 | 后端合同为准，前端工具仅显示 | `stats_service.py:675`, `src/utils/naver*` |
| 35 | 账号页面职责 | E | 内部成员、邀请、平台登录和 API 凭证堆在同一页 | 以“平台连接”主流程为主，员工管理移出首屏 | `BackendAccountsPage.jsx:15-18` |
| 36 | `sync_service.py` 多代实现 | E | 14,050 行，混合 Mock、Naver、Coupang、财务、回复和批量门禁；有 3 个重复顶层函数名 | 冻结新增，后续按调用边界渐进迁出 | `sync_service.py:3355-3537` |
| 37 | Mock/Backend 双运行路径 | E | 默认数据源为 Mock，`Proxy` 对缺失方法回退 Mock | 生产构建必须 fail-closed；Mock 仅测试/演示 | `dataSource.js:1`, `dataProvider.js` 尾部 |
| 38 | Mock 页面、数据和客户端 | F | 不进入生产主流程，但仍被开发模式使用 | 隔离到 demo/test 命名空间，先不删除 | `src/pages/Mock*`, `src/data/mockData.js`, `clients/*_client.py` |
| 39 | 旧 Phase 文档和过期状态头 | F | 历史价值高，但当前状态相互矛盾 | 归档、只读；当前事实只认控制文档 | 351 个根目录 `PHASE_*`, `docs/archive/governance/COMMANDER_STATE.md` 顶部 |
| 40 | 旧 SQLite 升级脚本和历史门禁脚本 | F | PostgreSQL/Alembic 已成为生产主线 | 标记 legacy，确认无生产调用后再决定移除 | `backend/scripts/upgrade_*.py` |

## 5. 已完成但暂缓扩展的能力

1. **邀请/密码重置/租户管理**：保留作为未来内部员工入职能力；停止开放注册、商业租户、套餐和客户自助管理扩展。
2. **Coupang 适配**：保留客户端、模型和历史验证；当前主阶段不继续打磨真实同步。
3. **API 能力矩阵和批量审批证据**：保留技术审计成果；普通运营界面不继续增加技术卡片和门禁页面。
4. **申诉案件**：保留本地资料结构；停止自动申诉和平台提交。
5. **手机端**：保留响应式和只读能力；停止在当前阶段增加发货、回复、凭证修改等手机写操作。

## 6. 可以重新定义和复用的能力

| 现有能力 | 新定义 | 最低成本做法 |
|---|---|---|
| `Tenant` | 公司/业务空间 | 保留表名和外键，只调整文案、权限说明和创建规则 |
| `ErpUser`/Role/Membership | 内部员工、岗位和店铺授权 | 保留安全模型；停止面向客户的 owner/plan 语义扩展 |
| T23 邀请流程 | 内部员工邀请 | 保留 24 小时邀请、MFA 和恢复码；不提供公开注册 |
| `DeviceEnvironment` | 紫鸟设备/网络环境 | `source_provider=ziniao` 作为自动来源，手工环境作为兼容来源 |
| `PlatformLoginCredential` | 平台后台账号绑定 | 仅做受控人工后台登录信息，不与 API 凭证合并 |
| API 能力矩阵 | 内部连接诊断 | 结果进入店铺连接状态；独立技术页面冻结 |
| 响应式 UI | 手机只读巡检 | 保留 390px 规则，统一隐藏写操作 |
| T19/T20 | Windows 紫鸟助手内核 | 服务器不运行 CLI；以后由配对的 Windows 助手执行 |

## 7. 重复实现和冲突点

### 7.1 用户、租户、公司和团队

- `Tenant` 已与 `ErpUser`、`Store`、`ErpSession.selected_tenant_id` 绑定，能承担内部公司空间。
- 没有公司主体、营业执照、税号或法律实体模型。当前把“租户”直接当“公司”只能覆盖权限范围，不能覆盖证照管理。
- `platform_admin` 全局选择租户的 SaaS 语义偏重，但安全边界可用于内部系统总管理员。

### 7.2 店铺、平台账号和 API 凭证

- `Store.platform` 表示业务平台；`ApiCredential` 表示 API 身份；`PlatformLoginCredential` 表示人工后台登录，三者职责原则上不同。
- 当前没有明确的“平台卖家账号/频道”聚合对象，频道号主要藏在 `ApiCredential.extra_config`。
- `BackendAccountsPage` 同时展示内部成员、邀请、平台登录和 API 凭证，导致“系统账号”和“店铺平台账号”概念混用。

### 7.3 店铺、紫鸟设备和浏览器环境

- `Store` 保存紫鸟外部身份；`DeviceEnvironment` 保存网络环境；`PlatformLoginCredential` 可绑定设备。
- `Devices` 与 `Environment` 两个前端路由在 backend 模式使用同一组件，是明确重复入口。
- 生产 Linux 关闭紫鸟 CLI，因此当前实现只能作为 Windows 本地能力，不能被描述为服务器功能。

### 7.4 店铺和邮箱

- `EmailAccount`、`ImportantEmail` 模型和 CRUD 已存在。
- 没有 IMAP/POP/API 收信适配器、同步 checkpoint、邮件风险分类器或真实平台邮件导入。
- `auth_email_delivery_service` 只服务系统邀请/密码重置 SMTP，不能冒充店铺邮箱读取。

### 7.5 商品、平台商品、SKU和库存

- `Product` 是平台商品主记录，唯一键为 `store_id + platform + external_product_id`。
- `Product.sku/stock_quantity` 是平台观察值；`LogisticsInventoryMapping/Item` 是物流仓 SKU 和库存。
- 当前 Inventory 页面读取 `Product.stock_quantity`，发货链读取物流库存，两者没有统一“来源/更新时间/可用量”合同。
- 映射表仍以规范化商品名+选项做唯一键，平台 ID 哈希只是可选字段；长期应优先稳定 ID，但本次不迁移。

### 7.6 订单、发货、物流和售后

- `Order` + `OrderStatusEvent` 是订单主线；`PxgNaverReadonlyLogisticsRecord` 是只读物流主线。
- `WarehouseShippingBatch` 是当前推荐发货主流程。
- 旧 `ShippingExportBatch`、`ShippingTrackingImportBatch` 仍被仓库批次复用部分数据结构，因此不能直接删除，但其独立入口不应继续扩展。
- 售后主要来自订单 claim 状态；`AppealCase` 是单独本地资料壳，不应复制订单状态。

### 7.7 客服咨询、历史消息和回复

- `PxgNaverReadonlyCustomerInquiry` 是当前生产 Naver 咨询主记录，内容加密、详情授权解密。
- `CustomerInquiry` 是早期通用表，旧 Naver 同步和回复服务仍引用它。
- 列表服务会合并两表并过滤被受保护记录替代的旧数据，但 `stats_service` 的部分统计和 `daily-context` 仍只统计通用表。
- 受保护咨询返回 `reply_enabled=false`，而前端回复请求仍指向旧 `/sync/customer-inquiries/naver/reply`。这是客服写入闭环的核心冲突。

### 7.8 前端待办和后端待办

- 推荐主实现是 `stats_service._build_operator_workbench()` 输出的 `operator_workbench`。
- `Dashboard` 已直接展示后端任务，但 `src/utils/naverOrderFulfillment.js`、`naverInventory.js`、`shippingAssistant.js` 等仍在页面侧派生状态。
- 页面局部展示可以保留工具函数；跨页面待办数量和优先级必须只由后端输出。

### 7.9 Mock 和真实数据

- `VITE_DATA_SOURCE` 默认 `mock`；当前本地忽略的 `.env.local` 决定是否使用后端。
- `dataProvider` 用 `Proxy` 将未实现方法回退到 `mockApi`，可能让 backend 页面悄悄显示 Mock 结果。
- CI 默认构建没有锁定 backend 数据源，因此 CI 产物与生产 backend 构建不是完全同一配置合同。

### 7.10 同步、重试和日志

- 长期自动同步的唯一状态应是 `SyncCheckpoint`，唯一日志应是 `SyncLog`。
- `StoreOnboarding` 只负责一次性开店和历史回填，不与自动任务竞争。
- `PxgNaverReadonlySyncBatch/Backup` 是受控持久化和回滚证据，不是第二套 scheduler。
- `sync_service.py` 仍包含旧 Mock、手工同步、preview、Coupang、批量门禁和旧客服回复，是实现重叠的主要来源。

### 7.11 真实写入、预览、确认、防重复和审计

- 发货主路径已具备审批 grant、原子 attempt、`unknown` 和 reconcile；推荐保留。
- 旧 `/shipment-writeback/*-gate` 仍注册为门禁接口，但唯一真实入口是仓库批次 writeback。
- 客服回复只有双开关和基本调用，缺少与受保护咨询兼容的 attempt/reconcile 主线。
- 所有真实写开关当前关闭，符合调整后的人工确认原则。

## 8. 推荐的唯一主实现

| 业务能力 | 推荐主实现 | 冻结/兼容实现 |
|---|---|---|
| 公司范围 | 现有 `Tenant`，产品语义改为内部公司/业务空间 | 新建第二套 Company/Tenant 表 |
| 内部账号 | `ErpUser` + Role + Membership + Session | MockAccounts 中的独立账号体系 |
| 店铺 | `Store` | 任何第二套紫鸟店铺表 |
| 平台连接 | `Store` 聚合 `ApiCredential` 与 `PlatformLoginCredential` | 在 Accounts 页面继续混合内部用户和平台账号 |
| Naver 开店 | `StoreOnboarding` | 手工反复 smoke/preview 流程作为运营主入口 |
| 商品 | `Product` | 独立 Naver 商品表 |
| 库存/SKU | `LogisticsInventoryMapping/Item` 作为仓库库存；`Product.stock_quantity` 仅平台库存 | 把两者合并为一个无来源数量 |
| 订单 | `Order` + `OrderStatusEvent` | 新订单表、历史订单表 |
| 物流 | `PxgNaverReadonlyLogisticsRecord` | 在订单 raw_data 中重复保存完整物流 |
| Naver 咨询 | `PxgNaverReadonlyCustomerInquiry` | 旧通用 Naver 写入链；通用表仅保留非 Naver/历史兼容 |
| 自动同步 | `SyncCheckpoint` + `automatic_read_sync_service` | 新 scheduler、新任务表 |
| 同步日志 | `SyncLog` | 第二套同步日志 |
| 今日待办 | 后端 `operator_workbench` | 前端跨页面重新统计优先级 |
| 仓库发货 | `WarehouseShippingBatch` 及其 rows/grants | 独立旧 shipment writeback 流程 |
| 发货 attempt | `WarehouseShippingApprovalGrant` 当前安全账本 | 无账本直接重发 |
| 客服写入 | 当前没有批准的唯一主实现 | 旧 generic reply 路径冻结，待受保护咨询 attempt 合同 |
| AI 输入 | `GET /ai/daily-context` 的结构化上下文 | 页面直接拼 Prompt 或直接执行写入 |
| 紫鸟 | T19/T20 服务逻辑迁入未来 Windows 助手 | Linux 服务器直接调用本机 CLI |

## 9. 渐进式迁移路线

### 阶段 0：冻结和标记，不改数据

1. 冻结 C/F 类模块和 E 类非主实现，不再增加字段、按钮和新 gate。
2. 在控制文档中固定本审计的唯一主实现表。
3. 修复测试时钟后恢复“全量验证必须每天可重复运行”的门禁。

### 阶段 1：统一数据口径

1. 客服统计、工作台、销售/风险上下文统一读取当前咨询主实现。
2. 库存响应明确区分平台库存、仓库库存、可用库存和更新时间。
3. 生产 frontend 构建显式锁定 backend，backend 模式禁止 Proxy 回退 Mock。
4. 后端工作台成为待办唯一计算源，前端只做展示和页面内格式化。

### 阶段 2：统一页面入口

1. “账号管理”重组为内部员工管理与平台连接两个职责，不改底层表。
2. 设备/环境保留一个主入口，另一路由兼容跳转。
3. 店铺连接页集中展示 API、平台登录、紫鸟、邮箱状态；技术能力矩阵折叠为管理员诊断。
4. 发货只展示仓库批次五阶段；旧 shipping gate 页面不进入导航。

### 阶段 3：完成受控写入闭环

1. 先为受保护咨询建立人工单条回复 attempt/reconcile 合同，再做一条真实试运营。
2. 客服稳定后，再按现有 T18 对一个精确发货记录做单独审批。
3. AI 只在读链路稳定后接入建议生成；自动平台写入继续冻结。

## 10. 不应删除的现有成果

- PostgreSQL/Alembic 生产结构和迁移证据。
- `Store`、`Product`、`Order`、`OrderStatusEvent` 主业务模型。
- 受保护 Naver recipient/logistics/inquiry、保留期和清理健康模型。
- `SyncCheckpoint`、`SyncLog`、自动读取租约/重试/恢复。
- 会话、MFA、CSRF、近期认证、店铺权限和操作审计。
- `WarehouseShippingBatch`、审批 grant、attempt、unknown/reconcile 安全逻辑。
- 商品缩略图、历史订单和咨询聊天 UI。
- 今日工作台后端任务合同和现有共享前端组件。
- OSS 加密备份、恢复演练、CI、Bundle 门禁和运维 runbook。
- T19/T20 的紫鸟解析、精确身份、IP 加密和打开后台安全边界。

## 11. 建议冻结的模块

立即冻结 8 个模块簇：

1. 商业 SaaS/开放注册/套餐方向。
2. Coupang 真实业务扩展。
3. 自动申诉和申诉平台提交。
4. 正式批量商品/订单写入及继续叠加 readonly gate。
5. 完整手机端写操作。
6. Mock 页面作为生产功能继续演进。
7. 旧 SQLite 升级脚本继续扩展。
8. 历史 Phase 文档继续承担当前状态来源。

此外冻结 E 类中的非主实现：旧通用 Naver 咨询写入、旧独立 shipment writeback gate、设备/环境第二入口和前端跨页面待办计算。

## 12. 疑似废弃、实验或无用代码

以下内容先标记，不删除：

- `src/pages/Mock*`、`src/data/mockData.js`、`src/data/shippingMockData.js`。
- `backend/app/clients/naver_client.py` 和 `coupang_client.py` 中纯 Mock client。
- `/sync/*/mock`、`/permissions/*mock*`、`/batch/*readonly-check` 的历史门禁接口。
- `backend/scripts/upgrade_*.py` 中被 Alembic 取代的 SQLite 升级脚本。
- 351 个根目录 Phase 文档中的旧计划和旧完成度。
- `sync_service.py` 中被后续同名函数覆盖的三个早期定义。

删除前必须先用路由注册、静态引用、测试引用和生产日志做四项依赖确认。

## 13. 当前最严重的五个混乱来源

1. **真实/Mock 运行边界不够硬**：默认 Mock、忽略的本地环境文件和 Proxy 回退使构建结果依赖机器状态。
2. **客服双数据链**：受保护 Naver 咨询已是生产主线，但旧统计和回复仍依赖通用表。
3. **`sync_service.py` 单体累积**：14,050 行混合多平台、多阶段、Mock 和真实逻辑，并存在同名函数覆盖。
4. **发货与库存多套口径**：WarehouseBatch 与旧 Shipping 结构并存，平台库存与物流库存没有统一来源合同。
5. **项目事实文档过期**：`docs/archive/governance/COMMANDER_STATE.md` 顶部仍写旧分支/旧状态，后部才是生产事实；大量 Phase 文档继续制造“完成/未完成”冲突。

## 14. 当前最需要收口的三条业务链路

### 链路 1：店铺接入到今日工作台

`Store -> ApiCredential -> StoreOnboarding -> SyncCheckpoint -> Product/Order/Inquiry/Logistics -> operator_workbench`

目标：一次配置后自动读取，所有状态只来自后端合同，失败进入同一个异常闭环。

### 链路 2：客户咨询到人工回复

`PxgNaverReadonlyCustomerInquiry -> Conversation -> Order/Logistics context -> AI draft (future) -> Human confirmation -> Reply attempt -> Reconcile`

目标：先消除通用表/受保护表冲突，再启用一条可对账的人工回复。

### 链路 3：订单到仓库发货

`Order -> Stable SKU mapping -> WarehouseShippingBatch -> Manifest -> Tracking import -> Human confirmation -> Writeback attempt -> Logistics readonly reconcile`

目标：WarehouseBatch 是唯一业务流程，旧 Shipping 数据结构只作为内部依赖。

## 15. 下一主阶段建议：最小改动收口方案

下一阶段最多两个并行工作流，不增加新业务功能。

### 工作流 A：核心数据合同收口

- 直接复用：`Store`、`ApiCredential`、`StoreOnboarding`、`Product`、`Order`、受保护咨询/物流、`SyncCheckpoint/SyncLog`、后端 workbench。
- 统一口径：咨询统计主表、库存来源、销售范围、状态时间和数据新鲜度。
- 渐进迁移：backend 模式禁止 Mock 回退；旧咨询/发货接口增加冻结标记和调用监控。
- 必须先修：T24 固定日期验证，恢复每日可重复的 `verify_all.py`。

### 工作流 B：内部运营主流程收口

- 只接入统一页面：店铺连接、今日工作台、订单/历史、咨询/聊天、物流、仓库批次。
- 重新定义：Tenant 显示为内部公司/业务空间；用户显示为内部员工。
- 冻结：租户商业化、Coupang、申诉自动化、完整手机写入、API 能力独立工作台。
- 不启用真实写：客服和发货按钮继续读取后端 capability，待单记录审批。

完成后，运营人员能够：登录并通过 MFA、切换两个 Naver 店铺、添加/验证店铺 API、自动查看商品/订单/咨询/物流、查询历史订单、查看客服完整对话、从今日工作台进入处理页面、准备并核对仓库批次、查看销售和库存来源。真实客服回复和发货回填仍需后续单独验收。

## 16. 无法确认的事项

1. 2026-07-18 之后生产两店每个后续同步周期是否持续成功；本次未连接生产服务器。
2. 公司主体需要保存哪些法律字段、是否存在多个营业执照或多个公司主体。
3. 一个 `Store` 是否永久等于一个平台卖家账号/频道；多频道需求尚未冻结。
4. 仓库库存的最终权威来源、盘点方式和可售库存算法。
5. 店铺邮箱使用的服务商、授权协议、收信频率和风险分类规则。
6. 客服回复 API 的最终官方合同、回复后只读对账字段和内容保留期。
7. 已有 Coupang 表中是否存在必须保留的正式数据；本次未读取生产数据库。
8. 生产前端构建时如何注入并锁定 `VITE_DATA_SOURCE=backend`；Git 中只有 CI，没有完整生产发布 workflow。
9. 紫鸟 Windows 助手的配对、升级、签名和离线命令合同。
10. T24 当前测试时钟失败是否还影响其他跨日测试；需要修复后重跑全量验证确认。

## 17. 代码、测试和 Git 证据索引

### Git 与生产事实

- `docs/archive/governance/COMMANDER_DECISIONS.md`：D027-D040（T11-T20）、D044-D049（生产迁移、咨询、双店、物流）。
- `docs/archive/governance/COMMANDER_STATE.md`：`Current Release Gate`、`T24 One-Time Inquiry Import Evidence`、`T24 Dual-Store Logistics Recovery Evidence`。
- 当前 Git：`release/operator-v1` / `4027e76`；生产代码：`62e49ba`。

### 核心模型

- 公司/账号：`backend/app/models/tenant.py`, `auth.py`。
- 店铺/凭证/设备/邮箱：`store.py`, `api_credential.py`, `platform_login_credential.py`, `device_environment.py`, `email_account.py`。
- 商品/订单：`product.py`, `order.py`, `order_status_event.py`。
- 咨询/物流：`customer_inquiry.py`, `pxg_naver_readonly.py`。
- 库存/发货：`shipping.py`。
- 同步/审计：`sync_checkpoint.py`, `sync_log.py`, `operation_audit_log.py`。

### 核心服务和接口

- 开店：`store_onboarding_service.py`, `store_onboardings.py`。
- 自动同步：`automatic_read_sync_service.py`, `main.py:68-105`。
- 咨询：`naver_readonly_inquiry_service.py`, `customer_inquiry_service.py`, `customer_inquiries.py`。
- 工作台：`stats_service.py:675-1188`, `dashboard.py`。
- 发货：`warehouse_shipping_service.py`, `shipping.py:43-207`。
- 紫鸟：`ziniao_directory_sync_service.py`, `platform_login_service.py`, `stores.py:386`。
- AI：`ai.py`, `stats_service.py:1382`。

### 前端

- 路由：`src/routes/index.jsx`。
- 工作台：`src/pages/Dashboard.jsx`。
- 订单：`src/pages/Orders.jsx`。
- 客服：`src/pages/CustomerService.jsx`。
- 发货：`src/pages/ShippingAssistant.jsx`, `src/features/shipping/warehouseBatch.js`。
- 平台连接：`src/pages/Stores.jsx`, `BackendAccountsPage.jsx`, `BackendCredentialPage.jsx`。
- 数据边界：`src/services/dataSource.js`, `dataProvider.js`, `adapters.js`。

### 验证

- 后端总门禁：`backend/scripts/verify_all.py`。
- T13-T24：`backend/scripts/verify_t13_onboarding.py` 至 `verify_t24_*.py`。
- 前端合同：`scripts/*.test.mjs`。
- 构建门禁：`scripts/verify-bundle-budget.mjs`, `.github/workflows/ci.yml`。
- 当前时间夹具问题：`verify_t24_dual_store_automatic_read.py:63`, `prepare_t24_dual_store_automatic_read.py:187`。

## 审计结论

现有系统不需要推倒重做。12 个核心能力簇可以直接保留，8 个核心能力簇应在现有代码上补齐，4 个能力簇只需重新定义，8 个非当前核心/实验模块簇应冻结。真正需要处理的是数据口径和调用主线，而不是重建表、页面或调度器。

必须渐进收口的核心冲突有三个：客服咨询主记录、库存/SKU来源、生产与 Mock 数据边界。`sync_service.py` 和旧发货接口需要后续拆分或冻结，但不构成当前大规模重构前置条件。

## 审计校准说明

本节是 2026-07-19 的一次性基准校准。第 4 节的 A/B/C/D/E/F 统计和本文件原结论不删除，但它们是校准前的审计记录；当前状态以本节和 `docs/PROJECT_CONTROL.md` 为准。校准遵循严格的 A1 条件：代码存在、单一主实现、真实 Backend、正式运营入口、完整前后端/API链路、关键测试和异常审计必须同时成立。单条成功测试、Mock 结果或历史部署记录不能单独证明 A1。

### 原始分类与校准分类

原审计的 40 个能力切片为：A 12、B 8、C 5、D 4、E 8、F 3。校准后保留这 40 个切片，并增加一个不代表业务功能的跨模块证据切片，因此当前盘点为 41 项：A1 3、A2 9、B 8、C 5、D 4、E 8、F 3、X 1。

| 原编号/原分类 | 校准后 | 能力 | 校准原因 |
|---|:---:|---|---|
| 1 / A | A2 | PostgreSQL、Alembic、HTTPS、备份与 CI | 有历史生产证据，但本地 PostgreSQL 专项因缺少 `T22_TEST_POSTGRES_URL` 跳过，当前生产发布与实时状态未在本次核验 |
| 2 / A | A1 | 会话、MFA、CSRF、近期认证 | 正式安全入口、Backend 链路和生产会话测试形成相对独立闭环；不把它扩展成商业注册 |
| 3 / A | A1 | 店铺权限、成员关系与审计边界 | 店铺隔离、敏感操作门禁和审计证据完整；公司主体语义是另一个未完成问题 |
| 4 / A | A2 | 店铺主数据与选择器 | `Store` 是主模型，但 Mock 回退、入口兼容和 Tenant/Company 语义尚未完全收口 |
| 5 / A | A2 | Naver 凭证与一键开店 | 两店首轮真实读取有证据，但持续稳定性、统一连接入口和当前服务器状态未重新确认 |
| 6 / A | A2 | 商品读取与缩略图 | 真实字段和媒体合同已有，但前端仍有 Mock/Backend 双路径，验证范围有限 |
| 7 / A | A2 | 订单、历史订单与状态事件 | 订单页面和模型可用，但旧字段兼容、数据源边界和整体运营闭环未完全统一 |
| 8 / A | A2 | Naver 物流只读 | D049 证明两店受保护快照和隐私边界，不等于当前持续运行和所有场景都已闭环 |
| 9 / A | A2 | Naver 受保护咨询与聊天展示 | 受保护表已是主线，但通用咨询表、旧统计和旧回复入口仍并存 |
| 10 / A | A2 | 自动读取、租约、重试与恢复 | `SyncCheckpoint` 主流程存在，但 T24 测试时钟不一致，且旧同步/Mock路径尚未全部冻结 |
| 11 / A | A1 | 同步日志与操作审计 | `SyncLog` 和 `OperationAuditLog` 是唯一推荐日志链，隐私扫描和安全证据可追溯 |
| 12 / A | A2 | 今日工作台任务中心 | 后端 `operator_workbench` 已存在，但前端仍有局部派生状态和 Mock 回退，尚未成为所有页面唯一口径 |
| 13-20 / B | B | 公司、平台账号、库存、发货、客服回复、销售/结算、邮件风险、AI | 原审计已正确识别为核心但缺关键数据或完整业务闭环，分类不变 |
| 21 / C | C | 邀请、密码重置和租户管理扩展 | 保留安全代码；商业 SaaS 和公共注册当前冻结 |
| 22 / C | C | Coupang 同步和财务适配 | 分类保持 C，但产品定位校准为“长期核心平台、当前冻结新增”，不是长期非核心 |
| 23-25 / C | C | 申诉、批量证据扩展、完整手机操作 | 保留已有成果，只冻结新能力和无人值守操作 |
| 26-29 / D | D | Tenant、员工语义、紫鸟助手、API能力矩阵 | 可直接复用，但必须重新定义为内部空间、员工权限、Windows助手和管理员诊断 |
| 30-37 / E | E | 咨询、发货、库存、设备、待办、账号页、同步单体、Mock/Backend | 新旧实现或职责重叠事实明确，推荐主实现已在第 8 节列出 |
| 38-40 / F | F | Mock内容、旧 Phase/状态头、旧 SQLite/历史门禁脚本 | 先标记和核查依赖，不在本次删除 |
| 新增证据切片 | X | 当前服务器版本、实时同步连续性和数据一致性 | 本次只审本地仓库，未连接服务器；历史 D044-D049 不能证明 2026-07-19 的当前状态 |

### 结论保持不变的部分

- 不需要推倒重做，不新增第二套订单、咨询、物流、调度器或同步日志。
- `Store`、`Product`、`Order`、`OrderStatusEvent`、受保护 Naver 物流/咨询、`SyncCheckpoint`、`SyncLog`、WarehouseBatch 和安全审计成果继续保留。
- 所有真实平台写入、自动客服、自动发货、库存/商品修改和 AI 自动操作继续关闭。
- 当前最需要收口的仍是咨询主记录、库存/SKU来源、Backend/Mock边界；旧 `sync_service.py` 和旧发货入口渐进冻结，不作为大规模重构前置条件。

### Coupang 定位校准

Coupang 的长期产品定位是核心平台。当前分类为 C，仅表示本阶段冻结新增能力；现有 Coupang 模型、适配器和历史结果继续保留。当前允许修复阻断性 bug、安全问题、数据损坏和已有能力回归。只有 Naver 主运营闭环和核心数据合同收口后，才重新评估新增 Coupang 能力。

### Workspace、Tenant、Company、Store 结论

代码事实是：`Tenant` 关联 `ErpUser` 和 `Store`，没有 `Company/LegalEntity` 或营业执照模型；当前用户权限主要是租户/店铺级。不能把 `Tenant` 直接写成公司主体。最低风险建议是保留 `Tenant` 作为内部 Workspace，一个 Workspace 未来可管理多个公司主体，一个公司主体可管理多个 Store；当前先通过文案、权限和聚合规则复用现有模型，待法律/财务字段确定后再评估最小 Company 扩展。本次不改 schema。

### 下一阶段正式边界

下一阶段正式名称为 **核心数据合同与内部运营主流程收口**，且仅有两个并行工作流：

1. **核心数据合同收口**：Workspace/Company/Store/平台账号/凭证关系、Naver 咨询唯一主链、平台/仓库库存和 SKU、销售/结算、后端待办、Backend/Mock边界、T24 统一时钟。
2. **内部运营主流程收口**：店铺连接、数据同步、今日工作台、订单/历史、客服、物流/仓库批次、库存异常和审计，逐项登记正式页面、接口、主数据源、旧入口和验收标准。

在这两个工作流完成前，不新增业务功能、不迁移数据库、不启用真实写入、不扩展 Coupang、不做完整手机操作。

### T24 与其他无法确认事项

T24 被校准为“测试夹具时钟不一致技术债务”：`verify_t24_dual_store_automatic_read.py:63` 固定 `2026-07-17`，而 `prepare_t24_dual_store_automatic_read.py:187` 调用的清理健康检查使用真实当前时间；2026-07-19 因此出现过期判断。它不证明核心生产同步失败；后续应使用可注入时钟或相对日期夹具，不应把一个固定日期替换成另一个固定日期。本次不修改测试代码。

仍无法确认的事项包括：当前服务器版本和实时同步状态、公司主体与证照字段、库存最终权威口径、店铺邮箱真实收信合同、客服回复官方对账合同、生产构建的 Backend 注入方式、紫鸟 Windows 助手配对合同，以及现有 Coupang 数据是否包含必须保留的正式数据。证据路径见本文件第 17 节、`docs/archive/governance/COMMANDER_STATE.md` 尾部和 `docs/archive/governance/COMMANDER_DECISIONS.md` D044-D049。

### 校准证据索引

- 状态与数量：`docs/PROJECT_CONTROL.md` 的“校准后的能力盘点”和“多维完成度与置信度”。
- 模型关系：`backend/app/models/tenant.py`、`store.py`、`product.py`、`shipping.py`、`customer_inquiry.py`、`pxg_naver_readonly.py`。
- 主服务与接口：`automatic_read_sync_service.py`、`stats_service.py:675`、`naver_readonly_inquiry_service.py`、`warehouse_shipping_service.py`、`api/v1/endpoints/dashboard.py`、`orders.py`、`customer_inquiries.py`、`shipping.py`、`stores.py`。
- 前端边界：`src/routes/index.jsx`、`src/services/dataSource.js`、`src/services/dataProvider.js`、`src/pages/Dashboard.jsx`、`Orders.jsx`、`CustomerService.jsx`、`ShippingAssistant.jsx`。
- 测试与历史生产证据：`backend/scripts/verify_all.py`、`verify_t24_*.py`、`scripts/*.test.mjs`、D044-D049；本次未连接生产服务器。
