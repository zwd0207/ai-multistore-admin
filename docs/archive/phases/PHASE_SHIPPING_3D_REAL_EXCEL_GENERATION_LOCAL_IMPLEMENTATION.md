# Phase Shipping-3D: Real Excel Generation Local Implementation

## Purpose

Generate a real local `.xlsx` logistics-provider request file from export-ready Shipping Assistant rows.

## Implemented

- Codex1 exposes `POST /api/v1/shipping/export-excel`.
- The route generates a local `.xlsx` file with Python standard library ZIP/XML writing.
- The route writes one export batch, export rows, and one safe operation audit row.
- Codex2 `/shipping` calls the route in backend mode when the operator clicks the export button.
- Mock mode remains preview-only.

## Boundary

The implementation does not call Naver, call a logistics provider, write orders/products/SyncLog/tested-success rows, include receiver privacy, import tracking numbers, or execute shipment writeback.
