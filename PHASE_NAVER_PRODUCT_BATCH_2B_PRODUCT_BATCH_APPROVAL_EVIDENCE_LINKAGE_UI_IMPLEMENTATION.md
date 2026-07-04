# Phase Naver-Product-Batch-2B: Product Batch Approval Evidence Linkage UI Implementation

## Goal

Implement the Naver product batch approval evidence linkage display in Codex2.

## Implementation

The Products page now shows:

`Naver 商品批量审批证据联动`

The panel explains that future product batch approval must link:

- readonly candidates
- backup and rollback evidence
- field whitelist
- audit correlation

## Safety Boundary

The panel is readonly. It does not:

- trigger a Naver request
- execute restore
- write products
- write orders
- write SyncLog
- write tested-success records
- write audit rows
- open formal product batch sync

## Result

Product operators can see the evidence chain required for a later product batch approval while the real write path remains closed.
