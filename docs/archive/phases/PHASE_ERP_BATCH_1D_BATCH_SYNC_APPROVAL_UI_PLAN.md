# Phase ERP-Batch-1D: Batch sync approval UI plan

## Purpose

Plan the future operator-facing UI for approving formal product/order batch sync.

This phase does not add an approval button and does not open formal batch sync.

## UI Principles

The UI should show business-first approval cards:

- what store is affected
- what data type is affected
- how many records are candidates
- what will be created, updated, refreshed, or skipped
- which fields changed
- whether backup evidence exists
- whether permission approval is present
- whether audit evidence will be written
- whether rollback instructions are ready

## Required Wording

Primary UI copy should say:

```text
正式批量同步仍未开放。当前仅展示进入审批前需要确认的证据。
```

If a product readonly preview finds stock changes, the UI should say:

```text
检测到库存字段变化，需要人工审核后才能进入后续写入阶段。
```

If an order readonly preview finds no write needed, the UI should say:

```text
订单已检查，当前没有需要写入的业务字段变化。
```

## Technical Details

Permission keys, backup manifest details, audit correlation ids, preview flags, and diagnostic reason codes must stay inside `TechnicalDetails` or an administrator-only advanced section.

