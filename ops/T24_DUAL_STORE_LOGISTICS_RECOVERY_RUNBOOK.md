# T24 Dual-Store Logistics Recovery Runbook

## Scope

This runbook re-enables exactly two previously approved Naver logistics
checkpoints after the `naver_logistics_external_order_id_mismatch` repair. It
does not enable any platform write, delete logistics history, or weaken order
association rules.

Keep store IDs, store-name hashes, database URLs, credentials, and approval
values in the protected operator shell. The command result may echo the two
store IDs to that shell for verification; do not persist the command or result
in Git, application logs, or deployment artifacts.

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
4. Export the protected recovery approval, exact two store IDs, exact
   store-name SHA-256 values, and
   `T24_DUAL_STORE_LOGISTICS_RECOVERY_SERVICE_STATE=api-service-confirmed-stopped`
   in the current shell only.
5. Run:

   ```text
   python scripts/recover_t24_dual_store_logistics.py --mode recover \
     --store STORE_ID_1:STORE_NAME_SHA256_1 \
     --store STORE_ID_2:STORE_NAME_SHA256_2
   ```

6. Capture stdout separately from stderr and parse it with a JSON parser.
   Require `status=scheduled`, exactly two unique `store_ids`,
   `checkpoint_count=2`, two schedules, `platform_write=false`, and
   `network_called=false`. Never validate with substring matching or field
   order. Exit code `2` is a closed safety blocker; exit code `1` is a failure.
   On either nonzero exit, keep the service stopped and read back markers and
   both checkpoints before deciding whether any transaction committed.
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
3. Export the separate close approval and
   `T24_DUAL_STORE_LOGISTICS_CLOSE_SERVICE_STATE=api-service-confirmed-stopped`
   in the protected shell. Keep the original exact store approvals in place.
4. Run:

   ```text
   python scripts/recover_t24_dual_store_logistics.py --mode close \
     --store STORE_ID_1:STORE_NAME_SHA256_1 \
     --store STORE_ID_2:STORE_NAME_SHA256_2
   ```

5. Capture stdout separately from stderr and parse it with a JSON parser.
   Require `status=closed`, exactly two unique `store_ids`,
   `checkpoint_count=2`, `platform_write=false`, `network_called=false`, and
   `records_deleted=false`. Never validate with substring matching or field
   order; treat any nonzero exit as a failed close until checkpoint readback
   proves otherwise.
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

## Reopen After A Closed Rollback

Do not delete recovery or close markers to retry a deployment. After the cause
of the rollback is fixed and a new release passes the full release gate:

1. Stop the API service and confirm `systemd` reports it as inactive.
2. Verify both logistics checkpoints are exactly blocked by
   `t24_logistics_rollback_closed`, with no lease or next run.
3. Verify both recovery markers and both close markers are present, and no
   reopen marker exists.
4. Export the original recovery approval, exact two store IDs, the service
   stopped confirmation
   `T24_DUAL_STORE_LOGISTICS_CLOSE_SERVICE_STATE=api-service-confirmed-stopped`,
   and the separate reopen approval in the protected shell.
5. Run the same command as controlled recovery with `--mode reopen`.
6. Parse stdout separately from stderr with a JSON parser. Require the same
   scheduled safety contract as controlled recovery plus
   `records_deleted=false`; never validate by substring or field order. On a
   nonzero exit, keep the service stopped and read back markers and both
   checkpoints before deciding whether reopen committed.
7. Start the repaired release and follow the normal observation and backup
   steps. Reopen is one-time and cannot be repeated. If rollback is required
   again, the existing `--mode close` command writes a separate reclose audit
   before old code is restored.
