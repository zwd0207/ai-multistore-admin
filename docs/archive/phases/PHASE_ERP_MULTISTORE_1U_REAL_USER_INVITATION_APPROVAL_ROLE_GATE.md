# Phase ERP-Multistore-1U: Real User Invitation Approval Role Gate

## Goal

Make the Accounts user-invitation readiness panel show whether the current administrator role passes the readonly approval gate for a future real invitation.

## Implementation

Codex2 now reads `approval_results` and `approval_role_verified` from the user invitation readonly response.

The Accounts page shows a separate business card:

- "审批角色门禁"
- passed or waiting for approval confirmation
- clear wording that passing the readonly gate does not send an invitation

## Boundary

This phase does not:

- create users
- send invitations
- create sessions
- assign roles
- create store memberships
- write audit rows
- call platform APIs

## Result

Operators can understand whether the future invitation is blocked by role/approval conditions without reading raw technical fields.
