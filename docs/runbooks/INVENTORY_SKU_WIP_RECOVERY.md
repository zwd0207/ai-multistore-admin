# 库存/SKU WIP 恢复说明

库存/SKU 的 7 项未完成改动未进入目录整理提交，完整保存在仅本地分支 `wip/inventory-sku-pre-cleanup-20260722`，提交为 `c9250dbc4801c10a85a47730924fe06f75168d1d`。工作区完整 bundle 也包含该提交。

仅在 `operator-v1.20260722.1` 的 GitHub CI 通过后恢复：

1. 切换到整理后的 `release/operator-v1`，新建独立库存任务分支。
2. 执行 `git cherry-pick --no-commit c9250dbc4801c10a85a47730924fe06f75168d1d`，只把改动放入工作树，不立即提交。
3. 保留当前整理后的控制文档与归档结构，人工核对 WIP 中对 `CHANGELOG.md`、`docs/PROJECT_CONTROL.md`、`docs/TASK_HANDOFF.md` 和 `docs/DECISION_LOG.md` 的历史状态更新，不用旧状态覆盖当前事实。
4. 如果 Git 未自动识别目录重命名而在旧嵌套目录重新创建服务文件，将其移到 `backend/app/services/inventory_service.py`，并确认旧 `codex1/` 仍不存在。
5. 保留并复核 `docs/INVENTORY_SKU_CONTRACT_AUDIT_20260720.md`；运行库存专项、完整后端验证、前端合同测试和浏览器验收后，再创建库存任务自己的提交。

恢复过程不得启用平台库存写入、仓库写入、同步、客服回复或发货回填。若 cherry-pick 出现冲突，先执行 `git cherry-pick --abort` 回到干净任务分支，再按文件选择性恢复；不得修改或删除原 WIP 分支。
