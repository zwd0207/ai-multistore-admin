# 项目控制（唯一当前状态入口）

## TASK-POST-CLEANUP-CONTINUITY-001 当前状态

- 状态：目录整理影响审计、已完成能力基线封装、未开发路线图和整理后完整回归已完成；未修改业务模型、API、数据库、迁移或页面规则。
- 影响结论：唯一运行仓库 `codex2/`、后端 `backend/`、CI、入口脚本和合同测试可持续开发；整理没有删除或改写现行业务实现。详细证据见 [`POST_CLEANUP_DEVELOPMENT_AUDIT_20260722.md`](POST_CLEANUP_DEVELOPMENT_AUDIT_20260722.md)。
- 已完成能力：以 [`COMPLETED_CAPABILITY_BASELINE.md`](COMPLETED_CAPABILITY_BASELINE.md) 登记唯一主实现和保护边界；`npm run capabilities:verify:full` 是统一本地门禁，不复制第二套业务代码。
- 未开发能力：按 [`DEVELOPMENT_ROADMAP.md`](DEVELOPMENT_ROADMAP.md) 的两个工作流推进；当前唯一允许开工项是库存/SKU 双来源只读合同。
- WIP 风险已隔离：原始库存提交 `c9250dbc...` 内容完整但整包恢复会冲突；已将可用服务与审计资料重新封装为本地分支 `wip/inventory-sku-post-cleanup-20260722` 的 `2e37c7e...`，不含旧治理文档。

## 已完成历史：TASK-WORKSPACE-CLEANUP-001

- 状态：完成。后端扁平迁移、351 份历史资料归档、本地数据保护、旧副本清理、8013/5181 运行验收、干净工作树全量回归、提交和精确 GitHub CI 均已通过。
- 唯一运行仓库：`codex2/`。后端物理路径为 `backend/`；数据库文件名 `codex1.db`、API 合同、模型和迁移版本均未改变。
- 整理提交：`416a888096f5a5e71714adf0419cda79126db410`；已推送 `origin/release/operator-v1`，GitHub 三个 job 全部成功。
- 可恢复点：完整 bundle 位于工作区 `archive/git/ai-multistore-pre-cleanup-20260722.bundle`；新加密快照位于 `backend/.local-trial/readonly-backups/workspace-migration-pre-cleanup-20260722.sqlite.enc`。
- 生产服务器、生产数据库、DNS、域名和平台接口未操作；所有真实平台写入继续关闭。

## 已完成历史：TASK-INQUIRY-READ-CONTRACT-001

- 状态：代码、自动化验证与登录态浏览器验收已通过；正在登记候选版本并执行最终全量回归，尚未自动提交、推送或开始下一任务。
- 已验证主实现：Naver 正式读链只使用 `PxgNaverReadonlyCustomerInquiry`；`CustomerInquiry` 的 Naver 历史/Mock 行保留但从客服列表、Dashboard、风险、每日上下文和工作台排除；非 Naver 通用记录仅作只读兼容且回复固定关闭。
- 已验证深链：受保护 `pxg_naver_readonly:<数字ID>` 不依赖首批 100 条列表，前端直接请求受保护详情；工作台只生成该规范 ID。
- 自动化证据：客服工作流、T14、工作台、多店隔离、前端合同/构建及 `verify_all.py` 已通过；T22 PostgreSQL 专项因未配置 `T22_TEST_POSTGRES_URL` 按既有规则跳过。
- 浏览器事实：项目负责人已完成本地 ERP 登录/MFA。重启经核对的本地 8013/5181 旧进程后，工作台仅保留 canonical `pxg_naver_readonly:21` 待办，详情直接打开、回复保持关闭；桌面与 390px 均无横向溢出，控制台无新增 error/warn。未触发平台操作或数据重置。
- 审计记录：[`docs/INQUIRY_READ_CONTRACT_AUDIT_20260719.md`](INQUIRY_READ_CONTRACT_AUDIT_20260719.md)。

## 已完成历史：TASK-PROD-RECONCILE-001

