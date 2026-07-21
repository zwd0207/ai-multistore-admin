> 文档类型：紫鸟集成研究快照
> 研究日期：2026-07-13
> 当前状态：参考资料
> 权威性：不替代 `PROJECT_CONTROL.md`
> 重新核实要求：实际开发或接入前必须重新核对紫鸟官方平台

# 紫鸟开放平台资料来源地图

> 调研日期：2026-07-13（Asia/Shanghai）
> 调研边界：仅公开页面、公开页面加载的数据、公开下载物和本地代码审查；未登录、未调用需凭证接口、未启动店铺、未执行 Skill。

## 1. 确认状态字典

本文档和同目录其他文档只使用以下确认状态：

- 官方文档确认
- ERP-Demo确认但需更新核对
- 页面发现但细节未确认
- 需要登录核对
- 未找到官方依据
- 已废弃或疑似失效

## 2. 实际访问的官方公开入口

| 入口 | 实际读取内容 | 结果 | 确认状态 |
|---|---|---|---|
| <https://open.ziniao.com/> | 首页、解决方案、开放 API、Skill Hub、插件生态、CLI 能力入口 | 可公开访问 | 官方文档确认 |
| <https://open.ziniao.com/skillHubAll> | 6 个分类、121 个 Skill、公开搜索和详情入口 | 可公开访问 | 官方文档确认 |
| `https://open.ziniao.com/skillHubDetail?id={id}` | 逐一读取 121 个 Skill 的公开详情元数据 | 全部详情元数据可读 | 官方文档确认 |
| <https://open.ziniao.com/docSupport?docId=110> | 卖家自研应用接入、企业认证、开发者认证 | 可公开访问 | 官方文档确认 |
| <https://open.ziniao.com/docSupport?docId=140> | 账号管理 API 目录 | 可公开访问 | 官方文档确认 |
| <https://open.ziniao.com/docSupport?docId=145> | `superbrowser://` 打开/关闭店铺与退出客户端 | 可公开访问 | 官方文档确认 |
| <https://open.ziniao.com/ziniaoCli> | CLI 安装、授权、企业管理与浏览器自动化场景 | 可公开访问；未安装、未执行 | 官方文档确认 |
| <https://open.ziniao.com/login> | 手机验证码、密码、紫鸟账号三种登录入口 | 仅查看登录页，未登录 | 需要登录核对 |
| <https://open.ziniao.com/contactUs> | 官方技术支持入口 | 可公开访问 | 官方文档确认 |

浏览器页面实际加载的公开内容接口：

- `GET https://sbappstoreapi.ziniao.com/rest/sop-portal/document/menu/tree`
- `GET https://sbappstoreapi.ziniao.com/rest/sop-portal/document/detail?docId={id}`
- `GET https://sbappstoreapi.ziniao.com/rest/sop-portal/document/api-info?apiId={id}`
- `POST https://sbappstoreapi.ziniao.com/rest/sop-portal/skill/category/list`
- `POST https://sbappstoreapi.ziniao.com/rest/sop-portal/skill/list`
- `POST https://sbappstoreapi.ziniao.com/rest/sop-portal/skill/detail?id={id}`

这些是官网页面内容接口，不是需要商户凭证的业务 OpenAPI。本次未调用 `/openapi-router/...` 下的任何真实业务接口。

## 3. 公开文档目录

公开文档树共读取到 105 个叶子文档。与当前项目最相关的文档如下。

### 3.1 接入与认证

