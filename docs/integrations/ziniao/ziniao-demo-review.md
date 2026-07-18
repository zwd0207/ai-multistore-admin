> 文档类型：紫鸟集成研究快照
> 研究日期：2026-07-13
> 当前状态：参考资料
> 权威性：不替代 `PROJECT_CONTROL.md`
> 重新核实要求：实际开发或接入前必须重新核对紫鸟官方平台

# ERP-Demo 审查报告

> 来源：`<local-research-source>/ERP-Demo.zip`
> 审查方式：解压到 `%TEMP%` 后静态读取；未编译、未运行、未配置凭证、未调用接口。

## 1. 技术形态

- 后端：RuoYi / Spring Boot / Java 8。
- 前端：RuoYi Vue。
- 数据库：RuoYi SQL 初始化脚本，并给 `sys_user` 增加紫鸟员工绑定字段。
- 紫鸟 SDK：`ruoyi-admin/lib/sdk-java-5.1.0.jar`。
- Base URL：`https://sbappstoreapi.ziniao.com`。
- 调用模式：复杂鉴权 SDK，`CommonRequest + POST_JSON + appAuthToken`。

当前系统是 Python/FastAPI/SQLAlchemy/React，Demo 不能直接移植，只能复用协议、字段和交互流程知识。

## 2. 已实现能力

| 能力 | Demo 路径 | 结果 | 确认状态 |
|---|---|---|---|
| 获取 App Token | `OpenApiService` | SDK 获取并缓存 | ERP-Demo确认但需更新核对 |
| 员工列表 | `/superbrowser/rest/v1/erp/staff/list` | 支持筛选和分页 | ERP-Demo确认但需更新核对 |
| 公司全部店铺 | `/superbrowser/rest/v1/erp/store/list` | 店铺、平台、设备和账号字段 | ERP-Demo确认但需更新核对 |
| 用户可访问店铺 | `/superbrowser/rest/v1/erp/user/stores` | 按 `userId` 查询 | ERP-Demo确认但需更新核对 |
| 店铺授权用户 | `/superbrowser/rest/v1/erp/store/user/list` | 按店铺查询人员 | ERP-Demo确认但需更新核对 |
| 新增店铺授权 | `/superbrowser/rest/v1/erp/store/auth/add` | 逐项写入授权 | ERP-Demo确认但需更新核对 |
| 删除店铺授权 | `/superbrowser/rest/v1/erp/store/auth/delete` | 逐项删除授权 | ERP-Demo确认但需更新核对 |
| 获取用户登录 Token | `/superbrowser/rest/v1/token/user-login` | 生成 SSO Token | ERP-Demo确认但需更新核对 |
| 一键启动店铺 | `superbrowser://OpenStrore?...` | 前端获得启动 URL | ERP-Demo确认但需更新核对 |
| ERP 用户绑定紫鸟员工 | `sys_user.zn_staff_id` | 后台人员关联 | ERP-Demo确认但需更新核对 |

## 3. 请求与返回模型

### 3.1 Demo 请求字段

- 员工：`companyId`, `username`, `name`, `level`, `departmentIds`, `delflag`, `isAccurate`, `page`, `limit`。
- 店铺列表：`companyId`, `storeName`, `ip`, `page`, `limit`。
- 用户店铺：`companyId`, `userId`, `storeName`, `isAccurate`, `page`, `limit`。
- 店铺用户：`companyId`, `storeIdList`, `page`, `limit`。
- 新增授权：`companyId`, `storeIdList`, `staffId`, `isAuthAddtion`。
- 删除授权：`companyId`, `storeIdList`, `staffId`。
- 用户登录 Token：`companyId`, `userId`。

### 3.2 Demo 返回字段

- 员工：`userId`, `username`, `name`, `level`, `mobile`, `authPhone`, `delflag`。
- 店铺：`id`, `ip/ipId`, 最近用户和时间、`name`, `platform`, 设备到期、套餐/地区、分类、平台登录账号、标签。
- 授权：`storeId`, `userId`, `username`。
- 用户 Token：`token`, `expireTime`, `timeUnit`。
- 业务包装：`ret`, `status`, `msg`, `data`, `count`。

这些字段与当前公开 API 详情基本吻合，但不能据此认为 Demo 的所有模型已覆盖 2026 年新增字段。

## 4. 2026 官方文档对照

