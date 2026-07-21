# Codex Project Entry Rules

Before planning, editing, reviewing, or delegating work, read these files in order:

1. `docs/PROJECT_CONTROL.md` - the only source of current project truth and next action.
2. `docs/TASK_HANDOFF.md` - the latest task scope, validation evidence, and continuation point.
3. `docs/DECISION_LOG.md` - durable product, privacy, permission, and release decisions.
4. `docs/governance/MODEL_TASK_ALLOCATION_RULES.md` - mandatory model task boundaries when delegation applies.

Files under `docs/archive/`, including Phase and Commander records, are historical evidence only. Do not reconstruct current state from them unless a current control document points to a specific archived record.

After a task changes project status, update `docs/PROJECT_CONTROL.md`, `docs/TASK_HANDOFF.md`, and `CHANGELOG.md` in the same integration cycle. Append to `docs/DECISION_LOG.md` only when a durable rule or boundary changes.

All real marketplace writes remain disabled unless `docs/PROJECT_CONTROL.md` records a separately approved production trial. Never use production customer data for tests, and never treat a local directory change as authorization to deploy or modify production.
