# Phase ERP-Multistore-2K - Invitation Approval Checklist Readonly API Frontend Integration Plan

## Goal

Plan how Codex2 Accounts should consume the invitation approval checklist readonly API after Codex1 exposes the local route.

## Scope

- Use `POST /api/v1/permissions/user-invitation/approval-checklist/readonly-check`.
- Keep the main Accounts page business-readable.
- Keep route flags, phase names, skipped reasons, and write flags inside `TechnicalDetails`.
- Keep a mock fallback for mock data mode.

## Safety Boundary

- No user creation.
- No invitation sending.
- No auth session creation.
- No role assignment.
- No store membership write.
- No audit-row write.
- Real invitation remains closed.

## Implementation Target

The next phase may add `dataProvider.checkUserInvitationApprovalChecklistReadonly(...)` and route-backed Accounts display.
