# 目录整理后开发连续性审计

## 结论

2026-07-22 的目录整理没有删除或改写现行业务实现，不阻断后续开发。前端、后端、CI、合同测试、本地运行脚本和正式文档均已使用 `backend/`；完整前后端回归在整理后的仓库再次通过。

唯一发现的连续性风险是库存/SKU WIP：旧提交 `c9250dbc...` 同时包含旧路径、过期控制文档和已归档文件删除，不能整包 cherry-pick 到当前发布分支。业务服务与审计文档已重新封装为新路径提交 `2e37c7e...`，风险已经隔离。

## 核查结果

| 检查项 | 结果 | 影响判断 |
|---|---|---|
| Git | `release/operator-v1` 与远端一致，整理基线 `416a888...`，检查开始时工作树干净 | 可从当前发布分支建立独立任务分支 |
| 目录 | 唯一仓库 `codex2/`，后端 `backend/`，旧 `codex1/` 不存在 | 新任务不得重新创建旧嵌套目录 |
| 路径引用 | 现行脚本、CI 和当前文档没有运行时旧后端路径；`.gitleaksignore` 仅保留历史提交定位 | 不影响启动、构建或 CI |
| 历史资料 | 根目录 Phase 为 0，`docs/archive/phases/` 有 351 份 | 历史可追溯且不竞争当前状态 |
| Git worktree | 仅主工作树；主分支、发布分支和库存 WIP 分支存在 | 消除多工作树误操作风险 |
| 本地状态 | `.env`、数据库、`.local-trial`、`.venv` 和 `node_modules` 均被 Git 忽略 | 不会因提交泄露或覆盖本地运行数据 |
| 恢复点 | 完整 bundle、新加密快照、恢复说明和删除清单均存在；bundle 校验成功 | 可以恢复 Git 历史和保留数据库快照 |
| 前端验证 | 21 个合同、编码、会话、生产构建和 Bundle 全部通过 | 路径迁移未破坏前端开发入口 |
| 后端验证 | `backend/scripts/verify_all.py` 全部通过 | 模型、API、安全、备份和 T13-T24 主合同未受影响 |
| PostgreSQL | 本地未配置临时测试 URL而跳过；整理提交的 GitHub PostgreSQL 16 job 已通过 | 本地结果不能单独证明 PostgreSQL；CI 已补齐该证据 |
| 生产环境 | 本任务未连接、部署或修改生产 | 当前候选版本仍不能写成已部署 |

## WIP 风险与处理

对旧库存提交执行三方补丁检查时，服务文件和审计资料仍可读取，但 `CHANGELOG.md`、`PROJECT_CONTROL.md`、`TASK_HANDOFF.md`、`DECISION_LOG.md` 以及旧路径删除发生冲突。这是预期的治理与目录冲突，不是业务代码损坏。

原始恢复时只允许取回：

- `codex1/backend/app/services/inventory_service.py`，目标映射为 `backend/app/services/inventory_service.py`；
- `docs/INVENTORY_SKU_CONTRACT_AUDIT_20260720.md`。

不得从旧 WIP 覆盖当前控制文档、变更日志或归档结构。为降低误操作，已在本地分支 `wip/inventory-sku-post-cleanup-20260722` 创建提交 `2e37c7e16a0b346f15093dbdf1a13bdada6effa6`，仅包含这两个目标文件。准确步骤见 [`runbooks/INVENTORY_SKU_WIP_RECOVERY.md`](runbooks/INVENTORY_SKU_WIP_RECOVERY.md)。

## 对后续开发的约束

- 所有新后端文件、测试和文档只使用 `backend/`。
- 已完成能力通过 [`COMPLETED_CAPABILITY_BASELINE.md`](COMPLETED_CAPABILITY_BASELINE.md) 和统一验证命令保护，不复制一套“封装版业务代码”。
- 未开发能力按 [`DEVELOPMENT_ROADMAP.md`](DEVELOPMENT_ROADMAP.md) 的两个工作流推进。
- 任何数据库迁移、生产部署、真实平台读写、DNS 或密钥操作仍需要独立授权。
