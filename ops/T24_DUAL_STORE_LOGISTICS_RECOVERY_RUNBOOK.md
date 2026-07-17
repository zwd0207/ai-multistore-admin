# T24 Dual-Store Logistics Recovery Runbook

## Scope

This runbook re-enables exactly two previously approved Naver logistics
checkpoints after the `naver_logistics_external_order_id_mismatch` repair. It
does not enable any platform write, delete logistics history, or weaken order
association rules.

Keep store IDs, store-name hashes, database URLs, credentials, and approval
values in the protected operator shell. Do not place them in Git, logs, or
deployment artifacts.

## Release Gate

1. Require a successful `Verify release candidate` run for the exact commit.
2. Verify all platform-write and AI settings remain false.
3. Verify orders, inquiries, and products are healthy for both stores.
4. Verify both logistics checkpoints are blocked only by
   `naver_logistics_external_order_id_mismatch`.
5. Create and remotely verify a fresh encrypted PostgreSQL backup.
6. Retain the current backend directory and environment file as the rollback
   release. Do not copy secrets into the staged release.

## Controlled Recovery

1. Stage the verified backend release and compile it before service impact.
2. Stop `ai-multistore-api.service` and confirm it is inactive.
3. Confirm there are no other scheduler processes using the production
   database.
4. Export the protected recovery approval, exact two store IDs, and exact
   store-name SHA-256 values in the current shell only.
5. Run:

   ```text
   python scripts/recover_t24_dual_store_logistics.py --mode recover \
     --store STORE_ID_1:STORE_NAME_SHA256_1 \
     --store STORE_ID_2:STORE_NAME_SHA256_2
   ```

6. Require `status=scheduled`, `checkpoint_count=2`,
   `platform_write=false`, and `network_called=false`.
7. Start the API service immediately. The existing scheduler performs the
   readonly work; the recovery command never contacts Naver.
8. Verify public and local health, then observe both logistics checkpoints
   until each reaches `success`, a legitimate `retry_wait`, or a new closed
   failure. Never rerun the recovery command.
9. Create and remotely verify a fresh encrypted PostgreSQL backup after both
   stores reach an accepted state.

## Emergency Code Rollback

If health fails, a checkpoint enters an unexpected state, or release rollback
is required:

1. Stop `ai-multistore-api.service` and confirm it is inactive.
2. Keep the repaired release available long enough to run its close mode.
3. Export the separate close approval and the service-stopped confirmation in
   the protected shell. Keep the original exact store approvals in place.
4. Run:

   ```text
   python scripts/recover_t24_dual_store_logistics.py --mode close \
     --store STORE_ID_1:STORE_NAME_SHA256_1 \
     --store STORE_ID_2:STORE_NAME_SHA256_2
   ```

5. Require `status=closed`, `checkpoint_count=2`,
   `platform_write=false`, `network_called=false`, and
   `records_deleted=false`.
6. Read back both logistics checkpoints. They must be disabled and blocked by
   `t24_logistics_rollback_closed`, with no lease or next run.
7. Restore the retained backend release and environment file, then compile it.
8. Before starting the service, use an offline configuration and readonly
   database probe to verify PostgreSQL connectivity and confirm every platform
   write and AI setting remains false.
9. Start the API service and verify health and the absence of new logistics
   scheduling. Preserve already-read logistics records for audit; do not
   delete them during code rollback.

## Acceptance Evidence

- Exact release commit and successful CI run
- Pre-release and post-recovery encrypted backup references
- Service stop/start timestamps
- Safe recovery or close JSON result
- Per-store checkpoint status and safe error code
- Logistics record and event counts without identifiers or tracking numbers
- Confirmation that ordinary logs, audits, and responses contain no complete
  tracking number, credential, token, or raw platform response
- Confirmation that every platform-write and AI setting remained false
