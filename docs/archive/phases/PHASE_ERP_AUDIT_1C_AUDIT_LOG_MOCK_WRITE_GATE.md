# Phase ERP-Audit-1C - Audit Log Mock Write Gate

## Summary

Phase ERP-Audit-1C validates the future `operation_audit_logs` write gate in a temporary verification database only.

This phase does not create or alter the real `backend/codex1.db` schema, does not add a SQLAlchemy model, does not run a migration, does not expose an endpoint, does not write real audit rows, does not call platform APIs, and does not change backup or restore runtime behavior.

## Scope

The mock gate is implemented in Codex1 `backend/scripts/verify_all.py`.

It creates `operation_audit_logs` only inside the isolated SQLite database used by `verify_all.py`.

## Verified Behavior

- Required columns exist.
- Required `NOT NULL` fields are enforced.
- Default values are safe:
  - `environment='local'`.
  - `sensitive_scan_passed=false`.
  - `raw_response_saved=false`.
  - `secrets_saved=false`.
  - `privacy_fields_redacted=true`.
- Planned indexes exist.
- Normal audit rows do not use a uniqueness constraint, because multiple rows may share one `correlation_id`.
- Empty `action` values are rejected.
- Invalid `backup_sha256` / `restore_source_sha256` values are blocked by the mock write gate.
- `write_enabled=false` writes nothing.
- `manual_approval=false` writes nothing.
- Safe mock audit rows can be inserted.
- A blocked-operation evidence row can be inserted without storing the blocked sensitive payload.
- Multiple safe rows can share one `correlation_id`.
- `orders`, products, `SyncLog`, and `ApiCapabilityTestResult tested_success` counts remain unchanged.

## Sensitive Boundary

The mock gate rejects sensitive JSON keys or values related to:

- token.
- Authorization.
- headers.
- signature.
- bcrypt.
- client secret.
- raw request.
- raw response.
- raw data.
- full channel number.
- full order id.
- full product-order id.
- buyer or receiver identity.
- phone number.
- address.
- zip code.

The test also scans persisted mock audit rows and gate responses to confirm sensitive marker values are not retained.

## Result

ERP-Audit-1C proves the schema proposal is testable and that a future runtime audit writer should be able to record safe accountability metadata while blocking unsafe payloads.

The real migration remains deferred to a later explicitly approved phase.
