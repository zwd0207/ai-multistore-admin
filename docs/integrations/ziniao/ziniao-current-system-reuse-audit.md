> 文档类型：紫鸟集成研究快照
> 研究日期：2026-07-13
> 当前状态：参考资料
> 权威性：不替代 `PROJECT_CONTROL.md`
> 重新核实要求：实际开发或接入前必须重新核对紫鸟官方平台

# 当前系统复用审查

> 分支：`integration/operator-v1-preview`
> 基线：`de94cec`
> 结果：未发现任何既有紫鸟生产实现；本阶段未修改代码。

## 1. 复用分类

本文采用任务指定的五类：

1. 可直接复用
2. 需要扩展
3. 确实需要新增
4. 与紫鸟无关，继续使用 Naver/Coupang 官方 API
5. 高风险或不应该接入

## 2. 模型与服务复用矩阵

| 现有能力 | 现有文件 | 分类 | 紫鸟映射 | 结论 |
|---|---|---|---|---|
| Store | `models/store.py`, `services/store_service.py` | 需要扩展 | 内部店铺与紫鸟账号 | 继续作为唯一内部店铺；不能把紫鸟店铺再建成第二套 Store |
| DeviceEnvironment | `models/device_environment.py` | 需要扩展 | 紫鸟设备、IP 标签、到期、状态 | 可承载运营展示；需外部设备 ID、套餐、到期和来源字段 |
| PlatformLoginCredential | `models/platform_login_credential.py` | 需要扩展 | 平台登录账号、设备绑定 | 只显示账号状态；不能向普通前端返回密码或紫鸟 Token |
| ApiCredential | `models/api_credential.py` | 需要扩展 | 紫鸟 App/API Key | 已加密字段可复用，但当前强制 `store_id`，而紫鸟 App 是公司级，不能复制到每个店铺 |
| ErpUser / Role / Permission | `models/auth.py` | 可直接复用 | 内部用户、角色、权限 | 继续作为系统唯一授权源 |
| ErpStoreMembership | `models/auth.py`, `operator_access_service.py` | 可直接复用 | 内部用户可访问店铺 | 所有紫鸟数据和动作仍必须先通过内部店铺成员关系 |
| Product | `models/product.py` | 与紫鸟无关，继续平台 API | Naver/Coupang 商品 | 紫鸟 ERP API 未证明提供这些业务数据 |
| Order / OrderStatusEvent | `models/order.py`, `models/order_status_event.py` | 与紫鸟无关，继续平台 API | Naver/Coupang 订单/状态 | 不从浏览器页面结果旁路覆盖官方 API 数据 |
| CustomerInquiry | `models/customer_inquiry.py` 及 PXG 只读模型 | 与紫鸟无关，继续平台 API | Naver 客服咨询 | 紫鸟 Skill/页面操作不能替代官方咨询 API |
| Email | `models/email_account.py`, `models/important_email.py` | 与紫鸟无关，继续现有能力 | 邮箱/重要邮件 | SkillHub 未发现本项目所需正式邮箱 API |
| 销售与结算 | `models/financial.py` | 与紫鸟无关，继续平台 API | Naver/Coupang 销售、结算 | 紫鸟公开浏览器 API 没有相关结构化接口 |
| SyncLog | `models/sync_log.py`, `sync_log_service.py` | 可直接复用 | 紫鸟只读同步结果 | 只记录范围、数量、状态、时间和安全错误码 |
| SyncCheckpoint | `models/sync_checkpoint.py` | 可直接复用 | 公司/店铺资源游标和租约 | 未来按 provider + scope 隔离；不新增第二套调度器 |
| ApiCapability | `models/api_capability.py`, `api_capability_service.py` | 可直接复用 | API 文档盘点与测试证据 | 可记录官方文档、权限、字段、测试状态 |
| OperationAuditLog | `models/operation_audit_log.py`, `operation_audit_service.py` | 可直接复用 | 授权、绑定、SSO、写入审批 | 不能记录 Token、请求头、完整响应或平台密码 |
| Store onboarding | `models/store_onboarding.py`, `store_onboarding_service.py` | 需要扩展 | 紫鸟发现店铺候选 | 仅生成匹配候选，正式绑定必须人工确认 |
| 自动读取调度 | `automatic_read_sync_service.py` | 可直接复用 | 后续紫鸟只读快照 | 复用租约、错峰、重试、失败隔离；首期默认关闭 |
| Dashboard/workbench | `stats_service.py`, `dashboard.py`, `Dashboard.jsx` | 需要扩展 | 紫鸟环境健康和到期提醒 | 扩展现有概览，不新增第二工作台 |
| AI Context | `ai.py` 及现有店铺上下文 | 需要扩展 | 已确认店铺/设备/权限状态 | AI 只读上下文；不得自动执行高风险写入 |

## 3. 页面和接口复用

