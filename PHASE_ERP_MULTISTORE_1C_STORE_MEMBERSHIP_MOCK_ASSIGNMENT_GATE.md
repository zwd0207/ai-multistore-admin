# Phase ERP-Multistore-1C: Store membership mock assignment gate

## Purpose

Add a private mock gate for future store membership assignment.

## Implemented Gate

Codex1 now has:

```text
evaluate_store_membership_assignment_mock_gate(...)
```

The helper verifies:

- private verification scope
- target user safe hash
- target store id
- allowed target role
- assignment reason
- no sensitive material
- admin approval for `store_membership.assign`
- no duplicate active membership

## Boundary

The mock gate does not create users, does not create memberships, does not activate login, and does not enable large-scale multi-store production operation.

The auth permission metadata now includes `store_membership.assign`.

