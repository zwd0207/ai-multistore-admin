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

## D016 - T09 safety passed; activation remains separate

Sol passed the final T09 safety review with no blocker. This does not authorize real persistence. Before activation, the project must define a historical-order retention policy that keeps necessary non-PII order records searchable by platform order number while recipient name, phone, address, and delivery memo continue to follow the immutable 7-day/30-day deletion boundary.

## D017 - Customer follow-up requires a separate privacy purpose

The owner requires customer follow-up history to improve after-sales service. This does not authorize indefinite retention of all order recipient PII. Customer profiles and contact history must be purpose-limited, consent-aware, access-controlled, auditable, and separate from fulfillment addresses and delivery notes. The existing 7-day/30-day recipient deletion policy remains in force until a replacement policy is approved and implemented.

## D018 - Defer advanced privacy policy; prioritize operator workflow

Customer CRM and advanced privacy-policy work are deferred because they do not yet improve the operator's immediate daily workflow. Existing security and privacy controls remain mandatory and unchanged. Current effort moves to bounded real-read data, order handling, warehouse batches, logistics return, and customer-inquiry visibility. Sol is reserved for major gates, Terra owns backend contracts, and Luna starts only after those contracts stabilize.

## D019 - First bounded real-read persistence executed

The owner explicitly approved one PXG/Naver real-read persistence batch in the isolated local database with a maximum of three product-order rows and all platform writes disabled. The run completed with 3 products, 0 current-window orders, 0 logistics records, and 1 customer inquiry. Encrypted backup and pre-write restore verification passed. All local persistence and activation approvals were closed immediately after execution; another real persistence run requires new explicit approval.

## D020 - One stable account for operator testing

All future local operator tests use the account displayed by `查看真实只读配置账号.cmd`. Its login and password remain stable for the isolated database; only the MFA code rotates. The account receives the read, warehouse-batch, and local readonly-configuration permissions needed for operator testing, while platform writeback, customer sending, inventory/product writes, and AI automatic operations remain disabled.

## D021 - Owner accepted real-read data

On 2026-07-12, the owner confirmed that the real data currently read from `pxg球包店 / Naver` is correct. The read contract is accepted for the next operator-workflow phase. Do not repeat platform-read investigation unless new evidence shows a regression. This acceptance does not authorize another persistence batch or any real platform write.

## D022 - T10 Terra contract accepted

Terra commit `bec5875` was independently reviewed and integrated as `66074a8`. The ordinary customer-inquiry API now aggregates generic inquiries with saved PXG/Naver read-only inquiry metadata under session, MFA, store, permission, privacy, and disabled-reply controls. Focused verification and `verify_all.py` passed after integration. Luna may now implement Phase B against this stable contract; Sol remains paused until the UI is integrated and browser-verified.

## D023 - T10 Commander Gate B accepted

Luna runtime correction `fb88c396` and mobile correction `01a8e52` passed focused contract tests, session verification, frontend build, and Commander browser verification. The saved real PXG/Naver inquiry remains visible after logout/login, missing order and logistics context is represented as a normal state, reply controls remain disabled, desktop and 390px layouts stay within the viewport, and the browser console is clean. Sol may now perform the single final Phase C boundary review; Terra and Luna remain paused.

## D024 - T10 final acceptance blocked by backend read boundaries

Sol Phase C passed operator usability but found two verified backend boundary gaps. Ordinary inquiry aggregation can serialize PXG/Naver persisted inquiry metadata without first enforcing the existing retention cleanup health gate. The legacy Naver inquiry synchronization service can still perform an external read and write into the generic inquiry table during trial mode, including through internal manual-batch callers. T10 remains blocked until Terra adds fail-closed cleanup enforcement and disables the legacy sync path before network or local writes, Commander verifies the corrections, and Sol performs one narrow re-review.

## D025 - T10 backend boundary corrections verified

Terra commit `deb14c3` was reviewed and integrated as `ac2b687`. PXG/Naver persisted inquiry aggregation now enforces the existing cleanup health gate before serialization while unrelated generic-only stores remain available. The legacy Naver inquiry sync is denied at pre-routing and service levels during trial mode, preventing direct and manual-batch bypass before token, network, sync-log, or local-write work. Customer workflow, retention cleanup, production sessions, and full verification passed independently. Sol may now perform one narrow re-review of these two boundaries.

## D026 - T10 customer inquiry workflow accepted

Sol T10 R2 passed the cleanup gate, legacy-sync gate, security, privacy, and write-boundary review with no blocker. The ordinary operator can view the saved real inquiry, understand missing order and logistics context as a normal state, and use the page on desktop and 390px mobile. Cleanup failures prevent PXG/Naver inquiry metadata from being returned, and legacy Naver inquiry synchronization cannot bypass the guarded persistence path. Customer sending, platform writes, scheduled synchronization, AI automation, and additional real persistence remain disabled. T10 is complete.

## D027 - T11 current-store operator workbench accepted

The owner accepted T11 at commit `61dda9a`. The existing dashboard summary now exposes a four-section operator workbench for the selected store by reusing existing order, warehouse-batch, and customer-inquiry services. Tasks deep-link to existing pages, source failures are isolated, ordinary responses remain privacy-safe, and no task table, duplicate API, platform write, customer send, scheduled sync, or AI execution path was added. Full verification and desktop/390px browser QA passed.

## D028 - T12 extends store overview, not the single-store summary

