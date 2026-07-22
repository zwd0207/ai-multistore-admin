# 已完成能力基线

本文把已经有代码、正式入口和验证证据的能力封装成一个稳定基线，供后续任务复用。它不是第二套状态文件；当前状态仍以 [`PROJECT_CONTROL.md`](PROJECT_CONTROL.md) 为准。

## 封装方式

- 业务实现继续保留在现有模型、服务、API 和页面中，不复制代码、不建立第二套服务。
- 每项能力登记唯一主实现、正式入口、保护边界和验证证据。
- `npm run capabilities:verify` 复用全部前端合同、编码、会话、构建和 Bundle 门禁。
- `npm run capabilities:verify:full` 在上述基础上复用 `backend/scripts/verify_all.py`。
- A2 表示技术链路已验证但仍有运营、部署或旧实现收口缺口，不能写成 A1。

## 稳定能力包

| 能力包 | 状态 | 唯一主实现与正式入口 | 主要验证 | 后续保护规则 |
|---|---|---|---|---|
| 身份与会话安全 | A1 | `session_service.py`、`tenant_auth_service.py`、`/api/v1/auth/*`、登录/MFA 页面 | `verify_production_sessions.py`、`session:verify` | 不新建旁路会话；敏感写入继续要求 MFA、近期认证和 CSRF |
| 店铺隔离与审计 | A1 | `Store`、店铺成员关系、`permission_service.py`、`OperationAuditLog` | `verify_t23_tenant_auth.py`、`verify_all.py` | 所有业务查询必须带租户与店铺范围；审计不得保存敏感原文 |
| 同步与操作日志 | A1 | `SyncLog`、`OperationAuditLog`、现有日志 API 与 `/logs` | `verify_all.py`、前端日志合同 | 不新增第二套日志或异常任务表 |
| 正式 Backend 数据边界 | A2 | `dataSource.js`、`dataProvider.js`、`backendApi.js` | `data-boundary.contract.test.mjs`、登录态浏览器验收 | Backend 失败显式呈现；Mock 只能显式启用 |
| 店铺连接与 Naver 凭证 | A2 | `Store`、`ApiCredential`、onboarding 服务、`/stores` | T13、凭证安全和多店隔离验证 | 复用现有开店流程；不建立第二套平台账号表 |
| 商品与缩略图只读 | A2 | `Product`、`product_service.py`、缩略图服务、`/products` | 商品读取、缩略图和 T13-T17 回归 | 平台观察库存不得冒充仓库库存 |
| 订单、历史和状态事件 | A2 | `Order`、`OrderStatusEvent`、`order_service.py`、`/orders` | `order-logistics-contract.test.mjs`、T13-T17 | 保留当前/历史范围；禁止原始隐私数据旁路返回 |
| Naver 物流只读 | A2 | 受保护物流快照、订单物流轨迹接口和现有弹窗 | T17、T24 恢复验证 | 物流写入与实时快递轨迹继续分离 |
| Naver 受保护咨询读链 | A2 | `PxgNaverReadonlyCustomerInquiry`、`naver_readonly_inquiry_service.py`、`/customer-service` | T14、客服工作流、桌面/390px 登录态验收 | 通用 Naver 历史行不得重新进入正式统计或回复链 |
| 自动读取与异常恢复 | A2 | `SyncCheckpoint`、`automatic_read_sync_service.py`、工作台概览 | T15、T16、T24 双店验证 | 复用租约、重试和恢复；不建第二套 scheduler |
| 今日工作台 | A2 | 后端 `operator_workbench` 与 `/dashboard/store-overview`、`/workbench` | 工作台、多店和前端合同 | 后端负责状态分类，前端不得重新推断业务优先级 |
| 仓库批次安全框架 | A2/B | `WarehouseShippingBatch`、grant、attempt、unknown/reconcile | T18、`warehouse-batch-contract.test.mjs` | 真实发货仍关闭；不能把技术门禁写成已上线发货能力 |
| PostgreSQL、备份与 CI | A2 | Alembic、PostgreSQL 备份脚本、GitHub Actions | 本地 `verify_all.py`、GitHub PostgreSQL 16 CI | 当前候选未部署生产；恢复能力须按独立运行手册验收 |
| 紫鸟本地集成 | D/A2 | Windows CLI、现有店铺打开和目录同步合同 | T19、T20、紫鸟前端合同 | Linux 服务端不直接调用 CLI；后续以 Windows 助手重新定义 |

## 不属于已完成运营能力

- 人工客服真实回复、真实发货回填、平台商品或库存修改尚未获得生产执行授权。
- 销售页当前是订单运营统计，不是平台结算或财务对账。
- AI 只有结构化上下文，没有真实模型总结、分类或建议闭环。
- 公司主体/证照、统一平台账号、店铺邮箱收信、完整紫鸟助手仍未完成。

## 基线验证

快速验证前端边界：

```powershell
npm.cmd run capabilities:verify
```

完整验证前后端：

```powershell
npm.cmd run capabilities:verify:full
```

本地未设置 `T22_TEST_POSTGRES_URL` 时，PostgreSQL 专项按既有规则跳过；发布候选必须由 GitHub CI 的 PostgreSQL 16 job 补齐。运行验证不会授权真实平台读写。
