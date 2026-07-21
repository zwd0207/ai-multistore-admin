# Phase ERP-Batch-2O - Formal Batch Approval Decision Audit Linkage Plan

## Goal

Plan how a future formal batch approval decision should link to append-only audit evidence before any execution phase.

## Required Linkage

- Approval decision record id.
- Readonly evidence snapshot hash.
- Backup manifest reference.
- Permission approval evidence.
- Sensitive scan evidence.
- Readback plan and result reference.
- Rollback report reference.
- Operator identity hash and store scope.

## Safety Boundary

This phase is plan-only. It does not write audit rows, does not approve execution, and does not open product/order batch sync.

## Next Use

Future execution phases should require this audit linkage before any local product/order write.
