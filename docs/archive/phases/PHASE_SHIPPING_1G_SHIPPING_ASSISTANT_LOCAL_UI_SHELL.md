# Phase Shipping-1G: Shipping Assistant Local UI Shell

## Purpose

Add a simple operator-facing Shipping Assistant shell for the first local production workflow.

## Implemented

- Added `src/pages/ShippingAssistant.jsx`.
- Added route `/shipping`.
- Added `发货辅助` to the main navigation.
- Added the business workflow strip:
  - read unshipped orders,
  - match inventory code,
  - maintain logistics stock,
  - generate export preview.

## UI Direction

The page is intentionally business-first. Ordinary operators see shipping tasks, counts, candidate rows, stock maintenance, and export preview. Technical flags remain folded in `TechnicalDetails`.

## Boundary

- No Codex1 runtime change.
- No real Naver API call.
- No database write.
- No real file generation.
- No formal order sync.
- No platform shipment write.