| docId | 文档 | URL | 结论 |
|---:|---|---|---|
| 101 | 平台简介 | <https://open.ziniao.com/docSupport?docId=101> | 卖家自研应用、卖家自研插件、服务商插件三种接入方式 |
| 102 | 应用/插件类型介绍 | <https://open.ziniao.com/docSupport?docId=102> | 企业内部应用不公开上架；插件需审核 |
| 110 | 成为紫鸟开发者 | <https://open.ziniao.com/docSupport?docId=110> | 需企业认证；部分流程需 BOSS |
| 111 | 绑定紫鸟企业账号 | <https://open.ziniao.com/docSupport?docId=111> | 可从紫鸟客户端进入开放平台控制台 |
| 85 | 创建应用 | <https://open.ziniao.com/docSupport?docId=85> | 可选简单通用模式或复杂鉴权模式 |
| 113 | 申请接口权限 | <https://open.ziniao.com/docSupport?docId=113> | 按接口申请权限；具体授权结果需登录核对 |
| 114 | 开发测试 | <https://open.ziniao.com/docSupport?docId=114> | 需 IP 白名单；列出应用 Token、公司、员工、店铺基础链路 |
| 233 | 简单通用模式（推荐） | <https://open.ziniao.com/docSupport?docId=233> | Bearer API Key；基址为 `/openapi-router` |
| 191 | 简单通用模式 | <https://open.ziniao.com/docSupport?docId=191> | 同上，含请求示例 |
| 192 | 复杂鉴权模式 | <https://open.ziniao.com/docSupport?docId=192> | App ID、RSA2、App Token、IP 白名单和 SDK |
| 136 | 其他语言 HTTP 说明 | <https://open.ziniao.com/docSupport?docId=136> | 公共参数、时间戳误差 5 分钟、RSA2 签名 |

### 3.2 SDK

| docId | 文档 | 当前公开下载信息 |
|---:|---|---|
| 129 | SDK 使用下载 | Java `sdk-java-5.0.6.jar`；Python/Node/PHP/C#/Go 压缩包 |
| 130 | Java 示例 | App Token、CommonRequest、App Token 调用 |
| 131 | Python 示例 | BaseRequest、App Token、业务接口调用 |
| 132 | Node.js 示例 | OpenClient、请求类型、App Token |
| 133 | PHP 示例 | BaseRequest 与 App Token |
| 134 | C# 示例 | OpenClient 与公共响应 |
| 135 | Go 示例 | OpenClient 与请求模型 |

### 3.3 紫鸟浏览器 API

| docId | 分组 | 当前目录条目数 |
|---:|---|---:|
| 155 | 获取紫鸟公司 ID | 1 |
| 140 | 账号管理 | 24 |
| 156 | 设备管理 | 11 |
| 141 | 部门员工 | 10 |
| 142 | 访问策略 | 22 |
| 146 | 角色和权限 | 7 |
| 247 | 消息推送回调配置 | 回调文档，不以 API 列表呈现 |
| 143 | SSO 时序图 | SSO 流程和 ERP-Demo 下载 |
| 144 | SSO 服务端接口 | 6 条引用，其中 3 条为基础/SSO 专用，其余复用员工和店铺 API |
| 145 | 打开紫鸟 | 3 个 Schema Action |
| 147 / 98 | Webdriver/CDP | 11 个本地 Action、框架和客户端要求 |

五个 ERP 核心分组当前共有 74 条目录记录、73 个唯一 API ID。`ERP-解绑设备` 同时出现在账号和设备分组。Skill `卖家自研 ERP 对接` 仍写“72 个接口”，与当前公开目录不一致。

### 3.4 回调、规则、CLI 和自动化

| docId | 文档 | 关键事实 |
|---:|---|---|
| 247 | 消息推送回调配置 | POST JSON；5 秒内返回 `success`；失败后 5/15/45 分钟重试；截图 URL 24 小时有效；安全管家剩余时长需大于 300 天 |
| 91 | 开发须知 | 最小权限、隐私、安全和插件审核规则 |
| 53 | 开发者协议 | 数据保护、合法使用、审核和开发者责任 |
| 83 | FAQ | 环境隔离、专业版限制、SiteId 附件入口 |
| 99 | Webdriver 权限开通 | BOSS 开启；建议专用自动化账号；需查看账号权限 |
| 98 / 147 | Webdriver 自动化 | 本地 HTTP、店铺启动、调试端口、Selenium/Playwright 等；不等同平台结构化 API |
| 267 | AI 辅助 Webdriver 开发 | Skill 主要用于查文档；真正执行仍在本机客户端和脚本 |
| 281 | 紫鸟 CLI 操作指南 | Node.js 16+、CLI 应用授权、成员应用需 BOSS 审核、终端管理 |
| 195 | MCP 服务说明 | MCP 市场接入说明；具体服务和凭证需登录核对 |

## 4. SkillHub 来源和限制

