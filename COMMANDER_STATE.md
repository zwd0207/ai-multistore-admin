# Commander State

Last updated: 2026-07-13
Owner: project commander
Status: T18 guarded Naver shipment writeback implementation accepted; real dispatch not authorized

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Last accepted integration: `fd8e565` (T18 identity and carrier hardening after final security review).
- Last accepted backend integration: `fd8e565` (session-backed T18 actions, development-auth closure, and canonical carrier persistence).
- Luna runtime correction `fb88c396` and mobile correction `01a8e52` passed Commander Gate B.
- Luna operator authentication and responsive UX are integrated.
- Terra production sessions and write authorization boundary commit `02aacdd` are integrated.
- Sol T06-FINAL-R2 returned `passed` with no blocker and approved a single-store manual trial with real platform writes disabled.
- The frontend fail-closed issue and the named write routes are fixed and tested.
- Terra commit `fd40add` adds default denial for unregistered write endpoints and is accepted into integration.
- Real Naver/Coupang writes remain forbidden during the trial.
- Persistent local trial database and restricted operator account are provisioned without deployment credentials.
- Current local frontend: `http://127.0.0.1:5181/`.
- T13 is active. Its product target is one Naver store submission with automatic credential/IP/permission validation, automatic 30-day local read import, and no repeated operator test step.
- T13 historical orders extend the existing Orders page and orders table. Queried history is locally indexed for after-sales and follow-up, excluded from today's workbench, and cannot invoke platform writes, customer sends, inventory writes, or AI actions.
- Products and orders are mandatory onboarding datasets. Customer inquiries and logistics may report partially available while their approved Naver read adapters remain incomplete; they must never report false success or block use of successfully imported products and orders.
- Credential handoff exists only in ignored local storage with a current-user Windows ACL.
- T16 is accepted. The existing store overview now surfaces safe automatic-read attention counts and resource guidance; credential and permission blocks can be verified and released through the existing T15 scheduler without running synchronization in the HTTP request.
- Ordinary operators receive only safe status and guidance. Recovery requires same-store `credentials.manage`, `platform.sync`, recent authentication, MFA, and CSRF; cursor, conflict, cleanup, retention, and unknown failures remain nonrecoverable.
- Frontend routes and the administrative layout now load on demand. The production entry chunk is limited to 300 KiB and every JavaScript chunk to 500 KiB; unauthenticated sessions do not download the full data provider.
- T17 is accepted. Naver order-detail reads now populate the existing logistics record and order-event models for recent 30-day orders through the existing T15 scheduler. The task runs about every 30 minutes with a 20-minute lease and a 75-minute checkpoint freshness window.
- Ordinary orders, customer inquiries, the workbench, and logistics traces expose only masked tracking numbers. Expired snapshots are evaluated at serialization time, marked stale, and do not return tracking values. A newer explicit no-logistics snapshot clears the previous encrypted/hash/masked tracking values and fails closed.
- The legacy T13 product-order-hash identifier is accepted only after an exact same-store, same-platform, unique product-order match. New T13 records use the correct platform-order hash.
- Customer platform replies now require both global real-write and customer-write settings inside the service before inquiry lookup, credential access, token retrieval, or network work. The approved trial keeps both switches off.
- T18 is implementation-accepted. It reuses the existing warehouse batch, approval grant, T17 readonly preflight, session permissions, and audit flow. The only real shipment endpoint is `POST /api/v1/shipping/warehouse-batches/{batch_id}/writeback`.
- The pilot remains limited to the exact PXG/Naver store, one active product-order row, one bound credential, one candidate hash, and at most one dispatch attempt. Approval and execution require a session-backed identity, MFA, recent authentication, CSRF, same-store permission, two authoritative readonly preflights, and an atomically claimed one-use attempt.
- Ambiguous post results remain `unknown` and cannot be resent. They permit readonly reconciliation only. Unapproved or tracking-like carrier values are rejected before preflight; ordinary orders and events retain only canonical carrier code/label and tracking hashes.
- Sol's initial T18 review found development-identity and carrier-field blockers. Commander commit `fd8e565` closed both, and Sol's narrow re-review passed with no blocker. No real Naver write was executed or authorized.

## Active Trial Boundary

