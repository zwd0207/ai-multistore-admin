# Phase Naver-Order-Batch-1H: Order Batch Audit Readiness UI Mock Display

Purpose: show Naver order batch audit readiness in seller-readable language on the Orders page.

Implemented:

- Codex2 Orders now shows a Naver order batch audit readiness panel for Naver stores.
- The panel says the audit preparation is organized, current order writes are closed, and formal order batch sync remains closed.
- It shows local Naver order count only as a review range, not as a new platform candidate count.
- Technical fields such as `phase`, `sync_kind`, `real_sync`, write flags, audit flags, and formal-sync flags remain folded in `TechnicalDetails`.

Safety:

- No Naver API is called by this panel.
- No orders or products are written.
- No SyncLog or tested-success rows are written.
- No platform shipment, cancel, return, or exchange write operation is exposed.
