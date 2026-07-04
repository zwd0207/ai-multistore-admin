# Phase Naver-ERP-20C: Controlled order refresh batch write approval

## Decision

This phase is approval planning only. It does not execute a local refresh write.

20B confirmed one existing local refresh candidate by safe hash, so a later controlled refresh write may be considered, but only under a separate execution phase.

## Required Gate For A Future Write

A future controlled refresh write must still pass:

- clean git worktrees
- fresh database backup and backup manifest evidence
- fresh readonly Naver repeat for the same selected safe hash
- exact identity match to an existing local Naver order
- store-scoped role permission check
- sensitive action approval by an allowed role
- privacy gate and raw-response safety gate
- one small batch only, with no partial-write ambiguity
- append-only audit evidence
- post-write readback
- sensitive field scan

## Still Closed

- Formal Naver order batch sync remains closed.
- Platform shipment, cancel, return, exchange, refund, settlement, mail, appeal, and AI actions remain closed.
- This phase writes no `orders`, `products`, `SyncLog`, `ApiCapabilityTestResult tested_success`, audit rows, or timeline events.