- Selected trial store: `pxg球包店` on `Naver`.
- Frontend mock id is `8`; the backend read-only store id must be resolved by exact name and platform, never assumed.
- The operator works manually; AI and automatic platform actions remain off.
- Guarded real reads are approved only for `pxg球包店 / Naver`; all real platform writes remain disabled.
- Guarded local persistence code is merged but default-disabled; no approval has been given to save real platform data.
- T09 automatic cleanup, encrypted backup lifecycle, restore drill, and batch-specific rollback are implemented and commander-verified.
- Guarded real refresh, backup, rollback, immediate expiry gates, and daily cleanup passed Sol re-review.
- Sol passed the final T09 safety review: immutable terminal deletion, non-extension by later updates, and the 30-day maximum all passed.
- Sol did not authorize activation; real persistence remains disabled pending a separate commander approval.
- Before activation, define how long non-PII historical order records remain searchable by platform order number. Recipient PII remains subject to the approved 7-day/30-day deletion boundary.
- Customer follow-up profiles and advanced privacy policy are deferred until the core operator workflow is usable.
- Existing privacy, write-disable, backup, rollback, and recipient deletion controls remain unchanged as the minimum safety baseline.
- The isolated local trial now has one exact `pxg球包店 / Naver` store, a restricted backup root, a local backup encryption key, successful cleanup health, and local Naver readonly credentials configured without exposing secrets.
- The owner approved and the commander executed one bounded real-read persistence batch: 3 products, 0 orders, 0 logistics records, and 1 customer inquiry. The empty order/logistics result reflects the current approved platform read window.
- The encrypted backup and pre-write restore drill passed. Persistence, activation, retention approval, and backup/rollback approval switches were closed immediately after the run; all platform writes remain off.
- Current local frontend: `http://127.0.0.1:5181/`.
- T12-R1 isolated multi-store rehearsal frontend: `http://127.0.0.1:5181/` with backend `http://127.0.0.1:8013/`. Do not use the separate `5175/8012` development runtime for this rehearsal.
- Local trial restarts now stop the previous recorded processes before selecting ports, keeping the preferred `5181/8013` addresses stable.
- After the stable account password is accepted, the local trial MFA page displays the current six-digit test code, countdown, and a fill command. This is available only for the exact stable configuration administrator in an active pending MFA session over loopback with `APP_ENV=test` and an explicit local-process flag. It is unavailable in every normal or production environment.
- The legacy local `pxg-trial-operator` remains accepted only as a compatibility login for existing browser credentials and receives its own session-bound local code under the same loopback/test gates. A failed or expired display now shows an explicit return-to-login action instead of empty unexplained digit cells.
- All future operator tests use the stable local configuration administrator shown by `查看真实只读配置账号.cmd`; only its MFA code rotates. The older trial-operator account is no longer the user-facing test account.
- Retention cleanup now enforces no-status, manual-review, failure, disabled-switch, and overdue daily health gates.
- Platform shipment writeback and customer-message sending remain disabled.
- Full recipient PII remains limited to the authorized warehouse fulfillment path.
- Every failure, manual workaround, and unclear screen is recorded as trial feedback.

## Accepted Evidence

