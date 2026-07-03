# Phase ERP-Audit-1I - Audit Logs API Readonly Plan

## Summary

Phase ERP-Audit-1I plans the future read-only API for `operation_audit_logs`.

This phase is planning-only. It does not add a route, expose a public audit API, query audit logs from runtime UI, write audit rows, modify schema, call platform APIs, or open product or order formal sync.

The current real database still has:

```text
operation_audit_logs=0
```

## Goal

The future API should let operators answer:

- who approved or performed a local ERP operation.
- what store, platform, and business object were affected.
- when it happened.
- whether the result succeeded, failed, blocked, skipped, or was only planned.
- whether backup or restore evidence exists.
- what safe business fields or counts changed.
- what the next safe action should be.

It must not make non-technical users read raw backend enums, hashes, payloads, or sensitive identifiers on the main page.

## Proposed Endpoints

Future endpoint candidates:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
GET /api/v1/operation-audit-logs/{audit_log_id}
```

These endpoints are not implemented in this phase.

## Readonly Query Rules

`GET /api/v1/operation-audit-logs` should accept only bounded filters:

- `store_id`: optional; must be scoped by future permissions.
- `platform`: optional enum such as `naver` or `coupang`.
- `status`: optional safe enum.
- `target_type`: optional safe enum.
- `action`: optional safe enum.
- `actor_type`: optional safe enum.
- `date_from` / `date_to`: optional ISO datetime window.
- `correlation_id`: optional exact safe id for advanced investigation.
- `limit`: default 20, maximum 50.
- `offset` or cursor: bounded pagination only.

The endpoint must not accept raw SQL, free-form JSON filters, platform request payloads, or unbounded export flags.

## Proposed List Response

The main response should be business-first:

```json
{
  "items": [
    {
      "id": 1,
      "created_at": "2026-07-03T10:00:00+09:00",
      "store_id": 8,
      "store_label": "pxg球包店",
      "platform": "naver",
      "platform_label": "Naver",
      "actor_label": "管理员",
      "actor_type_label": "人工操作",
      "action_label_zh": "订单刷新写入",
      "target_label": "Naver 订单",
      "status_label_zh": "已完成",
      "reason_label_zh": null,
      "changed_fields_label_zh": ["订单状态", "最近同步时间"],
      "counts_summary_label_zh": "更新 1 条订单",
      "backup_evidence_label_zh": "写入前已备份",
      "safety_label_zh": "未保存敏感原文",
      "next_action_label_zh": "无需处理"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "business_message": "已显示安全审计记录。"
}
```

If there are no rows, the response should be:

```json
{
  "items": [],
  "total": 0,
  "business_message": "当前还没有操作审计记录。后续受控写入、备份、恢复等操作接入后会显示在这里。"
}
```

## Advanced Details

Advanced details may include safe technical fields only in folded UI sections or diagnostic responses:

- `action`.
- `status`.
- `reason_code`.
- `operation_phase`.
- `target_type`.
- `target_id`.
- masked or abbreviated `target_hash`.
- masked or abbreviated `correlation_id`.
- masked or abbreviated `request_id`.
- `changed_field_names`.
- safe `counts_summary`.
- safe `safety_flags`.
- backup path basename or approved local path.
- abbreviated backup SHA-256.
- abbreviated restore SHA-256.

The default list response should not include full JSON summaries. A future detail endpoint may return sanitized summaries only after a separate mock gate proves sensitive fields are removed.

## Sensitive Data Boundary

The API must never return:

- token.
- Authorization.
- request headers.
- response headers.
- signature.
- bcrypt input or output.
- client secret.
- raw request body.
- raw response body.
- full channel number.
- full order id.
- full product-order id.
- full product id when sensitive.
- buyer or receiver full name.
- full phone number.
- address.
- zip code.
- raw before/after payloads containing platform data.

`before_summary`, `after_summary`, `counts_summary`, and `safety_flags` must be sanitized before response serialization.

## Store And Permission Boundary

The future API should be store-scoped:

- ordinary operators should see only stores they are allowed to operate.
- admin users may filter by store, but should still see business labels first.
- all-store audit views should require an explicit admin mode.
- store-less rows such as backup or schema operations should be visible only to admin users.

Until permissions are implemented, the first mock gate should keep the API private and local-test-only.

## Summary Endpoint

`GET /api/v1/operation-audit-logs/summary` should support Dashboard or Logs summary cards:

- total audit rows.
- rows by status label.
- recent failed or blocked operations.
- backup evidence count.
- restore evidence count.
- latest local write audit time.
- latest schema or backup audit time.
- `audit_runtime_status`: `not_connected`, `empty`, `available`, or `needs_attention`.

This endpoint must not expose raw hashes, payloads, or sensitive fields.

## Verification Plan For 1J

The next phase should add mock coverage only:

- temporary audit rows can be listed safely.
- empty real-like result returns a business message.
- default limit is bounded.
- maximum limit is enforced.
- date filters are bounded and validated.
- store/platform/status/action filters work.
- unsafe filter values are rejected.
- response fields are business-first.
- advanced fields are safe and not present in the main list by default.
- sanitized summaries do not contain sensitive keys or values.
- no rows are written.
- no platform API is called.
- no `orders`, products, `SyncLog`, `tested_success`, or `order_status_events` rows are changed.

## Still Not Approved

Still closed:

- public audit logs endpoint.
- frontend audit logs reader.
- automatic audit writing from business flows.
- broad all-store audit access.
- full JSON audit export.
- backup execution.
- restore execution.
- formal product or order batch sync.
- Naver shipment, cancel, return, exchange, refund, settlement, or other platform writes.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1J: Audit logs API readonly mock gate
```

1J should add private mock verification for the proposed read-only response shape before any route is exposed to runtime users.