| 对照项 | Demo | 2026 公开资料 | 判断 |
|---|---|---|---|
| 店铺、员工、授权路径 | 7 个固定路径 | 这些路径仍在公开目录 | 可参考，但仍需应用权限核对 |
| Java SDK | 5.1.0 | docId 129 公开下载仍写 5.0.6 | 版本不一致，需人工核对官方推荐版本 |
| 鉴权模式 | 复杂鉴权 | 官方推荐简单通用模式，也保留复杂鉴权 | 新系统优先评估简单通用模式 |
| 账号 API 数量 | 仅使用少数接口 | 当前账号组 24 条 | Demo 覆盖很小 |
| ERP API 总量 | README 未完整盘点 | 当前五组 74 条目录记录/73 唯一 ID | Demo 不是完整 SDK 样例 |
| SSO Schema | `OpenStrore` | 官方文档仍使用该拼写 | 协议名可参考 |
| Token 有效期 | 固定缓存 119/29 分钟 | 官方响应返回 `expiresIn` 或 `expireTime/timeUnit` | Demo 缓存策略不应复用 |
| API Key 简单模式 | 未实现 | 2026 文档标为推荐 | Demo 缺失 |
| 回调/Webhook | 未实现 | docId 247 已公开 | Demo 缺失 |
| Webdriver/CLI | 未实现 | 2026 文档已公开 | Demo 缺失 |

## 5. 可复用部分

### 可直接作为协议参考

- 已确认的七个路径和字段命名。
- `CommonRequest` 的业务参数与双层响应解析思路。
- 店铺列表、用户店铺、授权用户三种不同关系查询。
- SSO 前置链路：ERP 用户绑定 → 查可访问店铺 → 获取用户 Token → 启动客户端。
- 前端“我的店铺”列表和一键启动的用户流程概念。

### 需要重写后复用

- Token 缓存：必须使用服务端返回的有效期并设置提前失效，不能固定 119/29 分钟。
- 错误处理：只保存安全错误码和请求 ID，不保存完整请求/响应。
- 绑定关系：必须显式绑定内部 `store_id`、紫鸟 `storeId`、紫鸟 `userId` 和凭证版本。
- 授权写入：必须有预览、MFA、近期认证、审批令牌、幂等和审计。
- SSO 启动：Token 不能返回到普通前端 URL、日志、浏览器历史或可复制文本。

## 6. 禁止直接复用的实现

| 问题 | Demo 现状 | 风险 |
|---|---|---|
| 固定 Token 缓存 | App Token 119 分钟、用户 Token 29 分钟 | 与服务端真实有效期漂移 |
| 完整请求/响应日志 | 失败时记录请求对象和 `response.getBody()` | 可能泄露 Token、员工和店铺数据 |
| Token 暴露给前端 | SSO URL 含 `openapiToken` | 浏览器历史、前端日志和错误报告泄露 |
| 凭证配置 | YAML 直接配置 App ID/私钥 | 不符合当前系统加密凭证边界 |
| 店铺关联 | 主要依赖紫鸟 ID 和 ERP 用户字段 | 缺少内部店铺、平台、员工、设备四元绑定 |
| 授权写入 | Controller 直接循环调用新增/删除 | 无预览、原子性、幂等、回滚和审批 |
| 权限模型 | 依赖 RuoYi 菜单权限 | 无当前系统 MFA、近期认证、店铺级 RBAC |
| 数据范围 | 可查询手机、登录账号和设备 IP | 普通运营隐私边界不足 |

## 7. Demo 未实现的关键能力

- 简单通用模式 Bearer API Key。
- 账号/设备/人员/权限全目录。
- 公司级凭证与多店铺映射模型。
- 清晰的只读/写入能力分级。
- 回调、事件、重试和截图时效处理。
- Webdriver/CLI 的本地能力和安全隔离。
- 频率限制、错误码、版本废弃检测。
- 审批、审计、凭证轮换、失败锁和跨店铺隔离。
- Naver/Coupang 商品、订单、客服、物流等业务数据整合。

## 8. 最终复用结论

Demo 的价值是“协议样例和用户流程样例”，不是可直接合并的生产模块。

- 协议知识复用：高。
- Java/RuoYi 代码复用：低。
- 安全实现复用：禁止。
- 2026 兼容性：需重新核对。
- 真实写入：不批准。
