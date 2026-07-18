> 文档类型：紫鸟集成研究快照
> 研究日期：2026-07-13
> 当前状态：参考资料
> 权威性：不替代 `PROJECT_CONTROL.md`
> 重新核实要求：实际开发或接入前必须重新核对紫鸟官方平台

# 紫鸟开放 API 完整盘点

> 本清单基于 2026-07-13 实际读取的公开文档树和 `document/api-info` 页面数据。没有调用任何 `/openapi-router` 业务接口。

## 1. 能力来源边界

| 代号 | 来源 | 本文处理方式 |
|---|---|---|
| A | 紫鸟官方开放 API | 本文主体，按公开 API ID、路径和字段记录 |
| B | SkillHub Skill | 仅在 `ziniao-skillhub-inventory.md` 登记，不当作 A 类 API |
| C | 紫鸟客户端、CLI、SSO Schema、Webdriver | 单列说明，不当作服务端结构化业务 API |
| D | Naver/Coupang 官方 API | 商品、订单、客服、物流、广告、结算仍走平台 API |
| E | 人工登录或受控浏览器操作 | 无稳定结构化 API 时保留人工入口 |

## 2. 数量与版本差异

- 当前公开五个 ERP 核心分组：账号、设备、部门员工、访问策略、角色权限。
- 当前目录：74 条记录、73 个唯一 API ID。`ERP-解绑设备`（API ID 992）在账号和设备分组重复出现。
- 另有 3 个基础/SSO 专用服务端端点：获取应用 Token、获取公司 ID、获取指定用户登录 Token。
- 因此，本清单共登记 76 个唯一服务端端点。
- Skill ID 118 的公开包仍宣称“五组 72 个接口”，账号组仅列 22 个；当前文档账号组已是 24 个。该 Skill 包不得作为 2026 年唯一真相源。

## 3. 通用调用合同

### 3.1 简单通用模式

- 基址：`https://sbappstoreapi.ziniao.com/openapi-router`
- 鉴权：`Authorization: Bearer {API Key}`
- 认证材料和 API Key 只能在登录后的应用控制台查看。
- 运行时不要求紫鸟客户端，但应用创建、权限申请和 IP 白名单配置需要人工登录。

### 3.2 复杂鉴权模式

- 基址：`https://sbappstoreapi.ziniao.com`
- 公共参数：`app_id`、`charset=UTF-8`、`method`、`format=json`、`sign_type=RSA2`、`version=1.0`、`timestamp`、`biz_content`、`sdk_version`、可选 Token、`sign`。
- 时间戳公开说明允许误差 5 分钟。
- 先调用 `/auth/get_app_token`，再使用 `app_auth_token`；公开响应以 `expiresIn` 秒数表示有效期，`-1` 表示永久。
- 未找到专门刷新端点；不得自行假设刷新规则。

### 3.3 公共响应

- 网关层：`request_id`、`code`、`msg`、可选 `sub_code/sub_msg`、`data`。
- 业务层通常包含：`ret`、`status`、`msg`、`data`、`count`。
- 业务字段有时直接位于业务层根节点，不能统一假设都在 `data.data`。

### 3.4 公开资料缺口

- 所有 73 个 ERP API 详情的 `hasQuota/quotaThreshold/quotaUnit` 均未提供值。
- 所有 73 个 ERP API 详情的公开 `responseStatusCodes` 均为空。
- 有 `page/limit` 的接口按公开字段标记为分页；统一最大页大小未公开。
- 没有找到统一版本更新、弃用或迁移公告。

## 4. 基础与 SSO 服务端 API

| ID | 官方名称 | 方法与路径 | 主要输入 | 主要输出 | 分页 | 性质 | 客户端/人工 | 风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|---|---|
| 395 | 获取应用 token | `POST /auth/get_app_token` | 复杂鉴权公共签名参数 | `appAuthToken`, `expiresIn` | 否 | 凭证交换 | 无客户端；需人工创建应用 | 高 | 官方文档确认 |
| 631 | 获取当前自建应用的公司信息 | `GET /app/builtin/company` | 已授权应用 | `companyId` | 否 | 只读 | 无客户端；需应用权限 | 中 | 官方文档确认 |
| 325 | 获取指定用户登录 token | `POST /superbrowser/rest/v1/token/user-login` | `companyId`, `userId` | `token`, `expireTime`, `timeUnit` | 否 | 获取高敏 SSO 令牌 | 打开店铺时需客户端；权限需客服/BOSS 核对 | 高 | 官方文档确认 |

