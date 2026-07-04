# Phase ERP-Multistore-2J - Invitation Approval Checklist Readonly API Local Implementation

## Goal

Expose a local readonly API for reviewing real-user invitation approval checklist readiness.

## Completed

Codex1 now exposes:

```text
POST /api/v1/permissions/user-invitation/approval-checklist/readonly-check
```

The route accepts masked login display, target user/login hashes, store scope, role, manual approval, approval checklist, readonly API context, and existing-user hashes.

## Safety Result

- It does not create users.
- It does not send invitations.
- It does not create auth sessions.
- It does not assign roles.
- It does not write store memberships.
- It does not write audit rows.
- It does not open formal sync.
- It keeps secrets and raw responses out of the response.

This route is review-only and does not replace a future real invitation approval/write phase.
