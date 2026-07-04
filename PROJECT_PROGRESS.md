# Project Progress Record

更新日期：2026-07-04

本记录用于固定项目进度口径，避免后续阶段汇报出现“分母变化导致看起来倒退”的问题。除非发现重大返工或生产目标范围重新扩大，否则以下区间应保持持平或上升。

## 当前进度

- 项目总体规划进度：约 `72% - 78%`
- Naver 基础 ERP 闭环进度：约 `80% - 85%`
- ERP 给真实用户落地使用进度：约 `74% - 80%`
- 可交给非技术人员长期稳定使用的生产版进度：约 `68% - 74%`

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

### Latest update after `Phase Naver-ERP-19A`

- Project overall planning progress: about `62% - 69%`
- Naver basic ERP loop progress: about `73% - 78%`
- ERP real-user landing progress: about `65% - 72%`
- Production version for long-term non-technical use: about `58% - 63%`

Implemented in this update:

- Documented selected new-order candidate approval plan for safe hash `id-hash-192b9c67e8`.
- Confirmed this candidate is not approved for existing-order refresh.
- Approved only the next readonly repeat step before any write can be considered.
- Kept formal Naver order sync, product sync, SyncLog writes, tested-success writes, and platform order writes closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and selected Naver new-order candidate planning.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-19B: Selected new-order readonly repeat`
2. `Phase Naver-ERP-19C: Selected new-order single local write approval`
3. `Phase Naver-ERP-19D: Selected new-order single local write with audit evidence`
4. `Phase Naver-ERP-19E: Selected new-order post-write audit verification`
5. `Phase ERP-Auth-1A: Role and permission model plan`

### Latest update after `Phase Naver-ERP-19B`

- Project overall planning progress: about `62% - 69%`
- Naver basic ERP loop progress: about `74% - 79%`
- ERP real-user landing progress: about `66% - 73%`
- Production version for long-term non-technical use: about `58% - 63%`

Implemented in this update:

- Repeated the selected new-order candidate readonly preview.
- Confirmed token, feed, and detail HTTP 200.
- Confirmed safe hash `id-hash-192b9c67e8` matched the selected candidate.
- Confirmed local duplicate real-order matches remain zero.
- Confirmed local sync stayed `not_requested` and all counts stayed unchanged.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and stable selected Naver new-order candidate confirmation.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-19C: Selected new-order single local write approval`
2. `Phase Naver-ERP-19D: Selected new-order single local write with audit evidence`
3. `Phase Naver-ERP-19E: Selected new-order post-write audit verification`
4. `Phase ERP-Auth-1A: Role and permission model plan`
5. `Phase ERP-Auth-1B: Store-scoped access gate mock`

### Latest update after `Phase Naver-ERP-19C`

- Project overall planning progress: about `63% - 70%`
- Naver basic ERP loop progress: about `74% - 79%`
- ERP real-user landing progress: about `66% - 73%`
- Production version for long-term non-technical use: about `59% - 64%`

Implemented in this update:

- Approved only a later one-order local write for safe hash `id-hash-192b9c67e8`.
- Required fresh backup, fresh readonly preview, duplicate count zero, privacy gate, one-candidate limit, readback, and audit evidence.
- Kept formal Naver order sync, product sync, batch order sync, SyncLog writes, tested-success writes, and platform order writes closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and approved single selected new-order local write gate.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-19D: Selected new-order single local write with audit evidence`
2. `Phase Naver-ERP-19E: Selected new-order post-write audit verification`
3. `Phase ERP-Auth-1A: Role and permission model plan`
4. `Phase ERP-Auth-1B: Store-scoped access gate mock`
5. `Phase ERP-Auth-1C: Sensitive action approval roles`

### Latest update after `Phase Naver-ERP-19D`

- Project overall planning progress: about `64% - 71%`
- Naver basic ERP loop progress: about `75% - 80%`
- ERP real-user landing progress: about `67% - 74%`
- Production version for long-term non-technical use: about `60% - 65%`

Implemented in this update:

- Created a fresh pre-write database backup for the selected Naver new-order write.
- Repeated the selected readonly preview; token, feed, and detail returned HTTP 200.
- Confirmed safe hash `id-hash-192b9c67e8`, duplicate count zero, and privacy gate pass.
- Wrote exactly one local Naver order and five append-only audit evidence rows.
- Kept products, SyncLog, tested-success records, order timeline events, platform writes, and formal order sync closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and one selected Naver new-order local write with audit evidence.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-19E: Selected new-order post-write audit verification`
2. `Phase ERP-Auth-1A: Role and permission model plan`
3. `Phase ERP-Auth-1B: Store-scoped access gate mock`
4. `Phase ERP-Auth-1C: Sensitive action approval roles`
5. `Phase ERP-Auth-1D: Frontend role-aware action visibility plan`

