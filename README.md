# AI 多店铺运营与环境管理系统（Codex2）

React + Vite 后台前端，已完成 13 个业务路由、第一至第四阶段页面，以及第五阶段 A 的 Codex1 后端接口适配准备。默认继续使用本地 mock 数据，切换后端数据源不会要求重写页面字段。

## 环境要求

- Node.js 18 或更高版本
- npm 9 或更高版本
- 正式联调时启动 Codex1 FastAPI 后端

## 安装、启动与构建

```bash
npm install
npm run dev
```

开发地址通常为 `http://localhost:5173`。

```bash
npm run build
npm run preview
```

## 数据源配置

Codex1 本地接口：`http://127.0.0.1:8000/api/v1`

Swagger：`http://127.0.0.1:8000/docs`

在本机创建不提交 Git 的 `.env.local`，按需要设置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_DATA_SOURCE=mock
```

`VITE_DATA_SOURCE` 可选值：

- `mock`：默认值，所有已完成页面继续使用本地 Promise mock 接口。
- `backend`：Dashboard Summary 等已适配接口读取 Codex1；尚未正式迁移的页面能力仍保留 mock 实现。

修改环境变量后需要重新启动 Vite。需要调用商品、订单、客服咨询、设备环境、邮箱或申诉列表时，应提供 Codex1 合同要求的 `store_id`（前端也接受 `storeId` 并自动转换）。

## 服务层职责

- `src/services/mockApi.js`：第一至第四阶段的稳定 mock 数据源，保留完整查询和前端交互能力。
- `src/services/http.js`：统一 base URL、查询参数、JSON、超时、Token 预留及脱敏错误处理。
- `src/services/backendApi.js`：严格封装 Codex1 `/api/v1` 合同与统一响应格式。
- `src/services/adapters.js`：将 Codex1 snake_case 字段转换为现有页面字段。
- `src/services/dataProvider.js`：根据 `VITE_DATA_SOURCE` 选择数据源，页面无需散落数据源判断。

## 项目结构

```text
src/
├── components/common/  通用页面、表格、弹窗、表单与状态组件
├── data/               UTF-8 中韩文 mock 数据
├── layouts/            后台管理布局
├── pages/              13 个业务页面
├── routes/             集中路由配置
├── services/           mock、HTTP、Codex1 API、adapter 与 provider
└── styles/             全局及布局样式
```

## 本地自用敏感字段规则

本地业务页面允许展示运营地址、运营 IP、设备环境标签和明确标记为测试数据的手机号。真实客户数据仍应使用脱敏显示。

前端、mock、README、阶段文档及 Git 中不得写入或显示平台密钥、邮箱凭证、代理凭证、远程桌面凭证、银行卡号、身份证号或真实商家后台登录凭证。凭证页面只能展示“已配置/未配置”、到期时间、绑定状态和最后验证时间。HTTP 错误对象会按字段名隐藏凭证类值，也不会将请求或响应写入控制台。

本阶段不连接真实 Naver/Coupang API，不读取或发送真实邮件，也不调用 OpenAI、DeepSeek 或其他模型。

## 编码

HTML 明确声明 UTF-8，源码文件均以 UTF-8 保存。字体栈包含 `Microsoft YaHei`、`Noto Sans KR` 和 `Malgun Gothic`，用于兼容中文与韩文。
