# Phase Shipping-4B: Tracking-Number Import Mock Parser Gate

## Purpose

Validate the future tracking upload field contract using a mock parser gate.

## Implemented Gate

Codex1 exposes:

`POST /api/v1/shipping/tracking-import/mock-parse`

The gate validates required order references, carrier, tracking number, duplicate rows, manual approval, parser contract acknowledgement, and sensitive-field blocking.

## Boundary

The route writes no orders, no products, no SyncLog, no tested-success rows, no tracking import records, and no platform shipment state. Naver shipment writeback remains closed.
