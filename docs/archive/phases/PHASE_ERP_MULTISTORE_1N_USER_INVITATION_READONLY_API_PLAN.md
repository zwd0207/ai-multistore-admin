# Phase ERP-Multistore-1N: User Invitation Readonly API Plan

## Purpose

Plan a future readonly API that can show whether a user invitation is ready for administrator approval.

## Future API Direction

A later phase may expose a readonly endpoint that wraps the private invitation mock gate. It should return only:

- Business message.
- Target role.
- Target store count.
- Masked login identifier.
- Approval readiness.
- Backup and audit planning readiness.
- Safe skip reason.

## Must Not Return

- Plain login identifier.
- Password material.
- Invitation secret.
- Raw request or response payloads.
- Platform credentials.
- Buyer or receiver privacy data.

## Not Approved

This phase does not implement a public route. Real user invitation remains closed.

