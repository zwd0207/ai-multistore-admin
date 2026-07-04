# Phase ERP-Multistore-1V: User Invitation Audit Evidence Plan

## Goal

Make the Accounts user-invitation readiness panel show the audit-evidence plan required before any future real user invitation.

## Implementation

Codex2 now shows a separate business card:

- "审计证据计划"
- backup evidence planned
- audit evidence planned
- membership assignment plan ready
- operation audit rows planned but not written

## Future Real Invitation Gate

A later real invitation phase must still require:

- explicit user approval
- store-scoped role permission
- fresh database backup evidence
- append-only audit evidence
- safe masked login identifier
- invite expiry and one-time consumption design
- post-create readback
- rollback or disable-user instructions

## Boundary

This phase remains readonly. It writes no users, memberships, role assignments, auth sessions, or audit rows.

## Result

The UI is clearer for non-technical operators while preserving the production safety boundary.
