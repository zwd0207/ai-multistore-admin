# Phase ERP-Multistore-2L - Invitation Approval Checklist Readonly API Frontend Integration

## Goal

Connect the Accounts user invitation panel to the invitation approval checklist readonly API.

## Completed

- Added `backendApi.checkUserInvitationApprovalChecklistReadonly(...)`.
- Added data-provider adaptation and mock fallback.
- Added Accounts runtime display for checklist readiness.
- Kept the existing base invitation readonly check as a separate signal.

## User-Facing Behavior

Accounts now shows whether invitation approval checklist materials are ready for review. It states that no user will be created, no invitation will be sent, and no store membership will be assigned.

## Safety Result

- No real invitation.
- No user/auth/session/role/membership write.
- No audit-row write.
- Technical route and write flags stay folded.
