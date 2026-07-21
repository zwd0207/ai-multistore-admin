# Phase ERP-Multistore-1E: Store Membership Runtime Assignment Mock Gate

## Result

The runtime membership gate now reads the real auth schema to check whether a future store membership assignment would be allowed.

## Checks

- Target user safe hash exists.
- Target role exists and is active.
- Store scope and admin approval pass.
- Duplicate active memberships are blocked.
- Sensitive actor or assignment material is rejected.

## Boundary

No `erp_users` or `erp_store_memberships` row is created by the gate. Real membership assignment remains closed.