- 状态：完成。已以只读方式核验生产与本地的代码、运行合同和自动同步证据；未停止服务、部署、修改生产配置或数据库，也未触发平台操作。
- 前一任务：`TASK-DATA-BOUNDARY-001` 已完成 A2 收口。正式模式默认 Backend，只有显式 `mock` 才使用 Demo/Mock；相关登录态浏览器验收、完整回归和 GitHub CI 已通过。
- 已确认代码关系：服务器后端 `app/` 的 129 个受控源码文件与 `62e49ba9cfdd19a6f6b026c25d53fc3f2ad98401` 完全一致；前端受控源代码 HEAD 为 `e5697e4b2e12e44a7ba1eeaed8c0ee7b85f98f25` 且无受控改动；两者均为当前仓库 HEAD 的祖先。没有服务器独有业务实现需要回流，本地不应重建已有生产实现。
- 生产健康：API、Nginx、PostgreSQL、备份定时器、两店八个 checkpoint 和近期同步均已在本次只读审计中核验健康；所有平台写入继续关闭。活动前端静态产物未含 `release-version.json`，精确前端产物 SHA 仍为 X。
- 域名事实：当前 Nginx 与 HTTPS 健康入口是 `aiglxt.xyz`；`aiglxt.com` 当前公共 DNS 为 NXDOMAIN。本任务不修改 DNS、域名绑定或 Nginx，域名切换须另行确认。
- 开发优先级：电脑端为当前唯一新增界面与交互重点；手机版不增加新功能或专项优化，但每项任务仍保留完整 390px 回归，只修复本轮引入的回归、安全或阻断问题。

- 文档版本：1.0
- 状态：当前基准
- 最后校准：2026-07-22
- 当前分支：`release/operator-v1`
- 当前仓库候选版本：`operator-v1.20260722.1`；精确版本以该版本所在的 Git commit SHA 为准。
- 当前服务器已部署版本：后端 `app/` 已核验为 `62e49ba9cfdd19a6f6b026c25d53fc3f2ad98401`；前端受控源代码为 `e5697e4b2e12e44a7ba1eeaed8c0ee7b85f98f25`，但活动 `dist` 缺少 `/release-version.json`，精确前端静态产物版本为 X。
- 当前业务代码基线：`operator-v1.20260722.1`；精确仓库 HEAD 以 `git rev-parse HEAD` 为准，`ac9375b` 是历史数据边界主提交。
- 生产代码证据基线：`62e49ba9cfdd19a6f6b026c25d53fc3f2ad98401`（历史部署证据，不等同于当前 HEAD）
- 一次性对齐审计：[`docs/GOAL_ALIGNMENT_AUDIT.md`](GOAL_ALIGNMENT_AUDIT.md)
- 本次生产对齐审计：[`docs/PRODUCTION_RECONCILIATION_AUDIT_20260719.md`](PRODUCTION_RECONCILIATION_AUDIT_20260719.md)
- 紫鸟集成研究索引：[`docs/integrations/ziniao/README.md`](integrations/ziniao/README.md)

本文件是仓库内唯一的当前项目状态入口。`docs/TASK_HANDOFF.md`只记录最近一次任务交接，`docs/DECISION_LOG.md`只记录追加式决策，`CHANGELOG.md`只记录真实变更。`docs/archive/governance/COMMANDER_STATE.md`和`docs/archive/governance/COMMANDER_DECISIONS.md`保留为历史记录，不再作为当前状态或当前决策来源。

版本登记使用 `public/release-version.json`。GitHub 候选版本由该文件和精确 commit 共同确定；服务器只有在实际部署并从 `/release-version.json` 读回相同值后才登记为已部署。不得只依据聊天、分支名、文件时间或历史部署记录判断两边版本一致。

## 当前阶段

正式阶段名称：**核心数据合同与内部运营主流程收口**。

目录整理与开发连续性审计已经完成，不改变业务阶段和运行合同。当前唯一主目标是从干净发布基线启动库存/SKU 双来源只读合同，统一平台观察库存、仓库盘点库存、SKU/规格键和严格阻断规则。所有未确认的平台写入继续关闭。

## 长期目标

建设公司内部自用的 AI 多店铺运营系统，统一管理业务空间、公司主体、店铺、平台账号、API 凭证、紫鸟设备、店铺邮箱、商品、订单、库存/SKU、发货物流、客服咨询、销售、平台邮件与风险、同步日志和今日工作台。AI 只提供总结、分类、建议和异常分析，平台动作必须经过人工确认和受控审计。

## 当前业务边界

