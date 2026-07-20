# Naver 咨询唯一读链收口审计（浏览器验收完成，待提交）

## 任务边界

- 任务：`TASK-INQUIRY-READ-CONTRACT-001`
- 范围：统一 Naver 客服咨询的列表、统计、工作台和详情深链。
- 不在范围：数据库模型或迁移、历史数据删除、平台调用、客服回复或其他平台写入。

## 已验证事实

- 正式 Naver 列表只读取 `PxgNaverReadonlyCustomerInquiry`；旧 `CustomerInquiry` 中的 Naver 行仍保留，但不会进入正式客服列表、Dashboard、风险提示、每日上下文或工作台。
- 非 Naver 的 `CustomerInquiry` 保留为历史兼容只读记录，序列化结果固定 `reply_enabled=false`、`reply_disabled_reason=legacy_readonly`。
- `/customer-service?inquiryId=pxg_naver_readonly:<数字ID>` 可在前端直接构造受保护详情读取上下文，不再依赖首批 100 条列表；非规范深链仍保持原列表行为。
- 工作台 Naver 咨询待办只产生 `pxg_naver_readonly:<数字ID>` 深链；列表、看板、风险与每日上下文复用同一正式源选择规则。
- 旧 Naver 同步和回复入口仍被关闭；本任务未开启任何平台读取或写入。

## 已执行验证

- `python scripts/verify_customer_inquiry_operator_workflow.py`：通过。
- `python scripts/verify_t14_naver_readonly_inquiries.py`：通过。
- `python scripts/verify_operator_workbench.py`：通过。
- `python scripts/verify_multi_store_workbench.py`：通过。
- 前端客服、移动回归、核心页面合同和生产构建：通过。
- `python scripts/verify_all.py`：通过；T22 PostgreSQL 专项仍因未配置 `T22_TEST_POSTGRES_URL` 按既有规则跳过。

## 登录态浏览器验收（2026-07-20）

- 项目负责人已完成本地 ERP 登录与 MFA。验收开始前发现 8013/5181 仍是 2026-07-19 启动、未启用热更新的旧进程，因此先逐一核对 `.local-trial/processes.json`、进程命令和端口后，仅重启这两个本地进程。
- 重启复用原有 `.local-trial/runtime.env`、本地演练数据和会话环境；未执行初始化/预置脚本，未重置数据，未调用平台、刷新、回复、迁移或服务器。
- 工作台仅存在一个受保护入口：`#/customer-service?inquiryId=pxg_naver_readonly:21`；`generic:<数字ID>` 询盘待办数量为 0。
- 点击该入口后直接打开 `pxg_naver_readonly:21` 详情；页面显示“当前只读，不发送平台回复”，当前列表中的 10 个“回复”按钮全部禁用，详情仅显示本地保存记录。
- 桌面默认 1280×720：详情正常打开，页面 `scrollWidth=clientWidth=1265`，控制台无 error/warn。
- 390×844 回归：详情正常打开，`scrollWidth=clientWidth=375`、无横向溢出，控制台无 error/warn；验收后已恢复浏览器默认尺寸。

## 尚未核实的事项

- 本候选版本的最终全量回归、精确 Git commit 的 GitHub CI 与生产部署尚未完成；生产服务器、DNS/域名和真实平台操作仍不在本任务范围。

## 准确续接点

登记 `operator-v1.20260720.1` 后运行最终全量校验；通过后自动提交并推送 `release/operator-v1`，再核验该精确 commit 的 GitHub CI。GitHub CI 通过前不得进入库存/SKU任务或部署服务器。