### Latest update after `Phase Naver-ERP-19E`

- Project overall planning progress: about `64% - 71%`
- Naver basic ERP loop progress: about `75% - 80%`
- ERP real-user landing progress: about `67% - 74%`
- Production version for long-term non-technical use: about `60% - 65%`

Implemented in this update:

- Verified the selected safe hash exists exactly once in local Naver orders.
- Confirmed `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=10`, and `order_status_events=0`.
- Verified the five-row 19D audit chain and safe flags.
- Confirmed sensitive scan passed and no raw external response, token, header, secret, complete platform id, complete buyer/receiver privacy, phone, address, or zip code was present in the safe verification output.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, and verified selected Naver new-order local write evidence.
- Not suitable now: formal product/order batch sync, multi-user permissioned production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Auth-1A: Role and permission model plan`
2. `Phase ERP-Auth-1B: Store-scoped access gate mock`
3. `Phase ERP-Auth-1C: Sensitive action approval roles`
4. `Phase ERP-Auth-1D: Frontend role-aware action visibility plan`
5. `Phase Naver-ERP-20A: Controlled order refresh batch with audit approval plan`

### Latest update after `Phase ERP-Auth-1A` to `Phase Naver-ERP-20A`

- Project overall planning progress: about `66% - 72%`
- Naver basic ERP loop progress: about `76% - 81%`
- ERP real-user landing progress: about `69% - 75%`
- Production version for long-term non-technical use: about `62% - 67%`

Implemented in this update:

- Planned the first local ERP role model: owner, admin, operator, auditor, and viewer.
- Added a private backend store-scoped permission mock gate.
- Added a private backend sensitive-action approval mock gate.
- Verified role/store/permission/approval blocks in `verify_all.py`.
- Planned Codex2 role-aware action visibility without changing runtime UI.
- Planned the next Naver controlled order refresh batch approval path with backup, audit, permission, and sensitive-action gates.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, verified selected Naver order write evidence, and mock-proven role/store approval checks.
- Not suitable now: formal product/order batch sync, fully authenticated multi-user production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-20B: Controlled order refresh batch readonly repeat`
2. `Phase Naver-ERP-20C: Controlled order refresh batch write approval`
3. `Phase ERP-Auth-1E: Runtime permission API approval plan`
4. `Phase ERP-Auth-1F: Runtime permission API mock gate`
5. `Phase ERP-UX-2A: Role-aware action visibility implementation`

### Latest update after `Phase Naver-ERP-20B` to `Phase ERP-UX-2A`

- Project overall planning progress: about `68% - 74%`
- Naver basic ERP loop progress: about `77% - 82%`
- ERP real-user landing progress: about `71% - 77%`
- Production version for long-term non-technical use: about `64% - 69%`

Implemented in this update:

