# Phase ERP-Multistore-2E: Invitation Approval Checklist Readonly API Plan

## Purpose

Plan a future readonly API for real-user invitation approval checklists.

## Planned Route

```text
POST /api/v1/permissions/user-invitation/approval-checklist/readonly-check
```

## Planned Behavior

The route should show:

- Masked login identifier.
- Target role and store scope.
- Approval role readiness.
- Backup evidence readiness.
- Audit evidence plan.
- Invite expiry and one-time invite requirement.
- Post-create readback requirement.
- Rollback or disable-user instruction.
- Safety flags proving no real invitation was sent.

## Boundary

- No route in this phase.
- No user creation.
- No invitation sent.
- No auth session created.
- No role or membership write.
- No audit-row write.

## Next Step

A later route implementation can wrap the 2C mock gate after the UI wording and safety contract are approved.
