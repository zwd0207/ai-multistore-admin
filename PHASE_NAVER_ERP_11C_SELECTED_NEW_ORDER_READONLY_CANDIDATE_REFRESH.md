# Phase Naver-ERP-11C - Selected New-Order Readonly Candidate Refresh

## Summary

Phase 11C re-ran the selected new-order candidate refresh as a real readonly preview. The phase did not request `real_sync=true`, did not write local data, did not modify Codex1, did not modify Codex2 runtime behavior, and did not open formal Naver order sync.

The captured readonly result was blocked before the order feed by Naver API IP allow-list classification:

- backend HTTP result: 200.
- `preview_status=failed`.
- `error_code=ip_not_allowed`.
- `feed_called=false`.
- `detail_called=false`.
- `local_sync_result.status=not_requested`.
- `orders_written=false`.
- `raw_response_saved=false`.

Because feed and detail were not called, 11C could not confirm whether the older 3-day `candidate_new` from 10B is still visible.

## Request Boundary

The request used the existing Codex1 order preview endpoint:

- `POST /api/v1/sync/orders/naver/preview`.
- `store_id=8`.
- `credential_id=7`.
- KST window: `2026-06-30T14:38:00.547+09:00` to `2026-07-03T14:38:00.547+09:00`.
- `order_status=ALL`.
- `page=1`.
- `size=1`.
- `real_preview=true`.
- `include_detail=true`.
- `complete_field_preview=true`.
- `real_sync=false`.

The first command attempt did not emit a terminal summary, so the same readonly boundary was retried to capture a safe result. No write request was sent.

## No-Write Verification

Post-run local counts stayed unchanged:

- `orders_store8=4`.
- Naver orders for store 8: 4.
- real Naver local orders for store 8: 1.
- mock Naver orders for store 8: 3.
- `products_store8=5`.
- `sync_logs_store8=1`.
- `tested_success_store8=8`.

The response reported:

- `sync_log_written=false`.
- `capability_tested_success_written=false`.
- `formal_order_sync_open=false`.
- `complete_field_preview.save_plan.orders_written=false`.
- `complete_field_preview.save_plan.raw_response_saved=false`.

## Sensitive Data Boundary

This phase did not print or persist raw responses, tokens, request headers, Authorization values, signatures, bcrypt output, client secrets, access keys, secret keys, full order ids, full product order ids, full buyer names, full phones, or addresses.

Store 8 order data still has zero keyword hits for:

- token.
- client_secret.
- authorization.
- headers.
- signature.
- bcrypt.
- access_key.
- secret_key.

## Interpretation

11C is blocked by environment/API allow-list state, not by selected-candidate logic. The correct next action is to fix or confirm the Naver Commerce API Center API allowed IP setting before retrying 11C.

Do not proceed to selected-candidate write approval or local persistence while 11C cannot reach the order feed.

## Recommended Next Phase

Recommended next phase: `Phase Naver-ERP-11C-Retry: Selected new-order readonly candidate refresh after IP allow-list check`.

Purpose:

- Keep `real_sync=false`.
- Re-run the same readonly preview after the API allowed IP is confirmed.
- Confirm whether the candidate is `candidate_new`, duplicate, missing, stale, or blocked.
- Continue no local write and no formal order sync.
