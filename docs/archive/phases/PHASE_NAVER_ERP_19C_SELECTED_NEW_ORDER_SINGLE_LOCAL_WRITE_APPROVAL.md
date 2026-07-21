# Phase Naver-ERP-19C: Selected New-Order Single Local Write Approval

## Scope

Naver-ERP-19C approves a later controlled single local write for the selected new-order candidate only.

This phase is approval-planning only. It does not call Naver, does not execute `real_sync=true`, does not write orders, does not write audit rows, does not create backups, does not restore backups, does not modify schema, and does not open formal Naver order sync.

## Approved Candidate

```text
id-hash-192b9c67e8
```

This is approved only because:

- 19A selected it as a new-order candidate.
- 19B repeated it through real readonly preview.
- 19B confirmed local duplicate real-order matches are zero.
- 19B confirmed privacy and raw-response safety flags.

## Required 19D Preconditions

19D may write only if all conditions pass:

- Codex1 and Codex2 worktrees are clean.
- `orders_store8=6` before write.
- `products_store8=5` before write.
- `sync_logs_store8=1` before write.
- `tested_success_store8=8` before write.
- `operation_audit_logs=5` before write.
- `order_status_events=0` before write.
- A fresh backup of `backend/codex1.db` is created under the approved local backup root.
- Backup manifest exists.
- Backup SHA-256 is valid.
- SQLite integrity check is `ok`.
- A fresh readonly Naver preview returns safe hash `id-hash-192b9c67e8`.
- Local duplicate real-order matches are still zero.
- Candidate detail passes privacy and required-field gates.
- The write gate uses one candidate only.
- The write result creates exactly one local order.
- The operation writes no products, no SyncLog, no tested-success records, and no timeline event unless separately approved.

## Approved Future Audit Evidence

If 19D writes the local order, it may also write a five-row operation audit chain:

```text
approval_verified
pre_write_backup_verified
selected_operation_started
selected_operation_finished
post_write_verification_finished
```

The audit rows must:

- share one `correlation_id`
- use unique request ids
- target type `order`
- target hash `id-hash-192b9c67e8`
- include backup path and SHA-256
- keep `raw_response_saved=false`
- keep `secrets_saved=false`
- keep `privacy_fields_redacted=true`
- keep `formal_sync_open=false`
- keep `platform_writes_enabled=false`

## Forbidden

19D must not save or output:

- complete platform order id
- complete product-order id
- complete channel id
- buyer or receiver full name
- buyer or receiver phone
- address, zip code, detailed address, delivery memo
- raw platform payload
- raw response
- token or Authorization value
- request or response headers
- signature, bcrypt input, client secret, or decrypted credential

## Closed Boundaries

- Formal Naver order sync remains closed.
- Batch order sync remains closed.
- Product sync remains closed.
- Naver platform shipment/cancel/return/exchange/settlement/customer-service/mail/appeal/AI writes remain closed.

## Recommended Next Stage

`Phase Naver-ERP-19D: Selected new-order single local write with audit evidence`

19D may perform the approved single local write only if every precondition above is verified immediately before writing.
