# Phase ERP-Batch-1Q: Batch Approval Audit Evidence Local Route Plan

Purpose: document the next boundary after the local route mock gate.

Planned future route:

- `POST /api/v1/batch/approval-audit-evidence`
- Readonly local route only.
- Wrap the existing batch approval audit evidence gate.
- Return business readiness wording for manual review screens.

Still closed:

- No route is implemented in this phase.
- No audit row writing.
- No product/order writing.
- No SyncLog or tested-success writing.
- No formal product or order batch sync opening.

Future implementation requirements:

- Must keep `operation_audit_rows_written=false`.
- Must reject sensitive markers and unsafe payloads.
- Must keep `public_endpoint_enabled=true` only when the actual readonly route is intentionally implemented in a later phase.
