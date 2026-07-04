# Phase ERP-Batch-1G: Readonly Evidence API Mock Route Gate

## Result

The batch readonly evidence route is gated with mock-route tests before production use.

## Route

```text
POST /api/v1/batch/readonly-evidence
```

## Gate Rules

- Accepts only safe evidence summaries.
- Rejects sensitive markers such as token, Authorization, headers, signature, raw response, full order id, full product id, buyer privacy, phone, address, and zip code.
- Does not call Naver or other platforms.
- Does not write orders, products, SyncLog, tested-success, audit rows, timeline events, users, or memberships.
- Does not open formal product or order batch sync.

## Status

Route shape and blocked-sensitive-input behavior are covered by `verify_all.py`.
