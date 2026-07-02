# Phase Naver-ERP-5G - Controlled Order Complete-Field Preview Window

## Scope

This phase adds a bounded preview-window control to the Codex2 Orders page for the existing Naver order complete-field readonly preview.

It does not modify Codex1, does not write orders, does not change database schema, and does not open formal Naver order sync.

## Implemented

- Added a preview window selector beside `读取完整字段只读预览`.
- Allowed windows are:
  - `最近 24 小时`
  - `最近 3 天`
  - `最近 7 天`
- The preview still runs only after the operator clicks the button.
- The selected window is converted to KST `start_datetime` / `end_datetime`.
- The request remains constrained to:
  - `store_id=8`
  - `credential_id=7`
  - `page=1`
  - `size=1`
  - `real_preview=true`
  - `include_detail=true`
  - `complete_field_preview=true`
  - `real_sync=false`
- The UI records the selected window in technical details only.
- Empty preview messages now mention the selected window.

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
- `git diff --check`
- Browser walkthrough for backend Orders page:
  - no console errors
  - no `订单数据加载失败`
  - no `[object Object]`
  - the preview window selector is visible
  - complete-field readonly preview remains manual
  - no backend mock sync panel
  - no misleading formal-sync-open wording
