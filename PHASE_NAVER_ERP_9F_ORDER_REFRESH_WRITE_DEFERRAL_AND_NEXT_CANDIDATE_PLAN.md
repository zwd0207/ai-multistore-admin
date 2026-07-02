# Phase Naver-ERP-9F - Order Refresh Write Deferral And Next-Candidate Plan

## Summary

Phase 9F formally defers Naver order refresh writing. The current real backend readonly preview does not match the selected local operational order, so a refresh write would be unsafe.

This phase is documentation and planning only. It does not call Naver, does not change Codex1, does not change database schema, does not write `orders`, does not write `products`, does not write `SyncLog`, does not add `tested_success`, does not execute `real_sync=true`, and does not open formal Naver order sync.

## Current Decision

Do not proceed to a one-row order refresh write for the current local operational order.

Reason:

- Local operational Naver order: `PAYED`, `499000 KRW`.
- Latest controlled backend readonly preview: `DELIVERED / 配送完成`, `330000 KRW`.
- Phase 9E confirmed the product-order safe hash does not match the selected local operational order.
- Phase 9D identity gate correctly blocks the refresh review with `不可写库`.

The previewed Naver detail may be a different order candidate. It must not be used to update the existing local operational row.

## Write Deferral Rules

Refresh write remains blocked until all of these are true:

- The selected row is a local operational Naver order, not a mock/test row.
- A complete-field readonly preview has succeeded.
- The previewed product-order identity matches the selected local row.
- Preferred identity check is safe product-order hash equality.
- Full product order number comparison is allowed only when both sides have comparable full values in the controlled Orders detail context.
- Database backup has been completed.
- A human explicitly approves the write phase.
- The write is limited to one row.
- The write payload uses only the safe refresh whitelist.
- No `SyncLog` write.
- No `tested_success` write.
- No Naver platform order write operation.
- `raw_response_saved=false`.
- Formal Naver order sync remains closed.

If identity does not match, the gate must stay blocked even when the readonly preview itself succeeds.

## Next-Candidate Options

There are three safe options from here.

### Option A - Wait For A Matching Readonly Preview

Wait until the selected local operational order appears in a future Naver changed-order feed window, then rerun controlled readonly preview.

Recommended when:

- The goal is specifically to refresh the current local operational order.
- There is no full product-order id available for that local row.
- The operator does not want to create or refresh another candidate.

Boundary:

- Still readonly.
- Still no write.
- Still use `real_sync=false`.

### Option B - Treat The Mismatched Preview As A New Candidate

The 9C/9E previewed detail can be treated as a possible different order candidate, but only under a separate new-order candidate phase.

Recommended when:

- The operator wants to bring the newly observed Naver order into local ERP.
- The candidate is clearly not the existing local operational row.

Required next gates:

- New candidate classification.
- Duplicate check against all local Naver order hashes.
- Complete-field readonly preview.
- One-order write approval only in a later phase.
- No update to the existing local operational row.

### Option C - Manual Full Product-Order Id Review

If the operator can safely identify the exact product-order id for the existing local row from Seller Center or another approved source, a later phase may design a controlled direct detail preview for that single id.

This is not implemented now.

Required before any direct-id route:

- Explicit approval.
- No raw response storage.
- No request header or token output.
- One id only.
- Full id displayed only in the controlled Orders detail area.
- Safe hash comparison before any write.

## Recommended Next Step

Recommended next phase: `Phase Naver-ERP-10A: Naver new order candidate classification plan`.

Reason:

The current refresh path is blocked by identity mismatch. The previewed detail looks like a different Naver order, so the safer path is to classify it as a new candidate first rather than forcing it into the existing local order row.

## Not Recommended

Do not run a refresh write for the current local operational order.

Do not update the existing local order from the mismatched preview.

Do not open batch order sync.

Do not execute dispatch, cancel, return, exchange, refund, delivery, sales, settlement, customer-service, or claim write operations.

Do not rely on mock identity matching as proof that backend real data is safe to write.

## Safety Boundary

This phase stores no raw Naver response, token, Authorization value, request headers, client secret, signature, bcrypt output, access key, secret key, or platform write payload.

Full order and buyer fields remain limited to controlled order-detail display. Dashboard and summary cards remain aggregate-only.
