# Phase Naver-ERP-20A: Controlled Order Refresh Batch With Audit Approval Plan

Naver-ERP-20A plans the next controlled Naver order refresh batch write path.

## Scope

This phase is planning-only:

- No Naver API call
- No `real_sync=true`
- No orders/products/SyncLog/tested-success write
- No audit row write
- No schema change
- No Codex2 runtime change
- Formal Naver order sync remains closed

## Baseline

The system now has:

- `orders_store8=7`
- `products_store8=5`
- `sync_logs_store8=1`
- `tested_success_store8=8`
- `operation_audit_logs=10`
- one selected Naver new-order local write with audit evidence

## Future Approval Requirements

A later controlled refresh batch write may be considered only if all conditions pass:

- clean worktrees;
- fresh database backup and manifest;
- fresh readonly Naver order preview;
- refresh candidates match existing local real Naver orders;
- candidate count stays within the approved small batch limit;
- every candidate has a safe hash;
- no duplicate candidate hashes;
- privacy gate passes for every candidate;
- unknown status is blocked for manual review;
- role permission gate allows the actor for the selected store;
- sensitive action approval gate passes;
- five-row operation audit chain is prepared;
- post-write readback and sensitive scan are required.

## Still Closed

This plan does not open:

- formal Naver order batch sync;
- formal Naver product batch sync;
- shipment/cancel/return/exchange platform writes;
- settlement/customer-service/mail/appeal/AI automation;
- restore/delete backup actions.

## Recommended Next Stage

`Phase Naver-ERP-20B: Controlled order refresh batch readonly repeat`

20B should be readonly-only. It should identify at most a small set of existing local Naver orders that are safe refresh candidates before any write phase is considered.
