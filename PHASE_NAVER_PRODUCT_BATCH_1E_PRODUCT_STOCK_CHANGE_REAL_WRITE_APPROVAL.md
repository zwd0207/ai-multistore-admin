# Phase Naver-Product-Batch-1E: Product Stock-Change Real Write Approval

## Result

This phase approves only the observed Naver stock-only product changes for the next narrow local write phase.

## Scope

- Store scope: `store_id=8`
- Candidate evidence: latest readonly product preview, `page=1,size=5`
- Observed result: 5 matched existing local Naver products
- Write candidates: 3 products with `stock_quantity` changes only
- Refresh-only candidates: 2 products

## Required Gates

- Fresh readonly preview must show `would_create=0`, `would_skip=0`, and `changed_fields=["stock_quantity"]`.
- A real local database backup and manifest must exist before writing.
- Admin approval for `products.batch_sync_write` is required through the current role metadata gate.
- Rollback and post-write verification must be ready.

## Still Closed

- Formal Naver product batch sync is not open.
- Product creates are not allowed.
- Name, price, status, currency, raw response, and platform write operations are not allowed.
- SyncLog, tested-success, orders, timeline events, and store memberships must not be written by this phase.
