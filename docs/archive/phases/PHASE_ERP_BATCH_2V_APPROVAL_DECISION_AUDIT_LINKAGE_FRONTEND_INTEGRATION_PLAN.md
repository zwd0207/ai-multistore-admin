# Phase ERP-Batch-2V: Approval Decision Audit Linkage Frontend Integration Plan

## Goal

Plan a Codex2 Orders integration for the approval-decision audit-linkage readonly API.

## Plan

- Orders should call the route-backed readonly API after the existing readonly evidence, audit evidence, and approval decision checks.
- Main-page wording should explain that approval decisions and audit evidence can be reviewed together.
- Technical route metadata, phases, missing flags, and write flags must stay folded in `TechnicalDetails`.
- No execution button should be added.

## Safety Boundary

This phase is planning-only. It does not call Naver, write products, write orders, write audit rows, or open formal batch sync.