- Repeated the controlled Naver order refresh preview in readonly mode over a recent 3-day KST window.
- Confirmed token/feed/detail all returned HTTP 200 and safe hash `id-hash-192b9c67e8` matched one existing local Naver order.
- Kept `orders_total=10`, `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=10`, and `order_status_events=0` unchanged.
- Documented that a future refresh write still needs fresh backup, fresh readonly repeat, role permission, sensitive-action approval, audit evidence, readback, and sensitive scan.
- Added mock-only Codex1 permission API routes for role inventory, store-scoped permission checks, and sensitive action checks.
- Added Codex2 Orders role-aware action visibility so ordinary users see business messages while permission keys stay folded in technical details.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, verified selected Naver order write evidence, mock-proven role/store approval checks, and role-aware action visibility in Orders.
- Not suitable now: formal product/order batch sync, fully authenticated multi-user production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-ERP-20D: Controlled order refresh write execution approval with permission evidence`
2. `Phase Naver-ERP-20E: Controlled existing-order refresh single local write with audit evidence`
3. `Phase Naver-ERP-20F: Controlled refresh post-write verification`
4. `Phase ERP-Auth-1G: Permission API frontend-wide visibility plan`
5. `Phase ERP-Auth-1H: Runtime permission API production-auth boundary plan`

### Latest update after `Phase Naver-ERP-20D` to `Phase ERP-Auth-1H`

- Project overall planning progress: about `69% - 75%`
- Naver basic ERP loop progress: about `78% - 83%`
- ERP real-user landing progress: about `72% - 78%`
- Production version for long-term non-technical use: about `65% - 70%`

Implemented in this update:

- Approved one controlled existing-order refresh attempt for safe hash `id-hash-192b9c67e8` with permission evidence.
- Created a pre-write database backup and manifest before running the refresh gate.
- Repeated a real readonly Naver preview. Token/feed/detail returned HTTP 200 and the selected safe hash matched exactly one existing local Naver order.
- Ran the controlled refresh gate. It found no business-field changes, so no local order update was forced.
- Wrote five append-only audit evidence rows: `approval_planned`, `pre_write_backup_verified`, `local_write_attempted`, `local_write_blocked`, and `post_write_verification_succeeded`.
- Verified current counts: `orders_total=10`, `orders_store8=7`, `products_store8=5`, `sync_logs_store8=1`, `tested_success_store8=8`, `operation_audit_logs=15`, and `order_status_events=0`.
- Planned frontend-wide permission visibility and clarified that the current permission API is not production authentication.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, and controlled no-change refresh audit evidence.
- Not suitable now: formal product/order batch sync, fully authenticated multi-user production use, large-scale multi-store production, automated shipment/cancel/return/exchange, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Auth-1I: User and role schema proposal`
2. `Phase ERP-Auth-1J: Store membership schema proposal`
3. `Phase ERP-Auth-1K: Auth schema mock migration gate`
4. `Phase ERP-Backup-2A: Restore runbook and operator checklist plan`
5. `Phase Naver-ERP-21A: Existing-order refresh no-change UI/audit display check`

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

### Latest update after `Phase ERP-Auth-1I` to `Phase Naver-ERP-21A`

- Project overall planning progress: about `70% - 76%`
- Naver basic ERP loop progress: about `79% - 84%`
- ERP real-user landing progress: about `73% - 79%`
- Production version for long-term non-technical use: about `66% - 72%`

Implemented in this update:

