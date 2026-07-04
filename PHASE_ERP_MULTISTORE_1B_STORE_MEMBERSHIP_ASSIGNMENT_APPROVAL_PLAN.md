# Phase ERP-Multistore-1B: Store membership assignment approval plan

## Purpose

Plan the first production-safe store membership assignment flow.

This phase does not create users, does not create memberships, and does not activate production login.

## Required Gate

A future store membership assignment must require:

- known actor
- admin or owner role
- target user exists
- target store exists
- role exists
- no duplicate active membership
- assignment reason
- manual approval
- audit evidence
- rollback/revoke instruction
- post-write readback

## First Suggested Scope

The first runtime assignment phase should only allow one store membership for one user and one store:

```text
store_id=8
role=admin or operator
membership_status=active
```

## Boundary

No real users or store memberships are active yet. Multi-store production operation still depends on assignment UI, route authorization dependencies, cross-store isolation tests, audit evidence, and backup/restore readiness.

