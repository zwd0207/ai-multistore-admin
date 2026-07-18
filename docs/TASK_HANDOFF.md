# 当前任务交接

- 任务编号：`TASK-T24-CLOCK-001`
- 任务：修复 T24 测试夹具时钟不一致
- 完成日期：2026-07-19
- 分支：`release/operator-v1`
- 任务开始 HEAD：`23edcd94bab0c6bffba7c5fcb2a0424fa37844e3`
- 任务性质：最小范围测试确定性修复；未开始其他收口任务

## 根因

T24 使用固定 `NOW=2026-07-17 16:00 UTC`，并将该时间传入 `prepare_dual_store_automatic_read(now=NOW)`。准备函数内部计算出 `current`，但 `_assert_store_ready()` 调用 `assert_naver_inquiry_cleanup_healthy()` 时没有传递该时间。包装函数又调用已有的 `assert_pxg_naver_cleanup_healthy()`，后者未收到 `now` 时使用真实 `get_utc_now()`，导致固定时间的清理成功记录被判定为过期。

## 采用方案

- 给 `assert_naver_inquiry_cleanup_healthy()` 增加可选 `now` 参数，并透传到已有的 `assert_pxg_naver_cleanup_healthy(now=...)`。
- 给 T24 `_assert_store_ready()` 增加受控时间参数，由 `prepare_dual_store_automatic_read()` 传入已计算的 `current`。
- 复审并撤销 `verify_all.py` 的临时 `M` 状态允许项；该项会永久放行未来修改，不符合门禁安全原则。完整验证改在与最终 diff 一致的干净工作树执行。
- 保持生产默认行为：生产调用不传 `now` 时继续使用真实 UTC 时间；没有修改过期阈值、清理规则或数据库结构。

## 修改文件

- `codex1/backend/app/services/naver_readonly_inquiry_service.py`
- `codex1/backend/scripts/prepare_t24_dual_store_automatic_read.py`
- `docs/PROJECT_CONTROL.md`
- `docs/TASK_HANDOFF.md`
- `CHANGELOG.md`

## 验证命令与结果

- `.\.venv\Scripts\python.exe -m py_compile app\services\naver_readonly_inquiry_service.py scripts\prepare_t24_dual_store_automatic_read.py`：通过。
- `.\.venv\Scripts\python.exe scripts\verify_t24_dual_store_automatic_read.py`：第一次通过。
- 同一 T24 独立测试第二次运行：通过。
- T13、T14、T15、T16、T17、T18、T19、T20、T23 和全部 T24 专项：通过；`verify_recover_t24_dual_store_logistics.py` 的 PostgreSQL 并发分支按既有规则跳过。
- `verify_all.py`：在应用当前 diff 并临时提交的干净 detached 工作树完整通过，包含 `git tracking: ok` 和 `verify_all: ok`；没有保留任何新增工作树允许项。正式提交后将再次运行。
- `verify_all.py` 中 T22 PostgreSQL 专项仍按既有规则跳过，因为未配置 `T22_TEST_POSTGRES_URL`；这不是本任务失败。
- 本次未运行前端构建；没有前端文件修改。
- T21：仓库没有独立 `verify_t21*.py` 入口；已执行提交存在性、祖先关系和历史证据核验，未将历史服务器或 CI 证据冒充本次运行时测试。
- `git diff --check`：通过。
- `git diff --stat`：5 个文件，69 行新增、46 行删除；删除主要来自按协议覆盖上一任务的 `TASK_HANDOFF.md`。
- `git diff --name-only`：仅包含 2 个 T24 时间相关 Python 文件和 3 个权威状态文档；没有 `verify_all.py`、模型、迁移、API、前端、依赖或配置变更。
- `git status --short`：5 个文件未暂存修改，无暂存或未跟踪文件；提交前未推送。

## 生产代码影响

修改了 `naver_readonly_inquiry_service.py` 的包装函数签名，但仅增加可选参数并透传现有时间入口。未传参数时行为保持不变，仍使用生产真实 UTC 时间。没有修改清理过期语义、阈值、模型、迁移、API 或平台访问行为。

## 未解决事项

- T22 PostgreSQL 专项仍需配置一次性测试数据库后单独运行。
- `PROJECT_CONTROL.md` 页首仍记录旧基准 HEAD `4027e761...`，与当前任务起点 `23edcd94...` 不一致；本任务按限制只更新 T24 相关字段，未擅自校准该非 T24 字段。
- 当前阶段其他数据合同和运营流程技术债务未处理。
- 没有新增长期架构决策。

## 下一任务准确起点

下一任务仍从 `docs/PROJECT_CONTROL.md` 的工作流一开始，处理核心数据合同收口；T24 时钟修复不应自动扩展为咨询、库存、工作台或自动同步重构。

## 禁止误操作

- 不得将固定日期替换为其他固定日期来掩盖问题。
- 不得放宽生产清理规则、删除断言或跳过失败。
- 不得修改 T13–T23 业务目标，不得开始其他下一阶段任务。
- 不得推送、部署或继续执行下一任务；本任务只创建一个独立提交。