- `0b7d948`: login usability, Chinese errors, expiry handling, and mobile layout.
- `22ef5d3`: production session backend.
- `ce924b3`: frontend cookie, CSRF, and session transport.
- `02aacdd`: frontend session fail-closed behavior and named write-route authorization.
- `fd40add`: unregistered and future write routes default to privileged denial; capability-result writes are protected.
- `b81365c`: production reads require sessions and store membership; all-store sync is privileged; legacy shipping and direct customer platform replies are disabled.
- `eaef7f6`: PXG store is resolved by exact database name and platform; artificial-data-only runtime and single-store trial role are enforced.
- `8213f66`: guarded PXG/Naver real read-only preview passed for products, masked orders, masked logistics details, and customer inquiries.
- `64f1a88`: default-closed PXG/Naver local persistence, encrypted recipient isolation, resource freshness, legacy order uniqueness, and multi-item order support passed Terra verification and Sol final security review.
- `7ec7baf`: default-closed activation precheck, three-order fictional simulation, and temporary SQLite backup/restore drill passed commander verification.
- `e9873a7`: PXG-only retention cleanup, privacy deletion, cleanup audit, unfinished-batch freeze, daily health gate, and recovery tests passed commander verification.
- `6f34793` through `5d8c5ba`: encrypted SQLite backup, checksum and structure verification, Windows ACL isolation, privacy-derived backup expiry, restore drill, batch rollback, warehouse rollback protection, backup retention audit, and failure gates passed commander verification.
- `2010c6b` through `f8eb11b`: real refresh safety routing, source integrity, immutable terminal timing, pre-write restore failure handling, immediate expired-backup blocking, daily cleanup lifecycle, isolated lock recovery, and explicit lifecycle tests passed commander verification and `verify_all.py`.
- `b213c68` and `66eff2d`: actual recipient deletion uses immutable terminal time, with a regression test proving later order updates cannot extend the deadline and an independent full verification pass.
- `6684653`: persistent isolated SQLite trial, artificial PXG data, local credential handoff, and safe start/stop helpers.
- `12718ec`: authenticated store reload, artificial-order visibility, accurate closed-write health status, and exact trial-process shutdown.
- Browser QA passed local login, MFA, one-store isolation, three artificial orders, warehouse page visibility, and closed platform processing.
- First operator rehearsal proved batch persistence after logout/login and exposed two UX gaps; customer order/logistics context and closed-write UI were fixed and browser reverified.
- T10 Commander Gate B desktop verification passed: the saved real inquiry is visible, the no-related-order state is honest, reply is disabled, the detail modal works, and the browser console is clean.
- T10 Commander Gate B initially found 390px filter and header overflow; the detail modal already fit and scrolled correctly.
- T10 Luna R3 corrected the 390px filter and header overflow. Commander browser verification passed desktop and mobile layouts, real inquiry visibility, no-related-order detail, disabled reply controls, clean console, and persistence after logout/login.
- Real read-only evidence on 2026-07-12: 3 product summaries, 2 masked orders, 2 masked logistics details, and 3 customer inquiries; HTTP reads succeeded, local business state remained unchanged, and no credentials or complete recipient PII were returned.
- Sol T06-FINAL-R2: `passed`, no blocker, single-store manual trial approved with real writes disabled.
- Browser QA passed login, MFA, user display, logout, expiry, forbidden state, desktop, and 390px mobile.
- Frontend build, session contract, warehouse contract, production-session verification, warehouse verification, and `verify_all.py` passed before T06-R2.1.
- `61dda9a`: T11 reused the existing dashboard summary, order, warehouse, and inquiry services to deliver a real current-store workbench with four task sections and deep links. Full verification, desktop QA, and 390px QA passed; no production write or automation path was opened.
- `357a7d7`, `cda44ce`, and `9ebbf4e`: T12 added an authorized multi-store workbench to the existing store overview, removed dashboard synchronization controls, preserved single-store deep links, and enforced session/MFA plus active membership, role, store, and `dashboard.read`. Focused tests, `verify_all.py`, desktop QA, 390px QA, and Sol final review passed.
- `4a42f62`, `6729702`, and `a4bf490`: T12-R1 added an idempotent local-only second-store fixture, preserved it across stable-account provisioning, aligned its source and abnormal-order status with the existing workbench contract, and provided guarded cleanup without touching PXG data.
- `7589f2f` and `11e0a3e`: the dashboard store table is fully operable at 390px and the existing order page recognizes backend `rawStatus` during abnormal-order deep links.
- Actual browser QA passed exactly two authorized stores (`pxg球包店` and `[FICTIONAL][LOCAL][T12] Naver Multi-store Demo`), aggregate task uniqueness, single-store isolation, abnormal-order and inquiry deep links, desktop layout, 390px layout, and a clean application console. All observed business traffic stayed on localhost; no sync, reply, writeback, platform write, or AI action was called.
- `15975f7`, `975a481`, `279e0c8`, `8c36797`, and `9c1fce7`: local-only graphical MFA display, strict backend gates, unified response contract, stable trial ports, and correct pending-session timing passed focused tests, full verification, desktop login, and 390px browser QA. Both legacy `.cmd` entries now use the same stable configuration-admin credential source.
- `065ac83`, `d864f28`, `424b16f`, `f5ce53e`, `a1f03b2`, `c499b08`, `1e534d3`, and `7a6bc54`: T13 delivers resumable Naver store onboarding, automatic recent-30-day product/order import, and store-scoped historical order query/backfill through the existing order system. Secret validation output is redacted, configuration writes require store-level `credentials.manage`, historical backfill is strictly older than the current 30-day window, and historical sources are excluded from today's workbench and metrics. Focused tests, frontend contracts/build, full `verify_all.py`, desktop/390px browser QA, and Sol final review passed.
- `be091e8`, `e92bc18`, `5afcfa4`, `fe84b43`, `c290e70`, and `ca915b5`: T14 replaces the blocked legacy Naver inquiry sync with a store-scoped inquiry-only readonly path. Inquiry content is encrypted at rest, retained for an immutable maximum of 30 days, omitted from list/log/audit output, and decrypted only through a permission-gated detail request. Real PXG browser verification imported 19 Naver inquiries, displayed a real detail with preserved store/order context, kept reply disabled, and passed 390px layout. Focused tests, build, full `verify_all.py`, and Sol final review passed.
- `d55bebc`, `dae8fd2`, `471456e`, `24092c9`, `ae001f1`, and `0a56e39`: T15 adds one store-isolated Naver readonly scheduler using existing checkpoints, logs, T13 readers, and T14 inquiry service. Real PXG orders and inquiries run about every 10 minutes, products about every 2 hours, and logistics remains explicitly unsupported. The pre-T13 PXG store is admitted only through an active configured credential plus successful approved readonly evidence; the fictional store remains disabled. Real browser QA showed successful reads, next-run times in KST, desktop and 390px containment, and no platform writes. T13/T14/T15, production sessions, frontend build/encoding, and full `verify_all.py` passed.
- `1c9fcc7` through `9975db6`: T16 extends the existing store overview, T15 checkpoints/scheduler, connection editor, and workbench status panel. It adds safe exception summaries, store-scoped verify-and-recover, connection deep links, administrator/ordinary-operator response separation, and 68-second recovery polling without a new table, scheduler, log, page, or platform write path. T13-T16, production sessions, frontend contracts/build/encoding, full `verify_all.py`, desktop browser QA, 390px browser QA, and Sol final review passed.
- `8937d2d`: frontend business routes, the administrative layout, and the large data provider load on demand. The entry bundle fell from 901 KB to 253 KB, the data-provider chunk is 351 KB, all 37 JavaScript chunks pass enforced budgets, and the production build no longer emits the 500 KB warning. Browser QA passed login, workbench, orders, shipping, customer service, and 390px containment; invalid 200-row list requests were corrected to the backend limit of 100.
- `35b6f54` through `f60a754` and `fccb90b` through `8199f2e`: T17 reuses Naver order-detail reads, existing logistics records/events, T15 checkpoints/logs, order trace, inquiry context, and existing frontend pages. A bounded real PXG read checked 6 saved product-order candidates, produced 5 valid encrypted logistics snapshots and one honest no-logistics result, and ended with the logistics checkpoint at `success` and `platform_write=false`. T13-T17, production sessions, all frontend contracts, build, encoding, session security, bundle budget, final `verify_all.py`, desktop QA, 390px QA, and Sol final review passed.
- `077ad0b` through `44ad315` and `fd8e565`: T18 adds a single guarded warehouse-batch Naver shipment writeback path without a new table, scheduler, batch system, or public legacy execute route. Commander independently passed T18, warehouse, reprocess, production sessions, full `verify_all.py`, frontend contracts/build/encoding/session/bundle gates, and desktop/390px browser QA. Sol's final narrow review passed development-identity closure, canonical carrier handling, privacy, idempotency, and duplication checks. All real-write flags remain off and no dispatch was sent.
- T19 reuses the existing store model, store selector, store page, session/MFA/store-permission gates, local audit writer, and approved `ziniao-cli` profile to add one `打开店铺后台` action. No second store system, login table, page, scheduler, arbitrary URL handoff, or platform write path was added.
- T19 Commander browser QA passed the exact `pxg球包店 / Naver` handoff to the owner-approved unique Ziniao store, `planned -> success` privacy-safe audit, unbound fictional-store disablement, store-switch feedback reset, desktop layout, and 390px containment. The local database contains exactly the original two stores and passes SQLite foreign-key verification; no Ziniao ID, IP, API key, token, store mapping, or raw CLI response is persisted in source or returned.
- T20 is accepted in the local trial runtime. The real Ziniao directory contained 19 source entries; 17 business/open-only stores were admitted (11 Naver, 4 Coupang, and 2 custom), while 2 email entries were excluded and the existing local non-Ziniao trial store remained unmanaged. Startup and five-minute refresh use the existing lifecycle loop, complete-snapshot validation, one-transaction commit, encrypted external IDs/IPs, seven-day GeoIP caching, and two-miss archival. Manual memberships are preserved and local orders, logistics, inquiries, audits, and membership history remain intact.
- T20 browser QA passed the logged-in store management page, archived-store toggle, 17 active directory stores plus one unmanaged local store, full-IP permission display, desktop containment, and 390px containment. Store opening remains guarded by the existing Ziniao path; no external ID, username, password, token, raw CLI response, or complete IP enters ordinary API output/logs, and all platform writes, customer replies, inventory/product mutation, shipment writeback, scheduled platform actions, and AI actions remain disabled.

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | review-only | final gate | T18 final re-review passed; closed |
| Terra | `codex2-terra` | `task/t18-terra-fix` | T18 backend integrated and verified; paused |
| Luna | `codex2-luna` | `task/t18-luna-fix` | T18 frontend integrated and verified; paused |

