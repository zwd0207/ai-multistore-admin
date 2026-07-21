# Phase ERP-Batch-1M: Batch Approval Evidence Audit Linkage Plan

## Purpose

Record that future batch approval evidence must link to audit rows before any formal product or order batch write can be considered.

## Planned Linkage

- Readonly evidence should mark audit evidence as planned.
- Future write phases must create append-only audit chains for approval, backup, execution, and verification.
- UI should show audit readiness as a business requirement while keeping audit ids and diagnostics folded.

## Boundary

- No audit row is written in this phase.
- No product or order batch write is executed.
- Formal batch sync remains closed.
