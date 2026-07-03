# Phase Naver-ERP-14C - Orders UI Status Timeline Display Plan

## Summary

Phase 14C plans how Codex2 Orders UI should display future Naver order status timeline data. This phase is display-planning only: it does not modify runtime frontend code, does not call Codex1 or Naver, does not write local data, does not change database schema, and does not open formal Naver order sync.

Current frontend baseline:

- `src/pages/Orders.jsx` already shows Naver order detail, complete-field readonly preview controls, and manual refresh approval affordance.
- `src/utils/naverOrderFulfillment.js` already maps Naver order statuses into seller-facing Chinese business buckets.
- `src/components/common/Timeline.jsx` already exists and can be reused later for a collapsed status-history section.
- `TechnicalDetails` already provides a place for safe technical fields.

## Display Goal

Orders UI must clearly separate:

- current snapshot: what the order status is now.
- future status history: what changed over time.
- refresh gate: whether a future local refresh write is allowed.
- complete-field readonly preview: operator-only full-field review.

The main page must stay seller-friendly. It should not look like a developer console and must not imply that timeline persistence or formal order sync is already available.

## Proposed Layout

Future `Orders.jsx` should display Naver order timeline in this hierarchy:

1. Current order status badge.
2. Current delivery and claim summary.
3. Manual refresh gate status.
4. Collapsed "订单状态历史" section.
5. TechnicalDetails for safe raw enums, hashes, dedupe keys, and gate flags.

Recommended copy for an empty timeline:

```text
当前仅显示本地订单最新状态，状态历史功能尚未写入真实数据。
```

Recommended copy for planned-only timeline:

```text
系统已具备状态历史 mock 识别能力，但真实时间线写入尚未开放。
```

Recommended copy once persistence exists:

```text
以下为本地记录的订单状态变化历史，仅来自受控只读预览与本地刷新结果。
```

## Main Page Rules

Main page may show:

- `已付款 / 新订单`.
- `待发货`.
- `已发货 / 配送中`.
- `配送完成`.
- `取消请求`.
- `退货请求`.
- `换货请求`.
- `已取消`.
- `已确认购买`.
- `状态需人工复核`.
- business time such as "最近观察时间".
- safe source wording such as "本地只读记录".

Main page must not show:

- raw `event_type`.
- raw `status_raw`.
- raw `dedupe_key`.
- raw `mapping_version`.
- `store_id`.
- `credential_id`.
- full order id.
- full product order id.
- buyer or receiver privacy fields.
- phone numbers.
- addresses or zip codes.
- raw response markers.
- token, header, signature, bcrypt, or secret wording.

TechnicalDetails may show safe technical fields:

- safe order hash.
- safe product-order hash.
- `event_type`.
- `status_raw`.
- `delivery_status_raw`.
- `claim_status_raw`.
- `dedupe_key`.
- `mapping_version`.
- `source_phase`.
- `source_type`.
- `raw_response_saved=false`.
- `privacy_fields_redacted=true`.
- `address_saved=false`.
- `formal_order_sync_open=false`.
- `platform_writes_enabled=false`.

## Timeline Item Shape

Future frontend adapter should normalize event rows into:

```text
id
title
description
status
time
tone
technical
```

Example seller-facing entries:

- title: `订单已付款`
- description: `Naver 订单进入新订单状态，等待后续确认或发货处理。`
- status: `已付款 / 新订单`

- title: `配送完成`
- description: `订单已观察到配送完成状态。`
- status: `配送完成`

- title: `取消请求`
- description: `Naver 订单出现取消请求，需要人工查看。当前不执行平台取消操作。`
- status: `取消请求`

- title: `状态需人工复核`
- description: `系统观察到未识别的 Naver 状态，暂不允许刷新写入。`
- status: `需人工复核`

## Event Ordering

Timeline should order events by:

1. `observed_at` descending for UI display.
2. stable fallback by local event id if timestamps tie.
3. no sorting by raw status enum.

If `observed_at` is missing, show:

```text
观察时间待接入
```

and keep the event below entries with known times.

## Refresh Interaction

When a future refresh gate returns planned timeline info, Orders UI should show:

- current snapshot card remains primary.
- planned timeline event is marked as "将记录" or "待写入确认".
- no-change refresh is shown as "状态无变化，本次不会新增历史事件".
- deduped refresh is shown as "该状态历史已存在，不会重复记录".
- unknown status is shown as "状态需人工复核".

Do not show a planned timeline event as already saved.

## Disabled States

Until schema and write phases are approved:

- timeline history section remains collapsed by default.
- write buttons remain disabled.
- no "创建状态历史" action is clickable.
- no "正式订单同步已开放" wording.
- no "自动刷新订单状态" wording.

Suggested disabled note:

```text
状态历史目前处于规划 / mock 验证阶段，尚未写入真实数据库。
```

## Data Source States

Backend data source:

- show real local Naver operational orders only by default.
- keep mock/test orders isolated.
- show current status from local `orders` snapshot.
- show future timeline only after a dedicated read API exists.

Mock data source:

- may include sample timeline entries for visual testing.
- sample entries must be clearly marked as mock/demo.
- mock entries must not imply Naver API was called.

## Component Direction

Future runtime implementation may reuse:

- `src/components/common/Timeline.jsx`.
- `src/components/common/TechnicalDetails.jsx`.
- `src/utils/naverOrderFulfillment.js`.
- `src/pages/Orders.jsx`.

Likely new helper later:

```text
src/utils/naverOrderTimeline.js
```

Suggested helper responsibilities:

- normalize backend event rows.
- map event types to Chinese titles.
- assign UI tone.
- hide technical fields from main page.
- produce TechnicalDetails rows for safe fields only.

## Acceptance Checklist For Later Runtime Phase

Later runtime UI phase should pass:

- Orders page still opens in backend data source.
- Orders page still opens in mock data source.
- current status is visible without opening timeline.
- timeline section is collapsed by default.
- no raw technical fields appear in the main page.
- TechnicalDetails contains only safe fields.
- no raw response, token, header, signature, full order id, buyer privacy, phone, address, or zip code appears.
- no wording says formal order sync is open.
- no wording says status history has been saved before schema/write phases exist.
- encoding scan passes.
- frontend build passes if runtime code changes.

## Next Stage

Recommended next phase: `Phase Naver-ERP-14D: Order status events schema proposal`.

Purpose:

- Propose the future persistence model for status history.
- Keep schema changes separate from UI planning.
- Preserve the current no-write boundary until explicitly approved.
