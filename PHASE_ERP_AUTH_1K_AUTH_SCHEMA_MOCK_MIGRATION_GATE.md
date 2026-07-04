# Phase ERP-Auth-1K: Auth schema mock migration gate

## Result

Codex1 now verifies the proposed auth schema in `backend/scripts/verify_all.py` using only the isolated temporary verification database.

The mock gate creates and checks:

- `erp_users`
- `erp_roles`
- `erp_permissions`
- `erp_role_permissions`
- `erp_store_memberships`

## Verified Behavior

`verify_all.py` confirms:

- owner/admin/operator/auditor/viewer roles exist in the temporary schema
- `orders.refresh_batch_write` and `backup.create` permissions exist
- admin can approve `orders.refresh_batch_write`
- operator does not receive refresh-write permission
- a sample admin user has store 8 membership
- the same sample user has no store 9 membership
- proposed table columns do not contain token, Authorization, headers, signature, raw response, client secret, full buyer/receiver privacy, full platform order id, or full product-order id fields
- orders/products/SyncLog/tested-success/audit/timeline counts stay unchanged
- the real `backend/codex1.db` file is not touched by the mock gate

## Boundary

This phase does not run a real migration, create a real auth session, expose login APIs, write production auth rows, call Naver, write business data, modify Codex2 runtime code, or open formal sync.

## Next Gate

A real auth schema migration still needs a separate approval phase with backup evidence, rollback instructions, schema script review, and post-migration readback.

