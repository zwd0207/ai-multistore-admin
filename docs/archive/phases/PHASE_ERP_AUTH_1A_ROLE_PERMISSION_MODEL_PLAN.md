# Phase ERP-Auth-1A: Role and Permission Model Plan

ERP-Auth-1A defines the first production-oriented role model for the local ERP.

## Scope

This phase is planning-only:

- No schema change
- No real user table
- No public auth route
- No platform API call
- No business-data write
- No Codex2 runtime behavior change

## Roles

The first role set is intentionally small:

- `owner`: all stores, all local ERP actions, can approve sensitive actions.
- `admin`: assigned stores, operational reads/previews, controlled order writes/refreshes, backup creation, can approve selected sensitive actions.
- `operator`: assigned stores, normal reads and previews, cannot approve sensitive writes.
- `auditor`: assigned stores, audit/backup/order/product readonly access.
- `viewer`: assigned stores, dashboard/order/product readonly access only.

## Permission Groups

The first permission groups are:

- `dashboard.read`
- `products.read`
- `products.preview`
- `orders.read`
- `orders.preview`
- `orders.local_write`
- `orders.refresh_batch_write`
- `audit.read`
- `backup.read`
- `backup.create`
- `database.restore`
- `credentials.update`
- `schema.migrate`
- `formal_sync.open`

Sensitive actions require explicit approval and a role that is allowed to approve that action.

## Store Scope

Every permission decision must check `store_id`.

- `owner` may cover all stores.
- Other roles must have the requested store in their assigned store list.
- Store mismatch must block before operation permission is evaluated as approved.

## Safety Boundary

The model must never use or expose token, Authorization, headers, signature, bcrypt input, client secret, raw external response, full platform identifiers, or buyer/receiver privacy.

## Next Stage

`Phase ERP-Auth-1B: Store-scoped access gate mock`
