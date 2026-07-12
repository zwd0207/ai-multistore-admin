# Commander State

Last updated: 2026-07-12
Owner: project commander
Status: T10 customer inquiry runtime passed; Luna mobile layout correction pending

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Last accepted backend integration: `66074a8`
- Luna runtime correction is present at `fb88c396` but is not yet accepted by Commander Gate B.
- Luna operator authentication and responsive UX are integrated.
- Terra production sessions and write authorization boundary commit `02aacdd` are integrated.
- Sol T06-FINAL-R2 returned `passed` with no blocker and approved a single-store manual trial with real platform writes disabled.
- The frontend fail-closed issue and the named write routes are fixed and tested.
- Terra commit `fd40add` adds default denial for unregistered write endpoints and is accepted into integration.
- Real Naver/Coupang writes remain forbidden during the trial.
- Persistent local trial database and restricted operator account are provisioned without deployment credentials.
- Current local frontend: `http://127.0.0.1:5181/`.
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
- T10 Commander Gate B mobile verification at 390px is blocked: the filter row is clipped beyond the right viewport edge and the top account/role area crowds adjacent controls. The detail modal itself fits and scrolls correctly.
- Real read-only evidence on 2026-07-12: 3 product summaries, 2 masked orders, 2 masked logistics details, and 3 customer inquiries; HTTP reads succeeded, local business state remained unchanged, and no credentials or complete recipient PII were returned.
- Sol T06-FINAL-R2: `passed`, no blocker, single-store manual trial approved with real writes disabled.
- Browser QA passed login, MFA, user display, logout, expiry, forbidden state, desktop, and 390px mobile.
- Frontend build, session contract, warehouse contract, production-session verification, warehouse verification, and `verify_all.py` passed before T06-R2.1.

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | `codex2-sol` | `task/t03-6-session-contract` | paused until T10 Commander Gate B passes |
| Terra | `codex2-terra` | `task/terra-shipping-backend` | paused; T10 backend contract is complete |
| Luna | `codex2-luna` | `task/luna-operator-ux` | execute T10 R3 mobile layout correction only |

## Next Action

1. Keep `PXG_NAVER_LOCAL_READ_PERSISTENCE_ENABLED` disabled.
2. Treat the real-read result as owner-accepted; do not repeat platform-read investigation without regression evidence.
3. Terra Gate A is complete and integrated as `66074a8`; do not assign more backend work unless Luna finds a contract defect.
4. Luna runtime correction `fb88c396` passed focused tests, build, desktop browser verification, real inquiry visibility, empty-order handling, and disabled reply checks.
5. Luna executes `.codex-handoff/T10-LUNA-R3.md` to fix only the 390px filter and header overflow. Terra and Sol remain paused.
6. After Luna R3 integration and commander desktop/mobile browser verification, Sol performs the single final T10 boundary review.
7. Do not run another real persistence batch without a new explicit approval.

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.
