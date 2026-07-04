# Phase ERP-Multistore-2M - Invitation Approval Audit Linkage Plan

## Goal

Plan how a future real user invitation approval should link to audit evidence before any user, role, or store-membership write.

## Required Linkage

- Invitation approval decision id.
- Target user safe hash.
- Masked login identifier.
- Store scope and target role.
- Approval actor hash.
- Permission evidence.
- Backup evidence.
- Invitation expiry policy.
- Readback plan.
- Rollback plan.
- Audit correlation id.

## Safety Boundary

This phase is plan-only. It does not create users, send invitations, create auth sessions, assign roles, write memberships, or write audit rows.