适合首个真实只读微测试的只有公司信息，以及经批准后的员工/店铺只读查询。用户登录 Token 不属于普通只读数据测试。

## 5. 账号管理 API（24 条）

共同权限：登录后为应用申请对应账号查看、账号授权、标签、编辑、缓存或创建删除权限。所有端点都修改紫鸟侧数据或读取紫鸟账号元数据，不直接等于 Naver/Coupang 数据 API。

| ID | 名称 | 路径 | 主要请求字段 | 主要返回字段 | 分页 | 性质/风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|
| 656 | ERP-创建账号 | `/superbrowser/rest/v1/erp/store/create` | `companyId`, `name`, `siteId`, `username`, `password`, `proxyId`, `tagIds` | `storeId`, `siteId`, `riskMsgList` | 否 | 写入/高 | 官方文档确认 |
| 660 | ERP-删除账号 | `/superbrowser/rest/v1/erp/store/delete` | `companyId`, `storeIds` | `ret`, `status`, `msg` | 否 | 删除/高 | 官方文档确认 |
| 724 | ERP-清除账号授权 | `/superbrowser/rest/v1/erp/store/auth/clean` | `companyId`, `storeIdList` | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 657 | 查询某用户有权限的账号列表 | `/superbrowser/rest/v1/erp/user/stores` | `companyId`, `userId`, `storeName`, `isAccurate`, `page`, `limit` | 店铺 ID/名称/平台/IP 到期/地区/标签/最近用户 | 是 | 只读/中 | 官方文档确认 |
| 858 | 清除账号缓存 | `/superbrowser/rest/v1/erp/store/deletecookie` | `companyId`, `removeStoreId`, `removeType`, `userId` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 470 | 用户的账号列表查询 | `/superbrowser/rest/v1/erp/store/list/by/user` | `companyId`, `userId`, `storeName`, `page`, `limit` | `storeId`, `storeName`, `platformName`, `proxyId`, `ipExpiryTime` | 是 | 只读/中 | 官方文档确认 |
| 469 | 账号授权用户列表查询 | `/superbrowser/rest/v1/erp/store/user/list` | `companyId`, `storeIdList`, `page`, `limit` | `storeId`, `userId`, `username`, `count` | 是 | 只读/中 | 官方文档确认 |
| 468 | 账号授权删除 | `/superbrowser/rest/v1/erp/store/auth/delete` | `companyId`, `storeIdList`, `staffId` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 467 | 账号授权新增 | `/superbrowser/rest/v1/erp/store/auth/add` | `companyId`, `storeIdList`, `staffId`, `isAuthAddtion` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 360 | 替换账号标签 | `/superbrowser/rest/v1/store-tag/replace` | `companyId`, `storeIds`, `tagIds`, `userId` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 359 | 重命名账号标签 | `/superbrowser/rest/v1/store-tag/rename` | `companyId`, `tid`, `name`, `userId` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 465 | ERP-账号列表查询 | `/superbrowser/rest/v1/erp/store/list` | `companyId`, `storeId`, `storeName`, `ip`, `page`, `limit` | 店铺 ID/名称/平台/站点/登录账号/设备/套餐/标签 | 是 | 只读/中 | 官方文档确认 |
| 466 | ERP-账号授权查询 | `/superbrowser/rest/v1/erp/store/auth/query` | `companyId`, `userId` | `storeId`, `storeName` | 否 | 只读/中 | 官方文档确认 |
| 358 | 清空账号标签 | `/superbrowser/rest/v1/store-tag/clear` | `companyId`, `storeIds`, `userId` | `ret`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 351 | 解绑账号标签 | `/superbrowser/rest/v1/store-tag/unbind` | `companyId`, `storeIds`, `tagIds`, `userId` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 350 | 移除账号标签 | `/superbrowser/rest/v1/store-tag/remove` | `companyId`, `storeIds`, `tagIds`, `userId` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 348 | 删除账号标签 | `/superbrowser/rest/v1/store-tag/delete` | `companyId`, `tagIds`, `userId` | `ret`, `msg` | 否 | 删除/中 | 官方文档确认 |
| 346 | 添加账号标签 | `/superbrowser/rest/v1/store-tag/add` | `companyId`, `tagName`, `userId` | `tag_id`, `ret`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 347 | 绑定账号标签 | `/superbrowser/rest/v1/store-tag/bind` | `companyId`, `storeIds`, `tagIds`, `userId` | `ret`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 992 | ERP-解绑设备 | `/superbrowser/rest/v1/erp/ip/unbind` | `companyId`, `storeId` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 349 | 账号的标签列表 | `/superbrowser/rest/v1/store-tag/list` | `companyId`, `storeId`, `userId`, `withSystem` | 标签 ID/名称/系统标记/店铺数 | 否 | 只读/低 | 官方文档确认 |
| 781 | ERP-标签列表 | `/superbrowser/rest/v1/erp/tag/list` | `companyId` | 标签 ID/名称 | 否 | 只读/低 | 官方文档确认 |
| 993 | ERP-编辑账号基础信息 | `/superbrowser/rest/v1/erp/store/update/base` | `companyId`, `id`, `name`, `siteId`, `tagIds`, `customerUrl` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 765 | ERP-获取附加网站信息 | `/superbrowser/rest/v1/erp/store/addtion` | `companyId`, `accountName`, `categoryId`, `page`, `limit` | 平台/站点/附加账号/自定义 URL | 是 | 只读/中 | 官方文档确认 |

