# Phase Naver-Order-Batch-1B: Order batch readonly candidate window

## Purpose

Run a controlled Naver order readonly candidate window for future batch planning.

## Execution

Request shape:

```text
store_id=8
credential_id=7
window=recent 3 days KST
page=1
size=1
include_detail=true
complete_field_preview=false
real_preview=true
real_sync=false
```

The existing guardrail still allows only one readonly candidate at a time for this endpoint.

## Result

- HTTP result: `200`
- preview status: `success`
- safe observed order hash: `id-hash-192b9c67e8`
- would create: `0`
- would update: `0`
- local sync status: `not_requested`
- orders written: `false`
- SyncLog written: `false`
- tested-success written: `false`
- formal order sync open: `false`

Business message:

```text
Naver 订单接口已连接。本次只完成订单只读预览，没有写入本地订单。
```

## Boundary

This phase is readonly evidence only. It does not write orders, does not create timeline events, does not write SyncLog, does not add tested-success rows, and does not open formal Naver order batch sync.

