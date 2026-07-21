# Phase ERP-Batch-2T: Approval Decision Audit Linkage Readonly API Local Route Mock Gate

## Goal

Verify the local route boundary for a future approval-decision audit-linkage readonly API before exposing it as a backend route.

## Completed

- Added `evaluate_formal_batch_approval_decision_audit_linkage_readonly_api_local_route_mock_gate(...)`.
- Reused the existing approval-decision audit-linkage readonly API mock gate.
- Confirmed the planned route remains review-only:
  - no execution approval
  - no product or order writes
  - no audit-row writes
  - no platform calls
  - no formal batch sync opening

## Safety Boundary

This phase does not expose a public endpoint. It only proves the local route shape can be guarded safely before implementation.

