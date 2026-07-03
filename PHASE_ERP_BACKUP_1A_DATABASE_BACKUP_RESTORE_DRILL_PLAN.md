# Phase ERP-Backup-1A - Database Backup and Restore Drill Plan

## Summary

Phase ERP-Backup-1A defines the production backup and restore drill plan for the local Codex1 SQLite database.

This phase is planning-only. It does not create a backup, does not restore a database, does not modify `backend/codex1.db`, does not change schema, does not write business data, does not call platform APIs, and does not modify runtime UI.

## Goal

Production ERP work must be able to answer:

- Which database file was protected before a risky operation.
- Where the backup is stored.
- Whether the backup has a verified SHA-256 hash.
- Whether the backup can be opened and passes integrity checks.
- Whether a restore can be rehearsed without touching the production database.
- What must happen before a real restore can replace `backend/codex1.db`.

## Protected Database

Initial protected database:

```text
backend/codex1.db
```

Initial local backup directory:

```text
C:\Users\Administrator\Desktop\AI 多店铺运营系统项目\codex1-db-backups\
```

Recommended backup filename pattern:

```text
codex1.db.backup-<phase>-YYYYMMDD-HHMMSS.db
```

Recommended manifest filename pattern:

```text
codex1.db.backup-<phase>-YYYYMMDD-HHMMSS.manifest.json
```

## Backup Manifest

Each future production backup should have a safe manifest with:

- `phase`.
- `created_at`.
- `actor_type`.
- `actor_label`.
- `source_db_path`.
- `backup_path`.
- `backup_sha256`.
- `backup_size_bytes`.
- `git_commit_codex1`.
- `git_commit_codex2`.
- `database_integrity_check`.
- `baseline_counts`.
- `sensitive_scan_passed`.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `notes`.

The manifest must not contain tokens, Authorization values, headers, signatures, bcrypt inputs, client secrets, raw platform responses, full order ids, full product-order ids, buyer or receiver privacy fields, phone numbers, addresses, or zip codes.

## Backup Procedure

Future backup implementation should prefer SQLite's online backup API for a consistent snapshot.

The minimum procedure:

1. Confirm the target source path is exactly the intended `backend/codex1.db`.
2. Create the backup directory if missing.
3. Generate a phase-stamped filename.
4. Use a consistent SQLite backup method.
5. Compute SHA-256 of the backup file.
6. Capture baseline table counts needed by the phase.
7. Run `PRAGMA integrity_check` on the backup.
8. Write a safe manifest next to the backup.
9. Record the backup path and SHA-256 in the future audit trail once real audit logging exists.

If the backup tool cannot prove a consistent snapshot, the operation must stop before any write phase.

## Restore Drill Procedure

The first restore drill must restore only into a temporary drill location.

It must not replace the real `backend/codex1.db`.

The minimum drill:

1. Pick one known backup path and expected SHA-256.
2. Copy or restore it into a temporary drill path outside the production database location.
3. Verify SHA-256 before opening the drill database.
4. Open the drill database read-only when possible.
5. Run `PRAGMA integrity_check`.
6. Verify expected tables exist.
7. Verify phase-specific row counts match the manifest.
8. Run a sensitive-field scan against safe summaries and known risky fields.
9. Run read-only smoke queries for stores, products, orders, timeline events, and API capability counts.
10. Delete the temporary drill database after verification.

## Real Restore Approval Boundary

A real restore that replaces `backend/codex1.db` must be a separate explicitly approved phase.

Before a real restore:

- Stop backend processes that may write to the database.
- Confirm both git worktrees are clean.
- Create a pre-restore backup of the current live database.
- Verify the selected restore source SHA-256.
- Confirm the restore source is inside the approved backup directory or another explicitly approved path.
- Confirm the restore source is not a stale or unrelated project database.
- Confirm expected counts and integrity checks.
- Record approval evidence in the future audit trail.

After a real restore:

- Run `PRAGMA integrity_check`.
- Run backend `verify_all.py`.
- Verify key table counts.
- Verify frontend can read the restored state.
- Confirm no tokens, raw responses, headers, signatures, or privacy fields were exposed in logs or manifests.

## Required Backup Gates

The following future operations must require a backup before proceeding:

- Schema migrations.
- Naver order write phases.
- Naver order refresh write phases.
- Naver product write expansion phases.
- Batch refresh or batch sync phases.
- Any future credential or permission migration.
- Any future restore operation itself.

## Safety Boundary

This phase keeps the same ERP safety rules:

- No token storage.
- No Authorization storage.
- No request or response header storage.
- No signature or bcrypt input storage.
- No client secret storage.
- No raw platform response storage.
- No full channel number output.
- No full order or product-order id output in manifests.
- No buyer or receiver privacy in manifests.
- Preview and dry-run remain preferred before writes.
- Formal Naver product/order batch sync remains closed unless separately approved.

## Recommended Next Phase

Recommended next phase:

```text
Phase ERP-Backup-1B: Database backup mock verification gate
```

1B should add a mock or temporary-file verification gate that creates a small safe SQLite backup fixture, computes SHA-256, validates a manifest, performs a temporary restore drill, runs integrity checks, and confirms the real `backend/codex1.db` is untouched.