## Next Action

1. Keep `PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED` disabled.
2. Treat the real-read result as owner-accepted; do not repeat platform-read investigation without regression evidence.
3. Terra Gate A remains integrated as `66074a8`; the new Terra R1 scope is limited to the two Sol-confirmed backend boundary defects.
4. Luna commits `fb88c396` and `01a8e52` passed focused tests, build, desktop and 390px browser verification, real inquiry visibility, empty-order handling, disabled reply checks, and logout/login persistence.
5. Sol Phase C found two valid blockers: PXG inquiry aggregation lacks the retention cleanup gate, and legacy Naver inquiry sync can bypass guarded persistence during trial mode.
6. Terra commit `deb14c3` is integrated as `ac2b687`. Customer workflow, retention cleanup, production sessions, and full `verify_all.py` passed independently.
7. Sol T10 R2 passed cleanup, legacy sync, security, privacy, and write-boundary review with no blocker.
8. T11 is accepted at `61dda9a`.
9. T12 is accepted under `.codex-handoff/T12-SOL-CONTRACT.md`.
10. The multi-store workbench remains read-only. It does not authorize synchronization, bulk execution, platform writeback, customer sending, or AI actions.
11. Do not run another real persistence batch without a new explicit approval.
12. T12-R1 actual local multi-store rehearsal is accepted. Keep the fictional second store for repeatable operator testing; use its guarded cleanup script when the fixture is no longer needed.
13. The next product phase may build on verified multi-store visibility and navigation. It must not treat this fictional-store rehearsal as approval for a second real marketplace connection or any platform write.
14. Operators no longer need a `.cmd` file to obtain the local trial MFA code. Use the code displayed on the confirmation page; keep the `.cmd` entries only as a fallback for the same stable account.
15. T13 is accepted. The next controlled operator action is to add one Naver store through `店铺与平台连接 -> 添加 Naver 店铺` with its real Client ID/Secret and observe automatic validation and the initial 30-day import. Do not enable platform writes.
16. T14 is accepted. Naver inquiry refresh uses only the approved inquiry endpoint and local encrypted storage. Keep the legacy inquiry sync and every customer reply/platform write path closed.
17. T15 is Commander-verified in the isolated local trial. Keep `AUTOMATIC_READ_SYNC_ENABLED=true` only for this approved runtime; global/default configuration remains false.
18. T17 Naver logistics readonly is accepted. Keep it on the existing T15 scheduler and Naver order-detail read path; never substitute warehouse writeback or a platform write endpoint.
19. T16 automatic-read exception recovery is accepted. Keep transient failures on automatic retry; only credential and known permission blocks may use verify-and-recover.
20. Logistics automatic read is supported for approved Naver stores. Missing checkpoints and stores without approved credentials remain disabled; failures continue through T15 retry and T16 attention handling.
21. The next phase should improve operator handling of the refreshed order, inquiry, product, and warehouse data without creating a second scheduler, task table, order table, inquiry service, or platform-write path.
22. The next product decision is a separately approved single-store manual write trial: either shipment writeback or customer reply, not both at once. Until that decision, all real platform writes remain closed.
23. Keep `npm run bundle:verify` in every frontend acceptance run. Current baseline: 252,851-byte entry, 37 JavaScript chunks, all within budget.
24. T18 implementation is accepted, but real Naver shipment dispatch is not authorized. Keep `REAL_API_WRITE_ENABLED=false`, `SHIPPING_PLATFORM_WRITE_ENABLED=false`, `PXG_NAVER_SHIPPING_PILOT_ENABLED=false`, `PLATFORM_ORDER_WRITE_ENABLED=false`, and `ALLOW_DEV_AUTH=false` for any future pilot runtime until the owner explicitly approves one exact product-order candidate.
25. T19 local Ziniao store opening is accepted for the exact bound Naver store. New stores remain disabled until an administrator configures an exact `browser_profile_name`; opening a browser does not authorize Naver reads, writes, customer replies, or AI actions.
26. T20 directory synchronization and IP display are accepted for the local trial only. Keep the existing lifecycle loop, email exclusion, two-miss archival, store permissions, IP encryption, and no-platform-write boundaries in place; do not expose external IDs or complete IPs to unauthorized members.

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.

