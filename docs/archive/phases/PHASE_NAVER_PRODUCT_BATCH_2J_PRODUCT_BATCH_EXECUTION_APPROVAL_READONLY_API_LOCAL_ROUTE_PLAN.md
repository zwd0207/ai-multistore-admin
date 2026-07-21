# Phase Naver-Product-Batch-2J: Product Batch Execution Approval Readonly API Local Route Plan

## Goal

Plan a future local readonly route for Naver product batch execution approval evidence.

## Planned Route

```text
POST /api/v1/batch/naver/products/execution-approval/readonly-check
```

The route may wrap `evaluate_naver_product_batch_execution_approval_readonly_api_mock_gate(...)` in a later phase.

## Safety Boundary

This phase does not expose the route, call Naver, approve execution, write products, write audit rows, or open formal product batch sync.