- 公开分类：选品与开发、产品视觉、产品运营、营销广告、数据分析、通用/热点。
- 公开 Skill 总数：121。
- 公开详情元数据：121/121 可读取。
- 详情页内直接包含 Markdown 契约：18 个，主要为 Temu 系列。
- 公开 Skill 包成功读取：47 个。
- 公开 Skill 包无法读取：74 个，下载地址位于 `https://test-agent-files-sz.linkfox.com/skills/...`，返回 HTTP 403。
- `cdn-superbrowser-attachment.ziniao.com` 上的 4 个紫鸟核心包可读：ID 118、119、120、121。
- 未发现名称或公开说明明确对应 Naver SmartStore 或 Coupang 的 Skill。

无法读取的 74 个准确 URL（均返回 HTTP 403）：

- ID 1 Ozon-商品详情: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-product-detail/linkfox-mpstats-ozon-product-detail-2.0.0.zip>
- ID 2 Google AI Mode: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ai-mode-google-search/linkfox-ai-mode-google-search-2.0.0.zip>
- ID 36 1688-以图搜图: <https://test-agent-files-sz.linkfox.com/skills/linkfox-1688-search-by-image/linkfox-1688-search-by-image-2.0.0.zip>
- ID 37 智慧芽-专利PDF全文下载: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-pdf-data/linkfox-zhihuiya-pdf-data-2.0.0.zip>
- ID 38 智慧芽-专利引用查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-patent-forward-citation/linkfox-zhihuiya-patent-forward-citation-2.0.0.zip>
- ID 39 智慧芽-专利家族查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-patent-family/linkfox-zhihuiya-patent-family-2.0.0.zip>
- ID 40 智慧芽-专利法律状态查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-legal-status/linkfox-zhihuiya-legal-status-2.0.0.zip>
- ID 41 智慧芽-专利说明书翻译: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-description-data-translated/linkfox-zhihuiya-description-data-translated-2.0.0.zip>
- ID 42 智慧芽-专利说明书查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-description-data/linkfox-zhihuiya-description-data-2.0.0.zip>
- ID 43 智慧芽-专利著录项目查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-bibliography/linkfox-zhihuiya-bibliography-2.0.0.zip>
- ID 44 卖家精灵-市场统计分析: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sellersprite-market-statistics/linkfox-sellersprite-market-statistics-2.0.0.zip>
- ID 45 商品库-更新变体: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-variant-update/linkfox-product-center-variant-update-1.0.0.zip>
- ID 46 商品库-变体链接管理: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-variant-listings/linkfox-product-center-variant-listings-1.0.0.zip>
- ID 47 商品库-变体详情: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-variant-detail/linkfox-product-center-variant-detail-1.0.0.zip>
- ID 48 商品库-创建变体: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-variant-create/linkfox-product-center-variant-create-1.0.0.zip>
- ID 49 商品库-更新Listing信息: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-listing-update/linkfox-product-center-listing-update-1.0.0.zip>
- ID 50 商品库-Listing详情: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-listing-detail/linkfox-product-center-listing-detail-1.0.0.zip>
- ID 51 商品库-创建 Listing: <https://test-agent-files-sz.linkfox.com/skills/linkfox-product-center-listing-create/linkfox-product-center-listing-create-1.0.0.zip>
- ID 52 Ozon-卖家商品: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-seller-products/linkfox-mpstats-ozon-seller-products-2.0.0.zip>
- ID 53 Ozon-商品分日表现分析: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-product-trend/linkfox-mpstats-ozon-product-trend-2.0.0.zip>
- ID 54 Ozon-商品搜索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-product-search/linkfox-mpstats-ozon-product-search-2.0.0.zip>
- ID 55 Ozon-类目商品分析: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-category-products/linkfox-mpstats-ozon-category-products-2.0.0.zip>
- ID 56 Ozon-品牌商品分析: <https://test-agent-files-sz.linkfox.com/skills/linkfox-mpstats-ozon-brand-products/linkfox-mpstats-ozon-brand-products-2.0.0.zip>
- ID 57 亚马逊-Listing全能生成器: <https://test-agent-files-sz.linkfox.com/skills/linkfox-listing-master-test/linkfox-listing-master-test-3.0.0.zip>
- ID 58 Keepa-亚马逊-价格历史: <https://test-agent-files-sz.linkfox.com/skills/linkfox-keepa-product-series/linkfox-keepa-product-series-2.0.0.zip>
- ID 60 亚马逊-商品评论抓取: <https://test-agent-files-sz.linkfox.com/skills/linkfox-amazon-reviews-list/linkfox-amazon-reviews-list-2.0.0.zip>
- ID 62 亚马逊-商业洞察反向选品: <https://test-agent-files-sz.linkfox.com/skills/linkfox-amazon-opportunity-search-by-metrics/linkfox-amazon-opportunity-search-by-metrics-2.0.0.zip>
- ID 63 亚马逊-Alexa助手: <https://test-agent-files-sz.linkfox.com/skills/linkfox-amazon-alexa-search/linkfox-amazon-alexa-search-2.0.0.zip>
- ID 64 亚马逊-ABA数据挖掘: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aba-intelligent-query/linkfox-aba-intelligent-query-2.0.0.zip>
- ID 65 智慧芽-简单著录项: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-simple-bibliography/linkfox-zhihuiya-simple-bibliography-2.0.0.zip>
- ID 66 智慧芽-专利图像检索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-patent-image-search/linkfox-zhihuiya-patent-image-search-2.0.0.zip>
- ID 67 智慧芽-专利被引用: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-patent-cited/linkfox-zhihuiya-patent-cited-2.0.0.zip>
- ID 68 智慧芽-全文附图: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-fulltext-image/linkfox-zhihuiya-fulltext-image-2.0.0.zip>
- ID 69 智慧芽-权利要求翻译: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-claim-data-translated/linkfox-zhihuiya-claim-data-translated-2.0.0.zip>
- ID 70 智慧芽-权利要求查询: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-claim-data/linkfox-zhihuiya-claim-data-2.0.0.zip>
- ID 71 智慧芽-摘要附图: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-abstract-image/linkfox-zhihuiya-abstract-image-2.0.0.zip>
- ID 72 智慧芽-摘要翻译: <https://test-agent-files-sz.linkfox.com/skills/linkfox-zhihuiya-abstract-data-translated/linkfox-zhihuiya-abstract-data-translated-2.0.0.zip>
- ID 73 友鹰-Shopee 商品选品: <https://test-agent-files-sz.linkfox.com/skills/linkfox-youying-shopee-get-product-infos/linkfox-youying-shopee-get-product-infos-2.0.0.zip>
- ID 74 沃尔玛商品搜索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-walmart-search/linkfox-walmart-search-2.0.0.zip>
- ID 75 WallySmarter-沃尔玛商品详情: <https://test-agent-files-sz.linkfox.com/skills/linkfox-wallysmarter-product-detail/linkfox-wallysmarter-product-detail-2.0.0.zip>
- ID 76 网页检索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-tsearch-search/linkfox-tsearch-search-2.0.0.zip>
- ID 77 Sorftime-亚马逊产品搜索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sorftime-amazon-product-query/linkfox-sorftime-amazon-product-query-2.0.0.zip>
- ID 78 Sorftime-亚马逊产品详情（含趋势）: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sorftime-amazon-product-detail/linkfox-sorftime-amazon-product-detail-2.0.0.zip>
- ID 79 SIF-关键词流量来源: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sif-keyword-summary/linkfox-sif-keyword-summary-2.0.0.zip>
- ID 83 卖家精灵-关键词反查(流量词列表): <https://test-agent-files-sz.linkfox.com/skills/linkfox-sellersprite-traffic-keyword/linkfox-sellersprite-traffic-keyword-2.0.0.zip>
- ID 85 卖家精灵-选市场列表: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sellersprite-market-research/linkfox-sellersprite-market-research-2.0.0.zip>
- ID 86 卖家精灵-查竞品: <https://test-agent-files-sz.linkfox.com/skills/linkfox-sellersprite-competitor-lookup/linkfox-sellersprite-competitor-lookup-2.0.0.zip>
- ID 87 睿观-发明专利检测: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-utility-patent-detection/linkfox-ruiguan-utility-patent-detection-2.0.0.zip>
- ID 88 睿观-图形商标检测: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-trademark-graphic-detection/linkfox-ruiguan-trademark-graphic-detection-2.0.0.zip>
- ID 89 睿观-文本商标检测: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-text-trademark-detection/linkfox-ruiguan-text-trademark-detection-2.0.0.zip>
- ID 90 睿观-政策合规检测（纯图检测）: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-gun-parts-search/linkfox-ruiguan-gun-parts-search-2.0.0.zip>
- ID 91 睿观-外观专利检测: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-detection-patent-design/linkfox-ruiguan-detection-patent-design-2.0.0.zip>
- ID 92 睿观-版权检测: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ruiguan-copyright-detection/linkfox-ruiguan-copyright-detection-2.0.0.zip>
- ID 94 Keepa-亚马逊-商品详情: <https://test-agent-files-sz.linkfox.com/skills/linkfox-keepa-product-request/linkfox-keepa-product-request-2.0.0.zip>
- ID 96 极目-亚马逊-产品挖掘（按 ASIN）: <https://test-agent-files-sz.linkfox.com/skills/linkfox-jiimore-page-asins-by-asin/linkfox-jiimore-page-asins-by-asin-2.0.0.zip>
- ID 97 极目-亚马逊-细分市场评论: <https://test-agent-files-sz.linkfox.com/skills/linkfox-jiimore-get-niche-review-from-keyword/linkfox-jiimore-get-niche-review-from-keyword-2.0.0.zip>
- ID 98 极目-亚马逊-细分市场信息: <https://test-agent-files-sz.linkfox.com/skills/linkfox-jiimore-get-niche-info-by-keyword/linkfox-jiimore-get-niche-info-by-keyword-2.0.0.zip>
- ID 99 极目-亚马逊-细分市场洞察信息: <https://test-agent-files-sz.linkfox.com/skills/linkfox-jiimore-get-niche-info/linkfox-jiimore-get-niche-info-2.0.0.zip>
- ID 100 多平台竞品侦察: <https://test-agent-files-sz.linkfox.com/skills/linkfox-image-competitor-scout/linkfox-image-competitor-scout-1.0.0.zip>
- ID 101 谷歌趋势-时下流行: <https://test-agent-files-sz.linkfox.com/skills/linkfox-google-trend-get-trend-by-time/linkfox-google-trend-get-trend-by-time-2.0.0.zip>
- ID 102 谷歌趋势-关键词趋势信息: <https://test-agent-files-sz.linkfox.com/skills/linkfox-google-trend-get-trend-by-keys/linkfox-google-trend-get-trend-by-keys-2.0.0.zip>
- ID 103 FastMoss-TikTok 商品搜索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-fastmoss-product-search/linkfox-fastmoss-product-search-2.0.0.zip>
- ID 104 FastMoss-TikTok热销榜单: <https://test-agent-files-sz.linkfox.com/skills/linkfox-fastmoss-product-rank-top-selling/linkfox-fastmoss-product-rank-top-selling-2.0.0.zip>
- ID 105 EchoTik-TikTok 商品搜索: <https://test-agent-files-sz.linkfox.com/skills/linkfox-echotik-list-product/linkfox-echotik-list-product-2.0.0.zip>
- ID 106 EchoTik-TikTok 新品榜: <https://test-agent-files-sz.linkfox.com/skills/linkfox-echotik-list-new-product-rank/linkfox-echotik-list-new-product-rank-2.0.0.zip>
- ID 109 亚马逊-商业洞察报告（按关键词）: <https://test-agent-files-sz.linkfox.com/skills/linkfox-amazon-opportunity-report-by-keyword/linkfox-amazon-opportunity-report-by-keyword-2.0.0.zip>
- ID 110 多参考图生视频: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-videogen-multi/linkfox-aigc-videogen-multi-1.0.0.zip>
- ID 111 Aigc Videogen: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-videogen/linkfox-aigc-videogen-1.0.0.zip>
- ID 112 AI 生文: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-textgen/linkfox-aigc-textgen-2.0.0.zip>
- ID 113 商品图生成: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-imagegen-product/linkfox-aigc-imagegen-product-1.0.0.zip>
- ID 114 服饰图生成: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-imagegen-cloth/linkfox-aigc-imagegen-cloth-1.0.0.zip>
- ID 115 品牌基因样式提取: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-imagegen-brand-gene-extract/linkfox-aigc-imagegen-brand-gene-extract-1.0.0.zip>
- ID 116 AI 生图: <https://test-agent-files-sz.linkfox.com/skills/linkfox-aigc-imagegen/linkfox-aigc-imagegen-2.0.0.zip>
- ID 117 Google AI Mode: <https://test-agent-files-sz.linkfox.com/skills/linkfox-ai-model-google-search/linkfox-ai-model-google-search-2.0.0.zip>

