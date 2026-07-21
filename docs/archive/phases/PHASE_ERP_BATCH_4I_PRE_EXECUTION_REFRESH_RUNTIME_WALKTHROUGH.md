# Phase ERP-Batch-4I: Pre-Execution Refresh Runtime Walkthrough

Purpose: verify that the existing Orders runtime panel presents formal batch pre-execution refresh evidence in business wording.

Runtime surface:

- Page: `/orders`
- Panel: `正式批量执行前置检查`
- Related readonly route: `POST /api/v1/batch/pre-execution-refresh/readonly-check`

Expected business behavior:

- The panel shows preflight, dry-run, final approval, write-boundary, and pre-execution backup/audit refresh readiness.
- It shows product and order candidate summaries as review evidence only.
- It does not display an execution button.
- It keeps technical route flags, missing flags, store scope, counts, and safety flags folded under `TechnicalDetails`.

Safety boundary:

- no real Naver API call,
- no `real_sync=true`,
- no product write,
- no order write,
- no `SyncLog` write,
- no `ApiCapabilityTestResult tested_success` write,
- no operation audit row write,
- no backup creation or restore execution from this panel,
- no formal product/order batch sync opening.

Walkthrough acceptance:

- backend and mock builds pass,
- `/orders` opens without a white screen,
- the pre-execution panel is visible for a Naver store,
- main page wording says execution is still not approved,
- no mojibake replacement character is present.

Recommended next phase: `Phase ERP-Batch-5A: Formal product/order batch write execution approval plan`.
