# 库存/SKU WIP 恢复说明

库存/SKU 的 7 项未完成改动未进入目录整理提交，完整保存在仅本地分支 `wip/inventory-sku-pre-cleanup-20260722`，提交为 `c9250dbc4801c10a85a47730924fe06f75168d1d`。工作区完整 bundle 也包含该提交。

目录整理后的三方补丁检查已经确认：旧提交同时包含旧后端路径、过期控制文档和一个已归档文件的删除，整包 cherry-pick 会产生预期冲突。旧提交只作为原始恢复点，不应直接恢复到发布分支。

仅在 `operator-v1.20260722.1` 的 GitHub CI 通过后恢复：

1. 切换到整理后的 `release/operator-v1`，确认工作树干净，再新建独立库存任务分支。
2. 优先使用整理后 WIP 包提交 `2e37c7e16a0b346f15093dbdf1a13bdada6effa6`；它位于本地分支 `wip/inventory-sku-post-cleanup-20260722`，只包含新路径下的库存服务和库存合同审计，不包含旧治理文档。可执行 `git cherry-pick --no-commit 2e37c7e16a0b346f15093dbdf1a13bdada6effa6` 后先审查，不立即提交。
3. 从 `c9250dbc...` 只提取 `docs/INVENTORY_SKU_CONTRACT_AUDIT_20260720.md` 和旧路径的 `inventory_service.py`；后者必须保存为 `backend/app/services/inventory_service.py`。不得整包 cherry-pick，不得恢复或覆盖 `CHANGELOG.md`、`docs/PROJECT_CONTROL.md`、`docs/TASK_HANDOFF.md`、`docs/DECISION_LOG.md` 或旧 `codex1/` 文件。
4. 确认 `git status --short` 中没有 `codex1/`，并对 `backend/app/services/inventory_service.py` 执行编译检查。
5. 复核库存审计中的来源、阻断和未核实事项；在接入 API、页面或工作台前先补专项测试。
6. 运行库存专项、完整后端验证、前端合同测试和浏览器验收后，再创建库存任务自己的提交。

恢复过程不得启用平台库存写入、仓库写入、同步、客服回复或发货回填。若任何恢复命令产生治理文档或旧路径冲突，立即中止该恢复方式，回到干净任务分支后按文件选择性恢复；不得修改或删除原 WIP 分支。
