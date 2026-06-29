# 第五阶段 B：Codex1 正式接口联调第一轮

## 范围

本轮只迁移 Dashboard Summary、Stores、Products、Orders、Customer Inquiries、Sync Logs 与 AI Daily Context 的读取能力。未新增大页面，未连接真实平台或邮箱，未调用任何大模型。

## 数据链路

页面通过 `dataProvider.js` 选择 mock/backend 数据源，`backendApi.js` 请求 Codex1，`adapters.js` 统一 snake_case、状态、平台、分页及页面缺省字段。页面 JSX 不包含后端原始字段转换。

商品、订单和客服接口要求 `store_id`。provider 优先采用调用方的 `storeId`，否则读取 `/stores` 并自动选择首个店铺；后端店铺结果在单次页面会话中缓存，并用于补全列表店铺名称。

## 页面迁移

- Dashboard：Summary 卡片、风险与最近动态读取后端兼容结构；新增纯结构化 Daily Context 区块。
- Stores：列表读取后端；backend 模式只读。
- Products：列表按店铺读取后端；缺失店铺名称由 provider 补全；backend 模式只读。
- Orders：列表按店铺读取后端；`buyer_masked_phone` 映射为 `phone/maskedPhone`；backend 模式只读。
- Customer Service：咨询列表读取后端；缺失订单、商品、优先级与回复记录由 adapter 提供安全默认值；backend 模式只保留详情。
- Logs：保留原 mock 操作审计，增加 Codex1 Sync Logs 区块。

## 错误与空状态

Dashboard、通用资源页、Customer Service、Sync Logs 均捕获接口错误并展示中文 EmptyState。Codex1 未启动时返回 `HttpError / NETWORK_ERROR`，页面不会因未处理 Promise 变为空白。列表为空时沿用 DataTable 空状态。

## 验证结果

- Codex1 8011：启动与 health 正常。
- backend provider：Dashboard 1 个店铺、Stores 1 条、Products 3 条、Orders 3 条、Customer Inquiries 3 条、Sync Logs 4 条、Daily Context 日期 2026-06-29。
- 订单手机号：全部为掩码或空占位，金额为 number，币种存在。
- mock provider：Stores/Products/Orders/Customer Inquiries/Dashboard 均通过返回结构断言。
- Codex1 离线：中文 `NETWORK_ERROR` 断言通过。
- mock 模式路由：13/13 HTTP 200。
- backend 模式路由：13/13 HTTP 200。
- `npm run build`：通过。
- 严格 UTF-8 与替换字符扫描：0 异常。

## 当前边界

- 尚未提供全局店铺选择器，backend 模式默认首个店铺；provider 已支持显式 `storeId`。
- backend 模式仅迁移读取，不接入店铺、商品、订单或客服写接口。
- Sales、Devices、Emails、Appeals、Environment、Accounts、Settings 与原操作日志仍使用 mock。
- Daily Context 仅展示后端结构化数据，不生成 AI 内容。
