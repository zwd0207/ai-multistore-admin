# Phase ERP-Batch-2K: Formal Batch Approval Decision Readonly API Local Route Mock Gate

## Purpose

Verify the local route boundary before exposing the formal batch approval-decision readonly API.

## Implemented

- Added `evaluate_formal_batch_approval_decision_readonly_api_local_route_mock_gate(...)`.
- The gate wraps the 2I readonly API mock gate.
- It records the planned route path and method while keeping `public_endpoint_enabled=false` and `backend_route_implemented=false`.
- It continues to block execution approval, business writes, audit writes, SyncLog writes, tested-success writes, platform writes, and sensitive markers.

## Boundary

- No public route in 2K.
- No product/order write.
- No audit-row write.
- No platform call.
- No execution approval.

## Result

The future local route has a mock-proven contract before implementation.
