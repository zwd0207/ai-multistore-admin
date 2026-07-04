# Phase ERP-Batch-2A: Formal Batch Sync Operator Checklist Consolidation

## Goal

Consolidate the operator checklist required before any future formal product or order batch sync.

## Checklist

Before a formal batch write can be considered, the operator must confirm:

- explicit human approval
- store-scoped permission
- fresh database backup
- latest readonly candidate evidence
- field whitelist verification
- duplicate protection
- rollback or restore plan
- append-only audit evidence plan
- post-write readback plan
- sensitive-field scan

## Boundary

This phase is planning-only.

It does not:

- call Naver
- execute `real_sync=true`
- write orders
- write products
- write SyncLog
- write tested-success records
- write audit rows
- open formal product or order batch sync

## Result

The checklist is now ready to be shown in Codex2 as an operator-facing readonly panel.
