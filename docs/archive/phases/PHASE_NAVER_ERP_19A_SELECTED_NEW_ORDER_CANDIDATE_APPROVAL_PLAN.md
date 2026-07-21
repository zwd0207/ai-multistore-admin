# Phase Naver-ERP-19A: Selected New-Order Candidate Approval Plan

## Scope

Naver-ERP-19A is an approval-plan phase for a selected Naver new-order candidate observed in 18C.

This phase does not call Naver, does not execute `real_sync=true`, does not write local data, does not write audit rows, does not create or restore backups, does not modify schema, and does not open formal Naver order sync.

## Candidate

The approved candidate for further readonly confirmation is:

```text
id-hash-192b9c67e8
```

18C observed this candidate through a real readonly preview:

- order status: `DELIVERED` / `配送完成`
- delivery status: `DELIVERY_COMPLETION` / `配送完成`
- quantity: `1`
- amount: `499000 KRW`
- `raw_response_saved=false`
- `privacy_fields_redacted=true`
- `address_saved=false`

18D confirmed that this safe hash does not match an existing real local Naver order. Therefore it is not approved for the existing-order refresh path. It may be considered only as a selected new-order candidate.

## Required Gates Before Any Write

A later single local write may be considered only if all gates pass:

- Current worktrees are clean.
- A fresh readonly repeat returns the same selected safe hash.
- The candidate remains `candidate_new`.
- Local duplicate count is zero among real Naver operational orders.
- Mock/test rows are ignored for operational duplicate checks.
- The detail preview passes privacy and required-field gates.
- No unknown order, delivery, payment, or claim status blocks mapping.
- A fresh local backup of `backend/codex1.db` is created and verified.
- Backup manifest, SHA-256, SQLite integrity, and baseline counts are recorded.
- User approval remains explicit for the selected safe hash.
- The write remains limited to one order for `store_id=8`, platform `naver`.
- Post-write readback verifies the created row.
- Audit evidence is written only after safe local operation evidence exists.

## Allowed Future Write Fields

Future write payload may save only sanitized business fields already approved by earlier order gates:

- `store_id=8`
- `platform=naver`
- safe hashed external order id
- safe hashed external product-order id
- order/payment/delivery/claim status and Chinese labels
- safe product and option text
- quantity
- order amount
- currency `KRW`
- ordered/paid/last-changed timestamps if safely observed
- `source_type=naver_real_order_sync`
- `raw_response_saved=false`
- `privacy_fields_redacted=true`
- `address_saved=false`
- sanitized metadata with mapping version

## Forbidden Future Write Fields

The future write must not persist:

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
- SyncLog writes remain closed for this path.
- `ApiCapabilityTestResult tested_success` writes remain closed.
- Platform shipment/cancel/return/exchange/settlement/customer-service/mail/appeal/AI writes remain closed.

## Recommended Next Stage

`Phase Naver-ERP-19B: Selected new-order readonly repeat`

19B should call the existing Naver order preview endpoint in readonly mode only and stop if the selected safe hash does not match.
