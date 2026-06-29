# Phase 5C Store Context 正式联调记录

## 新增或修改文件清单

- `src/context/StoreContext.jsx`：新增全局店铺上下文。
- `src/components/common/StoreSelector.jsx`：新增全局店铺选择器。
- `src/components/common/BackendReadOnlyPage.jsx`：新增后端只读列表页通用组件。
- `src/components/common/ResourcePage.jsx`：支持 `extraParams` 和 `reloadKey`，用于显式传递 `selectedStoreId`。
- `src/App.jsx`：在路由外层接入 `StoreProvider`。
- `src/layouts/AdminLayout.jsx`：顶部工具区接入 `StoreSelector`。
- `src/styles/global.css`：新增 StoreSelector 样式。
- `src/services/backendApi.js`：新增 remaining read-only endpoints。
- `src/services/dataProvider.js`：统一按 `selectedStoreId` 读取后端数据。
- `src/services/adapters.js`：新增 device/email/appeal/credential 字段映射。
- `src/pages/Dashboard.jsx`、`Products.jsx`、`Orders.jsx`、`CustomerService.jsx`、`Logs.jsx`：Phase 5B 接口显式接入 `selectedStoreId`。
- `src/pages/Devices.jsx`、`Environment.jsx`、`Emails.jsx`、`Appeals.jsx`、`Accounts.jsx`：迁移剩余只读模块。
- `README.md`：追加 Phase 5C 运行和联调说明。

## StoreContext / StoreSelector 实现说明

`StoreContext` 提供：

- `stores`
- `selectedStore`
- `selectedStoreId`
- `setSelectedStoreId`
- `loading`
- `error`

backend 模式启动时通过 `GET /api/v1/stores` 获取店铺列表。默认店铺优先读取 `localStorage` 中的 `codex2.selectedStoreId`，没有可用缓存时使用后端返回的第一家店铺；没有店铺时页面显示空状态，不白屏。

mock 模式也通过同一套 context 读取 mock 店铺列表，保证 StoreSelector 和原有页面可继续使用。

`StoreSelector` 放在主布局顶部，支持 1 个或多个店铺正常显示和切换；无店铺时显示“暂无店铺数据”。

## selectedStoreId 传递规则

所有后端读取接口在页面层显式使用 `selectedStoreId`，并通过 `dataProvider` 转换为后端 `store_id` 查询参数。页面 JSX 不直接使用 Codex1 snake_case 原始字段。

切换店铺后：

- `StoreContext` 写入 `localStorage`。
- 依赖 `selectedStoreId` 的页面重新读取数据。
- `ResourcePage` 使用 `reloadKey` 和稳定的 `extraParams` 触发刷新。
- `BackendReadOnlyPage` 直接以 `{ storeId: selectedStoreId }` 调用读取函数。

## 已修正的 Phase 5B 接口

- Dashboard：`GET /api/v1/dashboard/summary?store_id={selectedStoreId}`
- Products：`GET /api/v1/products?store_id={selectedStoreId}`
- Orders：`GET /api/v1/orders?store_id={selectedStoreId}`
- Customer Service：`GET /api/v1/customer-inquiries?store_id={selectedStoreId}`
- Sync Logs：`GET /api/v1/sync-logs?store_id={selectedStoreId}`
- AI Daily Context：`GET /api/v1/ai/daily-context?store_id={selectedStoreId}`

Stores 页面继续读取全店铺列表，不强制传 `store_id`。

## 新增迁移的剩余只读模块

- Devices：`GET /api/v1/device-environments?store_id={selectedStoreId}`
- Environment：复用 `GET /api/v1/device-environments?store_id={selectedStoreId}`
- Emails：`GET /api/v1/email-accounts?store_id={selectedStoreId}`
- Important Emails：`GET /api/v1/important-emails?store_id={selectedStoreId}`
- Appeals：`GET /api/v1/appeal-cases?store_id={selectedStoreId}`
- Accounts / Credentials：`GET /api/v1/credentials?store_id={selectedStoreId}`

Credentials 只展示“已配置 / 未配置”等状态，不展示任何密钥原文或后端加密字段。

## mock 模式验证结果

使用临时 Vite 服务 `http://127.0.0.1:5174`，环境变量：

```text
VITE_API_BASE_URL=http://127.0.0.1:8012/api/v1
VITE_DATA_SOURCE=mock
```

13 个路由均可访问并渲染。Dashboard、Stores、Products、Orders、Customer Service、Sales、Devices、Emails、Appeals、Environment、Accounts、Settings、Logs 均未白屏。StoreSelector 在 mock 模式可显示 mock 店铺并可切换。

## backend 模式验证结果

使用当前正式联调环境：

```text
VITE_API_BASE_URL=http://127.0.0.1:8012/api/v1
VITE_DATA_SOURCE=backend
```

后端 `8012` health 正常，Swagger 可访问。前端 `5173` 正常启动。13 个路由均可访问并渲染。Dashboard 读取 Codex1 summary，Products、Orders、Customer Service、Logs、AI Daily Context 继续读取 Codex1 数据并显式传入当前店铺。

新增只读模块验证结果：

- Devices：读取 device-environments 成功。
- Environment：复用 device-environments 成功。
- Emails：读取 email-accounts / important-emails 成功。
- Appeals：读取 appeal-cases 成功。
- Accounts：读取 credentials 成功，仅展示配置状态。

## 空状态和错误处理结果

- 后端店铺为空时，依赖店铺的页面显示空状态，不白屏。
- 店铺列表或业务接口失败时，页面显示错误空状态。
- HTTP 错误对象继续经过 `http.js` 脱敏处理。

## 构建结果

`npm run build` 等价命令已通过：

```text
vite build: passed
```

## UTF-8 检查结果

U+FFFD 替换字符扫描结果：

```text
TOTAL 0
```

## 13 个路由访问结果

- `/dashboard`：200，正常渲染。
- `/stores`：200，正常渲染。
- `/products`：200，正常渲染。
- `/orders`：200，正常渲染。
- `/customer-service`：200，正常渲染。
- `/sales`：200，正常渲染。
- `/devices`：200，正常渲染。
- `/emails`：200，正常渲染。
- `/appeals`：200，正常渲染。
- `/environment`：200，正常渲染。
- `/accounts`：200，正常渲染。
- `/settings`：200，正常渲染。
- `/logs`：200，正常渲染。

## 当前风险点

- backend 模式本阶段仍为只读，不迁移新增、编辑、删除或回复操作。
- mock 模式为了保持原有可用性，仍保留 mockApi 和部分 mock 交互。
- 浏览器日志工具会返回历史 console 日志，最终回归以页面渲染、接口数据、构建和静态扫描结果为准。
- 后续如果 Codex1 新增多店铺测试数据，需要补充切换不同店铺后的数据差异验证。

## 是否可以进入第三轮正式联调

可以进入第三轮正式联调。Phase 5C 已完成全局店铺上下文、StoreSelector、Phase 5B 接口 store scope 修正，以及剩余只读模块迁移。
