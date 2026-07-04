# Phase ERP-Batch-1C: Formal batch sync readonly evidence API plan

## Purpose

Plan a future readonly evidence API for formal product/order batch sync approval.

This phase does not implement a public execution endpoint and does not open formal batch sync.

## Proposed Future API Shape

Future approval UI should read safe evidence from a readonly route such as:

```text
GET /api/v1/batch-sync/readonly-evidence
```

Candidate query fields:

```text
store_id
platform
sync_kind
window_label
limit
```

Allowed `sync_kind` values should remain narrow:

```text
naver_order_batch
naver_order_refresh_batch
naver_product_batch
```

## Allowed Response Fields

The response should include only:

- safe evidence id
- store id and safe store label
- platform
- sync kind
- readonly window label
- candidate count
- batch size requested
- would create/update/refresh/skip counts
- changed field names
- duplicate check result
- field whitelist result
- backup requirement state
- permission requirement state
- audit requirement state
- business message
- next action

## Forbidden Response Fields

The response must not include token, Authorization, request/response headers, signature, bcrypt input, client secret, raw response, full channel id, full product/order ids, full buyer or receiver privacy, phones, addresses, or zip codes.

## Gate Boundary

Readonly evidence is not execution approval. A future write phase must still separately require backup evidence, role permission, sensitive-action approval, audit evidence, readback, and sensitive scan.

