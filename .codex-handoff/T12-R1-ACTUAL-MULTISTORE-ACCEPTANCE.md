# T12-R1 Actual Multi-store Acceptance

Status: accepted on 2026-07-13

## Runtime

- Frontend: `http://127.0.0.1:5181/`
- Backend: `http://127.0.0.1:8013/`
- Database: isolated local SQLite under `codex1/backend/.local-trial`
- Stable account: use the existing local credential helper; never copy secrets into task messages

## Accepted Scope

- Authorized stores: `pxg球包店` and `[FICTIONAL][LOCAL][T12] Naver Multi-store Demo`
- Fictional data: one abnormal order and one open customer inquiry
- All-store aggregation has unique task IDs
- Single-store views do not leak the other store's data
- Order and inquiry tasks switch store context before deep-link navigation
- Desktop and 390px operator layouts passed

## Reuse Audit

- Reused the stable local account, existing role and permissions, Store, Order, CustomerInquiry, membership model, store overview, T11 workbench, order page, inquiry page, and DataTable.
- Added only local fixture provisioning/verification and narrow responsive/deep-link compatibility changes.

## Duplication Check

- No production API, service, model, table, state machine, or write path was added.
- No second workbench aggregation or frontend task classification was added.

## Closed Boundaries

- No Naver or Coupang network access for the fictional store
- No synchronization execution
- No customer sending
- No shipping writeback or other platform writes
- No scheduler or AI automatic action
- No credentials or recipient PII in the fixture

## Evidence Commits

- `4a42f62`, `6729702`, `a4bf490`: local fixture, contract alignment, abnormal task
- `7589f2f`: 390px store action reachability
- `11e0a3e`: abnormal-order deep-link filtering

Full backend verification, frontend contracts, session verification, production build, desktop browser QA, and 390px browser QA passed.
