# Phase ERP-Auth-1B: Store-Scoped Access Gate Mock

ERP-Auth-1B adds a private backend mock gate for future store-scoped permissions.

## Implementation

Codex1 adds `app/services/permission_service.py` with:

```text
evaluate_store_scoped_access_mock_gate(...)
role_permission_inventory()
```

The gate verifies:

- private verification scope;
- safe actor context;
- known role;
- valid `store_id`;
- assigned store coverage;
- operation permission;
- no sensitive actor material.

## Verified Roles

- `owner`
- `admin`
- `operator`
- `auditor`
- `viewer`

## Verified Results

`verify_all.py` covers:

- missing verification scope is blocked;
- owner can access a write-class operation in mock only;
- operator can access assigned-store preview;
- assigned-store mismatch is blocked;
- viewer write is blocked;
- actor context containing secret-like material is blocked;
- responses do not write orders, products, SyncLog, tested-success records, or platform data.

## Explicit Non-Goals

This phase does not:

- create user tables;
- add login/session middleware;
- add public permission APIs;
- connect permissions to runtime routes;
- write business data;
- call platform APIs;
- open formal sync.

## Next Stage

`Phase ERP-Auth-1C: Sensitive action approval roles`
