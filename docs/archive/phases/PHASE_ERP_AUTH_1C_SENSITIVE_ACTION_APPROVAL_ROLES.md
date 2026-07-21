# Phase ERP-Auth-1C: Sensitive Action Approval Roles

ERP-Auth-1C extends the private permission mock gate with sensitive-action approval checks.

## Implementation

Codex1 adds:

```text
evaluate_sensitive_action_approval_mock_gate(...)
```

The helper builds on the 1B store-scoped gate, then checks:

- the action is classified as sensitive;
- manual approval is present;
- the actor's role may approve that action;
- formal sync remains closed;
- platform writes remain disabled;
- no local business data is written.

## Sensitive Actions

The first sensitive action set is:

- `orders.local_write`
- `orders.refresh_batch_write`
- `backup.create`
- `database.restore`
- `credentials.update`
- `schema.migrate`
- `formal_sync.open`

`owner` may approve all sensitive actions. `admin` may approve selected operational actions such as controlled Naver order local writes/refreshes and backup creation. `operator`, `auditor`, and `viewer` cannot approve sensitive actions.

## Verified Cases

`verify_all.py` covers:

- missing manual approval blocks;
- operator approval is blocked;
- admin approval for `orders.refresh_batch_write` passes in mock only;
- no orders/products/SyncLog/tested-success rows are written;
- no raw response, token, Authorization, headers, signature, bcrypt input, client secret, full platform id, buyer/receiver phone, address, or zip code appears in safe output.

## Next Stage

`Phase ERP-Auth-1D: Frontend role-aware action visibility plan`
