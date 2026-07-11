# Commander State

Last updated: 2026-07-11
Owner: project commander
Status: blocked from single-store trial by Sol T06-FINAL review

## Mission

Build a management system that an ordinary operator can use without technical knowledge. The first usable loop is:

`platform orders -> warehouse shipping batch -> warehouse spreadsheet return -> validation -> operator confirmation -> platform writeback -> customer-service visibility`

AI automation is deferred until the manual operator workflow is stable and measurable.

## Current Truth

- Integration worktree: `codex2`
- Integration branch: `integration/operator-v1-preview`
- Last accepted code integration: `d37c59b`
- Luna operator authentication and responsive UX are integrated.
- Terra production sessions and write authorization boundary commit `02aacdd` are integrated.
- Sol's latest verdict is blocked: business reads lack authentication, single-store users can trigger all-store sync, and legacy real-platform writes bypass the approved workflow.
- The frontend fail-closed issue and the named write routes are fixed and tested.
- Terra commit `fd40add` adds default denial for unregistered write endpoints and is accepted into integration.
- Real Naver/Coupang writes are forbidden during this gate.

## Active Gate

T06-R3 must close the remaining trial boundary:

- Production business reads require a valid session and store membership.
- Store-list responses expose only stores assigned to the current user.
- A single-store operator cannot call all-store synchronization.
- Legacy shipment writeback and direct customer-reply platform writes are disabled for the operator trial.
- Rejected and disabled paths produce no database mutation or real-platform request.

Terra implements and verifies this boundary. Luna remains paused. Sol reviews only after commander acceptance.

## Accepted Evidence

- `0b7d948`: login usability, Chinese errors, expiry handling, and mobile layout.
- `22ef5d3`: production session backend.
- `ce924b3`: frontend cookie, CSRF, and session transport.
- `02aacdd`: frontend session fail-closed behavior and named write-route authorization.
- `fd40add`: unregistered and future write routes default to privileged denial; capability-result writes are protected.
- Browser QA passed login, MFA, user display, logout, expiry, forbidden state, desktop, and 390px mobile.
- Frontend build, session contract, warehouse contract, production-session verification, warehouse verification, and `verify_all.py` passed before T06-R2.1.

## Worktree Registry

| Role | Worktree | Branch | Current use |
|---|---|---|---|
| Commander | `codex2` | `integration/operator-v1-preview` | integration, verification, memory |
| Sol | `codex2-sol` | `task/t03-6-session-contract` | high-risk read-only review only |
| Terra | `codex2-terra` | `task/terra-shipping-backend` | active on T06-R3 security boundary |
| Luna | `codex2-luna` | `task/luna-operator-ux` | paused until a stable UI contract exists |

## Next Action

1. Terra implements T06-R3 from the current integration branch.
2. Commander verifies and integrates the result.
3. Sol performs one narrow read-only release review.
4. Enter a single-store artificial-data rehearsal only if Sol returns `passed`.

## Compact Reporting Contract

Worker tasks return only:

`STATUS / BRANCH / COMMIT / TESTS / BLOCKER`

The commander records accepted results here. Detailed evidence stays in Git, tests, and `.codex-handoff/`.
