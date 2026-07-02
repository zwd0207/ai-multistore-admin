# Phase Naver-ERP-5C - Naver Order Detail Complete Field Mock Display

## Scope

This phase implements the Codex2 frontend mock display for complete Naver order detail fields.

It does not modify Codex1, does not call Naver, does not write orders, does not change schema, and does not open formal order sync.

## Implemented

- Added a Naver order detail section on the Orders page.
- Added complete mock fields for the `pxg球包店` Naver order:
  - complete order number
  - complete product order number
  - platform product number
  - buyer name and phone
  - receiver name and phone
  - receiver address and zip code
  - product option
  - payment, delivery, and claim status
- Kept Dashboard summary-only. Complete buyer and receiver fields are not expanded on Dashboard.
- Kept backend mode tolerant when complete fields are absent.
- Added adapter compatibility for future backend complete fields without requiring schema changes in this phase.

## UI Boundary

Complete order and buyer fields are shown only in the Orders detail section.

Dashboard, API capability pages, technical detail grids, logs, error banners, and mock sync notices must not become broad displays for complete buyer information.

## Still Closed

- Formal Naver order sync.
- Naver delivery, cancel, return, and exchange write actions.
- Naver settlement, statistics, or sales API calls.
- Codex1 complete-field persistence.
- Raw response storage.

## Validation

- `npm.cmd run build`
- `VITE_DATA_SOURCE=mock npm.cmd run build`
- `npm.cmd run encoding:scan`
- `git diff --check`
- Browser walkthrough for mock Orders page with `pxg球包店`

## Next Step

Recommended next phase:

`Phase Naver-ERP-5D: Codex1 single order complete-field readonly preview`

That later phase should preview exactly which complete order fields would be saved by Codex1 before any real database write is approved.
