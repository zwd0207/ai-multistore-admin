# Phase Naver-ERP-5F - Complete Field Readonly Preview Walkthrough

## Scope

This phase verifies the Codex2 Orders page integration with the Codex1 Naver complete-field readonly preview.

It does not modify Codex1, does not write orders, does not change database schema, and does not open formal Naver order sync.

## Walkthrough Result

- Backend source was active.
- Selected store was `store_id=8` / `pxg球包店`.
- The Orders page loaded without console errors.
- The page did not show `订单数据加载失败`.
- The `读取完整字段只读预览` button was visible.
- The first click exposed a frontend adapter wiring issue: the named adapter existed but was not included in the default adapter object.
- Fixed the adapter default export so `dataProvider.previewNaverOrderCompleteFields` can adapt the Codex1 response.
- Re-ran the readonly preview from the Orders page.
- The preview no longer throws the adapter error.
- The current 24-hour window returned no available complete-field detail for display, and the page showed the safe empty message.
- Local sanitized order details stayed visible.
- No `[object Object]` status rendering appeared.
- No misleading formal-sync-open wording appeared.

## Safety Confirmation

Database counts were unchanged before and after the walkthrough:

```text
orders_store8=4
products_store8=5
sync_logs_store8=1
tested_success_store8=8
```

The walkthrough did not write `orders`, `products`, `SyncLog`, or `ApiCapabilityTestResult tested_success`.

The page did not display token, Authorization, client secret, request headers, signature, bcrypt output, or raw response content.

## Follow-up

Do not move to complete-field persistence yet. The next useful step is either:

- rerun this readonly preview when a fresh Naver order change exists in the 24-hour window, or
- add a separately approved bounded-window preview control before any complete-field write design.
