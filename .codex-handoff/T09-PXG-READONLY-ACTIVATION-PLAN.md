# T09 PXG/Naver Readonly Activation Plan

Status: planning only. Real readonly persistence remains disabled.
Scope: one store, PXG Naver only.

## Model Allocation

### Sol - policy and final gate

- Confirm retention and deletion policy.
- Confirm the first-sync limit and rollback conditions.
- Confirm which operator role may approve persistence.
- Review the final evidence and decide whether activation is allowed.

### Terra - backend and verification

- Add activation checklist enforcement.
- Add bounded first-sync limits and a dry-run mode.
- Add backup and rollback evidence before persistence.
- Verify store isolation, stale data, idempotency, audit records, and disabled writes.
- Do not enable the production flag.

### Luna - operator UI after Terra contract

- Show readonly status, last refresh, stale warnings, and blocked actions.
- Show only masked order, logistics, and inquiry data.
- Add a clear manual confirmation screen for the first local persistence.
- Do not display or handle complete recipient data.

## Parallel Work

1. Sol: decide policy and activation acceptance criteria.
2. Terra: prepare dry-run, backup, rollback, and feature-flag checks using fictional data only.

These tasks may run in parallel because Terra must keep the real persistence flag disabled and use the existing contract.

## Ordered Work

1. Sol completes the policy contract.
2. Terra applies the approved policy and runs backend verification.
3. Luna implements the UI against Terra's stable response contract.
4. Terra runs full integration and security verification.
5. Sol performs final acceptance.
6. Commander decides whether to enable one bounded real readonly sync.

## Activation Gate

Activation is forbidden until all are true:

- Retention is explicitly approved.
- Backup and rollback are verified.
- First sync is limited to PXG Naver and a small bounded batch.
- Ordinary responses remain masked.
- Warehouse recipient access still requires the existing approval path.
- All platform writes, customer sends, and AI automation remain disabled.
- Operator browser verification passes.

## Reporting

Each worker returns only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`
