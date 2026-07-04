# Project Progress Record

更新日期：2026-07-04

本记录用于固定项目进度口径，避免后续阶段汇报出现“分母变化导致看起来倒退”的问题。除非发现重大返工或生产目标范围重新扩大，否则以下区间应保持持平或上升。

## 当前进度

- 项目总体规划进度：约 `54% - 61%`
- Naver 基础 ERP 闭环进度：约 `70% - 75%`
- ERP 给真实用户落地使用进度：约 `58% - 65%`
- 可交给非技术人员长期稳定使用的生产版进度：约 `49% - 54%`

## 当前定位

现在适合：

- 单个 Naver 店铺内部试用。
- 查看本地商品、订单、库存、销售额。
- 做受控 preview、单条写入、小批量 refresh、人工审核。
- 演示 Naver-first ERP 工作台方向。
- 演示备份、恢复 dry-run、审计门禁和安全边界。

现在不适合：

- 开放 Naver 商品正式批量同步。
- 开放 Naver 订单正式批量同步。
- 多人多权限生产使用。
- 多店铺大规模生产使用。
- 自动化发货、取消、退货、换货。
- 作为最终财务、结算或利润系统。

## 已完成主线

### Naver 商品

- `store_id=8`、`credential_id=7` 的 Naver 授权、seller/account、seller/channels、channel 识别链路已完成。
- 商品 preview 已建立。
- 商品 `page=1,size=5` 小批量本地写库已完成。
- 当前本地 Naver 商品已稳定写入 5 条以上，后续又随着 ERP 演进进入本地展示、库存和价格变化提示阶段。
- 商品 post-sync dry-run 已验证无新增、无业务字段更新，仅同步时间刷新。
- 商品 `page=2,size=5` dry-run 曾返回 `success_empty`。
- 商品正式批量同步仍未开放。

### Naver 订单

- order feed-to-detail readonly preview 已打通。
- detail 安全字段映射、隐私 gate、状态中文化已固化。
- 单条订单本地写库、选中候选订单写库、post-write verification 已完成。
- 订单本地列表、状态展示层级、完整字段 preview、状态 mapping polish、订单 timeline 只读展示已推进。
- 订单状态事件 schema 已完成 migration，并已完成 timeline mock gate 与 post-refresh verification。
- Naver 订单 refresh 小批量 gate 已推进到 backup evidence gate，正式批量订单同步仍未开放。

### Naver 库存、配送、售后、销售额、Dashboard

- 基础库存提醒已接入。
- 商品价格和库存变化提示已接入。
- 配送状态 Dashboard summary 已接入。
- 售后 claim readonly classification 已接入。
- 基于本地订单金额的销售额 summary 已接入。
- Naver Dashboard ERP summary 已接入。

### 前端生产可用性

- Dashboard、Orders、Products、Credentials/API status、Logs/Audit 已做业务化文案清理。
- TechnicalDetails 已做安全加固，主页面默认不暴露技术字段。
- Logs runtime readability cleanup 已完成。
- Production usability mock walkthrough 已完成。

### 审计、备份、恢复

- Operation audit log schema migration 已完成。
- Audit writer service mock gate、local implementation、readonly API、Logs/Audit UI readonly integration 已完成。
- 真实本地备份 helper 已完成，并已产生 1G 本地备份和 manifest。
- Restore verification dry-run 已完成。
- Backup manifest mock gate、real local backup helper、restore dry-run helper、backup list/report readonly helper 已完成。
- Backup creation audit mock gate 已完成。
- Naver order refresh backup evidence gate 已完成。

## 未完成阶段

### 正式同步与写入闭环

- Naver 商品正式批量同步未开放。
- Naver 订单正式批量同步未开放。
- Naver 订单 refresh 仍需要从 mock/门禁阶段继续进入更小范围的真实受控写入复核。
- 商品扩容仍需要新的平台商品候选、跨页稳定性、重复检查、回滚/备份证据和人工批准。

### 审计

