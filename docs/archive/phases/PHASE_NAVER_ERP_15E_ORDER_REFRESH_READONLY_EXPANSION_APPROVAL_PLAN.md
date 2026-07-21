# Phase Naver-ERP-15E - Naver Order Refresh Batch Readonly Expansion Approval Plan

## Summary

Phase 15E defines the approval plan for a possible future readonly expansion of Naver existing-order refresh candidate discovery.

This phase is planning-only. It does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not insert `order_status_events`, does not write products, SyncLog, or ApiCapabilityTestResult rows, does not change database schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync.

## Current Baseline

- Phase 15A documented the future existing-order refresh batch gate.
- Phase 15B added a private mock gate for existing-order batch refresh candidates.
- Phase 15C ran the current public readonly preview shape with `page=1,size=1`.
- 15C returned HTTP 200 with feed/detail HTTP 200 and safe hash `id-hash-67b5fc1c97`.
- That hash did not match an existing local real Naver order, so it is a new-order candidate, not an existing-order refresh candidate.
- Current public `POST /api/v1/sync/orders/naver/preview` still caps real preview at `page=1,size=1`.
- No true multi-candidate readonly expansion has been executed.
- No existing-order batch refresh candidate is currently approved.
- Formal order sync, automatic refresh, local batch writes, timeline event insertion, and all Naver platform write APIs remain closed.

## Approval Decision

15E does not approve an immediate batch refresh write.

15E also does not change the public endpoint by itself. A later implementation phase would be required before any readonly request can exceed `size=1`.

The safest decision is:

- do not proceed to a batch refresh write from the 15C result.
- route the 15C safe hash `id-hash-67b5fc1c97` to the separate new-order candidate path if the operator wants to persist it.
- consider readonly expansion only as a future, separately approved implementation step.

## Future Readonly Expansion Shape

If the operator later approves a true readonly expansion implementation, the first expansion should be:

- `store_id=8`.
- `credential_id=7`.
- `platform=naver`.
- recent 3-day KST window.
- `page=1`.
- `size=2`.
- `order_status=ALL` internally, but do not pass order status to the Naver changed-feed request.
- `real_preview=true`.
- `include_detail=true`.
- `complete_field_preview=false`.
- `real_sync=false`.
- feed request body/query must stay minimal: `lastChangedFrom` and `limitCount=2` only.
- do not pass `lastChangedTo` to the Naver feed unless a later phase separately approves it.
- query detail for at most 2 product-order ids.
- do not save raw response, token, Authorization, request headers, signature, bcrypt output, client secret, full order id, full product-order id, buyer/receiver privacy, phone, address, or zip code.

The public write path must remain stricter:

- `real_sync=true` remains capped at the existing single-order gate.
- no batch write is allowed in the readonly expansion phase.
- no new order may be created in an existing-order refresh phase.

## Candidate Classification Required

Every future readonly candidate must be classified before any later approval:

- `existing_refresh_candidate`: safe hash matches exactly one local real Naver order for `store_id=8`, `platform=naver`, and `source_type=naver_real_order_sync`.
- `new_order_candidate`: safe hash does not match a local real Naver order.
- `duplicate_candidate`: the same safe hash appears more than once in the same readonly result.
- `ambiguous_local_match`: safe hash matches more than one local row.
- `blocked_candidate`: privacy gate fails, unknown status is observed, forbidden fields appear, or required safe hashes are missing.

The first future batch refresh approval must require all candidates to be `existing_refresh_candidate`.

If any new-order candidate is present, do not silently mix it into an existing-order refresh batch. Route it to a separate new-order approval phase.

## Stop Conditions

Stop immediately and do not continue to write planning if:

- HTTP is not 200.
- token or readonly request returns `ip_not_allowed`, `credential_invalid`, `permission_forbidden`, `product_api_not_allowed`, `token_auth_failed`, or `unknown_forbidden`.
- preview returns `success_empty`.
- candidate count is 0.
- candidate count exceeds 2 in the first expansion.
- any candidate is missing a safe hash.
- any duplicate safe hash appears.
- any candidate has zero or multiple local real Naver matches.
- any candidate is a new-order candidate while the requested action is existing-order refresh.
- any candidate has `unknown_status_observed=true`.
- any candidate fails privacy gate.
- any candidate includes raw response, complete-field payload for persistence, token, Authorization, headers, signature, bcrypt output, client secret, full order id, full product-order id, buyer/receiver full data, phone, address, or zip code.
- products, SyncLog, ApiCapabilityTestResult, or timeline event counts change during readonly preview.

## Future Implementation Requirements

A later implementation phase may only consider this readonly expansion if it adds tests proving:

- `real_preview=true, real_sync=false, page=1, size=2` is allowed only for `store_id=8` and `credential_id=7`.
- `real_sync=true` remains blocked for `size>1`.
- `page>1` remains blocked unless separately approved.
- `size>2` remains blocked in the first expansion.
- feed sends only `lastChangedFrom` and `limitCount=2`.
- detail is called for at most 2 product-order ids.
- success_empty does not call detail.
- no orders, products, SyncLog, ApiCapabilityTestResult, or timeline events are written.
- duplicate, new-order, ambiguous-local-match, unknown-status, privacy, and forbidden-field cases are classified safely.
- no sensitive values or raw responses appear in serialized outputs.

## Approval Record Shape

The later readonly expansion approval record should include only safe fields:

- phase name.
- requested action: `naver_order_readonly_candidate_expansion`.
- `store_id=8`.
- `credential_id=7`.
- requested `page=1`.
- requested `size=2`.
- requested window.
- expected write state: `real_sync=false`.
- expected candidate limit: 2.
- required stop conditions.
- expected classification buckets.
- `formal_order_sync_open=false`.
- `platform_writes_enabled=false`.

It must not contain raw responses, full order ids, full product-order ids, buyer privacy, addresses, tokens, headers, signatures, bcrypt output, client secrets, or complete-field preview payloads.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-16A: New-order candidate approval plan
```

Reason: the latest real readonly candidate is a new-order candidate. Processing that candidate through the new-order gate is more useful than expanding an existing-order refresh batch that currently has no approved matching candidates.

Alternative later stage if the operator still wants refresh-batch work first:

```text
Phase Naver-ERP-15F: Naver order refresh readonly expansion guardrail implementation plan
```

15F would still avoid writes and would only prepare the guarded `size=2` readonly implementation.
