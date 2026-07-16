# T22 PostgreSQL Migration And Rollback Runbook

## Current Boundary

- Production continues to use `/srv/codex1-backend/data/codex1.db` until the migration window is explicitly approved.
- The PostgreSQL database must contain the Alembic schema and no application rows before migration.
- Only the production server SQLite data is migrated. Local T20 Ziniao directory data is excluded.
- No Naver write capability is enabled by this procedure.

## Required Evidence

1. Record the approved release commit and a successful GitHub `Verify release candidate` run.
2. Run `ops/archive_server_baseline.sh` and verify its `SHA256SUMS` file.
3. Copy the fresh SQLite backup to a second private location before stopping the application.
4. Record the source SQLite SHA-256, integrity result, table counts, PostgreSQL revision, and operator identity.
5. Confirm the PostgreSQL application tables are empty. A migration replay against a non-empty target is forbidden.

Do not put database files, reports containing identifiers, environment files, invitation tokens, or backup archives in Git.

## Dry Run

Run from the checked-out backend release with the protected database URL loaded from `/etc/ai-multistore/postgresql.env`:

```bash
set -a
source /etc/ai-multistore/postgresql.env
set +a
export APP_ENV=production
export TARGET_DATABASE_URL="${DATABASE_URL}"

python -m alembic upgrade head
python -m alembic check

SOURCE_COPY=/path/to/protected/codex1.db
SOURCE_SHA256="$(sha256sum "${SOURCE_COPY}" | awk '{print $1}')"
python scripts/migrate_sqlite_to_postgres.py \
  --source-sqlite "${SOURCE_COPY}" \
  --tenant-name "Initial production tenant" \
  --report-json /path/to/private/t22-dry-run.json
```

The dry-run report must show `migration_ready`, `platform_admin_bootstrap_required=true`, and the reviewed source hash. The formal database currently has no ERP users, so no `--platform-admin-user-id` is supplied.

## Migration Window

1. Put the application into maintenance mode and stop `ai-multistore-api.service`.
2. Create a new SQLite online backup after the service stops. Verify `PRAGMA integrity_check`, counts, and SHA-256 again.
3. Confirm the final source hash equals the value passed to the execution command.
4. Execute exactly once:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source-sqlite "${SOURCE_COPY}" \
  --tenant-name "Initial production tenant" \
  --execute \
  --confirm EMPTY_TARGET_AND_BACKUP_VERIFIED \
  --source-sha256 "${SOURCE_SHA256}" \
  --report-json /path/to/private/t22-execution.json
```

5. Verify source and target counts, canonical digests, foreign keys, encrypted credential values, and `sessions_migrated=false`.
6. Create the only initial platform administrator invitation:

```bash
python scripts/bootstrap_platform_admin.py \
  --tenant-id 1 \
  --email '<approved-admin-email>' \
  --display-name '<approved-display-name>' \
  --secrets-output /path/to/private/platform-admin-invitation.json
```

7. Deliver the invitation URL through an approved private channel. Delete the secrets file after MFA enrollment and recovery-code handoff are confirmed.
8. Update the protected application environment to use PostgreSQL, start the service, and verify health, login, tenant selection, stores, orders, products, credentials, consultations, and logistics.

## Acceptance Checks

- Alembic reports revision `608122e7c9e6` and `alembic check` reports no changes.
- Migrated table counts and canonical row digests match the reviewed SQLite source.
- The original SQLite file hash remains unchanged.
- Existing encrypted credentials can be decrypted with the unchanged production encryption key.
- The initial administrator belongs to tenant `1`, has `platform_admin`, completes TOTP MFA, and receives recovery codes.
- No legacy session is accepted after migration.
- Cross-tenant and cross-store probes remain denied.
- Platform write settings remain false.

## Rollback

Rollback is an application configuration rollback, not a reverse data merge:

1. Stop `ai-multistore-api.service` immediately.
2. Preserve PostgreSQL and its logs for investigation; do not retry the migration or copy PostgreSQL changes into SQLite.
3. Restore the pre-migration application environment and point `DATABASE_URL` to the untouched SQLite production file.
4. Restore the previous release artifact if application code also changed.
5. Start the service in read-only mode and verify health, login, stores, orders, consultations, and logistics.
6. Record the failure and hashes in the private incident record.

If any platform write occurred after the PostgreSQL switch, do not perform this simple rollback until those attempts have been reconciled. T22 itself must keep all platform writes disabled.