| 现有页面/路由 | 分类 | 后续用途 |
|---|---|---|
| `src/pages/Stores.jsx` / stores API | 需要扩展 | 展示紫鸟绑定状态和候选匹配 |
| `src/pages/Devices.jsx` / device environments API | 需要扩展 | 展示紫鸟设备、套餐和到期提醒 |
| `src/pages/Accounts.jsx` / platform logins API | 需要扩展 | 展示平台登录账号与紫鸟账号关系 |
| `src/pages/Dashboard.jsx` / store overview | 需要扩展 | 展示环境异常、设备到期、绑定缺失 |
| 凭证页面/credentials API | 需要扩展 | 公司级紫鸟连接配置；前端只显示配置状态 |
| 同步日志页面/API | 可直接复用 | 展示紫鸟只读同步状态，不显示请求原文 |
| 权限与店铺成员页面/API | 可直接复用 | 控制谁能查看、绑定和启动店铺 |
| Products/Orders/CustomerService | 与紫鸟无关，继续平台 API | 不新增紫鸟旁路业务数据接口 |

## 4. 确实缺失且允许后续建议新增

在全仓库搜索后，未找到公司级外部连接或通用外部绑定模型。以下能力确实缺失，但本阶段只记录，不开发。

### 4.1 公司级紫鸟连接

缺失原因：`ApiCredential.store_id` 非空，无法正确表达“一个紫鸟应用覆盖公司多个店铺”。把同一 API Key 复制到每个店铺会造成轮换、审计和跨店铺风险。

推荐后续新增一个通用公司级连接实体，而不是紫鸟专用凭证副本。最小字段：

- provider
- auth_mode
- encrypted credential reference
- status / verified_at / rotated_at
- owner / approval / failure lock

### 4.2 外部店铺绑定

缺失原因：Store 没有通用的 provider store binding。推荐通用映射实体：

- internal `store_id`
- provider=`ziniao`
- external company/store/platform/site ID
- match status=`candidate|confirmed|rejected|inactive`
- confirmed_by / confirmed_at
- source_updated_at / last_synced_at

禁止根据相似店名自动确认。

### 4.3 外部用户绑定

缺失原因：当前 ErpUser 没有紫鸟 `userId` 绑定。推荐通用用户映射，不把紫鸟 ID 直接塞进用户主表。

### 4.4 回调收件箱

首期不需要新增。只有未来批准回调后，才能评估复用现有操作审计/事件模型；若截图和申请消息无法安全表达，再论证最小事件存储。

## 5. 禁止创建的重复能力

- 第二套 Store、Product、Order、CustomerInquiry 或员工表。
- 第二套同步调度器、同步日志或工作台。
- 为 SkillHub 新建重复商品库。
- 用 Webdriver 抓取结果覆盖 Naver/Coupang 官方 API 数据。
- 为 SSO Token 新建普通前端可读字段。
- 在每个店铺重复保存同一个公司级 API Key。

## 6. 高风险或不应该接入

| 能力 | 原因 | 决策 |
|---|---|---|
| 自动新增/删除员工授权 | 会改变紫鸟权限 | 只有独立审批阶段才评估 |
| 创建/删除账号 | 影响店铺资产和凭证 | 禁止首期接入 |
| 购买/续费/修改设备 | 付费和环境写入 | 禁止首期接入 |
| 修改代理/IP/缓存 | 可能影响店铺风控和登录状态 | 禁止 |
| Webdriver/CLI 自动页面提交 | 可能修改电商平台数据 | 禁止首期接入 |
| 指纹伪装、环境脱敏规避、验证码绕过 | 违反本项目安全边界 | 永久不设计 |
| Token 进入 URL/前端/日志 | 高敏凭证泄露 | 禁止 |
| 自动按店名绑定 | 可绑定错店 | 禁止；只产生候选 |

## 7. 复用优先的最小后续任务

下一阶段最小安全任务不是接真实 API，而是：

1. 定义公司连接、外部店铺候选和外部用户候选的接口合同。
2. 使用完全虚构的紫鸟响应建立本地 Mock 适配器。
3. 复用 Store、DeviceEnvironment、ErpUser、ErpStoreMembership、ApiCapability、SyncLog 和现有工作台。
4. 只展示“候选匹配”和“设备状态”，不保存凭证、不启动店铺、不写权限。
5. 验证不会新增重复表、旁路 API 或跨店铺缓存。

## 8. 重复能力检查

- 紫鸟生产模型/服务/页面：确认缺失。
- 公司级外部连接：确认缺失。
- 外部店铺/用户映射：确认缺失。
- Store、设备、用户、RBAC、同步、日志、审计、工作台：已有，必须扩展而非重建。
- Naver/Coupang 业务 API：已有，继续使用。

结论：未来接入重点是“连接和映射”，不是重建业务系统。
