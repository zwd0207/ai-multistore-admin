# Phase ERP-Audit-1J - Audit Logs API Readonly Mock Gate

## Summary

Phase ERP-Audit-1J adds private mock-gate verification for the future read-only `operation_audit_logs` API response shape.

This phase does not add a public endpoint, does not register an `APIRouter`, does not add a frontend reader, does not write real audit rows, does not modify schema, does not call platform APIs, and does not open product or order formal sync.

The real `backend/codex1.db` remains unchanged by this phase:

```text
operation_audit_logs=0
```

## Backend Change

Updated:

```text
backend/app/services/operation_audit_service.py
backend/scripts/verify_all.py
```

The service now exposes private verification helpers:

```text
list_operation_audit_logs_readonly_mock_gate(...)
summarize_operation_audit_logs_readonly_mock_gate(...)
```

Both helpers require the private verification scope and are not reachable from public HTTP routes.

## Verified Readonly Behavior

`verify_all.py` now proves:

- missing private scope blocks read access.
- unsupported filters are rejected.
- unsafe action filters are rejected.
- invalid date windows are rejected.
- empty results return a Chinese business message rather than an error.
- default and maximum pagination are bounded.
- store/platform/status/action/target/correlation filters work in private tests.
- list rows are business-first and do not expose raw JSON summaries by default.
- advanced details contain only safe enums, abbreviated hashes, abbreviated SHA-256 values, and safe summary field labels.
- summary response reports total rows, status counts, backup evidence count, restore evidence count, latest audit time, and attention status.
- no `orders`, products, `SyncLog`, `tested_success`, or `order_status_events` rows are changed.

## Response Boundary

The mock list response may return:

- business labels for actor type, action, target, status, reason, changed fields, counts, backup evidence, safety, and next action.
- safe local ids.
- store and platform labels.
- bounded pagination metadata.
- a business empty-state message.

Folded advanced details may return:

- `action`.
- `status`.
- `reason_code`.
- `operation_phase`.
- `target_type`.
- `target_id`.
- abbreviated `target_hash`.
- abbreviated `correlation_id`.
- abbreviated `request_id`.
- safe changed field names.
- safe summary field labels.
- abbreviated backup or restore SHA-256 metadata.

The read response intentionally does not return raw `before_summary`, raw `after_summary`, raw `counts_summary`, or raw `safety_flags`.

## Sensitive Field Ban

The read mock gate verifies the response does not contain:

- token.
- access token or refresh token.
- Authorization.
- request or response headers.
- signature.
- bcrypt.
- client secret.
- raw request body.
- raw response body.
- full channel number.
- full order id.
- full product-order id.
- buyer or receiver full name.
- full phone number.
- address.
- zip code.

## Still Not Approved

Still closed:

- public audit logs endpoint.
- runtime `/api/v1/operation-audit-logs` route.
- frontend audit log reader.
- automatic audit writing from business flows.
- broad all-store audit access.
- full JSON audit export.
- real audit row writes from runtime operations.
- backup execution.
- restore execution.
- formal product or order batch sync.
- Naver shipment, cancel, return, exchange, refund, settlement, or other platform writes.

## Verification

- `backend/.venv/Scripts/python.exe scripts/verify_all.py`: passed.
- `operation audit logs readonly mock gate: ok`.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1K: Audit logs API readonly implementation approval plan
```

1K should define the exact approval boundary for exposing the read-only route locally, including route path, auth/permission assumptions, empty real-database behavior, and a final sensitive-field response scan.
