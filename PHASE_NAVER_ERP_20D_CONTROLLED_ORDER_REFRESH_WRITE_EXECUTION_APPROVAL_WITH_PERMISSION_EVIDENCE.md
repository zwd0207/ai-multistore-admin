# Phase Naver-ERP-20D: Controlled order refresh write execution approval with permission evidence

## Purpose

Approve one controlled existing-order refresh attempt for the previously observed safe hash `id-hash-192b9c67e8`.

This phase is approval and evidence only. It does not itself open formal order sync and does not execute any Naver platform write operation.

## Permission Evidence

The runtime permission mock API confirmed:

- store-scoped permission check: allowed for `orders.refresh_batch_write`
- sensitive action approval check: allowed in mock with manual approval
- `formal_sync_open=false`
- `platform_writes_enabled=false`
- `real_auth_session_created=false`
- `real_database_written=false`

## Approval Boundary

The next execution phase may attempt exactly one existing-order local refresh only if:

- the worktrees are clean before execution
- a fresh pre-write database backup exists
- a fresh readonly Naver preview repeats the same safe hash
- the safe hash matches exactly one existing local Naver order
- the privacy and raw-response gates pass
- the permission and sensitive-action approval gates pass
- the operation writes append-only audit evidence
- post-write verification passes

If no business fields changed, the write gate must stop with no local order update.
