# Phase ERP-Multistore-2O: Invitation Approval Audit Linkage Readonly API Plan

## Goal

Plan a future readonly API for reviewing real user invitation approval audit linkage.

## Planned Review Evidence

- target user hash
- masked login identifier
- store scope
- target role
- approval actor hash
- permission evidence reference
- backup evidence reference
- invitation expiry policy reference
- readback plan reference
- rollback plan reference
- audit correlation id

## Safety Boundary

The future route must be review-only. It must not send invitations, create users, create auth sessions, assign roles, write store memberships, write audit rows, or open formal sync.

