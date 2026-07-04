# Phase ERP-Batch-2I: Formal Batch Approval Decision Readonly API Mock Gate

## Purpose

验证未来“正式批量审批决策只读 API”的安全形态。该阶段只做 mock gate，不开放真实后端路由。

## Implemented

- Added `evaluate_formal_batch_approval_decision_readonly_api_mock_gate(...)` in Codex1.
- The gate reuses the final approval decision mock gate from 2F.
- It additionally requires business wording, folded technical details, no execution button, no write endpoint, main-page sensitive field hiding, separate route implementation planning, and closed formal execution boundary.
- `verify_all.py` covers success, missing folded technical detail, accidental public endpoint, sensitive marker blocking, and no-write invariants.

## Boundary

- No public API route.
- No product/order write.
- No audit-row write.
- No platform call.
- No execution approval.

## Result

Future readonly API implementation now has a mock-proven safety contract before any route is added.
