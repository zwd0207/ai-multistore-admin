# Phase Naver-ERP-11A - Naver Selected New-Order Write Path Plan

## Summary

Phase 11A defines the safe path for a future selected Naver new-order local write. It is a plan and gate-design phase only.

This phase does not call Naver, does not write local data, does not change Codex1, does not change database schema, does not change Codex2 runtime behavior, and does not open formal Naver order sync.

## Background

Phase 10B found a 3-day readonly candidate classified as `candidate_new`.

Phase 10C executed the existing 24-hour one-order write gate. That gate safely returned `already_exists / no_duplicate_created` for the currently visible 24-hour order and did not create a duplicate.

Phase 10D decided not to widen the existing 24-hour `real_sync=true` write gate and not to reuse stale readonly preview responses as persistence payloads.

Phase 11A therefore plans a separate selected-candidate path. This avoids changing the blast radius of the existing write gate while still leaving a controlled route for a manually approved older candidate.

## Goal

Design a future path that can write at most one explicitly selected Naver order candidate after a fresh readonly confirmation.

The path must keep three ideas separate:

- readonly candidate discovery;
- operator candidate selection and approval;
- one-row local persistence.

It must not become formal order sync.

## Recommended Decision

Keep the existing 24-hour `real_sync=true` gate unchanged.

Add no write behavior in 11A.

If a future phase implements selected-candidate writing, it should be a new explicit path with its own request shape, tests, and audit language rather than a silent extension of the existing preview endpoint.

## Future Request Shape

A future selected-candidate write path should require:

- `store_id=8`.
- `credential_id=7`.
- `real_preview=true`.
- `real_sync=true`.
- `include_detail=true`.
- `complete_field_preview=true`.
- `selected_candidate_write=true`.
- one selected safe product-order hash or equivalent non-sensitive candidate identifier.
- a bounded readonly window, initially no wider than 3 days.
- `size=1`.
- no batch mode.

The request must not accept full order ids, full product order ids, buyer names, phone numbers, addresses, raw responses, request headers, Authorization values, tokens, signatures, or client secrets as client-provided persistence data.

## Future Server Flow

A future implementation must:

1. Re-run a fresh readonly feed-to-detail preview inside the approved window.
2. Recompute safe hashes server-side from the fresh detail response.
3. Match the selected safe candidate identifier against the fresh detail.
4. Reject the write if the selected candidate is missing, changed, stale, ambiguous, or not uniquely matched.
5. Run duplicate checks across local operational Naver orders and isolated mock/test rows.
6. Run the privacy gate.
7. Persist only the order field whitelist.
8. Create at most one local order.
9. Leave `products`, `SyncLog`, and `ApiCapabilityTestResult tested_success` unchanged.
10. Execute no Naver platform order write action.

## Required Write Gates

Before any future selected-candidate write, all gates must pass:

- User explicitly approves the selected-candidate write phase.
- `git status` is clean.
- `backend/codex1.db` is backed up.
- Baseline counts are recorded.
- Fresh readonly preview returns HTTP 200 and `preview_status=success`.
- Candidate classification is `candidate_new`.
- Detail count is exactly 1.
- Safe product-order hash is present.
- Safe order hash is present.
- Duplicate match count is 0.
- Privacy fields are redacted.
- Address is not saved.
- Raw response is not saved.
- No full order id or product order id is stored.
- No full buyer or receiver name, phone, or address is stored.
- `orders` increases by at most 1.
- `products` count is unchanged.
- `SyncLog` count is unchanged.
- `tested_success` count is unchanged.
- Sensitive scans pass after the attempt.

If any gate fails, the future path must return a safe blocked status and write nothing.

## Candidate States

The selected-candidate path should keep using the 10A candidate states:

- `no_candidate`.
- `candidate_new`.
- `candidate_duplicate`.
- `candidate_ambiguous`.
- `candidate_blocked_privacy`.
- `candidate_stale_preview`.

Additional selected-write statuses should be:

- `selected_candidate_missing`.
- `selected_candidate_changed`.
- `selected_candidate_not_unique`.
- `selected_candidate_duplicate`.
- `selected_candidate_privacy_blocked`.
- `selected_candidate_write_created`.
- `selected_candidate_write_not_requested`.

## Field Boundary

Allowed persisted fields remain limited to safe order business fields:

- `store_id`.
- `platform=naver`.
- safe hashed external order identifiers.
- order status and Chinese status label.
- delivery and claim status labels when safely observable.
- product and option text when they do not contain buyer privacy.
- quantity.
- order amount.
- currency.
- ordered, paid, and last-changed timestamps.
- source type.
- last synced timestamp.
- mapping version.
- redaction flags.

Forbidden persisted fields:

- full order id.
- full product order id.
- full buyer name.
- full buyer phone.
- full receiver name.
- full receiver phone.
- full address.
- zip code.
- detailed address.
- raw response.
- request headers.
- Authorization.
- token.
- signature or bcrypt output.
- client secret.

## Testing Plan For A Future Implementation

Future code tests must cover:

- selected candidate fresh match creates exactly one order.
- selected candidate stale mismatch writes nothing.
- selected candidate duplicate writes nothing.
- multiple matching candidates writes nothing.
- privacy gate failure writes nothing.
- feed success-empty writes nothing.
- detail failure writes nothing.
- unknown order status does not crash.
- no `SyncLog` row is created.
- no `tested_success` row is created.
- no product row changes.
- sensitive field scan rejects unsafe payloads.

## Recommended Next Phase

Recommended next phase: `Phase Naver-ERP-11B: Selected new-order write mock gate`.

Purpose:

- Add or verify mock-only tests for the selected-candidate gate.
- Keep real Naver API calls disabled.
- Keep local production database writes disabled.
- Prove that stale, duplicate, privacy-blocked, and successful one-row paths are handled before any real selected-candidate write is considered.
