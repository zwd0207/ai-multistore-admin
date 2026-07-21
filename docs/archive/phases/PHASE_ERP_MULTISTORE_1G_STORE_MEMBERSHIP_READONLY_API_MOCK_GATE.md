# Phase ERP-Multistore-1G: Store Membership Readonly API Mock Gate

## Purpose

Expose a safe local readonly API gate that lets administrators check whether a store membership assignment would be allowed, without creating users, sessions, roles, or memberships.

## Implemented

- Added `POST /api/v1/permissions/store-membership/readonly-check`.
- The route reads existing auth tables through the runtime mock gate.
- It returns business messages for missing users, duplicate active memberships, blocked checks, and ready-for-later-assignment checks.
- It keeps technical diagnostics available for folded details only.

## Safety Boundary

- No real user creation.
- No store membership write.
- No login/session activation.
- No order/product/SyncLog/tested-success/audit write.
- No platform API call.
- Formal product/order batch sync remains closed.
