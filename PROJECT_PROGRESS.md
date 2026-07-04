# Project Progress Record

更新日期：2026-07-04

本记录用于固定项目进度口径，避免后续阶段汇报出现“分母变化导致看起来倒退”的问题。除非发现重大返工或生产目标范围重新扩大，否则以下区间应保持持平或上升。

## 当前进度

- 项目总体规划进度：约 `58% - 65%`
- Naver 基础 ERP 闭环进度：约 `72% - 77%`
- ERP 给真实用户落地使用进度：约 `62% - 69%`
- 可交给非技术人员长期稳定使用的生产版进度：约 `55% - 60%`

## 当前定位

现在适合：

- 单个 Naver 店铺内部试用。
- 查看本地商品、订单、库存、销售额。
- 做受控 preview、单条写入、小批量 refresh、人工审核。
- 演示 Naver-first ERP 工作台方向。
- 演示备份报告、恢复 dry-run、真实备份创建审计链和安全边界。

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
- Backup report readonly API approval plan、mock gate、本地只读 API 已完成。
- Backup creation audit mock gate 已完成。
- Backup creation audit runtime wiring approval plan 已完成。
- Backup creation audit runtime wiring mock gate 已完成。
- Backup creation audit local implementation 已完成，真实 `operation_audit_logs` 已写入 5 条备份审计链。
- Backup audit post-write verification 已完成。
- Backup report frontend readonly display plan 和 Codex2 只读展示实现已完成。
- Naver order refresh backup evidence gate 已完成。
- Naver order refresh with real backup evidence approval plan 已完成。

## 未完成阶段

### 正式同步与写入闭环

- Naver 商品正式批量同步未开放。
- Naver 订单正式批量同步未开放。
- Naver 订单 refresh 仍需要从 mock/门禁阶段继续进入更小范围的真实受控写入复核。
- 商品扩容仍需要新的平台商品候选、跨页稳定性、重复检查、回滚/备份证据和人工批准。

### 审计

- Selected operation audit runtime wiring 仍需要从 approval/mock 进入受控真实写入路径。
- 审计日志还需要覆盖更多真实操作类型，例如订单 refresh 写入、恢复演练、人工审批。
- Audit UI 仍需要在真实生产数据量下继续可读性走查。

### 备份和恢复

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

1. `Phase ERP-Audit-2C: Selected operation audit local implementation approval plan`
   - 目的：为 Naver 订单 refresh 写入补真实操作审计审批边界。
   - 风险：低。
   - 真实 API：否。
   - 写库：否。
   - Codex2：否。

2. `Phase ERP-Audit-2D: Selected operation audit local implementation mock gate`
   - 目的：先在临时库验证订单 refresh 审计链真实接入前的调用形态。
   - 风险：中。
   - 真实 API：否。
   - 写库：只写临时验证库。
   - Codex2：否。

3. `Phase Naver-ERP-18C: Controlled order refresh readonly repeat with backup evidence`
   - 目的：重新只读确认可刷新的 Naver 订单候选，并关联可用备份证据。
   - 风险：中。
   - 真实 API：是，只读。
   - 写库：否。
   - Codex2：否。

4. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
   - 目的：为极小范围订单 refresh 写入做人工批准计划。
   - 风险：中。
   - 真实 API：否。
   - 写库：否。
   - Codex2：否。

5. `Phase Naver-ERP-18E: Controlled order refresh small write with audit evidence`
   - 目的：在备份和审计证据齐备后执行受控小范围本地订单 refresh 写入。
   - 风险：高。
   - 真实 API：是，只读 detail。
   - 写库：是，小范围订单 refresh 与审计行。
   - Codex2：后续展示复核。

### 后续 10 个阶段候选

1. `Phase ERP-Audit-2C: Selected operation audit local implementation approval plan`
2. `Phase ERP-Audit-2D: Selected operation audit local implementation mock gate`
3. `Phase Naver-ERP-18C: Controlled order refresh readonly repeat with backup evidence`
4. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
5. `Phase Naver-ERP-18E: Controlled order refresh small write with audit evidence`
6. `Phase Naver-ERP-18F: Controlled order refresh post-write audit verification`
7. `Phase ERP-Auth-1A: Role and permission model plan`
8. `Phase ERP-Auth-1B: Store-scoped access gate mock`
9. `Phase ERP-Auth-1C: Sensitive action approval roles`
10. `Phase ERP-Auth-1D: Multi-store data isolation verification`

### Latest update after `Phase ERP-Audit-2C`

