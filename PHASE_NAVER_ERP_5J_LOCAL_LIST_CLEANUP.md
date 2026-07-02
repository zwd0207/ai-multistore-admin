# Phase Naver-ERP-5J - Naver Order Local List Cleanup

## Scope

This phase cleans the default local Naver order list and seller-facing summaries after display hierarchy cleanup.

It does not call Naver, does not write or delete orders, does not change database schema, does not run `real_sync=true`, and does not open formal Naver order sync.

## Implemented

- Codex1 `/api/v1/orders` excludes local test rows by default when listing orders.
- `mock_sync` and `local_frontend_mock` rows remain in the database and can be inspected with `include_test_orders=true`.
- Codex1 order sales stats and Dashboard summary use operational orders by default, so local test rows do not inflate order count or order amount.
- Codex2 preserves `test_orders_excluded` metadata for status/technical display without loading test rows into the main seller-facing order list.

## Default Seller-Facing Behavior

- Orders list: operational local orders only.
- Dashboard order count: operational orders only.
- Dashboard order amount: operational order amount only.
- Recent orders: operational orders only.
- Test rows: retained but hidden by default.

## Diagnostic Behavior

- `/api/v1/orders?include_test_orders=true` returns operational rows plus local test rows.
- `/api/v1/stats/sales?include_test_orders=true` and `/api/v1/dashboard/summary?include_test_orders=true` can include test rows for controlled diagnostics.
- The diagnostic flag is readonly and does not create, update, delete, or sync data.

## Safety Boundary

- No real Naver API request.
- No order write or delete.
- No product write.
- No SyncLog write.
- No `ApiCapabilityTestResult tested_success` write.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Formal Naver order sync remains closed.

## Validation

- `backend/.venv/Scripts/python.exe scripts/verify_all.py`
- `npm.cmd run build`
- `$env:VITE_DATA_SOURCE='mock'; npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
