# AI 多店铺运营系统

`codex2/` 是本项目唯一运行仓库。前端位于仓库根目录，FastAPI 后端位于 `backend/`；历史 Phase 与旧治理材料已集中到 `docs/archive/`，不再作为当前状态来源。

## 当前事实入口

- [项目控制](docs/PROJECT_CONTROL.md)：唯一当前状态入口
- [任务交接](docs/TASK_HANDOFF.md)：最近任务、验证与续接方式
- [决策日志](docs/DECISION_LOG.md)：长期边界与追加式决策
- [变更日志](CHANGELOG.md)：已经发生的仓库变更
- [已完成能力基线](docs/COMPLETED_CAPABILITY_BASELINE.md)：稳定主实现、正式入口和统一验证
- [开发收口路线图](docs/DEVELOPMENT_ROADMAP.md)：尚未完成能力的两个工作流
- [模型分工](docs/governance/MODEL_TASK_ALLOCATION_RULES.md)
- [试运营说明](docs/runbooks/OPERATOR_TRIAL_PXG_NAVER.md)

## 目录

```text
backend/                 FastAPI、数据库模型、迁移与后端验证
src/                     React 运营前端
scripts/                 本地入口、合同测试与构建门禁
docs/                    当前控制、审计、治理与运行手册
docs/archive/phases/     只读 Phase 历史及索引
docs/archive/governance/ 旧 README、Commander 与进度资料
public/                  前端静态资源与候选版本登记
```

## 本地安装

需要 Node.js、npm 和 Python 3.12。

```powershell
npm.cmd ci
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

本地配置保存在未纳入 Git 的 `.env`、`.env.local` 和 `backend/.local-trial/`。不要把密钥、真实客户数据或平台原始响应写入仓库。

## 开发与验证

```powershell
npm.cmd run dev
npm.cmd run build
npm.cmd run encoding:scan
npm.cmd run session:verify
npm.cmd run bundle:verify
npm.cmd run capabilities:verify
npm.cmd run capabilities:verify:full
backend\.venv\Scripts\python.exe backend\scripts\verify_all.py
```

完整本地试运营使用 `scripts/start-local-pxg-naver-trial.ps1`，操作前先阅读运行手册。真实平台写入、客服回复、发货回填、生产部署、数据库迁移和 DNS 修改均不因本地启动而获得授权。

## 历史资料

Phase 文档索引见 [docs/archive/phases/README.md](docs/archive/phases/README.md)。历史文件只用于追溯；发生冲突时始终以 `docs/PROJECT_CONTROL.md` 为准。
