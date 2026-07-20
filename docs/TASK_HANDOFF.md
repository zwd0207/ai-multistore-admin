# 当前任务交接

> 最新任务状态：`TASK-INQUIRY-READ-CONTRACT-001` 已完成代码收口、自动化和登录态浏览器验收；现正进行版本登记和最终回归。通过后应自动提交/推送并核验 GitHub CI；在 CI 通过前，不得进入库存/SKU任务或部署服务器。以下旧内容保留为已完成任务的历史交接证据。

## 当前任务：TASK-INQUIRY-READ-CONTRACT-001

- 任务目标：将 Naver 正式客服读链统一到 `PxgNaverReadonlyCustomerInquiry`，覆盖列表、统计、风险、每日上下文、工作台和受保护详情深链；不改表、不删历史、不调用平台、不启用回复。
- 已完成：旧通用 Naver 行从正式业务面隐藏；非 Naver 通用行仅保留只读兼容并固定关闭回复；受保护 canonical 深链不再依赖首批 100 条列表。
- 自动化验证：`verify_customer_inquiry_operator_workflow.py`、`verify_t14_naver_readonly_inquiries.py`、`verify_operator_workbench.py`、`verify_multi_store_workbench.py`、前端合同/构建和 `verify_all.py` 均已通过；T22 PostgreSQL 专项按既有规则跳过。
- 浏览器验收：项目负责人已完成登录/MFA；重启经过进程、端口和命令核对的本地 8013/5181 旧服务后，工作台仅有 `pxg_naver_readonly:21` canonical 待办，打开详情成功，10 个“回复”按钮均禁用。桌面 1280×720 与 390×844 均无横向溢出，控制台无 error/warn；未重置数据或触发平台操作。
- 最准确续接：登记 `operator-v1.20260720.1` 后，运行最终全量回归、构建和工作树校验；全部通过即自动提交/推送 `release/operator-v1`，再核验 GitHub CI。
- 禁止事项：不启用回复、不执行刷新、不调用平台、不改数据库/迁移、不部署服务器、不修改域名/DNS；GitHub CI 通过前不进入库存/SKU任务。
- 详细证据：[`docs/INQUIRY_READ_CONTRACT_AUDIT_20260719.md`](INQUIRY_READ_CONTRACT_AUDIT_20260719.md)。

- 任务编号：`TASK-DATA-BOUNDARY-001`
- 任务：统一并锁定 Mock / Backend 运行边界
- 完成日期：2026-07-19
- 分支：`release/operator-v1`
- 候选版本：`operator-v1.20260719.1`
- 任务开始 HEAD：`403ed319c2f27c0662cba5e1c1f4d0e5bc15fcaa`
- 主提交：`ac9375b`（`fix: enforce explicit backend and mock modes`）
- 登录态验收修复：纳入候选版本 `operator-v1.20260719.1`，精确提交以 `git rev-parse HEAD` 为准。
- 版本登记：`public/release-version.json`；服务器部署后必须从同一路径读回相同版本再登记完成。

## 实际完成内容

- `VITE_DATA_SOURCE` 缺省和未知值进入 Backend；只有显式 `mock` 进入 Demo/Mock。
- 顶部显示 `正式 Backend` 或 `Demo / Mock 数据`，移动端不隐藏数据源标识。
- Dashboard 移除 Backend 请求到空列表的静默回退，失败进入可见错误状态。
- Sales 通过统一 `dataProvider.getSalesReport()` 读取现有 `/stats/sales`、`/stats/sales/by-platform`、`/stats/sales/by-date` 和订单接口；不再直连 Mock。
- Settings 在 Backend 模式只读取运营就绪检查，明确显示正式设置接口尚未接入，不读取或保存 Mock 设置。
- Stores 删除动作和仓库批次操作均经过显式 provider 分支；Mock 模式不会调用 Backend，Backend 模式不会回退 Mock。
- provider 缺少方法时，Backend 模式返回明确不可用错误，不再代理到 Mock。
- 登录态浏览器验收发现并修复销售订单请求超过 Backend 每页 100 条上限的问题。
- Sales 店铺筛选、排行和明细改为使用当前 Backend 店铺列表与名称，不再显示 Demo 店铺或 `店铺 #1`。
- Settings 将备份摘要的权限/可用性失败隔离为单项检查，后端健康和店铺总览成功结果继续显示，不回退 Mock。

## 数据源矩阵

