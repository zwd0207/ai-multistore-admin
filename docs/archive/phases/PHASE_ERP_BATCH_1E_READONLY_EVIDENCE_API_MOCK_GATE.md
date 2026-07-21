# Phase ERP-Batch-1E: Readonly evidence API mock gate

## Purpose

Add a private mock gate for the future readonly evidence API used by batch approval screens.

## Implemented Gate

Codex1 now has:

```text
_evaluate_batch_readonly_evidence_api_mock_gate(...)
```

The helper normalizes safe evidence for:

- `naver_product_batch`
- `naver_order_batch`
- `naver_order_refresh_batch`

Allowed output includes safe store id, platform, sync kind, candidate counts, would-create/update/refresh/skip counts, changed field names, duplicate/whitelist flags, and business messages.

## Boundary

No public route is enabled yet. The helper keeps `public_endpoint_enabled=false`, `formal_sync_open=false`, `orders_written=false`, and `products_written=false`.

