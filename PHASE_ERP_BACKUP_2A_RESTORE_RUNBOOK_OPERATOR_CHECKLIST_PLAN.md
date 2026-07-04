# Phase ERP-Backup-2A: Restore runbook and operator checklist plan

## Purpose

Prepare a production-friendly restore runbook before any real restore is allowed.

This phase is planning-only.

## Operator Checklist

Before a real restore can be approved, the operator must confirm:

- incident reason and target store/business impact
- current git status and current backend commit
- current production database backup created before restore
- restore source backup exists inside the approved local backup root
- restore source manifest exists and matches the backup file
- SHA-256 and file size match the manifest
- SQLite integrity check passes on a temporary copy
- baseline counts are reviewed
- restore target is explicitly not `backend/codex1.db` during dry-run
- restore dry-run passed
- human approval is recorded
- rollback plan is written down

## Restore Modes

Allowed now:

- report backup inventory
- verify backup manifest
- restore to a temporary file for dry-run

Still closed:

- restore over production database
- delete or cleanup backups
- upload backups
- restore from arbitrary paths
- restore without audit evidence

## Audit Requirements

A future real restore must write append-only audit rows for:

- restore approval
- pre-restore backup creation
- restore source verification
- temporary restore verification
- real restore execution
- post-restore verification

## Boundary

No restore, no backup deletion, no schema migration, no platform API call, no business-data write, no Codex2 runtime change, and no formal sync opening are performed in this phase.