- Project overall planning progress: about `59% - 66%`
- Naver basic ERP loop progress: about `72% - 77%`
- ERP real-user landing progress: about `63% - 70%`
- Production version for long-term non-technical use: about `56% - 61%`

Implemented in this update:

- Documented `Phase ERP-Audit-2C: Selected operation audit local implementation approval plan`.
- Approved only the future audit boundary for `controlled_naver_order_local_refresh`.
- Kept formal Naver order batch sync closed.
- Kept public audit write/delete/export/raw detail APIs closed.
- Confirmed this phase performs no real API call, no database write, no schema change, no backup/restore execution, and no Codex1 runtime code change.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, and audit trail review.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Audit-2D: Selected operation audit local implementation mock gate`
2. `Phase Naver-ERP-18C: Controlled order refresh readonly repeat with backup evidence`
3. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
4. `Phase Naver-ERP-18E: Controlled order refresh small write with audit evidence`
5. `Phase Naver-ERP-18F: Controlled order refresh post-write audit verification`

### Latest update after `Phase ERP-Audit-2D`

- Project overall planning progress: about `60% - 67%`
- Naver basic ERP loop progress: about `72% - 77%`
- ERP real-user landing progress: about `64% - 71%`
- Production version for long-term non-technical use: about `57% - 62%`

Implemented in this update:

- Added a private selected-operation audit local implementation mock gate in Codex1.
- Verified the future `controlled_naver_order_local_refresh` audit chain in the temporary verification database.
- Covered success and blocked paths with manual approval, backup evidence, formal-sync closure, platform-write closure, privacy redaction, and sensitive-field blocking.
- Kept real `backend/codex1.db` unchanged by the mock gate.
- Kept formal Naver order batch sync closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and mock-proven audit evidence for a future selected order refresh.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-18C: Controlled order refresh readonly repeat with backup evidence`
2. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
3. `Phase Naver-ERP-18E: Controlled order refresh small write with audit evidence`
4. `Phase Naver-ERP-18F: Controlled order refresh post-write audit verification`
5. `Phase ERP-Auth-1A: Role and permission model plan`

### Latest update after `Phase Naver-ERP-18C`

- Project overall planning progress: about `61% - 68%`
- Naver basic ERP loop progress: about `73% - 78%`
- ERP real-user landing progress: about `65% - 72%`
- Production version for long-term non-technical use: about `58% - 63%`

Implemented in this update:

- Repeated the controlled Naver order readonly preview after outbound IP allowlist confirmation.
- Confirmed token, feed, and one detail request all returned HTTP 200.
- Observed safe hash `id-hash-192b9c67e8` with status `DELIVERED / 配送完成` and amount `499000 KRW`.
- Confirmed local sync stayed `not_requested` with `real_sync=false`.
- Confirmed counts were unchanged for orders, products, SyncLog, tested-success records, operation audit logs, and order status events.
- Kept formal Naver order batch sync closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, mock-proven audit evidence, and readonly Naver order refresh candidate confirmation.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-18D: Controlled order refresh small write approval`
2. `Phase Naver-ERP-18E: Controlled order refresh small write with audit evidence`
3. `Phase Naver-ERP-18F: Controlled order refresh post-write audit verification`
4. `Phase ERP-Auth-1A: Role and permission model plan`
5. `Phase ERP-Auth-1B: Store-scoped access gate mock`

### Latest update after `Phase Naver-ERP-18D`

- Project overall planning progress: about `61% - 68%`
- Naver basic ERP loop progress: about `73% - 78%`
- ERP real-user landing progress: about `65% - 72%`
- Production version for long-term non-technical use: about `58% - 63%`

Implemented in this update:

- Reviewed whether 18C safe hash `id-hash-192b9c67e8` can enter the existing-order refresh write path.
- Confirmed local store 8 has 3 real local Naver orders and 3 mock/test Naver rows.
- Confirmed the 18C safe hash does not match an existing real local Naver order.
- Blocked controlled order refresh write approval for this candidate.
- Kept formal Naver order batch sync closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, mock-proven audit evidence, and readonly Naver order candidate classification.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-19A: Selected new-order candidate approval plan`
2. `Phase Naver-ERP-19B: Selected new-order readonly repeat`
3. `Phase Naver-ERP-19C: Selected new-order single local write approval`
4. `Phase Naver-ERP-19D: Selected new-order single local write with audit evidence`
5. `Phase Naver-ERP-19E: Selected new-order post-write audit verification`

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
