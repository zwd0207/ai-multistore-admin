# Phase ERP-Audit-1K - Audit Logs API Readonly Implementation Approval Plan

## Summary

Phase ERP-Audit-1K defines the approval boundary for a future local read-only audit logs API implementation.

This phase is documentation-only. It does not add a route, does not register an `APIRouter`, does not query audit logs from runtime UI, does not write audit rows, does not modify schema, does not call platform APIs, and does not open product or order formal sync.

The current real database must remain:

```text
operation_audit_logs=0
```

## Approved Direction For 1L

The next implementation phase may add local read-only audit endpoints only if it keeps the exact 1J safety shape:

```text
GET /api/v1/operation-audit-logs
GET /api/v1/operation-audit-logs/summary
```

Optional detail endpoint remains deferred:

```text
GET /api/v1/operation-audit-logs/{audit_log_id}
```

1L may expose list and summary routes for local backend use only. It must not expose write routes, export routes, delete routes, restore routes, or any platform operation.

## Files Allowed In 1L

Allowed backend implementation files:

- `backend/app/api/v1/endpoints/operation_audit_logs.py`
- `backend/app/api/v1/router.py`
- `backend/app/services/operation_audit_service.py`
- `backend/scripts/verify_all.py`
- `backend/README.md`
- `backend/docs/API_CONTRACT.md`

Allowed project documentation:

- `README.md`
- a new `PHASE_ERP_AUDIT_1L_...md` phase document.

Not allowed in 1L unless separately approved:

- Codex2 frontend runtime files.
- database schema migrations.
- business write services.
- Naver or Coupang clients.
- backup or restore execution scripts.
- auth/permission model rewrites.

## Route Behavior Requirements

`GET /api/v1/operation-audit-logs` must:

- be read-only.
- return an empty list plus a Chinese business message when the table has zero rows.
- keep default `limit=20` and maximum `limit=50`.
- support bounded filters only: `store_id`, `platform`, `status`, `target_type`, `action`, `actor_type`, `date_from`, `date_to`, `correlation_id`, `limit`, `offset`, and `include_advanced`.
- reject unsupported filters.
- reject unsafe enum-like values.
- reject invalid or too-large date windows.
- return business-first list rows.
- keep raw JSON summaries out of the default response.
- include advanced details only when explicitly requested.

`GET /api/v1/operation-audit-logs/summary` must:

- be read-only.
- return total count, status counts, backup evidence count, restore evidence count, attention count, latest audit time, runtime status, and a Chinese business message.
- return `audit_runtime_status=empty` when the table has zero rows.
- not expose raw payloads or sensitive fields.

## Response Safety Boundary

Main list rows may include:

- `id`.
- `created_at`.
- `store_id`.
- store and platform labels.
- actor label and actor type label.
- action, target, status, reason, changed-field, count, backup evidence, safety, and next-action Chinese labels.
- pagination metadata.
- business message.

Advanced details may include:

- safe enums such as `action`, `status`, `reason_code`, `operation_phase`, and `target_type`.
- local numeric target id.
- abbreviated `target_hash`, `correlation_id`, and `request_id`.
- safe changed field names.
- safe summary field labels.
- abbreviated backup or restore SHA-256 values.

Advanced details must not include raw `before_summary`, raw `after_summary`, raw `counts_summary`, or raw `safety_flags`.

## Sensitive Data Ban

The route response, logs, docs, and tests must not contain:

- token.
- access token or refresh token.
- Authorization.
- request headers.
- response headers.
- signature.
- bcrypt.
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
- raw platform payloads.

## Empty Real Database Behavior

Because the real table currently has `operation_audit_logs=0`, the first local route implementation is expected to return:

```json
{
  "items": [],
  "total": 0,
  "business_message": "当前还没有操作审计记录。后续受控写入、备份、恢复等操作接入后会显示在这里。"
}
```

This empty state is a valid success condition. It must not be treated as an error, missing migration, failed backend, or reason to write a seed audit row.

## Verification Required In 1L

1L must extend `verify_all.py` to prove:

- OpenAPI includes only the approved read-only audit paths.
- no POST/PUT/PATCH/DELETE audit routes exist.
- empty real-like audit result returns success with business message.
- private mock rows can be read through the route in the temporary verification database.
- default pagination and maximum limit are enforced.
- unsupported filters are rejected.
- unsafe values are rejected.
- advanced details are opt-in.
- responses do not contain raw summaries or sensitive fields.
- no audit rows are written by read calls.
- no `orders`, products, `SyncLog`, `tested_success`, or `order_status_events` rows are changed.
- no platform API is called.

## Runtime And Permission Assumptions

The first route implementation may use the current local backend dependency style. Full multi-user role permissions are still not complete, so 1L must document that:

- the route is for local/admin use first.
- future multi-user production usage requires a separate permission phase.
- store-scoped filtering is implemented, but not a substitute for full RBAC.
- all-store audit views remain admin-only by policy until role management is implemented.

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

## Go / No-Go Checklist For 1L

Before 1L can be considered complete:

- `python scripts/verify_all.py` passes.
- `git diff --check` passes.
- encoding scan passes.
- sensitive response scan passes.
- misleading wording scan passes.
- real `operation_audit_logs` count remains unchanged.
- no frontend runtime files are modified unless a separate UI phase is approved.
- git status is clean after commit.

## Recommended Next Stage

Recommended next stage:

```text
Phase ERP-Audit-1L: Audit logs API readonly local implementation
```

1L should add the read-only list and summary routes using the 1J service response shape, with no write route and no frontend integration.