## 5. 需要登录但未访问的页面

| 页面/功能 | 公开入口 | 未访问原因 | 人工需核对内容 |
|---|---|---|---|
| 开发者控制台 | <https://open.ziniao.com/login> | 需要真实账号登录 | 企业绑定、应用状态、审核状态 |
| 应用概览 | 登录后“应用管理 → 设置” | 需要登录和应用权限 | 鉴权模式、API Key 是否已生成、应用状态 |
| 接口权限申请结果 | 登录后“应用概览 → 接口权限” | 需要登录 | 已申请/已批准权限点、审批范围 |
| 安全中心/IP 白名单 | 登录后“应用概览 → 安全中心” | 需要登录 | IP 白名单、是否支持多 IP、变更审批 |
| 接口和调试工具 | 登录后“应用概览 → 接口和调试工具” | 需要登录 | 频率限制、错误码、测试环境、调试数据 |
| SSO 权限 | 同上 | `user-login` 文档提示需客服/BOSS 验证 | 是否批准、适用用户范围、Token 生命周期 |
| 回调配置 | 登录后“设置 → 消息推送回调配置” | 需要登录且依赖安全管家 | 回调 URL、服务剩余天数、事件权限 |
| Webdriver 状态 | 控制台首页“自动化/通讯录同步” | BOSS 权限 | 是否已开通、允许账号、客户端版本 |
| CLI 应用与终端管理 | 登录后“用户应用管理 → CLI 应用 → 设置 → 终端管理” | 需要登录 | 应用审核、权限、终端识别码绑定 |