T12 multi-store workbench extends the existing `GET /dashboard/store-overview` response and keeps `GET /dashboard/summary?store_id=` as the T11 single-store contract. Only active stores granted through active membership, active role, and `dashboard.read` may be aggregated. The backend reuses the T11 workbench builder per authorized store; the frontend must not reclassify tasks. T12 removes dashboard sync execution controls and remains read-only: no batch execution, manual task completion, platform write, customer send, scheduler, or AI action is allowed.

## D029 - T12 multi-store operator workbench accepted

T12 commits `357a7d7`, `cda44ce`, and `9ebbf4e` passed focused multi-store and single-store verification, frontend contracts, session security, production build, full `verify_all.py`, desktop browser QA, 390px browser QA, and Sol final review. The store overview now returns only distinct authorized active stores and aggregates the existing T11 workbench without exposing cross-store data or PII. The frontend supports all-authorized-store and single-store views, switches store context before task navigation, and does not display technical source errors. This acceptance is read-only and does not activate platform writes, customer sending, synchronization execution, task completion, scheduled jobs, AI actions, or additional real persistence.

## D030 - T12-R1 actual local multi-store rehearsal accepted

The commander accepts the actual two-store rehearsal in the isolated local SQLite runtime. The stable test account has access to the existing PXG store and one unmistakably fictional Naver store containing one artificial abnormal order and one artificial open inquiry. Provisioning is idempotent, survives stable-account reprovisioning, and has a guarded cleanup path that preserves PXG records. Local HTTP and browser verification passed authorized-store visibility, unique aggregate tasks, per-store isolation, abnormal-order and inquiry deep links, desktop and 390px operation, and application-console checks. No external marketplace request, synchronization, customer reply, platform write, scheduled action, AI action, credential disclosure, or recipient PII was introduced. The approved rehearsal runtime is `5181/8013`; `5175/8012` is a separate development runtime and is not valid evidence for this trial.

## D031 - Local trial MFA code may be displayed after password verification

The isolated local trial may display the current six-digit TOTP only after the stable configuration administrator has supplied the correct account password and received a valid pending MFA session. The endpoint is default-closed and requires exact `APP_ENV=test`, an explicit process-only enable flag, a loopback socket peer, an allowed local origin, the exact stable account, an active PXG/Naver membership with the configuration-admin role, current session/security versions, and an unexpired pending session. All failures return the same not-found response; the secret is never returned, persisted, logged, or placed in browser storage. Non-test environments fail configuration if the display flag is enabled. The page shows digit cells, countdown, and a fill command, while manual TOTP remains available. Both legacy command files now resolve to the same stable account source. This convenience is not part of production MFA and must remain disabled outside the local rehearsal runtime.

The legacy `pxg-trial-operator` identity is supported only as a local compatibility case because existing browsers may still autofill it. It must satisfy the same test, loopback, pending-session, active PXG membership, and exact trial-role gates, and receives only the code derived from its own encrypted MFA secret. Empty-code failures now present a clear return-to-login action. The stable configuration administrator remains the default account for future operator tests.

## D032 - T13 Naver one-click onboarding and historical orders

The first production-style store onboarding target is Naver only. An administrator submits the store name and Naver API credentials once. The system automatically validates authentication, store identity, required read permissions, and outbound-IP readiness; after success it creates the store and encrypted credential, grants the creator access, and automatically imports the most recent 30 days. Operators are not required to run repeated manual tests or re-enter accepted credentials.

Products and orders are mandatory onboarding datasets. Customer inquiries and logistics are optional until their approved Naver read contracts are confirmed; an unavailable optional source produces an honest partially-available state and automatic retry metadata, not false success and not a block on ordinary product/order operation. All platform writes, customer sending, inventory mutation, and AI execution remain closed.

Historical orders are a view and backfill workflow over the existing order system, not a duplicate order table or page. The Orders page receives Current and Historical views, server-side date/order/product/customer filters, and bounded on-demand Naver read backfill. Retrieved history is locally indexed for after-sales and customer follow-up, remains store-scoped and permission-controlled, does not enter today's workbench, and cannot expose platform write, send, inventory, or AI actions.

## D033 - T13 Naver onboarding accepted

T13 is accepted through commits `065ac83`, `d864f28`, `424b16f`, `f5ce53e`, `a1f03b2`, `c499b08`, `1e534d3`, and `7a6bc54`. The existing store, credential, product, order, checkpoint, and sync-log systems are reused; only durable onboarding state was added. A Naver configuration administrator can enter a store name and Client ID/Secret once, after which the backend validates and provisions the store, grants creator membership, imports the latest 30 days of products and orders, persists progress, and resumes interrupted work automatically. Products and orders are required; inquiry and logistics availability remains honest and partial until approved adapters exist.

Historical query and backfill remain inside the existing Orders page and order table. Backfill is limited to 31 days per request and must end strictly before the same rolling 30-day cutoff used by order classification. Historical-backfill records are defensively excluded from today's workbench and store metrics. The frontend resolves onboarding by the selected store and disables backfill when no matching task exists. Credential correction, resume, and backfill require store-level `credentials.manage`; ordinary members are denied. Validation errors cannot echo request input, and secrets are not stored in URLs or browser storage.

Commander verification passed the T13 frontend contract, core ERP contract, logistics contract, encoding scan, production build, T13 backend verification, and full `verify_all.py`. Standard local runtime browser QA passed the existing store administration page, password-type secret field and clear-on-close behavior, current-order preservation, selected-store onboarding lookup, historical read-only actions, desktop layout, and 390px layout without root overflow. Sol R2 passed security, permission, history, and write-boundary review with no blocker. Platform writes, customer sending, inventory/product mutation, scheduled platform actions, and AI execution remain closed.
