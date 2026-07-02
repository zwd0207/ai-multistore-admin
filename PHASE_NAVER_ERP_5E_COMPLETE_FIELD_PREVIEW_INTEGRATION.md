# Phase Naver-ERP-5E - Naver Order Complete Field Preview Integration

## Scope

This phase connects Codex2 Orders to the Codex1 Naver complete-field readonly preview added in Phase Naver-ERP-5D.

It does not modify Codex1, does not write orders, does not change database schema, and does not open formal Naver order sync.

## Implemented

- Added a Codex2 backend client method for `POST /api/v1/sync/orders/naver/preview`.
- Added `previewNaverOrderCompleteFields` in the data provider.
- Added a manual Orders-page button: `读取完整字段只读预览`.
- The preview request uses:
  - `store_id=8`
  - `credential_id=7`
  - 24-hour KST window
  - `page=1`
  - `size=1`
  - `real_preview=true`
  - `include_detail=true`
  - `complete_field_preview=true`
  - `real_sync=false`
- The page does not auto-run this preview. A user must click the button.
- The local sanitized order detail remains visible before the preview is clicked.
- If preview fields are available, they override the local sanitized placeholders only in the Orders detail panel.
- Backend mode no longer shows the local mock sync button on the Orders page.
- Orders loading now waits for store context before requesting backend order data, avoiding the misleading order loading failure state.
- Delivery and claim status values are normalized so object-shaped status payloads do not render as `[object Object]`.

## Safety Boundary

- No automatic Naver request on page load.
- No `real_sync=true`.
- No local write from Codex2.
- No `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success` write.
- No raw response, token, Authorization, headers, signature, bcrypt output, or client secret display.
- Complete order/product/buyer fields are shown only in the Orders detail panel after explicit readonly preview.
- Dashboard remains summary-only.
- Formal Naver order sync remains closed.

## Validation

- `npm.cmd run build`
- `VITE_DATA_SOURCE=mock npm.cmd run build`
- `npm.cmd run encoding:scan`
- Browser walkthrough for backend Orders page:
  - no console errors
  - no `订单数据加载失败`
  - no `[object Object]`
  - complete-field readonly preview button is visible
  - no backend mock sync panel
  - no misleading formal-sync-open wording
