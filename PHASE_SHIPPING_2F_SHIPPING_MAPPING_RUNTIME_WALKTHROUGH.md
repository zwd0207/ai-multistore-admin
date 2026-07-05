# Phase Shipping-2F: Shipping Mapping Runtime Walkthrough

## Purpose

Verify that the Shipping Assistant can read local mapping and stock readiness in both backend and mock modes without calling platform APIs or writing new business rows.

## Result

- `/shipping` keeps the ordinary operator flow focused on unshipped candidates, logistics inventory-code matching, stock readiness, and export preview.
- Backend mode continues to read `GET /api/v1/shipping/logistics-mappings`.
- Mock mode remains page-local and does not touch Codex1.
- Technical flags stay folded in `TechnicalDetails`.

## Boundary

No Naver API call, logistics-provider API call, real Excel file, export record, tracking-number import, shipment writeback, order write, product write, SyncLog write, or tested-success write is opened in this phase.
