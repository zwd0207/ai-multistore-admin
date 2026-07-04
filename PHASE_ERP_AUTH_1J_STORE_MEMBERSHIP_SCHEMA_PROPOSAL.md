# Phase ERP-Auth-1J: Store membership schema proposal

## Purpose

Define how future ERP users will be scoped to stores before any real migration.

This phase is proposal-only.

## Proposed Table

### `erp_store_memberships`

Purpose: bind users to stores and roles so every read/write approval can prove store scope.

Allowed fields:

- `id`
- `user_id`
- `store_id`
- `role_id`
- `scope_type`
- `membership_status`
- `assigned_by_user_id`
- `assigned_at`
- `revoked_at`
- `created_at`
- `updated_at`

## First Rules

- `owner` may use `scope_type=all` only after an explicit admin setup phase.
- `admin`, `operator`, `auditor`, and `viewer` must be assigned to specific stores.
- Every runtime permission check must verify `store_id`.
- Store mismatch must block before a write or preview is approved.
- Role assignment changes must be audited in a later phase.

## Indexes

Future migration should include:

- user plus membership status
- store plus membership status
- role membership lookup
- unique active membership shape for user, store, and role

## Boundary

This phase does not create users, assign roles, change schema, write the database, call platform APIs, modify Codex2 runtime code, or open formal Naver sync.

