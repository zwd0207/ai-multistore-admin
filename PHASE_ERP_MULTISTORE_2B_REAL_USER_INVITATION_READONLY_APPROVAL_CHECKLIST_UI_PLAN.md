# Phase ERP-Multistore-2B: Real User Invitation Readonly Approval Checklist UI Plan

## Goal

Plan a readonly approval checklist UI for future real user invitations.

## Proposed Checklist

Before a real invitation can be sent, the UI should show:

- target login identifier is masked
- target user hash is safe
- target role is allowed
- target stores are scoped
- admin or owner approval is present
- backup evidence is ready
- audit evidence plan is ready
- invitation expiry is configured
- one-time consumption is configured
- post-create readback is required
- disable-user or rollback instruction is ready

## Safety Boundary

This phase is planning-only.

It does not:

- send invitations
- create users
- create auth sessions
- assign roles
- create store memberships
- write audit rows
- expose full email or phone

## Result

The current Accounts user invitation panel remains readonly. A later implementation may add the production approval checklist while keeping real invitation closed.
