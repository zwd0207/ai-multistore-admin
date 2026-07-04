# Phase ERP-Audit-2C: Selected Operation Audit Local Implementation Approval Plan

## Scope

ERP-Audit-2C is an approval-plan phase for connecting selected local business operations to the real append-only audit writer in a later phase.

This phase is documentation-only. It does not modify runtime code, does not write `operation_audit_logs`, does not write orders, products, `SyncLog`, `ApiCapabilityTestResult`, or order timeline rows, does not create or restore backups, does not change database schema, does not call Naver or Coupang APIs, and does not open formal product or order sync.

## Current Baseline

- The `operation_audit_logs` schema exists.
- The audit writer service and readonly audit APIs exist.
- Logs/Audit UI can read audit logs.
- Backup creation audit local implementation has written and verified one five-row backup evidence chain.
- Selected operation audit runtime wiring has passed mock planning gates but is not connected to a real local order refresh/write path.
- Naver order refresh remains controlled and formal order batch sync remains closed.

## Approved Future Target

A later implementation may connect audit writing only to this selected operation:

```text
controlled_naver_order_local_refresh
```

The selected operation means a manually approved, local-only refresh of existing Naver order records after a readonly Naver detail check. It must not call any Naver write endpoint and must not open automatic or formal batch sync.

## Required Preconditions For The Later Implementation

Before a future real local implementation may write selected-operation audit rows:

- Codex1 and Codex2 worktrees must be clean.
- A fresh local backup of `backend/codex1.db` must be created and verified.
- Backup evidence must include manifest, SHA-256, SQLite integrity check, and safe baseline counts.
- The user must explicitly approve the selected local operation.
- The selected operation must be limited to `store_id=8`, platform `naver`, and an already known local Naver order target.
- The target identity must be stored in audit evidence only as a safe hash or safe internal local id.
- The future implementation must not add public audit write, delete, export, or raw detail routes.
- The future implementation must not add blanket middleware logging or automatic audit writing for every endpoint.
- Any Naver API call in the surrounding order refresh phase must remain readonly.

## Required Audit Chain

The future selected-operation audit chain must be append-only and use one shared `correlation_id` with unique request ids.

Required actions:

```text
approval_verified
pre_write_backup_verified
selected_operation_started
selected_operation_finished
post_write_verification_finished
```

The chain may record a blocked or failed final state, but it must not persist unsafe raw payloads. A blocked operation should write only safe blocked evidence.

## Allowed Audit Evidence

Future selected-operation audit rows may store:

- `store_id=8`
- `platform=naver`
- safe actor type and actor label
- operation type `controlled_naver_order_local_refresh`
- action and operation phase
- status and safe reason code
- correlation id and request id
- target type `order`
- local order id if it is an internal database id
- safe target hash
- safe changed field names
- count summary
- backup path and abbreviated or full SHA-256 as backup evidence
- `raw_response_saved=false`
- `secrets_saved=false`
- `privacy_fields_redacted=true`
- `formal_sync_open=false`
- business note suitable for Logs/Audit display

## Forbidden Audit Evidence

Future selected-operation audit rows must not store or echo:

- token, refresh token, access token, or Authorization values
- request headers or response headers
- signatures, bcrypt inputs, client secrets, or decrypted credentials
- raw request body or raw response body
- full channel number
- full platform order id or product-order id
- full platform product id
- buyer or receiver full name
- buyer or receiver phone
- address, zip code, detailed address, or delivery memo
- raw Naver platform payload snapshots

## Failure Boundary

- If backup creation or backup verification fails, the selected local operation must not proceed.
- If manual approval is missing, the selected local operation must not proceed.
- If privacy or sensitive-field scan fails, no selected-operation audit row may persist unsafe data.
- If the local write succeeds but audit writing fails, the phase must stop and block wider rollout.
- No audit failure may trigger a Naver platform write.
- Automatic restore is not approved by this plan. Restore remains a separate dry-run or explicitly approved recovery phase.

## Required Verification For The Future Implementation

The next mock gate and future local implementation must prove:

- Unsupported operation types are blocked.
- Unsupported store/platform values are blocked.
- Missing manual approval is blocked.
- Missing backup evidence is blocked.
- Unsafe target identifiers or privacy payloads are blocked.
- The success path writes only the expected append-only audit chain.
- The blocked path writes only safe blocked evidence, if any.
- Orders/products/SyncLog/tested-success/timeline counts match the approved operation expectation.
- Existing readonly audit APIs can read the rows safely.
- Logs/Audit UI remains business-readable and keeps technical evidence folded.
- Sensitive scan finds no token, Authorization, headers, signatures, client secrets, raw responses, full platform ids, buyer privacy, phone, address, zip code, or raw payloads.

## Still Closed

- Formal Naver product batch sync.
- Formal Naver order batch sync.
- Naver shipment, cancel, return, exchange, settlement, customer-service, mail, appeal, or AI automation writes.
- Public audit write/delete/export/raw detail APIs.
- Automatic blanket audit middleware.
- Real restore execution.
- Multi-store rollout of selected-operation audit writing.

## Recommended Next Stage

`Phase ERP-Audit-2D: Selected operation audit local implementation mock gate`

The next phase should implement or strengthen a private temporary-database mock gate for this exact selected-operation chain before any real local selected-operation audit writer is connected.