## T21-T22 Production Baseline Evidence (2026-07-17)

- Candidate release `ca3a213e2aa7eee557c78c2fa37aa52547b8e63a` is pushed to `origin/release/operator-v1`; GitHub `Verify release candidate` run `29565215300` completed successfully.
- Local frontend gates passed: encoding scan, session security, bundle budget, and production build. The entry chunk is about 268 KB and 38 JavaScript chunks pass the budget.
- Backend `verify_all.py` passed in `codex1/backend/.venv`, including T13-T20, production sessions, PostgreSQL migration contract, backup contract, and security scans. T22 live migration verification remains intentionally skipped until the migration window.
- Server baseline archive `/srv/release-archives/t21-baseline-20260717T080903Z` was created with root-only permissions. Its SHA256 manifest passed. SQLite integrity is `ok`, source and backup counts match, and `production_database_modified=false` (2 stores, 18 orders, 10 products, 2 credentials).
- HTTPS, Nginx, PostgreSQL, and `ai-multistore-api` are active on the production host. Certbot renewal dry-run passed. The live application still points to the formal SQLite database; this is intentional until migration approval.
- PostgreSQL `ai_multistore` has the Alembic revision `608122e7c9e6` and no application rows. The candidate release was staged at `/srv/releases/t21-ca3a213`; an isolated release virtualenv was used for the rehearsal.
- SQLite-to-PostgreSQL dry-run returned `migration_ready`, preserved the source SHA-256, reported `platform_admin_bootstrap_required=true`, and did not copy rows. Target counts remain zero except `alembic_version=1`.
- T22 is not production-complete: do not execute the one-time migration, bootstrap the initial platform administrator, switch `DATABASE_URL`, or enable the PostgreSQL OSS timer until the owner confirms the migration window, approved administrator email/display name, and private OSS bucket name. Do not request or store AccessKeys in chat.