当前主线只以 Naver 只读运营为现实基线，保留现有两店验证成果；Coupang 是长期核心平台，但当前冻结新增能力。系统面向内部账号，不开展公共注册、商业 SaaS 套餐或收费。手机端当前只承担查看和巡检。客服回复、发货回填、库存/商品修改、批量写入、自动回复、自动申诉、广告自动化和 AI 自动平台操作均未获真实执行授权。紫鸟 CLI 只作为 Windows 本地能力，Linux 服务端不直接依赖它。

## 统一状态分类

- **A1**：完整业务闭环。唯一主实现和主数据源、真实 Backend、正式运营入口、前后端/API链路、关键测试、日志/异常及当前目标均已闭合。
- **A2**：技术能力已完成但尚未收口。存在新旧实现、口径、入口、Mock/Backend、有限范围验证或未完成运营闭环中的至少一项。
- **B**：核心能力部分完成，缺少关键数据、真实接入、流程、前端、测试或异常处理。
- **C**：当前冻结扩展。长期可能有价值，但本阶段不继续增加能力。
- **D**：可复用但需要重新定义业务含义或职责。
- **E**：重复或冲突实现，需要确定主实现并渐进迁移。
- **F**：实验、废弃或待清理，暂不删除，先确认依赖。
- **X**：证据不足，当前不能确认，不把历史记录或单次测试当作现状。

## 校准后的能力盘点

主要能力切片共 41 项：A1 3 项、A2 9 项、B 8 项、C 5 项、D 4 项、E 8 项、F 3 项、X 1 项。X 是一个跨模块证据切片，不替代业务能力分类。

| 分类 | 当前能力切片 | 处理原则 |
|---|---|---|
| A1（3） | 会话/MFA/CSRF/近期认证；店铺成员权限与操作审计边界；`SyncLog` 与 `OperationAuditLog` 日志链 | 保留并停止重复开发；只处理已验证的安全缺陷 |
| A2（9） | PostgreSQL/Alembic/HTTPS/备份/CI；店铺主数据与选择器；Naver 凭证与开店；商品读取/缩略图；订单/历史订单/状态事件；Naver 物流只读；Naver 受保护咨询/聊天；自动读取/租约/重试/恢复；今日工作台 | 复用现有主实现，先统一数据源、入口、时钟和持续验证，不新增旁路实现 |
| B（8） | 公司主体/证照；平台账号聚合关系；SKU/库存口径；仓库发货与平台回填；人工客服回复；销售/结算；店铺邮箱/平台邮件风险；AI 总结/分类/建议/异常分析 | 只补齐核心缺口，先完成合同和人工闭环 |
| C（5） | 商业 SaaS/邀请扩展；Coupang 新增业务能力；自动申诉；批量审批/证据工作台扩展；完整手机端操作 | 保留已有成果，冻结新增；只处理阻断性 bug、安全问题或既有能力回归 |
| D（4） | `Tenant` 内部空间语义；用户/角色/成员语义；紫鸟 Windows 助手；API 能力矩阵 | 通过文案、入口和权限重新定义，暂不另建体系 |
| E（8） | 通用/受保护咨询双表；旧 Shipping 与 WarehouseBatch；平台/物流库存；设备/环境双入口；前后端待办计算；混合账号页；`sync_service.py` 多代实现；Mock/Backend 双路径 | 确定唯一主实现，冻结旧入口，后续按调用依赖渐进迁移 |
| F（3） | Mock 页面/数据/客户端；旧 Phase 与过期状态头；旧 SQLite 升级和历史门禁脚本 | 先隔离、标记和核查依赖，不在本阶段删除 |
| X（1） | 服务器活动前端静态产物的精确 SHA/版本登记 | 后端源码、同步与数据健康已本次核验；活动 `dist` 缺少版本文件，不能由源码 HEAD 推断其精确构建版本 |

## 当前真实可用能力

以下是有代码、测试或历史生产证据支持、可以直接保留的技术成果：登录和 MFA 安全链、店铺隔离、Naver 凭证验证和一次性开店、最近 30 天读取、历史订单回填、商品/订单/物流/受保护咨询模型、同步租约与重试、工作台任务合同、仓库批次审批与 unknown/reconcile、防泄露审计、响应式只读页面、备份/恢复和 CI 门禁。它们属于 A1 或 A2；A2 不等同于当前已完成的完整运营闭环。

平台真实读取的当前可确认范围是两店 Naver 首轮只读证据。订单、商品、咨询和物流写入关闭；客服回复和发货回填代码存在，但必须在数据合同和安全 attempt 收口后另行审批。AI 当前只有结构化上下文，没有真实模型调用。

