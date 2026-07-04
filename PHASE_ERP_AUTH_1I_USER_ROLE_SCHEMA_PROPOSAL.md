# Phase ERP-Auth-1I: User and role schema proposal

## Purpose

Define the first production-auth schema shape for local ERP users and roles before any real migration.

This phase is proposal-only.

## Proposed Tables

### `erp_users`

Purpose: identify a human or service operator without storing secrets.

Allowed fields:

- `id`
- `user_key_hash`
- `display_name`
- `login_identifier_hash`
- `login_identifier_masked`
- `status`
- `auth_provider`
- `last_login_at`
- `created_at`
- `updated_at`

Explicitly excluded from this first schema:

- plaintext password
- token
- Authorization
- headers
- signature
- bcrypt input
- client secret
- raw response
- full buyer or receiver privacy
- full platform order or product identifiers

### `erp_roles`

Purpose: keep the first ERP role inventory as database-managed records.

Initial system roles:

- `owner`
- `admin`
- `operator`
- `auditor`
- `viewer`

Allowed fields:

- `id`
- `role_key`
- `role_label_zh`
- `role_label_en`
- `system_role`
- `status`
- `created_at`
- `updated_at`

### `erp_permissions`

Purpose: record safe permission keys such as `orders.read`, `orders.refresh_batch_write`, `backup.create`, and `audit.read`.

Allowed fields:

- `id`
- `permission_key`
- `permission_group`
- `permission_label_zh`
- `sensitive_action`
- `status`
- `created_at`
- `updated_at`

### `erp_role_permissions`

Purpose: connect roles to permissions and mark whether a role can approve a sensitive action.

Allowed fields:

- `id`
- `role_id`
- `permission_id`
- `can_approve_sensitive`
- `created_at`
- `updated_at`

## Gate Before Real Migration

A future real migration must require:

- database backup and manifest
- clean git status
- schema diff review
- temporary database mock migration pass
- sensitive-column scan
- rollback plan
- post-migration readback
- no public login route until route-level auth is separately approved

## Boundary

No schema migration, no real auth session, no password flow, no database write to production, no Codex2 runtime change, no Naver API call, and no formal sync opening are performed in this phase.

