# Phase ERP-Multistore-2C: Real User Invitation Approval Checklist Mock Gate

## Purpose

固化真实用户邀请前的审批清单 mock 门禁。该门禁只验证材料是否可以进入人工审批，不创建用户、不发送邀请、不分配店铺成员。

## Implemented

- Added `evaluate_real_user_invitation_approval_checklist_mock_gate(...)` in Codex1 permission service.
- The gate requires masked login display, target user hash, target login hash, target stores, target role, admin approval, backup evidence, audit plan, membership assignment plan, invite expiry, one-time invite planning, post-create readback, disable-user rollback instruction, privacy display verification, and login boundary acknowledgement.
- The gate blocks full login identifiers, phone patterns, secrets, tokens, headers, raw-response markers, and any pre-written user or membership state.
- `verify_all.py` covers success, missing expiry, unmasked login identifier, sensitive marker blocking, and no-write invariants.

## Boundary

- No user creation.
- No invitation sent.
- No auth session creation.
- No role assignment.
- No store membership write.
- No audit-row write.

## Result

The project now has a safe checklist gate before any future real user invitation implementation.
