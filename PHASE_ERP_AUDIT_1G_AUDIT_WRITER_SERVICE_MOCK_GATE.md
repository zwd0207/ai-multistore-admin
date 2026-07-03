# Phase ERP-Audit-1G - Audit Writer Service Mock Gate

## Summary

Phase ERP-Audit-1G adds a private audit writer service mock gate and verifies it against the temporary `verify_all.py` database only.

This phase does not write real audit rows, does not write business rows, does not change schema, does not create a backup, does not add a public audit endpoint, does not add a frontend audit reader, does not call platform APIs, and does not open formal product or order sync.

## Backend Change

Added:

```text
backend/app/services/operation_audit_service.py
```

The service exposes a private helper:

```text
write_operation_audit_log_mock_gate(...)
```

The helper is intentionally blocked by default. It writes only when all of these are true:

- `write_enabled=true`.
- `manual_approval=true`.
- `verification_scope="verify_all_temp_db"`.
- required fields are present.
- `created_at` and `updated_at` are valid datetimes or ISO datetime strings.
- backup/restore SHA-256 fields are valid when present.
- `raw_response_saved=false`.
- `secrets_saved=false`.
- `privacy_fields_redacted=true`.
- non-blocked rows have `sensitive_scan_passed=true`.
- JSON summaries contain no forbidden sensitive fields or values.

If the private verification scope is missing, the helper returns:

```text
skip_reason=runtime_writer_not_enabled
```

This keeps runtime audit writing closed until a later separately approved phase.

## Verified Mock Gate Behavior

`verify_all.py` now covers:

- write not requested -> no row.
- runtime scope missing -> blocked.
- manual approval missing -> blocked.
- missing required fields -> blocked.
- invalid SHA-256 -> blocked.
- unsafe saved flags -> blocked.
- privacy not redacted -> blocked.
- sensitive scan not passed -> blocked.
- sensitive JSON payload -> blocked without echoing sensitive values.
- approved safe row -> written to temporary verification database only.
- blocked-operation evidence row -> written to temporary verification database only.
- shared `correlation_id` chain works.
- `orders`, products, `SyncLog`, `tested_success`, and `order_status_events` counts remain unchanged.

## Real Database Boundary

The real `backend/codex1.db` remains unchanged by this phase:

```text
operation_audit_logs=0
products=9
orders=9
sync_logs=47
tested_success=8
order_status_events=0
```

No public endpoint is registered for audit logs.

## Safety Boundary

The service blocks audit payloads containing:

- tokens.
- Authorization values.
- request or response headers.
- signatures.
- bcrypt inputs.
- client secrets.
- raw request bodies.
- raw response bodies.
- full channel numbers.
- full order ids.
- full product-order ids.
- buyer or receiver full names.
- phone numbers.
- addresses.
- zip codes.

Allowed values remain limited to safe hashes, local ids, field names, counts, booleans, safe status enums, Chinese business labels, backup metadata, and safe reason codes.

## Verification

- `backend/.venv/Scripts/python.exe scripts/verify_all.py`: passed.
- `operation audit writer service mock gate: ok`.
- `npm.cmd run encoding:scan`: passed.
- `git diff --check`: passed.
- sensitive and misleading wording scans: passed.

Frontend build was not required because no frontend runtime code changed.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1H: Audit writer local implementation
```

1H should decide which real local operations are allowed to write audit rows first, and must keep public audit endpoints and broad automation closed unless separately approved.
