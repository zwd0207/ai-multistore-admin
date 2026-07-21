# Phase 5D-1 写操作联调记录

## 本阶段范围

Phase 5D-1 只完成 Store 与 Device Environment 的本地 Codex1 backend 写操作联调：

- Store 新增 / 编辑。
- Device Environment 新增 / 编辑。
- Store 保存后刷新 StoreContext / StoreSelector。
- mock 模式继续保留原新增 / 编辑交互。

本阶段未执行 Credential、Email、mock 同步、真实平台 API、真实邮箱或 AI 调用。

## 对接接口

Codex1 backend base：

```text
http://127.0.0.1:8012/api/v1
```

Store：

- `POST /stores`
- `PUT /stores/{store_id}`

Device Environment：

- `POST /device-environments`
- `PUT /device-environments/{environment_id}`

删除接口本阶段不迁移，backend 模式隐藏删除入口。

## 字段映射

页面继续使用前端字段，Codex1 payload 由 `src/services/adapters.js` 统一转换。

Store payload：

- `name`
- `platform`
- `country`
- `language`
- `status`
- `owner_name`
- `remark`

Device Environment payload：

- `store_id`
- `environment_name`
- `device_type`
- `os_name`
- `browser_name`
- `ip_label`
- `proxy_label`
- `status`
- `last_used_at`
- `remark`

## StoreContext 刷新

`StoreContext` 新增 `refreshStores`。Store 新增 / 编辑成功后刷新全局店铺列表：

- 当前 `selectedStoreId` 仍存在时保持选择。
- 当前 `selectedStoreId` 不存在时回退到第一家店铺。
- 选择结果继续写入 `localStorage`。

## 错误与重复提交处理

- 表单提交中禁用确认和取消按钮，避免重复创建。
- backend 写失败时保留弹窗和非敏感字段输入。
- backend 模式失败不会 fallback 到 mock 成功。
- Store / Device 本阶段不涉及密钥、邮箱认证 token 或密码字段。

## 验证记录

- backend 模式：验证 Store 新增 / 编辑、Device Environment 新增 / 编辑、StoreSelector 刷新。
- mock 模式：验证 13 路由正常，Store / Device 原 mock 交互保留。
- build：通过。
- UTF-8：U+FFFD 扫描为 0。
- 页面/组件 Codex1 snake_case 字段扫描：0。

## 风险点

- 本阶段会写入本地 Codex1 SQLite 开发数据，属于本地联调数据变化。
- Device 与 Environment 共用同一后端 endpoint，两个入口需保持一致。
- 5D-2 Credential / Email 和 5D-3 mock sync 尚未执行。

## Phase 5D-2 - API Credential and Email Account Writes

Phase 5D-2 keeps the formal local integration target:

```text
VITE_API_BASE_URL=http://127.0.0.1:8012/api/v1
VITE_DATA_SOURCE=backend
```

Implemented backend writes:

- API Credential create/update through Codex1 `POST /credentials` and `PUT /credentials/{credential_id}`.
- API Credential disable through `PUT /credentials/{credential_id}` with `status: inactive`.
- Email Account create/update through Codex1 `POST /email-accounts` and `PUT /email-accounts/{email_account_id}`.
- Saves refresh the current `selectedStoreId` list.
- Test connection buttons are local notices only and say that no real platform or mailbox validation was performed.

Still excluded:

- Credential DELETE and Email Account DELETE.
- Real Naver/Coupang connection tests.
- Real Gmail/Naver/Daum/Outlook mailbox connection.
- AI calls.
- Phase 5D-3 mock sync.

Field mapping stays in `src/services/adapters.js`:

- Credential frontend fields map to Codex1 payload fields including `store_id`, `credential_name`, `access_key`, `secret_key`, `platform`, and `status`.
- Email frontend fields map to Codex1 payload fields including `store_id`, `email_address`, `account_label`, `password_or_token`, `provider`, `status`, and `remark`.

Sensitive field rule:

- Backend field names are allowed in service, adapter, and payload mapper code where required by Codex1 contracts.
- Pages, visible labels, notices, and errors do not display plaintext credential values or encrypted backend credential fields.
- Edit forms never prefill sensitive inputs. Leaving a sensitive input blank means it is not updated.
- On save failure, non-sensitive inputs remain and sensitive input state is cleared.
- No complete payload is logged to console.

Verification notes:

- backend mode: Credential create/edit/disable and Email Account create/edit were verified against Codex1 on port 8012.
- mock mode: 13 routes returned 200 on the temporary mock server, and `MockAccounts` / `MockEmails` remained the mock-mode entry points.
- Important Emails remain read-only in this phase.
- Backend write errors were verified with a validation failure and were not converted to mock success.
- build passed with Vite.
- UTF-8 replacement character scan returned 0.
- page/component raw backend sensitive field scan returned 0; service/adapter payload field names remain intentionally present for Codex1 mapping.

## Phase 5D-3 - Local Mock Sync Buttons and Refresh Wiring

Phase 5D-3 adds frontend controls for Codex1 local mock sync only:

- Products: `POST /sync/products/mock`
- Orders: `POST /sync/orders/mock`
- Customer inquiries: `POST /sync/customer-inquiries/mock`

The UI labels every action as local mock sync and states that no real platform is connected. It does not call real Naver or Coupang APIs, real mailboxes, or AI models.

Refresh behavior:

- Product sync refreshes Products, Sync Logs, and Dashboard Summary.
- Order sync refreshes Orders, Sync Logs, Dashboard Summary, and AI Daily Context.
- Customer inquiry sync refreshes Customer Service, Sync Logs, Dashboard Summary, and AI Daily Context.

Platform selection:

- Prefer the selected store platform when it is `naver` or `coupang`.
- If the store platform is not usable, read current-store credential metadata and use an active configured `naver` or `coupang` platform.
- If no platform can be inferred, require the user to choose `naver` or `coupang`.

Failure handling:

- Each sync button has independent loading state.
- Missing store or platform blocks sync with a visible message.
- backend failures are shown as local mock sync errors and never fallback to mock success.
