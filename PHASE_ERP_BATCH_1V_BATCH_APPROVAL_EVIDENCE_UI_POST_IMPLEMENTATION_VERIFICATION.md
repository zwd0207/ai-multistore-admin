# Phase ERP-Batch-1V: Batch Approval Evidence UI Post-Implementation Verification

## Goal

Verify the Orders page after the readonly batch approval audit-evidence route was integrated.

## Scope

- Codex2 Orders page only.
- Backend and mock data-source walkthrough.
- No real Naver API calls.
- No product, order, SyncLog, tested-success, audit-log, user, or membership writes.
- Formal product and order batch sync remain closed.

## Expected Operator Wording

The main Orders page should show that batch approval evidence and audit evidence are ready for human review, but should not imply that formal batch sync is open.

Business wording must say:

- readonly evidence is for manual review
- audit evidence is only planned or checked
- no audit rows are written by this panel
- no business data is written by this panel
- any later batch write still needs separate approval, backup, permission, readback, and rollback evidence

## Verification Result

Runtime walkthrough should confirm:

- `/orders` opens in backend mode
- `/orders` opens in mock mode
- the Orders page shows Chinese business wording
- `TechnicalDetails` keeps route path, phase, status, `would_*`, and write flags folded
- no misleading "formal batch sync is open" wording appears
- no console errors appear

## Result

This phase is verification-only. It does not change backend contracts and does not write audit rows.