- Proposed the future production-auth user, role, permission, role-permission, and store-membership schema.
- Added a temporary-database `verify_all.py` mock migration gate for the auth schema proposal.
- Verified the mock auth schema creates roles, permissions, store 8 membership evidence, cross-store isolation, and sensitive-column exclusions without touching `backend/codex1.db`.
- Planned the production restore runbook and operator checklist while keeping real restore closed.
- Checked how the 20E/20F no-change Naver order refresh should be displayed: no business-field change, no forced local update, audit evidence recorded, formal sync still closed.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, controlled no-change refresh audit evidence, and mock-proven auth schema gate.
- Not suitable now: formal product/order batch sync, fully authenticated multi-user production use, large-scale multi-store production, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Auth-1L: Auth schema migration approval plan`
2. `Phase ERP-Auth-1M: Auth schema migration implementation`
3. `Phase ERP-Auth-1N: Auth schema post-migration verification`
4. `Phase ERP-Backup-2B: Restore runbook mock drill gate`
5. `Phase Naver-ERP-21B: Existing-order no-change audit UI runtime walkthrough`

### Latest update after `Phase ERP-Auth-1L` to `Phase Naver-ERP-21B`

- Project overall planning progress: about `72% - 78%`
- Naver basic ERP loop progress: about `80% - 85%`
- ERP real-user landing progress: about `74% - 80%`
- Production version for long-term non-technical use: about `68% - 74%`

Implemented in this update:

- Approved and implemented the local ERP auth foundation schema migration.
- Created a pre-migration backup and manifest for `backend/codex1.db`.
- Added auth models and `upgrade_auth_schema.py` in Codex1.
- Migrated the real local database to include auth foundation tables and safe system role/permission metadata.
- Verified `erp_roles=5`, `erp_permissions=10`, `erp_role_permissions=35`, `erp_users=0`, and `erp_store_memberships=0`.
- Added a private restore runbook mock drill gate.
- Recorded the no-change Naver order refresh UI/audit wording boundary.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, controlled no-change refresh audit evidence, and migrated auth foundation tables.
- Not suitable now: formal product/order batch sync, active multi-user login production use, large-scale multi-store production, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Auth-1O: Auth role assignment approval plan`
2. `Phase ERP-Auth-1P: Auth role assignment mock gate`
3. `Phase ERP-Auth-1Q: Auth readonly users/roles API approval plan`
4. `Phase ERP-Backup-2C: Restore runbook readonly UI plan`
5. `Phase Naver-ERP-21C: No-change audit display implementation check`

### Latest update after `Phase ERP-Batch-1A` to `Phase ERP-Multistore-1A`

- Project overall planning progress: about `73% - 79%`
- Naver basic ERP loop progress: about `81% - 86%`
- ERP real-user landing progress: about `75% - 81%`
- Production version for long-term non-technical use: about `69% - 75%`

Implemented in this update:

- Shifted the near-term priority to formal product/order batch sync readiness and large-scale multi-store production operation.
- Documented the production gate for formal batch sync: human approval, store-scoped permission, sensitive-action approval, fresh readonly preview, verified backup, duplicate protection, field whitelist, rollback plan, failure isolation, audit evidence, readback, and sensitive scan.
- Added private Codex1 mock gate coverage for Naver order batch, Naver order refresh batch, and Naver product batch readiness.
- Added safe permission keys for `products.batch_sync_write` and `orders.batch_sync_write` to the role model.
- Applied the safe auth permission metadata seed locally: `erp_permissions=12`, `erp_role_permissions=39`, `erp_users=0`, and `erp_store_memberships=0`.
- Documented Naver order batch refresh and Naver product batch sync production plans.
- Documented the multi-store production operation model with actor identity, active store membership, per-store task isolation, audit, backup, and business-safe summaries.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, controlled no-change refresh audit evidence, migrated auth foundation tables, and mock-proven formal batch sync production gate design.
- Not suitable now: actually opening formal product/order batch sync, active multi-user login production use, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Batch-1C: Formal batch sync readonly evidence API plan`
2. `Phase ERP-Batch-1D: Batch sync approval UI plan`
3. `Phase Naver-Order-Batch-1B: Order batch readonly candidate window`
4. `Phase Naver-Product-Batch-1B: Product batch page expansion readonly repeat`
5. `Phase ERP-Multistore-1B: Store membership assignment approval plan`

### Latest update after `Phase ERP-Batch-1C` to `Phase ERP-Multistore-1B`

- Project overall planning progress: about `74% - 80%`
- Naver basic ERP loop progress: about `82% - 87%`
- ERP real-user landing progress: about `76% - 82%`
- Production version for long-term non-technical use: about `70% - 76%`

Implemented in this update:

- Planned a future readonly evidence API for formal batch sync approval screens.
- Planned the future batch sync approval UI with business-first wording and folded technical diagnostics.
- Ran a protected Naver order readonly candidate window over a recent 3-day KST range. The existing endpoint still limits the window to one candidate at a time. HTTP returned `200`, preview status was `success`, safe hash `id-hash-192b9c67e8` was observed, and no local write was requested.
- Ran protected Naver product readonly previews for `page=1,size=5` and `page=2,size=5`.
- Product page 1 now reports `would_update=3`, `would_refresh_only=2`, and changed field `stock_quantity`; page 2 remains `success_empty`.
- Planned the first store membership assignment approval flow for future multi-store production operation.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync production gate design, and readonly evidence for future batch approval.
- Not suitable now: actually opening formal product/order batch sync, automatic product stock update writes, active multi-user login production use, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-Product-Batch-1C: Product stock-change approval plan`
2. `Phase Naver-Product-Batch-1D: Product stock-change mock write gate`
3. `Phase ERP-Batch-1E: Readonly evidence API mock gate`
4. `Phase ERP-Multistore-1C: Store membership mock assignment gate`
5. `Phase ERP-Auth-1O: Auth role assignment approval plan`

