# Phase Naver-ERP-10A - Naver New Order Candidate Classification Plan

## Summary

Phase 10A defines how to classify a Naver readonly preview result as a possible new local order candidate. It follows Phase 9F, where refresh writing was deferred because the real preview did not match the selected local operational order.

This phase is documentation and planning only. It does not call Naver, does not change Codex1, does not change database schema, does not write `orders`, does not write `products`, does not write `SyncLog`, does not add `tested_success`, does not execute `real_sync=true`, and does not open formal Naver order sync.

## Current Context

Known local state from the latest phases:

- Local operational Naver order remains `PAYED / 499000 KRW`.
- Latest controlled readonly preview observed `DELIVERED / 配送完成 / 330000 KRW`.
- Phase 9E confirmed the previewed product-order safe hash does not match the selected local operational row.
- Phase 9F formally blocked refresh writing for the existing row.

Decision:

- Do not update the existing local operational order from the mismatched preview.
- Treat the mismatched preview only as a possible new order candidate.
- Require a separate candidate classification and duplicate gate before any future write.

## Candidate Classification Goals

The classification step should answer four questions without writing data:

1. Is there a real candidate from the readonly preview?
2. Does the candidate already exist locally?
3. Is the candidate safe enough to enter one-order write planning?
4. What should the operator do next?

## Candidate States

### `no_candidate`

Use when the feed is empty or detail is unavailable.

Action:

- Stop.
- Do not write.
- Wait for a later readonly preview window.

### `candidate_new`

Use when:

- The readonly preview has a product-order safe hash.
- The hash does not match any existing local Naver order.
- Required business fields are present.
- Privacy and raw-response gates pass.

Action:

- Candidate can move to the next readonly repeat phase.
- Still no write in 10A.

### `candidate_duplicate`

Use when:

- The previewed product-order safe hash already exists in local `orders`.

Action:

- Do not create a new row.
- If it matches the selected local row, route back to refresh gate.
- If it matches another local row, require manual review.

### `candidate_ambiguous`

Use when:

- The preview has no comparable safe hash.
- Full product-order identity is missing or not safely comparable.
- Multiple possible local matches exist.

Action:

- Stop.
- Do not write.
- Require a clearer readonly preview or manual identity review.

### `candidate_blocked_privacy`

Use when:

- Raw response would be needed to decide.
- Required privacy flags fail.
- Buyer or address data would need to be persisted beyond the allowed display-only boundary.

Action:

- Stop.
- Do not write.
- Keep complete fields in controlled detail display only.

### `candidate_stale_preview`

Use when:

- The preview is older than the approved window for write planning.
- A newer preview is required before any write decision.

Action:

- Repeat readonly preview in a later phase.

## Minimum Candidate Summary

A candidate summary may contain only safe fields:

- `store_id=8`.
- `platform=naver`.
- product-order safe hash.
- order safe hash if available.
- order status enum and Chinese label.
- payment status if safely observed.
- delivery status and Chinese label if safely observed.
- claim status and Chinese label if safely observed.
- product name and option name if safe.
- quantity.
- order amount.
- currency.
- ordered / paid / last-changed timestamps.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false` for persistence planning.
- classification state.
- duplicate check result.

The candidate summary must not contain raw Naver response bodies, request headers, Authorization values, tokens, client secrets, signatures, bcrypt output, full channel numbers, or platform write payloads.

## Duplicate Check Plan

Before a new-order write can be considered, compare the previewed product-order safe hash against:

- all operational Naver orders for `store_id=8`;
- all isolated mock/test Naver orders for `store_id=8`;
- any future diagnostic include-test order view, if used.

Expected outcomes:

- No match: candidate may be classified as `candidate_new`.
- Match operational row: candidate is not new; route to refresh gate.
- Match mock/test row: stop and require manual review before using it for operational data.
- Missing hash: classify as `candidate_ambiguous`.

## Required Gates Before Any Future Write

A later single new-order write phase may only proceed if all are true:

- User explicitly approves the write phase.
- `backend/codex1.db` is backed up first.
- Candidate is classified as `candidate_new`.
- Candidate duplicate check returns no local match.
- Candidate comes from a fresh readonly complete-field preview.
- One-order limit is enforced.
- Only safe whitelisted fields are persisted.
- Full buyer and receiver fields remain display-only unless a later approved policy changes persistence.
- No address persistence.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- No `SyncLog` write.
- No `tested_success` write.
- No Naver platform order write operation.
- Formal Naver order sync remains closed.

## Frontend Display Plan

Future Codex2 display can show:

- `可能是新订单候选`.
- `已通过/未通过重复检查`.
- `仍需只读复核`.
- `仍需数据库备份和人工批准`.
- `正式订单同步未开放`.

Main pages should not show raw technical fields. Technical details may show safe enum/status metadata such as classification state, duplicate check state, preview window, and safe write flags.

## Recommended Next Stage

Recommended next phase: `Phase Naver-ERP-10B: Naver new order candidate readonly repeat`.

Purpose:

- Repeat a controlled readonly preview for the candidate window.
- Produce a safe candidate summary.
- Perform local duplicate checks.
- Still do not write `orders`.

## Not Allowed

- Do not update the existing local operational order from the mismatched preview.
- Do not create a new local order in 10A.
- Do not open batch order sync.
- Do not execute dispatch, cancel, return, exchange, refund, delivery, sales, settlement, customer-service, or claim write operations.
- Do not store raw response, token, Authorization, request headers, client secret, signature, bcrypt output, access key, secret key, full channel number, or platform write payload.
