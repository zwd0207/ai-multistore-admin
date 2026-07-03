# Phase Naver-ERP-14F - Order Status Timeline Schema Approval Plan

## Summary

Phase 14F is the approval and rollback plan for a future `order_status_events` schema migration. It does not create the table, does not add a SQLAlchemy model, does not run a migration, does not call Naver, does not execute `real_sync=true`, does not write local business data, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

The result of this phase is a controlled checklist for the next separately approved phase: `Phase Naver-ERP-14G: Order status events schema migration`.

## Current Baseline

- 14A planned the order status timeline behavior.
- 14B added a private mock mapper for safe planned events.
- 14C planned Orders UI display.
- 14D proposed the future `order_status_events` table.
- 14E verified the proposed table shape in a temporary verification database only.
- The real `backend/codex1.db` still must not contain `order_status_events` before 14G.

## Approval Boundary

14F does not approve automatic execution of 14G.

Before 14G, the user must explicitly approve the actual schema migration with a new request. The request should name 14G and confirm that creating `order_status_events` in the real `backend/codex1.db` is allowed.

## 14G Preflight Checklist

Before any real schema change:

- Confirm both Codex1 and Codex2 git worktrees are clean.
- Confirm no Naver API request will be made.
- Confirm `real_sync=true` will not be executed.
- Confirm formal Naver order sync remains closed.
- Confirm current counts:
  - `orders_store8`.
  - real Naver local orders.
  - mock/test Naver orders.
  - `products_store8`.
  - `sync_logs_store8`.
  - `tested_success_store8`.
- Confirm `order_status_events` does not already exist, or if it exists, stop for manual review.
- Back up `backend/codex1.db` before schema creation.

## Backup Plan

Recommended backup directory:

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\
```

Recommended backup filename:

```text
codex1.db.backup-naver-erp-14g-order-status-events-schema-YYYYMMDD-HHMMSS
```

Backup must complete before any `CREATE TABLE` or `CREATE INDEX` statement runs.

## Migration Shape For 14G

14G may create only:

- `order_status_events` table.
- `uq_order_status_event_dedupe` unique index or equivalent unique constraint on `store_id/platform/dedupe_key`.
- indexes for:
  - `store_id/platform/observed_at`.
  - `order_id/observed_at`.
  - `store_id/platform/event_type`.
  - `external_product_order_id_hash`.

14G must not:

- alter existing `orders` rows.
- alter existing `products` rows.
- write `SyncLog`.
- add `ApiCapabilityTestResult tested_success`.
- insert timeline event rows.
- call Naver.
- save raw responses.
- save tokens, Authorization values, request headers, signatures, bcrypt output, or client secrets.
- save full order ids, full product-order ids, buyer privacy, phones, addresses, or zip codes.

## Rollback Plan

If migration fails before any event data exists:

- stop immediately.
- restore the database backup.
- confirm baseline counts match the preflight counts.
- confirm `order_status_events` does not exist after restore.

If table creation succeeds but index creation fails:

- prefer restoring the backup.
- do not leave a partially indexed table in place unless a later manual recovery plan explicitly approves it.

If post-migration verification fails:

- restore the backup.
- rerun readback counts and sensitive-field checks.
- do not proceed to event writes.

## Post-Migration Verification For 14G

After migration, before any event writes:

- Confirm `order_status_events` exists.
- Confirm required columns exist.
- Confirm unique dedupe boundary exists.
- Confirm planned indexes exist.
- Confirm existing counts are unchanged:
  - `orders_store8`.
  - real Naver local orders.
  - mock/test Naver orders.
  - `products_store8`.
  - `sync_logs_store8`.
  - `tested_success_store8`.
- Confirm no event rows were inserted by the schema migration.
- Confirm sensitive scans find no raw response, token, Authorization, header, signature, full order id, full product-order id, buyer/receiver data, phone number, address, or zip code.
- Run `python backend/scripts/verify_all.py`.
- Run `git diff --check`.
- Run encoding scan.

## Future Event Write Boundary

Creating the table in 14G still must not allow event writes by itself.

A later event write phase must separately approve:

- fresh readonly preview.
- selected local order identity match.
- exactly one local Naver order row.
- privacy gate success.
- known status mapping, or explicit manual-review event handling.
- duplicate-event check.
- one-event insert limit.
- post-write readback.

## Recommended Next Phase

Recommended next phase after 14F:

```text
Phase Naver-ERP-14G: Order status events schema migration
```

14G should be executed only after explicit user approval and only for the schema migration. It should not insert status events or open formal Naver order sync.