## 6. 设备管理 API（11 条，ID 992 与账号组重复）

| ID | 名称 | 路径 | 主要请求字段 | 主要返回字段 | 分页 | 性质/风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|
| 652 | ERP-套餐列表查询 | `/superbrowser/rest/v1/erp/package/new` | `companyId` | 地区、网络、系统、配置、带宽、价格 | 否 | 只读/中 | 官方文档确认 |
| 658 | ERP-购买设备 | `/superbrowser/rest/v1/erp/purchase` | `companyId`, `packageId`, `periodId`, `num`, `storeIds` | `order_id`, `proxyIdList` | 否 | 购买写入/高 | 官方文档确认 |
| 659 | ERP-续费设备 | `/superbrowser/rest/v1/erp/renew` | `companyId`, `ipIds`, `periodId` | 订单、设备、到期时间 | 否 | 付费写入/高 | 官方文档确认 |
| 784 | ERP-开关自动续费 | `/superbrowser/rest/v1/erp/ip/renewal` | `companyId`, `ids`, `isOpen` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 759 | ERP-设备查询 | `/superbrowser/rest/v1/erp/ip/page` | `companyId`, `ipAddr`, `page`, `limit` | 设备 ID/IP/端口/类型/到期/续费状态 | 是 | 只读/中 | 官方文档确认 |
| 654 | ERP-绑定设备 | `/superbrowser/rest/v1/erp/ip/bind` | `companyId`, `proxyId`, `storeIdList`, `defyWarning` | `riskMsgList`, `ret`, `status` | 否 | 写入/高 | 官方文档确认 |
| 992 | ERP-解绑设备 | `/superbrowser/rest/v1/erp/ip/unbind` | `companyId`, `storeId` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 1043 | 查询已购设备价格 | `/superbrowser/rest/v1/erp/proxy/purchased_package_info` | `companyId`, `proxyId` | `price`, `regionCloudId` | 否 | 只读/中 | 官方文档确认 |
| 760 | 设备历史绑定记录 | `/superbrowser/rest/v1/erp/ip/historybind` | `companyId`, `proxyId` | 店铺、解绑用户、解绑时间、云类型 | 否 | 只读/中 | 官方文档确认 |
| 954 | 添加自有设备（新） | `/superbrowser/rest/v1/erp/ip/self/add/new` | `companyId`, `addr`, `port`, `type`, `username`, `passwd` | 新设备 ID | 否 | 写入且含代理凭证/高 | 官方文档确认 |
| 1086 | 修改自有设备信息（新） | `/superbrowser/rest/v1/erp/ip/self/edit/new` | 上述字段及 `proxyId` | `ret`, `status`, `msg` | 否 | 写入且含代理凭证/高 | 官方文档确认 |

## 7. 部门员工 API（10 条）

