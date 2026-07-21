# Phase ERP-Auth-1F: Runtime permission API mock gate

## Implementation

Codex1 now exposes the approved mock permission API routes:

- `GET /api/v1/permissions/role-inventory`
- `POST /api/v1/permissions/mock-check`
- `POST /api/v1/permissions/sensitive-action/mock-check`

The routes wrap the private permission service using the internal verification scope. Callers cannot provide that scope directly.

## Verified Behavior

`verify_all.py` covers:

- role inventory returns owner/admin/operator/auditor/viewer
- admin/operator read-style access can pass when store scope matches
- viewer write-style access is blocked with safe `permission_denied`
- sensitive order refresh write needs manual approval
- admin sensitive approval can pass in mock when approval is true
- sensitive actor context is blocked without leaking the sensitive input

## Safety Flags

Responses keep:

- `mock_permission_api=true`
- `public_endpoint_enabled=true`
- `real_auth_session_created=false`
- `real_database_written=false`
- `orders_written=false`
- `products_written=false`
- `sync_log_written=false`
- `capability_tested_success_written=false`
- `raw_response_saved=false`
- `formal_sync_open=false`
- `platform_writes_enabled=false`

This is still not the final multi-user auth system.
