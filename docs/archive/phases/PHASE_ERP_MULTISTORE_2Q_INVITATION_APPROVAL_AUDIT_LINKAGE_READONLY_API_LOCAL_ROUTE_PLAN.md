# Phase ERP-Multistore-2Q: Invitation Approval Audit Linkage Readonly API Local Route Plan

## Goal

Plan a future local readonly route for invitation approval audit-linkage evidence.

## Planned Route

```text
POST /api/v1/permissions/user-invitation/approval-audit-linkage/readonly-check
```

The route may wrap `evaluate_real_user_invitation_approval_audit_linkage_readonly_api_mock_gate(...)` in a later phase.

## Safety Boundary

This phase does not expose the route, send invitations, create users, create auth sessions, assign roles, write store memberships, write audit rows, or open formal sync.