## 核心数据关系

### 已确认的代码事实

- `Tenant` 当前拥有 `ErpUser` 和 `Store`，会话有租户选择；没有独立 `Company`、`LegalEntity` 或营业执照模型。
- `Store` 保存平台归属；`ApiCredential` 是 API 身份，`PlatformLoginCredential` 是人工后台登录身份，`DeviceEnvironment` 是设备/网络环境，`EmailAccount` 是店铺邮箱能力；它们没有一个完整的平台账号聚合合同。
- `Product` 保存平台商品和平台库存观察值；物流库存使用 `LogisticsInventoryMapping/Item`；`Order` 与 `OrderStatusEvent` 是订单主线；受保护 Naver 物流/咨询是专用只读链。
- 用户当前主要按租户和店铺成员关系授权，没有独立公司级授权层。

### 推荐的最低成本关系

```text
Workspace / Tenant（内部组织或业务空间）
  -> LegalEntity / Company（未来明确的公司主体、证照和税务归属）
       -> Store（一个公司主体可拥有多个店铺）
            -> Platform Account / API Credential / Login Credential
            -> Ziniao Device Environment / Store Email
  User / ErpUser -> Workspace，并通过公司或店铺成员关系获得权限
```

这是迁移建议，不是当前模型事实。一个 Workspace 可以在业务确认后管理多个公司主体；一个公司主体可以管理多个店铺。当前 `Store` 尚不能明确关联公司主体，因此不能写成 `Tenant = Company`，本次不改表、不迁移。平台账号、API 凭证、紫鸟环境和邮箱的业务归属应以 `Store` 为核心，用户只负责授权和操作主体。

## 重复与冲突主实现

| 领域 | 推荐主实现 | 暂冻结/兼容实现 |
|---|---|---|
| 店铺 | `Store` + 现有选择器 | 第二套紫鸟店铺表或名称匹配 |
| Naver 咨询 | `PxgNaverReadonlyCustomerInquiry` | `CustomerInquiry` 的旧 Naver 读写链 |
| 库存 | 明确区分 `Product.stock_quantity` 平台观察值与 `LogisticsInventoryItem` 仓库值 | 把两个数量混成一个库存 |
| 订单/物流 | `Order` + `OrderStatusEvent` + 受保护 Naver 物流快照 | `raw_data` 重复保存完整物流 |
| 发货 | `WarehouseShippingBatch`、grant、attempt、reconcile | 旧 Shipping 导出/导入和独立 gate 入口 |
| 自动同步 | `SyncCheckpoint` + `automatic_read_sync_service` + `SyncLog` | 新 scheduler、任务表或第二套日志 |
| 待办 | 后端 `operator_workbench` | 前端跨页面自行计算优先级/数量 |
| 数据源 | 正式 Backend 明确 fail-closed；Mock 仅显式启用 | 销售、设置和仓库批次边界已统一，仍需后续真实 Backend 联调 |

主要技术债务还包括 `sync_service.py` 单体和设备/环境重复路由。它们需要渐进迁移，不是本次重构前置条件。

## 多维完成度与置信度

不使用一个总百分比。工程通过数量、Bundle 大小、编码扫描等只计入工程健康度。

| 维度 | 当前判断 | 证据 | 尚未完成 | 置信度 |
|---|---|---|---|---|
| 工程健康度 | A2 | 前端合同、构建、Bundle 和会话扫描通过；T24 时钟修复后 `verify_all.py` 通过；本地 PostgreSQL 一次性变量未配置而跳过 | 继续确认生产发布链；T22 PostgreSQL 专项仍需独立环境 | 高 |
| 基础数据模型 | B | `Tenant/Store/Product/Order` 和物流/咨询模型存在 | Company/证照、平台账号聚合、库存/SKU和销售结算合同 | 高 |
| 平台真实数据接入 | A2 | D047-D049 记录两店 Naver 只读和物流证据 | 当前服务器重新核验、持续稳定性、邮箱和 Coupang 业务接入 | 中 |
| 普通运营界面 | A2 | 工作台、订单、客服、物流、发货和 390px 页面存在 | 统一 Backend 入口、隐藏旧入口、完成写入前置反馈 | 高 |
| 核心业务闭环 | B | 只读主线较完整，仓库批次安全链存在 | 咨询/发货人工写入、库存异常、统一数据口径和真实验收 | 中 |
| AI 能力 | B | `daily-context` 结构化上下文接口存在 | 模型总结、分类、建议和人工确认流程 | 高 |
| 安全与审计 | A2 | MFA、CSRF、近期认证、租约、attempt、审计和隐私门禁已有证据 | 受保护咨询写入账本、真实写入试运行和当前生产复核 | 高 |

