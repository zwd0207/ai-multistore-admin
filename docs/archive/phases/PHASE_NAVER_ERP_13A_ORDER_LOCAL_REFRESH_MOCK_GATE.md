# Phase Naver-ERP-13A - Naver Order Local Refresh Mock Gate

## Summary

Phase 13A adds a private Codex1 mock-testable gate for a future Naver local order refresh path. It is not wired to a public endpoint, does not call Naver, does not modify Codex2 runtime behavior, and does not open formal Naver order sync.

The gate is only exercised inside `verify_all.py` with the temporary verification database.

## Gate Rules

The local refresh mock gate requires:

- a selected local order hash.
- a fresh readonly preview.
- matching `external_product_order_id_hash`.
- exactly one existing local Naver order for `store_id=8`.
- privacy gate success.
- manual approval before a mock update can run.
- safe field whitelist only.

The gate blocks:

- stale preview.
- missing selected order hash.
- missing preview.
- identity mismatch.
- local order not found.
- non-unique local order.
- privacy gate failure.
- write-enabled requests without manual approval.

## Mock Write Behavior

When `write_enabled=true` and `manual_approval=true`, the helper can update exactly one existing order in the temporary verification database.

It must not:

- create another order.
- write products.
- write SyncLog.
- add `ApiCapabilityTestResult tested_success`.
- save raw response data.
- save token, Authorization, request headers, signature, bcrypt output, or client secret.
- open formal order sync.
- execute any Naver platform write action.

## Verification

`verify_all.py` now covers:

- readonly refresh not requested.
- stale preview blocked.
- identity mismatch blocked.
- missing local order blocked.
- privacy failure blocked.
- manual approval required.
- one-row mock refresh success.
- no-change repeat refresh.
- sensitive field scan of the refreshed row.

## Next Stage

Recommended next phase: `Phase Naver-ERP-13B: Naver order local refresh approval plan`.

Purpose:

- Document how a real selected local order refresh would be approved later.
- Keep it planning-only unless the user explicitly approves a real write phase.
- Keep formal Naver order sync and platform writes closed.
