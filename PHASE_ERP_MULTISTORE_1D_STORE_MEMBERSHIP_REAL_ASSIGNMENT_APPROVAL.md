# Phase ERP-Multistore-1D: Store Membership Real Assignment Approval

## Purpose

Define the approval boundary before creating real store membership rows.

## Required Before Real Assignment

- Real user identity must exist.
- Target user must use a safe user hash, not secrets or raw login material.
- Target store and role must be explicit.
- Admin approval for `store_membership.assign` is required.
- Duplicate active memberships must be blocked.
- Audit evidence and rollback notes must be prepared.

## Current Status

No real user or store membership row is created in this phase. Large-scale multi-store production operation remains closed.