## 下一主阶段：两个且仅两个工作流

### 工作流一：核心数据合同收口

| 步骤 | 正式入口/接口 | 主数据源 | 当前状态 | 旧/重复实现 | 收口验收 |
|---|---|---|---|---|---|
| 关系定义 | 店铺连接页 `/stores`；`GET /api/v1/stores` | `Tenant`、`Store`、凭证模型 | B/D | 混合账号页、Tenant/Company 语义混用 | 明确 Workspace/Company/Store/平台账号/凭证归属；跨店拒绝 |
| 咨询口径 | `/customer-service`；`GET /api/v1/customer-inquiries` | 受保护 Naver 咨询 | A2（本地自动化、登录态浏览器和 GitHub CI 已通过，尚未部署当前候选） | 通用 `CustomerInquiry` 的 Naver 历史行、旧 `/sync/customer-inquiries/naver` | 列表、统计、详情和后续 attempt 只认一个 Naver 主链 |
| 库存/SKU | `/inventory`、`/shipping`；现有库存与映射接口 | `Product` 平台值 + `LogisticsInventoryItem` 仓库值 | E/B | 名称/选项匹配和跨页库存计算 | 每个数量标来源、时间、SKU键；不得相互覆盖 |
| 销售/待办 | `/workbench`；`GET /api/v1/dashboard/store-overview` | 后端 `operator_workbench` | A2/E | 前端派生统计、旧 summary/mock fallback | 后端单一计算源，前端只展示；跨店汇总可追溯 |
| Backend/Mock 边界 | 生产构建和 `dataProvider` | 真实 Backend | A2 | Mock 仅作显式 Demo/Test 兼容 | 生产缺少后端能力时显式失败，不显示 Mock |
| T24 时间 | `verify_all.py` 与 T24 fixtures | `prepare_dual_store_automatic_read(now=...)` 和清理健康检查可选 `now` | A2 | 历史缺陷：旧调用未把准备时间传入清理健康检查；已修复 | T24 独立测试重复通过；生产默认仍使用真实 UTC 时间 |

### 工作流二：内部运营主流程收口

正式路径固定为：`店铺连接 -> 数据同步 -> 今日工作台 -> 订单/历史 -> 客服 -> 物流/发货 -> 库存异常 -> 操作审计`。

| 环节 | 正式页面/接口 | 主数据源 | 当前状态 | 旧入口 | 收口验收 |
|---|---|---|---|---|---|
| 店铺连接 | `/stores`；`GET/POST /api/v1/stores`、onboarding 服务 | `Store` + `ApiCredential` | A2 | Accounts 页混合凭证和员工管理 | 一次验证后能明确显示连接状态和下一步 |
| 数据同步 | `/workbench`；`GET /api/v1/dashboard/store-overview` | `SyncCheckpoint`、`SyncLog` | A2 | 手工 sync、preview 和 mock 路径 | 订单/商品/咨询/物流状态均来自同一 checkpoint 合同 |
| 今日工作台 | `/workbench`（`/dashboard` 仅别名） | 后端 `operator_workbench` | A2 | 前端工具函数派生待办 | 异常、过期、下一步和深链与后端详情一致 |
| 订单/历史 | `/orders`；`GET /api/v1/orders`、物流 trace | `Order`、`OrderStatusEvent` | A2 | Mock 订单和旧字段兼容 | 当前/历史范围、物流和状态时间线一致 |
| 客服 | `/customer-service`；`GET /api/v1/customer-inquiries` | 受保护 Naver 咨询 | A2（本地验收与 GitHub CI 通过，待后续部署） | 通用表的 Naver 历史行和旧 reply endpoint | 读链唯一；人工回复另行通过 attempt/reconcile 验收 |
| 物流/发货 | `/shipping`；`/shipping/warehouse-batches/*` | 物流快照、`WarehouseShippingBatch` | A2/B | 旧 Shipping 导出/导入/gate | 只展示单批次、精确记录、审批和不确定结果；真实写入仍关闭 |
| 库存异常 | `/inventory` | 明确后的平台/仓库库存合同 | B/E | 前端 `naverInventory` 和名称映射 | 异常可追溯至 SKU、来源和时间，不直接改平台 |
| 审计 | `/logs`；`OperationAuditLog` | 操作审计/同步日志 | A1 | 页面局部 mock 日志 | 敏感操作、失败和跨店访问均可追溯且无敏感原文 |

