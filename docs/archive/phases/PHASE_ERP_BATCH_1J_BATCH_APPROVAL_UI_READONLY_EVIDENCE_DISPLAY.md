# Phase ERP-Batch-1J: Batch Approval UI Readonly Evidence Display

## Purpose

Display Naver product and order readonly evidence in the Orders page so operators can see whether approval material is ready before any future batch-write phase.

## Implemented

- Added a Naver batch approval evidence panel to Codex2 Orders.
- Added `dataProvider.normalizeBatchReadonlyEvidence(...)` for backend and mock data sources.
- The panel shows product/order evidence counts, business messages, and the current write-protection boundary.
- Technical evidence fields are folded inside TechnicalDetails.

## Safety Boundary

- The panel does not call Naver.
- The panel does not write products, orders, SyncLog, tested-success, audit rows, or timeline events.
- The panel does not open formal product or order batch sync.