| ID | 名称 | 路径 | 主要请求字段 | 主要返回字段 | 分页 | 性质/风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|
| 738 | 用户的部门变更 | `/superbrowser/rest/v1/erp/staff/department` | `companyId`, `departmentIds`, `staffIds` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 464 | 部门移动 | `/superbrowser/rest/v1/erp/department/order` | `companyId`, `parentId`, `order` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 463 | 部门删除 | `/superbrowser/rest/v1/erp/department/delete` | `companyId`, `id` | `ret`, `status`, `msg` | 否 | 删除/高 | 官方文档确认 |
| 462 | 部门修改 | `/superbrowser/rest/v1/erp/department/update` | `companyId`, `id`, `name`, `parentId` | `ret`, `status`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 461 | 部门新增 | `/superbrowser/rest/v1/erp/department/add` | `companyId`, `name`, `parentId`, `hierarchy` | 新部门 ID | 否 | 写入/中 | 官方文档确认 |
| 460 | 部门查询 | `/superbrowser/rest/v1/erp/department/list` | `companyId` | 部门 ID/名称/层级/父级/排序 | 否 | 只读/低 | 官方文档确认 |
| 458 | ERP-员工查询 | `/superbrowser/rest/v1/erp/staff/list` | `companyId`, `username`, `name`, `level`, `departmentIds`, `delflag`, `page`, `limit` | `userId`, 用户名/姓名/级别/电话/状态 | 是 | 只读但含个人信息/中 | 官方文档确认 |
| 630 | ERP-员工修改 v2 | `/superbrowser/rest/v2/erp/staff/modify` | 身份、手机、部门、登录端、双重验证、登录时间限制 | `ret`, `status`, `msg` | 否 | 写入且安全敏感/高 | 官方文档确认 |
| 629 | ERP-员工新增 v2 | `/superbrowser/rest/v2/erp/staff/add` | 姓名、手机、部门、角色、密码、登录限制 | 新用户 ID/初始密码 | 否 | 写入且凭证敏感/高 | 官方文档确认 |
| 459 | 员工启用禁用 | `/superbrowser/rest/v1/erp/staff/status` | `companyId`, `staffIds`, `status` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |

## 8. 访问策略 API（22 条）

| ID | 名称 | 路径 | 主要请求字段 | 主要返回字段 | 分页 | 性质/风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|
| 723 | 添加网页 | `/security/access_rule_url/add` | `companyId`, `groupId`, `name`, `urlPattern`, `desc` | 新网页 ID | 否 | 写入/高 | 官方文档确认 |
| 720 | 网页详情 | `/security/access_rule_url/detail` | `companyId`, `urlId`/`urlPattern` | URL、名称、分组、类型、描述 | 否 | 只读/中 | 官方文档确认 |
| 719 | 网页列表 | `/security/access_rule_url/list` | `companyId`, `groupIds`, `search`, `tType`, `page`, `limit` | URL 列表与分组 | 是 | 只读/中 | 官方文档确认 |
| 718 | 网页分组列表 | `/security/access_rule_url_group/list` | `companyId`, `groupIdParent`, `isAll` | 分组树、URL 数量 | 否 | 只读/中 | 官方文档确认 |
| 714 | 删除网页分组 | `/security/access_rule_url_group/delete` | `companyId`, `groupId` | `ret`, `msg` | 否 | 删除/高 | 官方文档确认 |
| 713 | 编辑网页分组 | `/security/access_rule_url_group/edit` | `companyId`, `groupId`, `name` | `ret`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 712 | 添加网页分组 | `/security/access_rule_url_group/add` | `companyId`, `groupIdParent`, `name` | 新分组 ID | 否 | 写入/中 | 官方文档确认 |
| 711 | 网页修改分组 | `/security/access_rule_url/change_group` | `companyId`, `groupId`, `urlIds` | `ret`, `msg` | 否 | 写入/中 | 官方文档确认 |
| 710 | 删除网页 | `/security/access_rule_url/delete` | `companyId`, `urlIds` | `ret`, `msg` | 否 | 删除/高 | 官方文档确认 |
| 709 | 编辑网页 | `/security/access_rule_url/edit` | `companyId`, `urlId`, `groupId`, `name`, `urlPattern` | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 726 | 账号移除访问策略 | `/security/access_rule/account_ref/remove_from_account` | `companyId`, `accountId`, `ruleIds` | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 725 | 账号添加访问策略 | `/security/access_rule/account_ref/add_to_account` | `companyId`, `accountId`, `ruleIds`, 冲突检查开关 | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 722 | 账号绑定的访问策略列表 | `/security/access_rule/list/one_account` | `companyId`, `accountId`, `page`, `limit` | 策略、成员、状态、URL 数 | 是 | 只读/中 | 官方文档确认 |
| 717 | 访问规则详情 | `/security/access_rule/detail` | `companyId`, `ruleId` | 生效账号/成员/部门/角色/URL/元素/时间/审批配置 | 否 | 只读但安全敏感/高 | 官方文档确认 |
| 715 | 访问规则列表 | `/security/access_rule/list` | 多种生效范围、账号/用户筛选、`page`, `limit` | 规则列表、账号、用户、部门、角色 | 是 | 只读但安全敏感/高 | 官方文档确认 |
| 708 | 访问规则删除 | `/security/access_rule/delete` | `companyId`, `ruleIds` | `ret`, `msg` | 否 | 删除/高 | 官方文档确认 |
| 707 | 访问规则启用禁用 | `/security/access_rule/active` | `companyId`, `ruleIds`, `isActive` | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 705 | 访问规则设置生效成员 | `/security/access_rule/change_user` | 规则、用户/部门/角色增删集合 | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 704 | 访问规则编辑 | `/security/access_rule/edit` | 规则、URL/DOM、成员、账号、权限、时间和审批配置 | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 703 | 访问规则新建 | `/security/access_rule/add` | 上述规则完整定义 | 新规则 ID | 否 | 写入/高 | 官方文档确认 |
| 721 | 规则可绑定的账号列表 | `/security/access_rule/account/bindable_list` | `companyId`, `ruleId`, 平台/标签/名称、`page`, `limit` | 可绑定账号、平台、标签 | 是 | 只读/中 | 官方文档确认 |
| 706 | 访问规则设置生效账号 | `/security/access_rule/change_account` | `companyId`, `ruleId`, 增删账号集合 | `ret`, `msg` | 否 | 写入/高 | 官方文档确认 |

