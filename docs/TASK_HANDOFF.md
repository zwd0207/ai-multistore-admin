# 当前任务交接

- 任务编号：`TASK-POST-CLEANUP-CONTINUITY-001`
- 任务：检查目录整理对后续开发的影响，记录项目进展，封装已完成能力并规划未开发能力
- 日期：2026-07-22
- 分支：`release/operator-v1`
- 任务开始 HEAD：`416a888096f5a5e71714adf0419cda79126db410`
- 当前候选版本：`operator-v1.20260722.1`

## 实际完成内容

- 读取并复核项目负责人提供的昨日整理任务记录，与当前 Git、路径、恢复点和权威文档交叉验证。
- 确认目录整理未删除或改写现行业务实现；现行入口、CI 和合同测试均使用 `backend/`。
- 再次运行全部前端合同、编码、会话、生产构建、Bundle 和后端 `verify_all.py`，整理后的代码基线通过。
- 建立已完成能力基线，按唯一主实现、正式入口、保护边界和证据封装，不复制第二套业务代码。
- 增加 `capabilities:verify` 与 `capabilities:verify:full`，只编排现有门禁。
- 建立两个工作流的未开发路线图，当前唯一允许开工项为库存/SKU 双来源只读合同。
- 发现原库存 WIP 整包补丁会与新路径和当前治理文档冲突；已在本地分支 `wip/inventory-sku-post-cleanup-20260722` 创建干净 WIP 包 `2e37c7e...`，只含新路径服务和审计文档。

## 目录整理影响结论

- 开发基线可继续使用：`codex2/` 是唯一仓库，后端是 `backend/`，发布分支与远端在任务开始时一致且工作树干净。
- `.env`、数据库、`.local-trial`、`.venv` 和 `node_modules` 均未被 Git 跟踪。
- 根目录没有 Phase 文档；351 份历史 Phase 位于 `docs/archive/phases/`。
- 仅保留一个 Git worktree；完整 bundle、新加密快照、恢复说明和删除清单均存在，bundle 验证成功。
- `.gitleaksignore` 中两条旧路径只用于历史提交定位，不是运行时依赖。
- 原始库存 WIP `c9250dbc...` 内容仍完整但不得整包 cherry-pick；后续优先移植整理后提交 `2e37c7e...`。

## 修改文件

- `scripts/verify-completed-capabilities.mjs`
- `package.json`
- `README.md`
- `docs/COMPLETED_CAPABILITY_BASELINE.md`
- `docs/DEVELOPMENT_ROADMAP.md`
- `docs/POST_CLEANUP_DEVELOPMENT_AUDIT_20260722.md`
- `docs/runbooks/INVENTORY_SKU_WIP_RECOVERY.md`
- `docs/PROJECT_CONTROL.md`
- `docs/TASK_HANDOFF.md`
- `docs/DECISION_LOG.md`
- `CHANGELOG.md`

## 验证命令和结果

- `npm.cmd run encoding:scan`：通过。
- `npm.cmd run session:verify`：通过。
- `scripts/*.test.mjs` 共 22 项：全部通过。
- `npm.cmd run build`：通过，38 个 JavaScript chunk。
- `npm.cmd run bundle:verify`：通过，入口 273,766 bytes。
- `backend/.venv/Scripts/python.exe backend/scripts/verify_all.py`：通过，包含 T13-T24、会话、工作台、Git 跟踪和文档秘密扫描。
- 本地 T22 PostgreSQL 专项：因未配置一次性 `T22_TEST_POSTGRES_URL` 按既有规则跳过；整理提交 `416a888...` 的 GitHub PostgreSQL 16 job 已通过。
- `git bundle verify archive/git/ai-multistore-pre-cleanup-20260722.bundle`：通过。
- 原始库存 WIP `git apply --check --3way`：预期失败，冲突仅涉及旧路径、已归档文件和过期治理文档；业务服务与审计资料可读取。

## 当前未完成内容

- 本任务没有部署生产，也没有重新验证服务器活动前端的精确构建 SHA。
- 当前候选代码仍未部署生产；真实客服回复、发货回填、库存/商品写入继续关闭。
- 库存/SKU 只读服务仍是 WIP，尚未接入 API、页面、工作台或仓库批次。
- Settings 正式配置接口、平台结算、邮箱收信、真实 AI 建议、公司主体和紫鸟 Windows 助手仍未完成。

## 阻塞问题

- 无目录或代码阻塞。
- 库存 WIP 必须按恢复手册使用整理后提交 `2e37c7e...`，不能执行原始提交的整包 cherry-pick。

## 下一任务准确起点

任务编号：`TASK-INVENTORY-SKU-CONTRACT-001`。

1. 从最新 `release/operator-v1` 新建独立任务分支。
2. 阅读 `docs/INVENTORY_SKU_CONTRACT_AUDIT_20260720.md` 的原始 WIP 版本和 `docs/runbooks/INVENTORY_SKU_WIP_RECOVERY.md`。
3. 执行 `git cherry-pick --no-commit 2e37c7e16a0b346f15093dbdf1a13bdada6effa6`，确认只出现新路径服务和库存审计文档，不立即提交。
4. 先补只读 API、合同测试和唯一映射阻断，再接 `/inventory`、`/products`、工作台和 WarehouseBatch。
5. 不启用平台库存写入、仓库自动扣减、客服回复、发货回填或真实同步。

## 禁止误操作事项

- 不得重新创建 `codex1/`，也不得恢复旧 README、Phase 或 Commander 文件到仓库根目录。
- 不得删除原始 WIP 分支、完整 bundle、新加密快照或当前本地运行数据库。
- 不得把 Mock 恢复为默认数据源或增加 Backend 静默回退。
- 不得将 A2 技术能力描述成 A1 运营闭环。
- 服务器部署、数据库迁移、DNS、密钥和真实平台操作仍需要独立门禁。
