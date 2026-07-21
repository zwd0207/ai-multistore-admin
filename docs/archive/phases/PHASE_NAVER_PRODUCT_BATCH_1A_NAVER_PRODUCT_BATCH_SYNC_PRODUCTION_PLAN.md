# Phase Naver-Product-Batch-1A: Naver product batch sync production plan

## Purpose

Prepare the Naver product line for a future formal batch sync path after the current 5-row local write stabilization.

## Proposed Gate

A future product batch sync must require:

- fresh page/window readonly preview
- page overlap and duplicate detection
- product field whitelist verification
- price/stock/status change classification
- no raw response storage
- no full product id display
- verified database backup
- role permission for `products.batch_sync_write`
- explicit sensitive-action approval
- append-only audit chain
- rollback and recovery plan
- post-write readback and sensitive scan

## Current Boundary

The existing `products_store8=5` result remains a small-batch proof, not a formal batch opening. Page expansion and size expansion still require separate controlled phases.

