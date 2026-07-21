# Phase Naver-ERP-9D - Order Refresh Candidate Match Gate

## Summary

Phase 9D turns the Phase 9C finding into a frontend safety gate. A Naver order complete-field readonly preview is no longer enough to enter refresh-write manual review. The previewed order must also match the selected local operational Naver order.

This phase does not call Naver, does not change Codex1, does not write `orders`, does not write `products`, does not write `SyncLog`, does not add `tested_success`, and does not open formal Naver order sync.

## Why This Gate Was Needed

Phase 9C proved that the controlled readonly feed-to-detail path still works, but the previewed detail observed `DELIVERED / 配送完成` and `330000 KRW`, while the current local operational order remained `PAYED` and `499000 KRW`.

That means a successful preview by itself does not prove that the previewed Naver detail belongs to the selected local order. A later refresh write must not update the local row unless identity matching is proven first.

## Implementation

Codex2 now reads safe identity metadata from the existing Codex1 preview response:

- `detail_preview.external_product_order_id_hash`
- `detail_preview.product_order_id_hash`
- complete-field `external_product_order_id` only as a fallback when the local row also has a comparable full product order number

The Orders page compares that preview identity with the selected local order:

- Preferred match: preview product-order hash equals local product-order hash.
- Fallback match: preview full product order number equals local full product order number.
- If no comparable safe identity exists, the gate is blocked.
- If identities differ, the gate is blocked.

## User-Facing Behavior

The `Naver 订单刷新写库门禁计划` block now includes `订单身份匹配`.

Possible outcomes:

- `待只读预览`: no preview has been run yet.
- `身份匹配`: the preview can move to manual review, but still does not write.
- `身份不匹配`: refresh write is blocked.
- `身份无法确认`: refresh write is blocked until comparable identity metadata exists.

Even when identity matches, the page still requires database backup and explicit manual approval before a future write phase.

## Technical Boundary

Technical details may show safe booleans and labels only:

- `identity_match_state`
- `identity_matched`
- `identity_comparable`
- `identity_match_method`

The page does not print raw response bodies, request headers, Authorization values, client secrets, signatures, bcrypt output, or platform tokens. Full IDs can remain in the controlled order detail area, but the gate itself uses safe match status rather than exposing raw comparison payloads.

## Verification

Backend-source Orders page:

- Page opened without white screen.
- No browser console errors were observed.
- The gate shows `订单身份匹配`.
- Before a readonly preview is run, identity matching remains `待准备`.
- The page still states that formal order sync is not open.

Mock-source Orders page:

- Page opened without white screen.
- No browser console errors were observed.
- After the existing mock complete-field readonly preview, the selected pxg Naver order matched by full product order number.
- The gate moved to `可进入人工审核，不会自行写库`.
- The gate still showed no `orders`, `SyncLog`, or `tested_success` write.

Build and scan:

- `npm.cmd run build`: passed.
- `VITE_DATA_SOURCE=mock npm.cmd run build`: passed.
- `npm.cmd run encoding:scan`: passed.
- `git diff --check`: passed.

## Next Stage

Recommended next phase: `Phase Naver-ERP-9E: Order refresh match walkthrough`.

Purpose: verify the new identity gate in backend and mock pages. Backend should remain blocked unless the previewed detail matches the selected local operational order. Mock can demonstrate the matched path without calling Naver or writing data.
