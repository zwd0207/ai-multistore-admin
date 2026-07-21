# Phase Naver-ERP-10D - Naver New-Order Write Window Decision

## Summary

Phase 10D is a decision and documentation phase for the Naver new-order write window. It does not call Naver, does not write local data, does not change Codex1, does not change database schema, and does not open formal Naver order sync.

Decision:

- Keep the existing Codex1 `real_sync=true` Naver order write gate capped to a 24-hour window.
- Do not force-write the 3-day `candidate_new` observed in Phase 10B through the current 24-hour write gate.
- Do not reuse an old readonly preview response as a write payload.
- If a 3-day candidate must be considered for local persistence, require a separate selected-candidate write path with a fresh readonly preview, duplicate checks, privacy gates, database backup, and explicit approval.

## Inputs

Phase 10B found a readonly candidate:

- Window: recent 3 days in KST.
- `real_sync=false`.
- Classification: `candidate_new`.
- Status: `DELIVERED / 配送完成`.
- Amount: `330000 KRW`.
- Local duplicate check: zero matches across operational and mock/test Naver orders.
- No local counters changed.

Phase 10C executed the existing one-order write gate:

- Window: recent 23 hours 55 minutes in KST.
- `real_sync=true`.
- Result: HTTP 200 with `preview_status=success`.
- The 24-hour detail matched an existing local order.
- `local_sync_result.status=already_exists`.
- `no_duplicate_created=true`.
- `orders_written=false`.
- No local counters changed.

## Decision Rationale

The 10B and 10C results describe two different windows:

- 10B proves a 3-day readonly candidate may exist.
- 10C proves the approved 24-hour write gate correctly blocks duplicates.

Those results should not be merged into one write operation. A wider write window has more risk because it can pick older orders, stale details, already-handled orders, or a different candidate than the one the operator intended to approve.

Therefore, the safe decision is to preserve the 24-hour write limit and treat any wider candidate write as a new controlled feature, not as a parameter change to the existing generic preview endpoint.

## Current Gate Status

Allowed today:

- Readonly preview with a controlled window.
- One-order detail preview.
- Existing 24-hour `real_sync=true` duplicate-protected write gate.
- No-op duplicate result such as `already_exists / no_duplicate_created`.

Not allowed today:

- Automatic formal order sync.
- Automatic order refresh writing.
- Automatic 3-day candidate writing.
- Multi-order write.
- Reusing stale preview payloads for persistence.
- Any Naver platform order write action such as dispatch, cancel, return, exchange, or refund.

## Future Selected-Candidate Write Requirements

If the 3-day `candidate_new` should be considered again, the next phase must require all of the following:

- Explicit user approval naming the phase and one-order limit.
- Database backup before any write attempt.
- Fresh readonly preview immediately before the write decision.
- `store_id=8` and `credential_id=7`.
- `page=1`, `size=1`, `include_detail=true`.
- Candidate classification remains `candidate_new`.
- Safe product-order hash and order hash are present.
- Duplicate checks return zero matches across local operational Naver orders and mock/test Naver orders.
- Privacy gate passes.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- Only whitelisted safe fields are persisted.
- `orders` can increase by at most 1.
- `products`, `SyncLog`, and `ApiCapabilityTestResult tested_success` stay unchanged.
- No Naver platform write action is executed.
- Sensitive scans pass after the attempt.

## Rejected Options

Rejected: simply raising the existing 24-hour write window to 3 days.

Reason: it changes the blast radius of the existing write endpoint and can select an unintended older candidate.

Rejected: forcing the 10B readonly response into the database.

Reason: the response was collected under `real_sync=false` and was not a persistence payload.

Rejected: opening formal order sync now.

Reason: only one operational Naver order has been written locally, and the current flow still needs controlled candidate selection, repeatable duplicate checks, audit documentation, and UI review before wider sync can be considered.

## Recommended Next Phase

Recommended next phase: `Phase Naver-ERP-10E: Naver selected new-order write path plan`.

Purpose:

- Design a separate selected-candidate write path without changing the existing 24-hour gate.
- Keep the first 10E step documentation/test-plan only unless explicitly approved otherwise.
- Decide whether the operator should prefer waiting for a fresh 24-hour order candidate or approving a dedicated 3-day selected-candidate path.
- Preserve duplicate prevention and formal sync closure.
