# Phase ERP-Auth-1E: Runtime permission API approval plan

## Purpose

Approve a narrow runtime API surface for the already verified role/store permission mock gates.

The goal is not to create a production authentication system yet. The goal is to let Codex2 ask Codex1 for safe, business-readable role and approval states so the UI can explain which actions are visible, disabled, or approval-required.

## Approved Mock API Shape

- `GET /api/v1/permissions/role-inventory`
- `POST /api/v1/permissions/mock-check`
- `POST /api/v1/permissions/sensitive-action/mock-check`

All routes must be mock-gate only:

- no real auth session
- no user table
- no schema migration
- no local business writes
- no platform API calls
- no formal sync opening
- no secret or raw response fields

## Safety Boundary

Responses may include role labels, store-scope verification, permission booleans, approval status, safe skip reason, and business message. Main frontend pages should show Chinese business messages; technical permission keys remain folded.
