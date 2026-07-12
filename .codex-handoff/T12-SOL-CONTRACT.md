# T12 Sol Contract

Status: frozen on 2026-07-13

## API Ownership

- Extend `GET /dashboard/store-overview`.
- Keep `GET /dashboard/summary?store_id=` unchanged as the T11 single-store contract.
- Do not add an API, task table, task model, state machine, or production service.

## Authorization

- Require session and MFA.
- Aggregate only distinct active stores for which the current user has an active membership, active role, and active `dashboard.read` or `*` permission.
- No authorized store returns `403 dashboard_read_forbidden`.
- Store names, task counts, tasks, and source failures must never reveal another store.

## Response

- Preserve all existing store-overview fields.
- Add top-level `operator_workbench` with T11 `summary`, `sections`, and `sources`.
- Add `store_id`, `store_name`, and `platform` to each task.
- Add four-count `workbench_summary` to each store row.
- Each source reports `status`, `reason_code`, `failed_store_count`, and safe store-level failures.

## Aggregation

- Reuse the existing T11 workbench builder once per authorized store with test orders excluded.
- Deduplicate by `(store_id, task_id)`.
- Sort by priority descending, update time ascending, store id ascending, then task id ascending.
- `ApiError` degrades only its source. Unexpected errors remain visible as server failures.

## Frontend

- Consume the backend aggregate; do not classify business states in the browser.
- Support all-authorized-stores and one-store views.
- Set the selected store before following a task deep link.
- Remove dashboard all-store and single-store synchronization controls.

## Closed Boundaries

- No bulk execution or manual task completion.
- No platform writeback or customer sending.
- No scheduled synchronization or AI execution.
- No new real-data persistence batch.