## 6. ERP-Demo 来源

原始压缩包：

- `<local-research-source>/ERP-Demo.zip`

只读审查目录：

- `<local-research-source>/ziniao-erp-demo-review`

实际读取的核心文件：

- `README.md`
- `ruoyi-admin/pom.xml`
- `ruoyi-admin/lib/sdk-java-5.1.0.jar`
- `ruoyi-admin/src/main/java/com/ruoyi/web/core/config/OpenApiConfig.java`
- `ruoyi-admin/src/main/java/com/ruoyi/web/service/OpenApiService.java`
- `ruoyi-admin/src/main/java/com/ruoyi/web/service/CacheService.java`
- `ruoyi-admin/src/main/java/com/ruoyi/web/controller/ziniao/StoreManageController.java`
- `ruoyi-admin/src/main/java/com/ruoyi/web/controller/ziniao/StaffManageController.java`
- `ruoyi-ui/src/api/ziniao/store.js`
- `ruoyi-ui/src/api/ziniao/user.js`
- `ruoyi-ui/src/views/store/index.vue`
- `sql/ry_20240629.sql`

## 7. 当前系统来源

当前分支：`integration/operator-v1-preview`，调研前 HEAD：`de94cec`。

实际审查范围包括：

- `backend/app/models/` 中的 Store、DeviceEnvironment、PlatformLoginCredential、ApiCredential、Product、Order、CustomerInquiry、Email、SyncLog、SyncCheckpoint、ApiCapability、操作审计、认证与店铺成员关系。
- `backend/app/services/` 中的店铺、设备、凭证、平台登录、同步、能力检测、操作审计、Naver/Coupang 适配与工作台聚合。
- `backend/app/api/v1/endpoints/` 中的 stores、credentials、device_environments、dashboard、sync、orders、products、customer inquiries 等现有路由。
- `src/pages/`、`src/services/`、`src/context/` 中的店铺、账号、设备、工作台、订单、咨询和同步状态页面/适配器。
- 现有专项验证脚本和 `verify_all.py`。

全工作区未发现 `ziniao`、`紫鸟` 或 `superbrowser` 的既有生产实现。

## 8. 明确未取得的官方依据

- ERP OpenAPI 的统一 QPS、日配额和每接口限流规则。
- ERP OpenAPI 的公开完整错误码表；公开 API 详情的 `responseStatusCodes` 均为空。
- 正式沙箱与生产环境是否物理隔离。
- API/字段版本变更、弃用和迁移公告的统一公开入口。
- 74 个返回 403 的 Skill 包内部输入输出契约。
- Naver SmartStore 或 Coupang 专用 Skill。
- 紫鸟是否提供 Naver/Coupang 商品、订单、客服、广告、结算的正式结构化 API。

这些事项均不得据接口名称或页面营销文案推断。
