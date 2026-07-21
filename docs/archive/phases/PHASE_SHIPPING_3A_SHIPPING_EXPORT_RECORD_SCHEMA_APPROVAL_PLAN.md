# Phase Shipping-3A: Shipping Export Record Schema Approval Plan

## Purpose

Approve the local schema direction for recording generated logistics-provider export files.

## Decision

Use two store-scoped tables:

- `shipping_export_batches`
- `shipping_export_batch_rows`

The records keep file metadata, row counts, file hash, audit correlation id, product/option text, logistics inventory code, and optional hashed platform product/option ids.

## Boundary

No platform API call, Naver shipment writeback, tracking-number import, order write, product write, SyncLog write, or tested-success write is approved by this schema plan.
