# Coupang Real API Phase 6C

## 1. 当前正式店铺与凭证状态

当前本地真实联调使用以下正式绑定：

- `store_id=7`
- `store.name=陈美抛`
- `platform=coupang`
- `active credential_id=6`
- `vendor_id=A01223021`

说明：

- 文档不记录 `access key` 或 `secret key` 原文。
- 历史测试凭证与旧正式凭证仍保留在本地数据库中，但当前正式 active 凭证仅应为 `credential_id=6`。

## 2. 已完成 endpoint 清单

### Orders

- `POST /api/v1/sync/orders/coupang/preview`
- `POST /api/v1/sync/orders/coupang`

### Products

- `POST /api/v1/sync/products/coupang/preview`
- `POST /api/v1/sync/products/coupang`

### Sales

- `POST /api/v1/sync/sales/coupang/preview`
- `POST /api/v1/sync/sales/coupang`

### Settlements

- `POST /api/v1/sync/settlements/coupang/preview`
- `POST /api/v1/sync/settlements/coupang`

### Summary / Context

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/ai/daily-context`

## 3. 前端入口清单

当前 Codex2 已提供以下手动入口：

- `/orders`
- `/products`
- `/sales`
- `/dashboard`

入口说明：

- `/orders`：Coupang 订单 preview / 本地 sync
- `/products`：Coupang 商品 preview / 本地 sync
- `/sales`：Coupang 销售明细 preview、结算明细 preview
- `/dashboard`：财务摘要与 AI Daily Context 摘要展示

## 4. 当前真实数据状态

基于当前本地真实库的已知状态：

- `orders=0`
- `products=4`
- 商品状态总览：
  - `APPROVED=4`
  - `DELETED=1`
- `platform_sales_details=0`
- `platform_settlement_details=2`
- `settlementAmount=368870`
- `finalAmount=263479`
- `serviceFee=71042`

补充说明：

- 当前订单窗口内 `0` 单与 Coupang 后台核对结果一致。
- 当前 sales 明细同步链路已验证成功，但真实样本行为仍为 `0` 行成功路径。
- 当前 settlement 已有真实持久化数据，可用于 Dashboard / AI Context 本地摘要读取。

## 5. 运营核对方法

### 5.1 订单如何核对 Coupang 后台

建议核对步骤：

1. 在 `/orders` 使用 preview 或 sync，输入小范围日期窗口。
2. 当前系统单次日期窗口最多 `3` 天，建议先从 `1` 天开始。
3. 如果返回 `0`：
   - 先核对该日期窗口内 Coupang 后台是否也无订单。
   - 若后台同样为 `0`，则该结果应视为成功无数据，不是失败。
4. 若未来出现非 `0` 订单：
   - 以平台订单号或 sample IDs 对照后台订单列表。

### 5.2 商品如何按状态核对 Coupang 后台

建议核对步骤：

1. 在 `/products` 先使用 `status=APPROVED` preview。
2. 当前已知真实结果：
   - `APPROVED=4`
3. 再使用 `status=all` preview 核对每个官方状态分组。
4. 当前已知真实结果：
   - `APPROVED=4`
   - `DELETED=1`
5. 注意：
   - `APPROVED` 是 Coupang API 商品审核 / 刊登状态。
   - 它不一定完全等于卖家后台界面里的“销售中”。

### 5.3 sales=0 如何解释

当 `platform_sales_details=0` 或 sales preview / sync 返回 `0` 时：

- 表示当前查询窗口下，本地没有写入 sales 明细。
- 这不自动等于平台没有订单。
- 也不自动等于平台没有结算。
- 当前阶段应理解为：
  - sales 明细接口调用成功；
  - 该窗口没有返回可写入的销售确认 / 营收明细。

### 5.4 settlement 如何按月份核对

settlement 的核对必须按月份理解：

1. 结算接口按 `revenueRecognitionYearMonth=YYYY-MM` 查询。
2. `start_date` / `end_date` 只是用于派生需要查询的月份集合。
3. 返回结果不代表按日精确截断。

建议核对方式：

1. 先记录本地 `months`。
2. 到 Coupang 后台结算页面，按相同月份核对。
3. 优先核对以下字段：
   - `settlementAmount`
   - `finalAmount`
   - `serviceFee`
4. 不要把结算记录当作“某一天的销售额”。

### 5.5 finalAmount 的解释

`finalAmount` 不能直接理解为：

- 利润
- 可提现余额

当前阶段应理解为：

- 这是结算口径中的一个金额字段。
- 如需定义利润、净利、可提现余额，必须由后续业务规则单独定义。

## 6. 口径边界

以下三类金额必须严格分开：

- `orders.order_amount`
  - 订单金额口径
- `platform_sales_details`
  - 销售确认 / 营收明细口径
- `platform_settlement_details`
  - 结算口径

禁止事项：

- 不要把三类金额合并成单一 `total_sales`
- 不要把 settlement 当作订单销售额
- 不要把 finalAmount 当作利润
- 不要把 settlement 当作按日销售明细

当前 Dashboard / AI Context 已按分区展示，不应再额外做混合汇总字段。

## 7. 安全边界

当前阶段安全边界如下：

- `REAL_API_WRITE_ENABLED=false`
- 当前只做 Coupang 只读请求
- Sync 只写本地数据库
- 不调用 Coupang 写接口
- 不保存以下敏感信息：
  - `key`
  - `secret`
  - `header`
  - `signature`
  - `token`
  - `authorization`
- 不保存以下银行相关字段：
  - `bankAccountHolder`
  - `bankName`
  - `bankAccount`
- `verify_all.py` 使用临时测试库
- `verify_all.py` 不应污染真实 `backend/codex1.db`

## 8. 常见问题

### 8.1 0 单是不是失败

不是。

如果订单 preview / sync 在合法窗口内成功返回 `0`，应理解为：

- 请求成功
- 当前窗口没有符合条件的订单

### 8.2 0 sales 是否等于后台没有结算

不是。

当前 `sales=0` 只表示：

- sales 明细口径下没有写入本地明细

它不代表：

- 后台没有订单
- 后台没有结算

### 8.3 settlement 为什么不是按天精确

因为 settlement 查询是按 `revenueRecognitionYearMonth` 进行的。

- `start_date` / `end_date` 只用于派生月份
- 返回结果本质上是月口径查询结果

### 8.4 status=APPROVED 是否等于后台“销售中”

不一定。

`APPROVED` 是 Coupang API 商品审核 / 刊登状态，不应直接等同于后台展示用语“销售中”。

### 8.5 inactive 测试凭证为什么保留

因为当前策略是：

- 不删除历史测试数据
- 只停用测试凭证

这样可以保留联调审计痕迹，同时避免误用。

### 8.6 为什么 8012 上看不到新 endpoint 或新字段

常见原因是：

- `8012` 仍在运行旧后端进程

处理方式：

1. 停掉旧 `8012` 进程
2. 从当前 Codex1 最新代码重新启动
3. 再检查 OpenAPI / Dashboard / AI Context

## 9. 后续建议

当前阶段不建议继续扩大 Coupang API 范围。

建议顺序：

1. 等真实 sales 出现非 `0` 样本后，再做 sales 非 `0` 抽检
2. 保持 Coupang 当前范围稳定一段时间
3. 后续再考虑 Naver API
4. 后续再考虑邮件 / 申诉 / AI 自动日报

当前不建议：

- 继续新增更多 Coupang 写能力
- 扩大更多高风险真实 API 范围
- 把三类财务口径继续混合汇总

## 10. 本阶段结论

Phase 6C 当前已经完成：

- Coupang 真实只读链路验证
- 订单本地同步
- 商品本地同步
- sales 明细空数据成功路径验证
- settlement 本地同步
- Dashboard / AI Context 财务摘要读取与展示

当前阶段可以作为本地运营核对和只读联调基线继续使用。
