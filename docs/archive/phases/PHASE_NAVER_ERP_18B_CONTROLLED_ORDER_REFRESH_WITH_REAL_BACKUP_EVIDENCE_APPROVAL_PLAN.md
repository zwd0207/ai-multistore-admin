# Phase Naver-ERP-18B: Controlled order refresh with real backup evidence approval plan

## Scope

Naver-ERP-18B plans a later controlled order refresh write that must use real backup evidence before any local update.

This phase is planning-only. It does not call Naver, does not execute `real_sync=true`, does not write local orders, does not write timeline events, does not write `SyncLog`, does not write `ApiCapabilityTestResult`, does not change schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Future Gate

A later write phase may proceed only if all of the following are true:

- user explicitly approves the write phase;
- Codex1 and Codex2 worktrees are clean;
- a real local backup is created immediately before the write;
- backup manifest exists and passes safety checks;
- backup SHA-256 is valid;
- SQLite integrity is `ok`;
- backup evidence passes the Naver-ERP-18A gate;
- a fresh readonly Naver order refresh candidate set exists;
- candidates match existing local real Naver orders by safe hash;
- no new-order candidate is mixed into refresh;
- duplicate hashes are blocked;
- privacy gate passes;
- status and field whitelist gates pass;
- max write count is explicitly capped;
- no partial writes in the first real small refresh write;
- post-write readback verifies changed fields and safety booleans.

## Write Boundary For Later Phase

The later write phase may update only safe local order refresh fields:

- status, delivery status, claim status, payment status;
- quantity and amount;
- safe product and option text;
- ordered/paid/last changed timestamps;
- last synced timestamp;
- sanitized metadata flags.

It must not save platform raw responses, tokens, request or response headers, signatures, client secrets, complete buyer/receiver privacy fields, addresses, zip codes, or complete platform ids in audit/backup evidence.

## Still Not Approved

- Formal Naver order sync.
- New-order creation in the refresh path.
- Naver shipment/cancel/return/exchange platform writes.
- Batch size expansion beyond a separately approved small window.
- Automatic scheduled refresh.