上述路径均省略共同前缀 `/superbrowser/rest/v1/erp`，完整路径以公开 API 详情为准。

## 9. 角色和权限 API（7 条）

| ID | 名称 | 路径 | 主要请求字段 | 主要返回字段 | 分页 | 性质/风险 | 确认状态 |
|---:|---|---|---|---|---|---|---|
| 766 | ERP-调整角色 | `/superbrowser/rest/v1/erp/staff/change/role` | `companyId`, `roleId`, `staffIds` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 756 | ERP-用户角色列表 | `/superbrowser/rest/v1/erp/staff/role/list` | `companyId`, `staffId` | 角色 ID/名称 | 否 | 只读/中 | 官方文档确认 |
| 737 | ERP-角色详情 | `/superbrowser/rest/v1/erp/per/role/detail` | `companyId`, `roleId` | 角色、权限列表、分组 | 否 | 只读/中 | 官方文档确认 |
| 675 | ERP-修改角色 | `/superbrowser/rest/v1/erp/per/role/edit` | `companyId`, `roleId`, `roleName`, `permissionIds` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 674 | ERP-添加角色 | `/superbrowser/rest/v1/erp/per/role/add` | `companyId`, `roleName`, `permissionIds` | `ret`, `status`, `msg` | 否 | 写入/高 | 官方文档确认 |
| 676 | ERP-权限列表 | `/superbrowser/rest/v1/erp/per/permission/list` | `companyId`, `identityId` | 权限 ID/名称/依赖/分组 | 否 | 只读但安全敏感/中 | 官方文档确认 |
| 628 | ERP-角色列表查询 | `/superbrowser/rest/v1/erp/per/role/list` | `companyId`, `filterKeyword`, `page`, `limit` | 角色、用户、权限、依赖关系 | 是 | 只读/中 | 官方文档确认 |

## 10. 回调与事件

公开文档 `docId=247` 确认以下能力，但没有以独立出站 API 路径公开：