工作流完成前不新增表、第二套调度器、第二套日志或真实写入能力。完成后仍需分别审批一条人工客服回复和一条人工发货回填。

## 当前冻结范围

冻结不是删除。冻结模块的已有成果保留，仍被主流程依赖的部分只允许修 bug、安全问题、数据损坏修复和回归；恢复扩展必须由项目负责人新增决策确认。

- 商业 SaaS、公共注册、套餐收费和客户自助租户扩展。
- Coupang 新增业务能力（长期仍是核心平台）。
- 完整手机写操作、自动申诉、广告自动化、邮件自动回复。
- 手机版新增界面、交互和专项视觉优化；现有 390px 能力只做完整回归，不作为新功能开发目标。
- 未经人工确认的真实平台写入、批量写入、AI 自动平台操作。
- 旧页面、旧数据链、Mock/preview/readonly-check 继续扩展。
- Linux 服务端直接调用紫鸟 CLI。

## 风险与待核实事项

1. 服务器后端版本、实时同步、数据一致性和备份已本次核验；仅活动前端静态产物的精确 SHA/版本登记仍为 X，因为 `/release-version.json` 当前落入 SPA HTML 回退。`aiglxt.com` 也尚未配置为可解析的生产域名。
2. T24 的 `verify_t24_dual_store_automatic_read.py:63` 固定日期与清理健康检查默认真实时钟的冲突已修复：准备层现在将受控 `now` 传入清理健康检查，生产未传入时仍使用真实 UTC 时间；T24 和 `verify_all.py` 已通过。
3. 本地 PostgreSQL 并发验证因未设置一次性 `T22_TEST_POSTGRES_URL` 跳过；整理提交的精确 GitHub CI 已在 PostgreSQL 16 环境通过，后续发布仍需对新提交重复该门禁。
4. Naver 咨询正式读链已完成本地自动化、登录态浏览器和 GitHub CI；库存/SKU、旧发货入口和其余兼容路径仍待收口。
5. 库存/SKU 原始 WIP 的整包补丁会冲突；业务内容未丢失，必须按恢复手册只提取服务和审计资料，不得覆盖当前控制文档。
6. 公司主体/证照字段、邮箱收信、销售结算、客服写入官方合同和紫鸟助手配对合同仍待确认。

## 当前阶段验收标准

- 仅有本文件作为当前状态入口，历史文件不再竞争。
- 两个工作流的主页面、主接口、主数据源和冻结入口均已登记。
- A1/A2/B/C/D/E/F/X 分类可由代码、测试或明确待核实证据追溯。
- T24 时钟缺陷已修复并保留专项证据；后续测试新增时间来源必须继续复用可控时钟入口。
- 生产 Backend 不显示 Mock，核心跨店数据和权限边界有可重复测试。
- 在任何真实写入前，咨询和发货分别完成人工确认、attempt、unknown/reconcile 和审计验收。
- 已完成能力必须通过 `npm run capabilities:verify:full` 或等价 CI 门禁，不能靠历史聊天或单条测试判定。

## 下一步三个具体动作

1. 完成本次开发连续性记录、能力基线和统一门禁的提交/CI，保持发布分支与权威文档一致。
2. 从整理后的发布分支新建 `TASK-INVENTORY-SKU-CONTRACT-001` 独立任务分支，按恢复说明以无提交方式移植整理后 WIP 包 `2e37c7e...`。
3. 先实现并验证只读库存合同、唯一映射和严格阻断；不得同时启动客服写入、发货真实写入、手机版新功能或其他路线图项目。

## 文档优先级

当前状态：`docs/PROJECT_CONTROL.md`。最近任务交接：`docs/TASK_HANDOFF.md`。追加决策：`docs/DECISION_LOG.md`。一次性审计证据：`docs/GOAL_ALIGNMENT_AUDIT.md`。真实变更记录：`CHANGELOG.md`。聊天记录、Codex 会话和模型上下文不是项目状态来源。
