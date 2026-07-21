# Phase ERP-Auth-1L: Auth schema migration approval plan

## Purpose

Approve the narrow local migration for the ERP auth foundation tables.

This phase is approval planning only.

## Approved Migration Scope

The next implementation may create only:

- `erp_users`
- `erp_roles`
- `erp_permissions`
- `erp_role_permissions`
- `erp_store_memberships`

The migration may seed only system role and permission metadata:

- roles: `owner`, `admin`, `operator`, `auditor`, `viewer`
- safe permission keys from the existing mock permission service
- role-permission links

## Explicitly Not Approved

The migration must not:

- create real users
- assign store memberships
- create login sessions
- add password flows
- expose public login APIs
- connect route-level production auth
- change Naver sync behavior
- write products, orders, SyncLog, tested-success records, or timeline rows

## Required Gate

Before migration:

- git status must be clean
- `backend/codex1.db` must be backed up
- backup manifest must be written
- backup integrity must be `ok`
- `verify_all.py` must pass on a temporary database

After migration:

- auth tables must exist
- system role and permission seeds must exist
- `erp_users=0`
- `erp_store_memberships=0`
- business table counts must stay stable
- formal sync remains closed

## Boundary

No platform API call, no business-data write, no real restore, no Codex2 runtime change, and no formal sync opening are performed in this phase.

