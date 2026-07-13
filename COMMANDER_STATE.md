# Commander State

Last updated: 2026-07-13
Owner: project commander
Status: T13 Naver one-click onboarding and historical orders in progress

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Last accepted integration: `8e48607` (protected order product display and responsive operator shell).
- Last accepted backend integration: `66074a8`
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
- Current local frontend: `http://127.0.0.1:5182/`.
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

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | `codex2-sol` | `task/t03-6-session-contract` | paused; T10 final review passed |
| Terra | `codex2-terra` | `task/terra-shipping-backend` | paused; T10 R1 is integrated and verified |
| Luna | `codex2-luna` | `task/luna-operator-ux` | paused; T10 operator UI passed Gate B |

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

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.
