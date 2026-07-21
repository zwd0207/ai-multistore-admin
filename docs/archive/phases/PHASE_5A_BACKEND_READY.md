# 第五阶段 A：Codex1 后端联调准备完成说明

## 1. 新增或修改文件

- 新增 `src/services/backendApi.js`
- 新增 `src/services/adapters.js`
- 新增 `src/services/dataProvider.js`
- 修改 `src/services/http.js`
- 修改 `src/pages/Dashboard.jsx`
- 修改 `.gitignore`
- 修改 `README.md`
- 新增 `PHASE_5A_BACKEND_READY.md`

放入项目目录的 `codex1/` 仅作为接口合同与本地联调参考，保留其独立 Git 历史，不纳入 Codex2 前端提交。

## 2. 后端 base URL

`http.js` 默认 base URL 已从 `/api` 修正为 `http://127.0.0.1:8000/api/v1`，并支持 `VITE_API_BASE_URL` 覆盖。路径尾部斜杠、查询参数、请求超时、网络失败和统一错误对象均已处理。

## 3. backendApi 实现

已按 Codex1 合同封装 health、stores、dashboard summary、AI daily context、products、orders、customer inquiries、sync logs、device environments、email accounts、important emails、appeal cases。所有方法解析 `{ success, message, data }`，失败时抛出包含状态和错误码的可读错误，不输出请求体、响应体或凭证。

## 4. adapters 字段映射

已完成 Store、Product、Order、CustomerInquiry、SyncLog、DeviceEnvironment、EmailAccount、ImportantEmail、AppealCase 和 Dashboard 映射。Dashboard 会生成现有卡片字段、风险列表、客服待办、同步/订单最近动态；AI Daily Context 也提供 camelCase 映射。分页响应统一为 `items/total/page/pageSize`。

为保持已完成页面兼容，部分对象同时提供语义相同的现有别名，例如 `email/address`、`customer/customerName`、`subject/title`。

## 5. dataProvider 数据源切换

默认 `VITE_DATA_SOURCE=mock`，现有 mock 交互不变。设置为 `backend` 后，Dashboard Summary 通过 `backendApi + adapters` 获取；其他已封装列表已具备切换方法，但本阶段没有批量替换第一至第四阶段页面。未迁移的交互继续回退到 mock。

Dashboard 已从直接调用 `mockApi` 改为调用 `dataProvider`，是本阶段的最小真实接入点。

## 6. 本地自用敏感字段规则

允许运营地址、运营 IP、设备环境和本地测试手机号用于本地业务展示。前端不展示或写入平台密钥、邮箱凭证、代理凭证、远程桌面凭证、银行卡号、身份证号或真实商家登录凭证。凭证状态仅使用布尔状态和验证时间等非秘密字段。

HTTP 与 backendApi 错误处理会递归隐藏凭证类字段，不写控制台。`mockData.js`、README 和阶段文档的敏感值扫描结果为 0。

## 7. Codex1 healthCheck 联调结果

Codex1 复制来的虚拟环境引用原电脑 Python 路径，已使用本机 Python 3.13 在被 Git 忽略的 Codex1 副本内重建并安装锁定依赖。由于本机 `8000` 端口已由另一套 FastAPI 服务占用，未擅自终止该服务；Codex1 临时运行于隔离端口 `8011`，通过 Vite 临时环境变量实际调用 `backendApi.healthCheck()`，结果为 `status=ok`、`environment=development`、`api_version=v1`。

正式使用默认地址前，需要先释放 `8000` 端口并启动 Codex1，或在本机 `.env.local` 中配置实际 Codex1 地址。

## 8. Dashboard Summary 准备情况

已通过同一临时 Codex1 实例实际调用 `backendApi.getDashboardSummary()` 并经 Dashboard adapter 转换。测试库返回 1 个店铺，字段类型与页面预期一致。默认 mock 模式 Dashboard 也通过运行级检查。

## 9. 页面回归结果

第一至第四阶段组件和业务页未被删除或重写。Dashboard 只修改了数据入口与错误提示，其余页面仍使用原 mockApi。默认 mock provider 运行验证通过，返回 7 个店铺。

## 10. 构建结果

`npm install` 可执行，`npm run build` 通过。

## 11. UTF-8 扫描

源码、配置、README 与阶段文档通过严格 UTF-8 解码检查；Unicode 替换字符 `U+FFFD` 扫描结果为 0。

## 12. 13 个路由检查

以下路由经 Vite 开发服务器逐一请求，全部返回 HTTP 200：

- `/dashboard`
- `/stores`
- `/products`
- `/orders`
- `/customer-service`
- `/sales`
- `/devices`
- `/emails`
- `/appeals`
- `/environment`
- `/accounts`
- `/settings`
- `/logs`

检查结果：13/13 通过。

## 13. 对前四阶段的影响

未影响第一至第四阶段已完成页面；mockApi 和 mockData 均保留，默认数据源仍为 mock。

## 14. 尚未完成的正式联调项

- 尚未将店铺、商品、订单、客服、设备、邮箱和申诉页面整体切换到后端数据源。
- Codex1 当前没有配置浏览器 CORS 来源；前后端分端口直接访问前，需要 Codex1/合并工程增加允许的本地前端来源，或使用同源反向代理。
- 商品、订单、客服咨询及运营支持列表需要在页面接入全局店铺选择器后传入 `store_id`。
- 本阶段未连接真实平台、真实邮箱或任何大模型。

## 15. Codex3 合并前注意事项

- 以后端 Swagger、`API_CONTRACT.md` 和 `CODEX2_FRONTEND_HANDOFF.md` 为准，不新造路径。
- 保留 adapters 边界，不把 snake_case 兼容逻辑散落到页面。
- 合并时不要提交本地环境变量、数据库、虚拟环境或 Codex1 参考副本。
- 正式切换前先解决端口与 CORS，再逐页迁移并保留 mock 回退策略。
