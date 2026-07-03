# Phase Naver-ERP-17B - Orders UI Claim/Delivery Wording Check

## Summary

Phase 17B verifies and fixes the frontend wording for Naver delivery and claim status display.

This phase does not call Naver, does not execute `real_sync=true`, does not write local business rows, does not modify database schema, does not modify Codex1 backend runtime behavior, and does not open formal Naver order sync. It only updates Codex2 frontend display mapping and documentation.

## Why This Phase Was Needed

Phase 17A taught the backend that `COLLECT_DONE` means `售后取件完成`. The existing frontend could still show stale sanitized labels or raw enums in the Orders detail area when reading historical local rows written before 17A.

During the 17B browser walk-through, the selected written order showed:

- claim status correctly as `售后取件完成`.
- delivery status incorrectly as raw enum `DELIVERY_COMPLETION`.

17B fixes that frontend display gap.

## Frontend Changes

Updated frontend display behavior:

- `DELIVERY_COMPLETION` now displays as `配送完成`.
- `COLLECT_DONE` now displays as `售后取件完成` even if older sanitized raw_data still contains the previous unknown label.
- `COLLECT_REQUEST` displays as `售后取件请求`.
- `COLLECTING` displays as `售后取件中`.
- `RETURN_DONE` / `RETURNED` display as `退货完成`.
- `EXCHANGE_DONE` / `EXCHANGED` display as `换货完成`.
- Orders detail fields prefer current business mapping from safe raw enum over stale historical unknown labels.
- Recent complete-field preview display uses the same business mapping.
- Timeline display descriptions also prefer business labels in the main UI.

Technical raw enums are still available only in collapsed technical details.

## Browser Walk-Through

Checked `/orders` against the local frontend:

- page opened successfully.
- selected Naver store displayed 3 operational Naver orders.
- the written order safe hash was selectable.
- delivery status displayed as `配送完成`.
- claim status displayed as `售后取件完成`.
- main page did not show `DELIVERY_COMPLETION`.
- main page did not show `COLLECT_DONE`.
- main page did not show `DELIVERED`.
- main page did not show `未识别状态，需人工确认`.
- main page did not claim formal order sync, automatic sync, or batch write approval is open.

Checked `/dashboard`:

- page opened successfully.
- Dashboard showed 3 Naver operational orders.
- delivery summary used Chinese business wording.
- claim summary used Chinese business wording.
- Dashboard did not show raw Naver enums in the main area.
- Dashboard did not claim formal order sync, automatic sync, or platform write actions are open.

## Verification

- `npm.cmd run build`: passed.
- `VITE_DATA_SOURCE=mock npm.cmd run build`: passed with PowerShell environment-variable syntax.
- `npm.cmd run encoding:scan`: passed.
- `git diff --check`: passed.
- Misleading copy scan did not find claims that formal batch sync, automatic shipment, or automatic after-sales actions are open.
- Diff-only sensitive scan did not find newly added token, Authorization, client secret, signature, bcrypt, or raw response payload values.

## Safety Boundary

This phase does not approve:

- formal Naver order sync.
- batch order sync.
- automatic selected-candidate writes.
- existing-order refresh batch writes.
- timeline event insertion.
- shipment, cancel, return, exchange, refund, delivery, settlement, sales, customer-service, or any other Naver platform write operation.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1D: Audit log schema migration approval plan
```

The Naver order display path is now clearer for operators, so the next production-readiness priority should return to audit accountability before expanding more writes.