| 能力 | 方向 | 主要字段 | 重试/时效 | 风险 | 确认状态 |
|---|---|---|---|---|---|
| 会员到期通知 | 紫鸟 → ERP | `company_id`, `msg_type=0`, `content` | 失败后 5/15/45 分钟 | 中 | 官方文档确认 |
| 事中监管告警 | 紫鸟 → ERP | 事件、账号、网站、操作、用户、时间 | 同上 | 高 | 官方文档确认 |
| 访问策略申请 | 紫鸟 → ERP | 申请人、店铺、资源类型、URL/DOM/监管信息 | 同上 | 高 | 官方文档确认 |
| 截图证据 | 紫鸟 → ERP | `screenshot_url` | URL 24 小时有效 | 高、可能含敏感页面 | 官方文档确认 |

接收端必须 `POST application/json` 并在 5 秒内返回字符串 `success`。开通要求安全管家剩余时长大于 300 天，实际服务状态需登录核对。

## 11. C 类客户端与本地协议

### 11.1 SSO Schema

| Action | 作用 | 关键字段 | 是否写/高风险 | 确认状态 |
|---|---|---|---|---|
| `OpenStrore` | 打开指定店铺 | `storeId`, `userId`, 可选 `openapiToken`, `lanuchUrl`, `debuggPort` 等 | 启动客户端并进入店铺，高风险 | 官方文档确认 |
| `CloseStrore` | 关闭指定店铺 | `storeId` | 客户端控制 | 官方文档确认 |
| `exit` | 退出紫鸟浏览器 | 无公开业务字段 | 客户端控制 | 官方文档确认 |

官方拼写就是 `OpenStrore/CloseStrore/lanuchUrl/debuggPort`。实现时不能擅自纠正协议字段。

### 11.2 Webdriver 本地 Action

| Action | 作用 | 关键输入/输出 | 风险 | 确认状态 |
|---|---|---|---|---|
| `applyAuth` | 设备授权 | 公司/用户凭据 → 状态码 | 高 | 官方文档确认 |
| `getBrowserList` | 获取店铺列表 | 凭据 → `browserOauth`/店铺列表 | 高敏只读 | 官方文档确认 |
| `startBrowser` | 启动店铺窗口 | 凭据、店铺 → `debuggingPort`, `core_version` | 高 | 官方文档确认 |
| `stopBrowser` | 关闭店铺窗口 | 凭据、店铺 → 状态码 | 高 | 官方文档确认 |
| `logout` | 退出登录 | 无 → 状态码 | 高 | 官方文档确认 |
| `exit` | 退出进程 | 无 → 状态码 | 中 | 官方文档确认 |
| `ClearCache` | 清理本地缓存 | 店铺集合 → 状态码 | 高 | 官方文档确认 |
| `ClearOnline` | 清理在线缓存 | 凭据、店铺、类型 → 状态码 | 高 | 官方文档确认 |
| `getPluginInstalled` | 查询插件安装状态 | 店铺/插件 ID → 安装状态 | 中 | 官方文档确认 |
| `getRunningInfo` | 查询已打开店铺 | 无 → 店铺列表 | 中 | 官方文档确认 |
| `updateCore` | 检测/下载内核 | 凭据 → 进度/状态 | 修改本地环境，高 | 官方文档确认 |

这些 Action 运行在本地紫鸟客户端 HTTP 服务上，不是 A 类云端业务 API；本阶段全部禁止执行。

## 12. 接入决策

### 优先候选（未来单店只读微测试）

1. 获取公司 ID。
2. 员工查询，只保存哈希/脱敏标识。
3. 账号列表查询，只保存店铺 ID、名称、平台、设备 ID、到期时间和标签。
4. 指定用户可访问账号列表。
5. 设备查询和设备历史绑定记录。

### 暂不接入

- 获取用户登录 Token、SSO 打开店铺。
- Webdriver、CLI 自动执行和页面操作。
- 回调截图和监管证据归档。
- 所有账号、设备、员工、角色、授权、访问策略写入。

### 继续走 Naver/Coupang 官方 API

- 商品、选项、库存、订单、客户咨询、物流、广告、销售和结算。
- 紫鸟公开 ERP API 目录没有证明其能提供上述 Naver/Coupang 结构化业务数据。

## 13. ERP-Demo 可复用度

- 可参考：SDK 请求封装、七个已用路径、请求/响应模型、店铺/员工查询流程。
- 不可直接复用：固定 Token 缓存时间、完整请求/响应日志、Token 回传前端、无审批授权写入、无公司/店铺/用户绑定校验。
- 当前项目是 Python/FastAPI/React，Demo 是 Java/RuoYi/Vue；只能复用协议知识，不能复制框架代码。
