# Phase Naver-Order-Batch-2C - Order Batch Execution Approval Readonly UI Plan

## Goal

Plan how future Naver order batch execution approval evidence should appear in the UI without letting operators mistake review readiness for execution approval.

## UI Direction

- Show order batch execution as closed until a separate approved write phase exists.
- Show fresh readonly candidates, backup evidence, permission gate, privacy gate, whitelist, duplicate check, delivery/claim mapping review, audit chain, readback, rollback, and sensitive scan as business checklist items.
- Keep technical flags such as phase, write switches, raw-response markers, and execution flags folded.

## Safety Boundary

- No Naver API call in this planning phase.
- No order write.
- No shipment/cancel/return/exchange platform write.
- No formal order batch sync opening.

The implementation should follow after route-backed evidence is stable and explicitly approved.
