# Phase ERP-Multistore-2H: Invitation Approval Checklist Readonly API Local Implementation Plan

## Purpose

Plan the future local readonly API implementation for invitation approval checklists.

## Planned Route

```text
POST /api/v1/permissions/user-invitation/approval-checklist/readonly-check
```

## Planned Behavior

The route should return masked login display, role/store scope, approval readiness, backup evidence, audit plan, expiry, one-time invite, readback, rollback, and safety flags.

## Boundary

- No route in this phase.
- No user creation.
- No invitation sent.
- No auth session.
- No role or membership write.
- No audit-row write.

## Result

Real user invitation remains closed while the future readonly API contract is prepared.
