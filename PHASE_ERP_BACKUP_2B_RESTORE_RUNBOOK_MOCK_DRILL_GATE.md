# Phase ERP-Backup-2B: Restore runbook mock drill gate

## Result

Codex1 now has a private restore runbook mock drill gate in `backend/app/services/backup_service.py`.

The gate verifies that a future real restore request has the required checklist before any restore can be considered.

## Checked Items

The mock gate requires:

- incident reason recorded
- current git status recorded
- pre-restore backup planned
- source manifest verified
- source SHA-256 verified
- source size verified
- temporary restore dry-run passed
- baseline counts reviewed
- production target blocked during dry-run
- human approval recorded
- audit evidence plan ready
- rollback plan ready
- post-restore verification plan ready

## Blocked Cases

`verify_all.py` covers:

- missing private mock scope
- incomplete checklist
- real restore request inside mock gate
- sensitive input in checklist

## Boundary

The gate does not restore over production, touch `backend/codex1.db`, delete backups, write rows, expose a public API, call platform APIs, or open formal sync.

