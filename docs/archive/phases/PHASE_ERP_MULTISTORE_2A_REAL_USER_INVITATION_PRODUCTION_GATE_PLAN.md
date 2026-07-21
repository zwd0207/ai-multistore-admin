# Phase ERP-Multistore-2A: Real User Invitation Production Gate Plan

## Goal

Define the production gate for future real user invitations.

## Required Gate

A future real invitation phase must require:

- explicit human approval
- active admin or owner role
- store-scoped permission
- masked login identifier only
- fresh database backup evidence
- append-only audit evidence plan
- invitation expiry and one-time consumption design
- post-create readback
- rollback or disable-user instructions
- no full email or phone in main UI

## Boundary

This phase is planning-only.

It does not:

- create users
- send invitations
- create auth sessions
- assign roles
- create store memberships
- write audit rows
- call platform APIs

## Result

Real user invitation remains closed until a separate implementation phase is explicitly approved.
