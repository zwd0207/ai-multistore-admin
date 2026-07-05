# Phase Shipping-3B: Shipping Export Record Schema Migration

## Purpose

Create local export-record tables for the Shipping Assistant.

## Implemented

- `shipping_export_batches`
- `shipping_export_batch_rows`
- Store/platform scoped indexes for export batches and rows.
- File hash and audit correlation fields for later recovery and audit lookup.

## Real Database

The real local `codex1.db` was backed up before migration. The migration created the export tables with zero rows.

## Boundary

The migration does not generate files, write orders/products/SyncLog/tested-success rows, call Naver, or call logistics-provider APIs.
