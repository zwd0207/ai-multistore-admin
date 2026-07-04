# Phase ERP-Multistore-1I: Store Membership Readonly API UI Plan

## Purpose

Plan a business-first UI surface for the store membership readonly API before any real membership assignment work.

## UI Direction

- Show whether the selected store membership check is ready, duplicated, missing a target user, or blocked.
- Keep `phase`, `skip_reason`, target role, safe user hash, and safety booleans inside folded technical details.
- Show explicit business wording that no user, session, role assignment, or store membership is created.

## Boundary

- No real user creation.
- No store membership write.
- No login/session activation.
- No route-level production authorization.
- Large-scale multi-store production operation remains closed.
