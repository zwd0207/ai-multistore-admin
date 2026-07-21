# Phase Naver-Product-Batch-1I: Product Batch Sync Rollback Drill Plan

## Purpose

Plan the rollback drill required before any formal product batch sync can be opened.

## Drill Requirements

- Start from a verified local backup manifest.
- Restore only to a temporary database copy.
- Compare product counts and selected safe stock/price/status summaries.
- Prove no raw response or secrets are present in backup evidence.
- Produce an operator checklist for rollback decision making.

## Still Closed

No real restore is executed. Formal Naver product batch sync remains closed.