### Latest update after `Phase Naver-Product-Batch-1C` to `Phase ERP-Auth-1O`

- Project overall planning progress: about `75% - 81%`
- Naver basic ERP loop progress: about `83% - 88%`
- ERP real-user landing progress: about `77% - 83%`
- Production version for long-term non-technical use: about `71% - 77%`

Implemented in this update:

- Planned the approval boundary for the 3 stock-only Naver product changes observed in readonly preview.
- Added private Codex1 mock gate `_evaluate_naver_product_stock_change_mock_write_gate(...)`.
- Added private Codex1 mock gate `_evaluate_batch_readonly_evidence_api_mock_gate(...)` for future readonly evidence API design.
- Added private Codex1 mock gate `evaluate_store_membership_assignment_mock_gate(...)`.
- Added safe auth permission metadata for `store_membership.assign`; current auth metadata is `erp_permissions=13`, `erp_role_permissions=41`, `erp_users=0`, and `erp_store_memberships=0`.
- Planned future auth role assignment approval.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync production gate design, readonly evidence for future batch approval, and mock-proven stock-change/membership gates.
- Not suitable now: actually writing the 3 product stock changes, opening formal product/order batch sync, active multi-user login production use, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase Naver-Product-Batch-1E: Product stock-change real write approval`
2. `Phase Naver-Product-Batch-1F: Product stock-change small local write`
3. `Phase Naver-Product-Batch-1G: Product stock-change post-write verification`
4. `Phase ERP-Batch-1F: Readonly evidence API local implementation plan`
5. `Phase ERP-Multistore-1D: Store membership real assignment approval`

### Latest update after `Phase Naver-Product-Batch-1E` to `Phase ERP-Multistore-1D`

- Project overall planning progress: about `76% - 82%`
- Naver basic ERP loop progress: about `84% - 89%`
- ERP real-user landing progress: about `78% - 84%`
- Production version for long-term non-technical use: about `72% - 78%`

Implemented in this update:

- Approved the latest Naver product stock-only evidence for controlled local writing after backup, role approval, and rollback/audit readiness.
- Added a private Codex1 real-write approval wrapper `_evaluate_naver_product_stock_change_real_write_approval(...)`.
- Added a narrow private Codex1 local writer `_sync_naver_product_stock_change_local_write(...)` that may update only `products.stock_quantity` for existing Naver products.
- Re-ran protected Naver product readonly evidence for `page=1,size=5` and `page=2,size=5`.
- Executed the controlled stock-only local write for 3 existing store 8 Naver products after creating a verified backup.
- Verified that product count stayed stable and that orders, SyncLog, tested-success, timeline events, users, and store memberships did not change.
- Planned the future readonly evidence API local implementation and the real store membership assignment approval boundary.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync production gate design, readonly evidence for future batch approval, and controlled stock-only local product update.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Batch-1G: Readonly evidence API mock route gate`
2. `Phase ERP-Batch-1H: Readonly evidence API local route implementation`
3. `Phase ERP-Multistore-1E: Store membership schema runtime assignment mock gate`
4. `Phase Naver-Product-Batch-1H: Product stock-change UI verification`
5. `Phase Naver-Product-Batch-1I: Product batch sync rollback drill plan`