| 模块 | 正式数据源 | Mock 数据源 | 选择位置 | 静默降级 | 当前风险 / 推荐主路径 |
|---|---|---|---|---|---|
| 店铺 | `backendApi.getStores` 与 Store onboarding | `mockApi.getStores` | `dataProvider.getStores` | 否 | 正式删除未开放并明确失败；继续以 `Store` Backend 为主 |
| 商品 | `backendApi.getProducts` | `mockApi.getProducts` | `dataProvider.getProducts` | 否 | 继续复用 Backend 商品读取，不新增页面数据源 |
| 订单 | `backendApi.getOrders` | `mockApi.getOrders` | `dataProvider.getOrders` | 否 | Dashboard 不再吞掉失败；订单主路径保持 Backend |
| 咨询 | Backend customer-inquiries 接口 | `mockApi.getCustomerTickets` | `dataProvider.getCustomerInquiries` | 否 | 本任务未改咨询双链；后续只收口 Backend 主链 |
| 物流 / 发货 | Backend warehouse-batches 与物流接口 | 显式 Mock 不可用结果及既有测试夹具 | `dataProvider` 仓库方法 | 否 | Mock 不调用 Backend；平台写入继续受 T18 门禁 |
| 库存 | Backend 商品/物流库存现有接口 | Mock 商品与 Shipping 测试数据 | `dataProvider` 显式分支 | 否 | 本任务未统一 SKU 口径；后续只接 Backend 主链 |
| 今日工作台 | Backend `dashboard/store-overview`、订单和审计 | `mockStoreOverview` 与 Mock 列表 | `dataProvider` + Dashboard | 否 | Backend 任一请求失败显示错误，不伪装空结果 |
| 平台账号 / 凭证 | Backend credentials/platform-logins | `mockApi.getAccounts` | `dataProvider` 显式分支 | 否 | 正式模式不读取 Mock 账号；保持现有脱敏和权限门禁 |
| 销售 | Backend `/stats/*` 与订单读取 | `mockApi.getSales*` | `dataProvider.getSalesReport` | 否 | 退款/优惠无正式统计接口时显示零，不等同平台结算 |
| 设置 | Backend 运营就绪检查 | Mock settings CRUD | Settings + `dataProvider` | 否 | 正式设置接口未接入，Backend 模式明确只显示就绪检查 |

## 修改文件

- `src/services/dataSource.js`
- `src/services/dataProvider.js`
- `src/services/backendApi.js`
- `src/pages/Dashboard.jsx`
- `src/pages/Sales.jsx`
- `src/pages/Settings.jsx`
- `src/pages/Stores.jsx`
- `src/layouts/AdminLayout.jsx`
- `src/styles/layout.css`
- `scripts/data-boundary.contract.test.mjs`
- `README.md`
- `docs/PROJECT_CONTROL.md`
- `docs/TASK_HANDOFF.md`
- `docs/DECISION_LOG.md`
- `CHANGELOG.md`

## 验证命令和结果

- `npm.cmd run build`：通过。
- `npm.cmd run encoding:scan`：通过。
- `node scripts/data-boundary.contract.test.mjs`：通过。
- `node scripts/t13-frontend-contract.test.mjs`：通过。
- `node scripts/t14-customer-service-contract.test.mjs`：通过。
- `node scripts/t15-store-sync.contract.test.mjs`：通过。
- `node scripts/t16-automatic-read-recovery.contract.test.mjs`：通过。
- `node scripts/t17-frontend-logistics.contract.test.mjs`：通过。
- `node scripts/t23-t26-auth-boundary.contract.test.mjs`、`node scripts/t23-tenant-auth-ui.contract.test.mjs`：通过。
- `node scripts/warehouse-batch-contract.test.mjs`、`node scripts/manual-sync-contract.test.mjs`：通过。
- `npm.cmd run build`：通过；显式 `VITE_DATA_SOURCE=mock` 构建也通过。
- `npm.cmd run encoding:scan`、`npm.cmd run session:verify`、`npm.cmd run bundle:verify`：通过。
- 全部 20 个 `scripts/*.test.mjs` 前端合同测试：通过。
- 登录态浏览器验收：工作台、订单、销售、设置、店铺与仓库批次通过；销售店铺筛选交互通过；桌面与 390px 无横向溢出；冷加载控制台无错误或警告。
- 正式构建 Bundle：入口 273,766 字节，共 38 个 JavaScript chunk，预算门禁通过。
- `operator-readiness-check.mjs`：失败，因本机 `127.0.0.1:8012` 后端未启动，`fetch failed`。
- `verify_all.py`：在干净工作树中 123.8 秒完整通过，包含 `git tracking: ok`、`docs secret scan: ok` 和 `verify_all: ok`；T22 PostgreSQL 专项因未配置 `T22_TEST_POSTGRES_URL` 按既有规则跳过。
- `git diff --check`：通过。

## 当前未完成内容

- Settings 正式后端配置接口尚未接入，正式模式仅提供运营就绪检查。
- Sales 退款和优惠字段没有对应正式统计接口，当前按订单销售统计合同显示为零；不得解释为平台结算数据。

## 阻塞问题

- 无代码阻塞。
- 当前任务无代码或浏览器验收阻塞；仅剩最终校验、提交/推送与 GitHub CI 核验。

## 下一任务准确起点

完成当前任务的最终校验、自动提交/推送与 GitHub CI 后，下一准确起点是库存/SKU 双来源合同：先只读盘点现有平台库存、仓库库存、SKU/规格键和不唯一映射；明确唯一口径与阻断规则前，不新增平台或仓库写入，也不启动手机版新功能。

## 禁止误操作事项

- 不得把 Mock 恢复为默认数据源或增加静默回退。
- 不得修改数据库模型、迁移、后端业务合同、同步、咨询、库存或工作台规则。
- 不得删除 Mock 文件；它们仍是显式 Demo/Test 来源。
- 已完成任务可按 D060 自动提交和推送；服务器部署、数据库或生产配置修改、DNS/域名切换和真实平台操作仍需独立门禁。
- 不得停掉、覆盖或重建正在运行的服务器能力；不得把生产密钥、客户数据或环境值复制到仓库。