## T23-T24 Release Candidate Evidence (2026-07-17)

- Terra T23 commit `6498d569e7fe0d19d1509e9af83a72280e572162` and Luna T23/T26 boundary commit `2a970e007f8921ded32ab206fe6ff19eb42f3daa` are integrated into `release/operator-v1`; T24 readonly inquiry hardening is integrated as `e31aa51`.
- T23 email delivery is guarded and disabled by default. SMTP SSL/STARTTLS, HTTPS public URL, secret redaction, invitation/password-reset safety, and tenant-auth contracts passed with mocked delivery only. No real email was sent.
- T24 Naver inquiry readonly uses the approved inquiry endpoint, KST 30-day window, complete pagination validation, one-second page spacing, shared store/resource lease, safe 400/429/5xx classification, and the existing T14 encrypted retention path. The legacy generic inquiry route remains closed. The release candidate began with `safe_to_real_test=false`; the owner-approved PXG probe later supplied the missing SELF and `order_seller` evidence.
- Correct-environment verification passed: T13-T20, T23, T24, production sessions, frontend auth/mobile contracts, encoding, production build, bundle budget, Ziniao contract, and full `verify_all.py`. The only intentional skip is the T22 live PostgreSQL migration test because no disposable `T22_TEST_POSTGRES_URL` is configured.
- Current frontend build produced a 273,625-byte entry chunk and 38 JavaScript chunks; `bundle:verify` passed. No bundle warning blocks this candidate.
- GitHub Actions `Verify release candidate` run `29568334003` for `ee3d17f51c994922ec2903e516167e6167166ac0` passed all three jobs: secret history, frontend contracts/build, and backend full verification.
- The owner confirmed that the previously requested Aliyun console-side configuration is complete. This does not by itself authorize a production database cutover, real SMTP send, OSS backup activation, or a real Naver request; each remains a separate controlled gate.

