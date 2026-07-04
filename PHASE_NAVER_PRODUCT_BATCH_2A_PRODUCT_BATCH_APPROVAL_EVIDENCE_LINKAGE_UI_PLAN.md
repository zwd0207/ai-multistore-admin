# Phase Naver-Product-Batch-2A: Product Batch Approval Evidence Linkage UI Plan

## Goal

Plan a Codex2 UI surface that links product batch approval evidence before any future Naver product batch write.

## Evidence To Link

The UI should show:

- latest readonly product candidates
- product changed fields
- product field whitelist
- backup evidence
- rollback readonly report
- temporary restore or restore drill evidence
- audit correlation
- post-write readback plan
- sensitive-field scan

## Boundary

This phase is planning-only and does not:

- call Naver
- write products
- restore a database
- write audit rows
- write SyncLog
- write tested-success records
- open formal product batch sync

## Result

The implementation may add a readonly Products-page panel, but it must remain a planning and review surface only.
