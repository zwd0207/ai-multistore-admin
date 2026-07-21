# Phase Naver-ERP-17A - Claim Status Mapping Expansion

## Summary

Phase 17A expands Naver claim/status mapping for readonly order previews and timeline planning.

This phase does not call Naver, does not execute `real_sync=true`, does not write local business rows, does not modify database schema, does not modify Codex2 runtime UI, and does not open formal Naver order sync. It only updates backend safe mapping logic, mock verification, and documentation.

## Why This Phase Was Needed

Phase 16D-Retry and 16E observed a real Naver order with:

```text
claimStatus = COLLECT_DONE
```

Before 17A, this safe enum was classified as:

```text
未识别状态，需人工确认
```

That was too conservative for a commonly observed after-sales pickup state. 17A maps the enum to a user-facing business label without enabling any platform-side after-sales operation.

## Mapping Changes

New or reinforced status labels:

- `COLLECT_REQUEST` -> `售后取件请求`.
- `COLLECTING` -> `售后取件中`.
- `COLLECT_DONE` -> `售后取件完成`.
- `RETURNED` / `RETURN_DONE` -> `退货完成`.
- `EXCHANGED` / `EXCHANGE_DONE` -> `换货完成`.

Timeline event mapping now also recognizes:

- `COLLECT_REQUEST` -> `claim_collect_requested`.
- `COLLECTING` -> `claim_collecting`.
- `COLLECT_DONE` -> `claim_collected`.
- `RETURN_DONE` -> `returned`.
- `EXCHANGE_DONE` -> `exchanged`.

## Verification

Mock verification now confirms:

- `COLLECT_DONE` detail preview returns `claim_status.label_zh=售后取件完成`.
- `COLLECT_DONE` does not set `unknown_status_observed=true`.
- detail preview still suppresses raw response and privacy fields.
- timeline mapper returns `claim_collected` for `COLLECT_DONE`.
- timeline mapper still writes no orders or timeline rows in mock gate coverage.
- sensitive test payload values do not appear in serialized preview output.

## Safety Boundary

This phase does not approve:

- formal Naver order sync.
- batch order sync.
- automatic selected-candidate writes.
- existing-order refresh batch writes.
- timeline event insertion.
- shipment, cancel, return, exchange, refund, delivery, settlement, sales, customer-service, or any other Naver platform write operation.

The existing 16D-Retry order row is not rewritten in this phase. If a persisted row already contains an older sanitized raw_data label, display cleanup or a later approved refresh should handle that separately without storing raw platform responses.

## Recommended Next Stage

Recommended next stage:

```text
Phase Naver-ERP-17B: Orders UI claim/delivery wording check
```

17B should verify that the Orders UI and Dashboard display claim/delivery labels as business text, not raw technical enums, and that historical sanitized rows do not confuse operators.
