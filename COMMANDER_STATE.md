# Commander State

Last updated: 2026-07-11
Owner: project commander
Status: local isolated PXG artificial-data trial is running and ready for operator rehearsal

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Last accepted code integration: `12718ec`
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
- Real platform reads and writes are disabled; the first rehearsal uses artificial data only.
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
- `6684653`: persistent isolated SQLite trial, artificial PXG data, local credential handoff, and safe start/stop helpers.
- `12718ec`: authenticated store reload, artificial-order visibility, accurate closed-write health status, and exact trial-process shutdown.
- Browser QA passed local login, MFA, one-store isolation, three artificial orders, warehouse page visibility, and closed platform processing.
- First operator rehearsal proved batch persistence after logout/login and exposed two UX gaps; customer order/logistics context and closed-write UI were fixed and browser reverified.
- Sol T06-FINAL-R2: `passed`, no blocker, single-store manual trial approved with real writes disabled.
- Browser QA passed login, MFA, user display, logout, expiry, forbidden state, desktop, and 390px mobile.
- Frontend build, session contract, warehouse contract, production-session verification, warehouse verification, and `verify_all.py` passed before T06-R2.1.

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | `codex2-sol` | `task/t03-6-session-contract` | paused after trial release approval |
| Terra | `codex2-terra` | `task/terra-shipping-backend` | paused after PXG trial configuration acceptance |
| Luna | `codex2-luna` | `task/luna-operator-ux` | paused until a stable UI contract exists |

## Next Action

1. Operator opens the local credential handoff file and signs in at the local frontend URL.
2. Operator runs `OPERATOR_TRIAL_PXG_NAVER.md` once with artificial data.
3. Commander reviews the rehearsal record before allowing real read-only store data.

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.
