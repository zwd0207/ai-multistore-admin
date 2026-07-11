# Commander Decisions

This is an append-only record of durable decisions. Implementation progress belongs in `COMMANDER_STATE.md`.

## D001 - Human-first product strategy

The system first improves a human operator's daily work. AI may summarize, translate, or draft, but autonomous marketplace operations wait until the manual workflow is stable.

## D002 - Warehouse fulfillment model

Inventory is stocked in advance. The daily fulfillment workflow uses internal SKU matching and warehouse shipment batches; it is not a purchase-after-order workflow.

## D003 - Privacy boundary

Ordinary order lists and technical previews never show complete recipient PII. Full recipient data is available only through an authorized operational fulfillment path with confirmation and audit evidence.

## D004 - Production writes

Real platform operations require preview, explicit human confirmation, execution, and audit logging. Tests and rehearsals must not call real Naver or Coupang writes.

## D005 - Authentication and authorization

Production access is fail-closed. Session service failure must block the UI. Unsafe backend requests require session, CSRF, store scope, and permission checks. Unknown write routes must not default to open access.

## D006 - Model allocation

- Commander: current truth, task routing, integration, verification, and concise user reporting.
- Sol: architecture, privacy, permissions, production risk, and final gate reviews only.
- Terra: backend, security, database, cross-module integration, and complete engineering verification.
- Luna: stable-contract UI, copy, styling, mobile adaptation, and low-risk repetitive work.

Use the lowest-cost model that can reliably complete the work. Do not ask multiple models to implement or review the same low-risk change.

## D007 - Parallel execution

Parallel tasks are allowed only when file ownership and contracts are independent. Security boundaries and upstream API contracts complete before dependent UI work begins.

## D008 - PXG Naver real read-only boundary

Guarded real reads are allowed only for the uniquely resolved `pxg球包店 / Naver` store. Product, order, logistics, and customer-inquiry previews must remain bounded and privacy-safe. Preview calls must not persist platform payloads or alter local business state. Shipment writeback, customer sending, product/order/inventory modification, all-store sync, and AI automatic operations remain disabled.

## D009 - Read-only persistence activation

Merging the PXG/Naver persistence foundation does not authorize real data storage. The persistence feature remains default-disabled. Activation requires a separate approval covering retention, backup, rollback, one-store scope, bounded first sync, privacy verification, and operator UI acceptance. Real platform writes remain disabled independently of this decision.
