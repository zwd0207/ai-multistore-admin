# Phase ERP-Multistore-2D: Real User Invitation Approval Checklist UI Implementation Plan

## Purpose

Plan how Codex2 should display the future real-user invitation approval checklist for non-technical administrators.

## UI Plan

The UI should show:

- Masked login identifier only.
- Target role and target store scope.
- Admin approval requirement.
- Backup evidence readiness.
- Audit evidence plan.
- Invite expiry and one-time consumption requirement.
- Post-create readback requirement.
- Rollback or disable-user instruction.
- Clear status that real invitation remains closed until a later implementation phase.

## Technical Details

Hashes, skip reasons, checklist flags, route paths, and write flags should stay in folded details. The main page should only show business wording.

## Boundary

- This phase adds no new invitation send button.
- No user, session, role, or membership write.
- No audit-row write.
- No production login system change.

## Next Step

A later implementation phase can extend the existing Accounts readonly invitation panel with this checklist once the backend route contract is approved.