### Latest update after `Phase ERP-Batch-1G` to `Phase Naver-Product-Batch-1I`

- Project overall planning progress: about `77% - 83%`
- Naver basic ERP loop progress: about `85% - 90%`
- ERP real-user landing progress: about `79% - 85%`
- Production version for long-term non-technical use: about `73% - 79%`

Implemented in this update:

- Added the local batch readonly evidence route `POST /api/v1/batch/readonly-evidence`.
- Added Codex2 `backendApi.normalizeBatchReadonlyEvidence(...)` for later approval UI integration.
- Added route-level mock gate coverage for safe evidence normalization and sensitive-field blocking.
- Added `evaluate_store_membership_assignment_runtime_mock_gate(...)`, which reads real auth tables for target user, role, approval, and duplicate-membership checks without writing rows.
- Documented Products UI verification after the controlled Naver stock-only local write.
- Planned the product batch sync rollback drill required before any future formal product batch sync opening.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync production gate design, readonly evidence API normalization, controlled stock-only local product update, and runtime mock checks for future store membership assignment.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Batch-1I: Batch approval UI evidence integration plan`
2. `Phase ERP-Batch-1J: Batch approval UI readonly evidence display`
3. `Phase ERP-Multistore-1F: Store membership assignment readonly API plan`
4. `Phase Naver-Product-Batch-1J: Product rollback drill mock gate`
5. `Phase Naver-Order-Batch-1C: Order batch readonly evidence API alignment`

### Latest update after `Phase ERP-Batch-1I` to `Phase Naver-Order-Batch-1C`

- Project overall planning progress: about `78% - 84%`
- Naver basic ERP loop progress: about `86% - 91%`
- ERP real-user landing progress: about `80% - 86%`
- Production version for long-term non-technical use: about `74% - 80%`

Implemented in this update:

- Added a Codex2 Orders panel for Naver batch approval readonly evidence.
- Added `dataProvider.normalizeBatchReadonlyEvidence(...)` so backend and mock mode can display the same evidence shape.
- Kept product/order evidence as approval material only; no batch sync execute button was added.
- Planned the future store-membership assignment readonly API.
- Added the private Codex1 product rollback drill mock gate for the controlled stock-only product write path.
- Aligned Naver order batch readonly evidence with the shared batch evidence API shape.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync gate design, readonly evidence API normalization, approval evidence display, controlled stock-only local product update, and runtime mock checks for future store membership assignment.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Batch-1K: Batch approval UI runtime walkthrough`
2. `Phase ERP-Multistore-1G: Store membership readonly API mock gate`
3. `Phase ERP-Multistore-1H: Store membership readonly API local implementation plan`
4. `Phase Naver-Product-Batch-1K: Product rollback drill readonly report plan`
5. `Phase Naver-Order-Batch-1D: Order batch approval evidence UI walkthrough`

### Latest update after `Phase ERP-Batch-1K`

- Project overall planning progress: about `79% - 84%`
- Naver basic ERP loop progress: about `86% - 91%`
- ERP real-user landing progress: about `81% - 86%`
- Production version for long-term non-technical use: about `75% - 80%`

Implemented in this update:

- Runtime-walked the Orders batch approval evidence panel in mock data-source mode.
- Runtime-walked the same panel in backend data-source mode after refreshing local backend port `8012`.
- Confirmed the evidence panel renders without white screen and does not show formal-sync-open wording.
- Fixed the main evidence status copy so backend mode shows Chinese seller-facing wording instead of the backend English status message.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, mock-proven formal batch sync gate design, readonly evidence API normalization, approval evidence UI display, controlled stock-only local product update, and runtime mock checks for future store membership assignment.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Multistore-1G: Store membership readonly API mock gate`
2. `Phase ERP-Multistore-1H: Store membership readonly API local implementation plan`
3. `Phase Naver-Product-Batch-1K: Product rollback drill readonly report plan`
4. `Phase Naver-Order-Batch-1D: Order batch approval evidence UI walkthrough`
5. `Phase ERP-Batch-1L: Batch approval evidence backend wording cleanup`

### Latest update after `Phase ERP-Multistore-1G` to `Phase ERP-Batch-1L`

- Project overall planning progress: about `80% - 85%`
- Naver basic ERP loop progress: about `87% - 92%`
- ERP real-user landing progress: about `82% - 87%`
- Production version for long-term non-technical use: about `76% - 81%`

Implemented in this update:

- Added Codex1 `POST /api/v1/permissions/store-membership/readonly-check` as a readonly membership assignment readiness API.
- The new API reads existing auth tables, reports missing target user, duplicate active membership, blocked checks, or ready-for-later-assignment status, and keeps `membership_written=false`.
- Documented the local implementation boundary for future membership assignment UI usage.
- Planned a product rollback drill readonly report surface for backup, temporary restore, readback, and sensitive-scan evidence.
- Confirmed the Orders batch approval evidence UI remains a readonly business review panel for Naver order evidence.
- Cleaned Codex1 batch evidence default business messages so backend responses use Chinese seller-facing copy instead of English fallback text.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, readonly batch evidence API normalization, approval evidence UI display, controlled stock-only local product update, and readonly membership assignment readiness checks.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Multistore-1I: Store membership readonly API UI plan`
2. `Phase ERP-Multistore-1J: Store membership readonly UI display`
3. `Phase Naver-Product-Batch-1L: Product rollback drill mock report gate`
4. `Phase Naver-Order-Batch-1E: Order batch evidence backend wording alignment`
5. `Phase ERP-Batch-1M: Batch approval evidence audit linkage plan`

### Latest update after `Phase ERP-Multistore-1I` to `Phase ERP-Batch-1M`

- Project overall planning progress: about `81% - 86%`
- Naver basic ERP loop progress: about `88% - 93%`
- ERP real-user landing progress: about `83% - 88%`
- Production version for long-term non-technical use: about `77% - 82%`

Implemented in this update:

- Planned the Accounts-page UI boundary for store membership readonly checks.
- Added a Codex2 Accounts panel for store membership readiness in backend and mock data-source modes.
- Added `dataProvider.checkStoreMembershipReadonly(...)` and backend adapter support for `POST /api/v1/permissions/store-membership/readonly-check`.
- Added a private Codex1 product rollback drill readonly report mock gate.
- Aligned default Naver order batch evidence backend wording to Chinese business copy.
- Added an audit-linkage planned flag to readonly batch evidence so future batch writes must still prove audit readiness.

Current positioning:

- Suitable now: single Naver store internal trial, local product/order/inventory/sales viewing, controlled preview/single/small refresh/manual review, backup report display, restore dry-run evidence, audit trail review, role-aware action visibility, migrated auth foundation tables, readonly batch evidence API normalization, approval evidence UI display, controlled stock-only local product update, readonly membership assignment readiness checks, and rollback report planning.
- Not suitable now: opening formal product/order batch sync, broad product writes, active multi-user login production use, real store membership assignment, large-scale multi-store production operation, automated shipment/cancel/return/exchange, real production restore, or final finance/settlement/profit use.

Next 5 recommended stages:

1. `Phase ERP-Multistore-1K: Store membership readonly UI walkthrough`
2. `Phase ERP-Multistore-1L: Real user invitation approval plan`
3. `Phase Naver-Product-Batch-1M: Product rollback readonly report UI plan`
4. `Phase ERP-Batch-1N: Batch approval audit evidence mock gate`
5. `Phase Naver-Order-Batch-1F: Order batch approval evidence audit readiness plan`