- Backup creation audit 还停留在 mock gate，未接入真实 backup helper runtime。
- Selected operation audit runtime wiring 仍需要从 approval/mock 进入受控真实写入路径。
- 审计日志还需要覆盖更多真实操作类型，例如备份创建、订单 refresh 写入、恢复演练、人工审批。
- Audit UI 仍需要在真实生产数据量下继续可读性走查。

### 备份和恢复

- Backup report 目前是本地脚本，还未提供只读 API。
- Backup report 还未接入前端。
- 真实 restore 仍未开放，只允许 dry-run。
- 备份保留策略目前未执行自动清理，后续必须先做 report-only，再由人工审批。
- 还没有完整的恢复操作手册和生产演练 runbook。

### 权限与多店铺

- 角色和权限模型未落地。
- 多店铺访问隔离 gate 未完成。
- 敏感操作审批角色未完成。
- 多店铺数据隔离验证未完成。

### 多平台

- Coupang ERP 化暂缓。
- 多平台共享订单/商品/库存合同未完成。
- 平台中立 Dashboard 还未完成。

### 生产交付

- 生产 readiness checklist 未完成。
- 端到端带备份演练未完成。
- 非技术人员操作手册未完成。
- 异常恢复手册未完成。
- 部署、监控、日志轮转和长期运维流程未完成。

## 近期推荐执行计划

### 接下来 5 个阶段

1. `Phase ERP-Backup-1J: Backup report readonly API approval plan`
   - 目的：把 1I 本地脚本报告规划成后端只读 API，但不立即开放写入、恢复或删除能力。
   - 风险：低。
   - 真实 API：否。
   - 写库：否。
   - Codex2：否。

2. `Phase ERP-Backup-1K: Backup report readonly API mock gate`
   - 目的：用 mock/临时数据验证备份报告 API 输出只包含安全字段。
   - 风险：低。
   - 真实 API：否。
   - 写库：否。
   - Codex2：否。

3. `Phase ERP-Backup-1L: Backup report readonly local API implementation`
   - 目的：实现只读本地备份报告 API，前端未来可展示备份证据。
   - 风险：中。
   - 真实 API：否。
   - 写库：否。
   - Codex2：后续需要。

4. `Phase ERP-Audit-1Y: Backup creation audit runtime wiring approval plan`
   - 目的：规划真实 backup helper 创建备份时如何写入 append-only 审计链。
   - 风险：中。
   - 真实 API：否。
   - 写库：计划阶段否，后续实现会写 audit rows。
   - Codex2：否。

5. `Phase Naver-ERP-18B: Controlled order refresh with real backup evidence approval plan`
   - 目的：把 18A backup evidence gate 转成下一次真实受控订单 refresh 写入前的审批计划。
   - 风险：中。
   - 真实 API：否。
   - 写库：计划阶段否，后续实现可能写 1 到 2 条 refresh。
   - Codex2：否。

### 后续 10 个阶段候选

1. `Phase ERP-Audit-1Z: Backup creation audit runtime wiring mock gate`
2. `Phase ERP-Audit-2A: Backup creation audit local implementation`
3. `Phase ERP-Audit-2B: Backup audit post-write verification`
4. `Phase ERP-Backup-1M: Backup report frontend readonly display plan`
5. `Phase ERP-Backup-1N: Backup report frontend readonly implementation`
6. `Phase Naver-ERP-18C: Controlled order refresh readonly repeat with backup evidence`
7. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
8. `Phase Naver-ERP-18E: Controlled order refresh small write`
9. `Phase Naver-ERP-18F: Controlled order refresh post-write audit verification`
10. `Phase ERP-Auth-1A: Role and permission model plan`

## 安全边界

继续遵守：

- 不保存 token。
- 不保存 Authorization。
- 不保存请求或响应 headers。
- 不保存 signature、bcrypt 输入、client secret。
- 不保存平台 raw response。
- 不输出完整 channel id、完整订单号、完整商品编号，除非处于已批准的订单详情展示范围。
- 买家、收件人、电话、地址等隐私字段只在批准的详情页展示，主列表和审计/备份证据中不保存完整隐私。
- 所有业务数据必须绑定 store。
- preview 优先、dry-run 优先、小窗口优先、单条写库优先。
- 正式批量同步必须单独批准。

