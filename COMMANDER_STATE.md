# Commander State

Last updated: 2026-07-11
Owner: project commander
Status: blocked from single-store operator trial pending final security gate

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Integration HEAD: `02aacdd`
- Luna operator authentication and responsive UX are integrated.
- Terra production sessions and write authorization boundary commit `02aacdd` are integrated.
- Sol's last verdict was blocked: session failure previously allowed frontend entry and write routes lacked unified authorization.
- The frontend fail-closed issue and the named write routes are fixed and tested.
- Terra candidate `fd40add` adds default denial for unregistered write endpoints. It is not yet accepted into integration and requires commander verification.
- Real Naver/Coupang writes are forbidden during this gate.

## Active Gate

T06-R2.1 must prove all unsafe production API requests are fail-closed:

- Authentication endpoints are the only deliberate exception.
- Known writes require session, CSRF, store scope, and explicit permission.
- Unregistered or future writes default to denial or `system.configure` authority.
- `api-capability-results` cannot bypass the gate.
- Rejected requests produce no database or platform side effects.

After commander verification, Sol performs one read-only final review. Terra and Luna do not repeat Sol's review.

## Accepted Evidence

- `0b7d948`: login usability, Chinese errors, expiry handling, and mobile layout.
- `22ef5d3`: production session backend.
- `ce924b3`: frontend cookie, CSRF, and session transport.
- `02aacdd`: frontend session fail-closed behavior and named write-route authorization.
- Browser QA passed login, MFA, user display, logout, expiry, forbidden state, desktop, and 390px mobile.
- Frontend build, session contract, warehouse contract, production-session verification, warehouse verification, and `verify_all.py` passed before T06-R2.1.

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | `codex2-sol` | `task/t03-6-session-contract` | high-risk read-only review only |
| Terra | `codex2-terra` | `task/terra-shipping-backend` | T06-R2.1 security engineering |
| Luna | `codex2-luna` | `task/luna-operator-ux` | paused until a stable UI contract exists |

## Next Action

1. Verify Terra commit `fd40add` against the active gate.
2. If it passes, fast-forward integration and run the full verification suite.
3. Send Sol a narrow read-only security and operator-trial review using this file as context.
4. Enter a single-store artificial-data rehearsal only if Sol returns `passed`.

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.

