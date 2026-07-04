# Phase ERP-Batch-2G: Formal Batch Approval Decision Readonly API Plan

## Purpose

Plan a future readonly API for formal batch approval decisions. This phase is a plan only; it does not expose a backend route.

## Planned Contract

Future readonly response should include:

- Decision status in business wording.
- Store scope and sync kind.
- Readonly evidence readiness.
- Backup manifest and rollback evidence.
- Permission gate and human approval requirement.
- Sensitive scan and post-write readback requirement.
- Audit correlation readiness.
- Safety flags showing writes remain closed.

## Technical Fields

Technical fields such as phase, store ids, sync kind, decision id, route path, and write flags should stay in folded details in Codex2.

## Boundary

- No new backend route in this phase.
- No database schema change.
- No real API call.
- No product/order write.
- No approval execution.

## Next Step

The UI may display a readonly decision checklist using business wording while backend route implementation remains a separate phase.
