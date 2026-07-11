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

## D010 - T09 retention and rollback gate

PXG/Naver activation is blocked until automatic retention cleanup, cleanup audit, encrypted-backup lifecycle, restore verification, and batch-specific rollback pass tests and Sol review. Recipient PII expires operationally after 15 minutes and must be deleted within the approved shipment/cancellation and 30-day limits. First sync remains one manual batch with at most three product-order rows. Full policy: `.codex-handoff/T09-SOL-ACTIVATION-POLICY.md`.

## D011 - T09 engineering acceptance

The commander accepts the T09 cleanup, encrypted backup, ACL, checksum, structure verification, restore drill, and batch rollback implementation after independent verification. This engineering acceptance does not enable real persistence. `PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED` remains disabled until Sol passes the final activation review and the commander separately approves one bounded manual sync.

## D012 - T09 activation remains blocked

Sol's final activation review found three release blockers: the real refresh route does not use the backup/batch/rollback wrapper, expired backup cleanup is not automatically scheduled or enforced as an activation/refresh gate, and terminal recipient retention is based on mutable `order.updated_at` instead of a stable terminal event time. Real persistence remains disabled until all three are implemented, commander-verified, and approved in a new Sol review.

## D013 - T09-R3 engineering blockers resolved

The real refresh path now preserves its source and uses the guarded backup, pre-write restore drill, sync batch, and rollback flow. Cleanup runs at startup and every 24 hours when enabled, expired undeleted backups immediately block protected data use, cleanup recovery cannot clear unrelated safety locks, and terminal privacy timing is immutable. Focused lifecycle tests and `verify_all.py` passed. Real persistence remains disabled pending Sol re-review and a separate commander approval.

## D014 - Recipient deletion must use immutable terminal time

Sol's T09-R3 re-review passed security, backup, rollback, and cleanup but found that actual recipient deletion still uses mutable `order.updated_at`. The seven-day terminal retention deadline must use `secure.terminal_confirmed_at`, and later order updates must never extend that deadline. Real persistence remains disabled pending this fix and re-review.

## D015 - Immutable recipient deletion implemented

Actual recipient deletion now uses `secure.terminal_confirmed_at` for the seven-day terminal deadline and retains the independent 30-day collection maximum. Regression coverage proves that later `order.updated_at` changes cannot extend retention. The focused cleanup test and `verify_all.py` passed; real persistence remains disabled pending Sol's final narrow re-review.
