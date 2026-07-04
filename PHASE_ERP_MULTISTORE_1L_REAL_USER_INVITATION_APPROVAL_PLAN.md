# Phase ERP-Multistore-1L: Real User Invitation Approval Plan

## Purpose

Define the approval boundary for a future real user invitation flow. This is required before multi-user and multi-store production operation can be opened.

## Current Decision

Real user invitation remains closed. The current system may show readonly readiness checks, but it must not create users, login sessions, role assignments, or store memberships.

## Future Gate

A later invitation implementation must require:

- Explicit operator approval.
- Store-scoped role permission.
- A verified database backup.
- Append-only audit evidence.
- Invitation link or invitation code expiry and one-time-use checks.
- Safe display of user identifiers.
- No plaintext password, invite secret, API secret, raw response, or platform credential exposure.
- Post-create readback verification.
- Rollback or disable-user instructions.

## Not Approved

- Production login.
- Real user creation.
- Real membership assignment.
- Role assignment UI.
- Route-level authorization enforcement.
- Large-scale multi-store operation.

## Result

This phase is planning-only and writes no data.
