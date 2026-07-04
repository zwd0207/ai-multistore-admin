# Phase ERP-Multistore-1F: Store Membership Assignment Readonly API Plan

## Purpose

Plan a future readonly API that can tell administrators whether a store-membership assignment would be allowed, without creating users or memberships.

## Planned API Direction

- Read target user, target role, target store, existing active membership, and approval readiness.
- Return safe booleans such as `target_user_exists`, `target_role_exists`, `duplicate_active_membership`, and `membership_would_create`.
- Keep `membership_written=false` and `real_database_written=false`.

## Deferred

- Real user creation.
- Real role assignment.
- Real store membership creation.
- Login/session enforcement.
- Large-scale multi-store production operation.
