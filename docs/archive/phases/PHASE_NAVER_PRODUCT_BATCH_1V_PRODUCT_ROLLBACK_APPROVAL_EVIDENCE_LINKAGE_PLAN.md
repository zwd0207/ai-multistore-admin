# Phase Naver-Product-Batch-1V: Product Rollback Approval Evidence Linkage Plan

## Goal

Plan how the product rollback readonly report should connect to future product batch approval evidence.

## Boundary

This phase is planning-only.

It must not:

- execute restore
- create or restore backups
- write products
- write orders
- write SyncLog
- write tested-success records
- write operation audit rows
- call Naver
- open formal product batch sync

## Future Linkage

A future product batch write approval screen should link three kinds of evidence before any write:

1. Pre-write evidence:
   - readonly candidates
   - changed fields
   - field whitelist
   - duplicate protection
   - store scope
   - permission check

2. Safety evidence:
   - verified backup manifest
   - rollback readonly report
   - restore dry-run or temporary database drill result
   - sensitive-field scan

3. Post-write evidence:
   - readback counts
   - changed row count
   - skipped row count
   - audit record correlation id
   - operator-facing result summary

## UI Rule

The Products page may show a business summary of rollback readiness, but route paths, phase keys, skip reasons, and write flags must remain in folded technical details.

## Result

The next implementation phase may add a readonly evidence-link panel, but it still must not perform restore or product writes.
