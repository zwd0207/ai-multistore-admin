# Phase ERP-Multistore-1H: Store Membership Readonly API Local Implementation Plan

## Purpose

Define how the new store membership readonly API should be used before any real membership assignment phase.

## Local Implementation Boundary

- The readonly API may be called by future admin UI screens to show whether an assignment is ready, duplicated, or blocked.
- It requires a safe target user hash, store id, target role, manual approval flag, and assignment reason.
- A successful result means only that a later explicit write phase may be planned.

## Deferred

- Real user invitation.
- Real role assignment.
- Real store membership creation.
- Route-level production authentication.
- Large-scale multi-store rollout.
