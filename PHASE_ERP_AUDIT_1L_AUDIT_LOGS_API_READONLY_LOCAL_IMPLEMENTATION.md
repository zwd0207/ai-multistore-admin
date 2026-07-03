# Phase ERP-Audit-1L - Audit Logs API Readonly Local Implementation

## Summary

Phase ERP-Audit-1L implements the local read-only audit logs API approved by 1K.

This phase adds only read routes. It does not add audit write routes, delete routes, export routes, frontend readers, schema changes, platform API calls, backup execution, restore execution, or product/order formal sync approval.

The real `backend/codex1.db` remains:

```text
operation_audit_logs=0
```

An empty audit-log response is currently expected and valid.

## Backend Change

Added:

```text
backend/app/api/v1/endpoints/operation_audit_logs.py
```

Updated:

```text
backend/app/api/v1/router.py
backend/app/services/operation_audit_service.py
backend/scripts/verify_all.py
backend/README.md
backend/docs/API_CONTRACT.md
```

## New Readonly Routes

Implemented:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
```

Not implemented:

```text
POST /api/v1/operation-audit-logs
PUT /api/v1/operation-audit-logs
PATCH /api/v1/operation-audit-logs
DELETE /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/{audit_log_id}
```

## Route Behavior

The list route is read-only, returns an empty list plus a Chinese business message when there are no rows, enforces `limit<=50`, supports only bounded filters, rejects unsupported filters without echoing raw unsupported names, rejects unsafe enum-like values, rejects invalid or too-large date windows, keeps advanced details opt-in, and returns business-first rows.

The summary route is read-only and returns total count, status counts, backup evidence count, restore evidence count, attention count, latest audit time, runtime status, and a Chinese business message.

## Response Safety

Main list rows return business labels for actor type, action, target, status, reason, changed fields, counts, backup evidence, safety, and next action.

Advanced details may include only safe enums, local target id, abbreviated target hash, abbreviated correlation id, abbreviated request id, safe changed field names, safe summary field labels, and abbreviated backup or restore SHA-256 values.

The route response does not return raw `before_summary`, raw `after_summary`, raw `counts_summary`, raw `safety_flags`, raw platform payloads, tokens, Authorization values, headers, signatures, client secrets, full platform ids, buyer/receiver privacy, phones, addresses, or zip codes.

## Verified Behavior

`verify_all.py` now verifies:

- OpenAPI contains exactly the approved audit read paths.
- audit paths expose only GET methods.
- empty list route succeeds with business message.
- private temporary audit rows can be read through the route.
- summary route returns expected counts and attention status.
- default and maximum pagination are enforced.
- unsupported query params are rejected without echoing raw names.
- unsafe action values are rejected.
- large date windows are rejected.
- advanced details are opt-in.
- non-GET methods return 405.
- read calls do not write audit rows.
- read calls do not change `orders`, products, `SyncLog`, `tested_success`, or `order_status_events`.
- no platform API is called.

## Still Not Approved

Still closed:

- audit write API.
- audit delete API.
- audit export API.
- frontend audit reader.
- automatic audit writing from business flows.
- broad all-store access for non-admin users.
- full raw JSON detail endpoint.
- backup execution.
- restore execution.
- formal product or order batch sync.
- Naver shipment, cancel, return, exchange, refund, settlement, or other platform writes.

## Verification

- `backend/.venv/Scripts/python.exe scripts/verify_all.py`: passed.
- `operation audit logs readonly local api: ok`.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1M: Audit logs API post-implementation verification
```

1M should verify the newly exposed read-only routes against the real empty audit table, re-check no write methods exist, and prepare the frontend integration plan.