## Current Release Gate

- Production cutover completed on `2026-07-17` from the approved `19:00 Asia/Shanghai` window. The backend cutover release remains `820bfab6c4cc23fd716f2fb61e2070d1780720e1`; the production frontend includes authenticated-acceptance hotfix `f3036e32321756997e5b54f6bd720289b97d6838`. GitHub Actions runs `29572971660` and `29582534495`, local `verify_all.py`, server build, Sol security review, disposable migration, and isolated production startup all passed.
- The live application now uses local PostgreSQL 16 at Alembic revision `d4b7a91c2e6f`. All 29 migrated table digests matched the protected SQLite source: 2 stores, 18 orders, 10 products, and 2 encrypted credentials. Credential decryption and PostgreSQL constraint validation passed; legacy sessions were not migrated.
- The final SQLite source, two protected copies, previous backend, and previous frontend remain available for configuration rollback. A protective pre-activation abort restarted the old service once; a second stopped-service snapshot proved all 29 logical table digests unchanged before activation resumed.
- HTTPS, HTTP redirect, production session configuration, unauthenticated 401 behavior, new frontend assets, and zero post-activation API error log lines passed. Real Naver reads, lifecycle schedulers, email delivery, Ziniao server integration, platform writes, customer replies, shipment dispatch, inventory/product mutation, and AI operations remain disabled.
- The first age-encrypted PostgreSQL backup uploaded to private OSS with object-private ACL, OSS AES256, and remote size/SHA-256 readback. Restore into a disposable PostgreSQL database matched all 48 production table counts, the Alembic revision, constraints, and credential decryption; plaintext restore files and the disposable database were removed. The hourly timer is active.
- The bootstrap platform-administrator invitation was accepted, password and TOTP MFA enrollment completed, ten unused recovery codes exist, and an MFA-verified tenant-selected session passed production acceptance. The administrator display name was corrected with a Unicode-safe PostgreSQL update after the bootstrap shell had stored six question marks. Both protected copies of the consumed invitation token were deleted after acceptance.
- OSS `DeleteObject` permission for the backup prefix is accepted. The two private preflight objects were removed, a new upload/read/delete probe passed, the hourly encrypted backup passed again, and the protected T22 evidence now records `authenticated_acceptance=passed` and `oss_delete_permission=passed` with a regenerated 7/7 SHA-256 manifest.
- Authenticated browser QA passed the 1440px workbench, two-store switching, orders, shipping, customer service, store connection, tenant invitation, and 390px mobile navigation with no root overflow or console errors. Hotfix `f3036e3` closes the mobile More menu on every route change and was deployed atomically without restarting PostgreSQL or the backend.
- Keep real platform writes, real customer replies, and real shipment dispatch disabled. The owner selected the exact PXG Naver store and authorized one controlled inquiry GET after the cooldown; that probe passed. Do not repeat it, fetch the remaining pages, enable persistent inquiry reads, or start automatic synchronization without a new explicit approval.
- T24 controlled production evidence: commit `adacd19` adds a one-shot probe guarded by exact store/name hash, one active credential, closed write/test/scheduler gates, lease and 429 cooldown checks, one business GET, zero follow-up pages, safe capability evidence, and unchanged business counts. GitHub Actions run `29584540587` passed. Production returned HTTP 200 for page 1 size 10, reported 35 total inquiries across four pages, confirmed `order_seller`, saved no raw response or inquiry content, and left all automatic-read and platform-write settings false.
