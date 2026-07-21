# Phase ERP-Batch-2D: Formal Batch Approval Decision Record Plan

## Goal

Plan the decision record required before any future formal product or order batch sync can be approved.

## Decision Record Fields

A future formal batch approval decision record should include:

- `decision_id`
- `store_id`
- `platform`
- `sync_kind`
- `decision_status`
- `decision_label_zh`
- `actor_id_hash`
- `actor_role`
- `approved_scope_summary`
- `readonly_evidence_id`
- `backup_manifest_id`
- `rollback_report_id`
- `permission_gate_status`
- `field_whitelist_status`
- `duplicate_check_status`
- `sensitive_scan_status`
- `post_write_readback_required`
- `operation_audit_correlation_id`
- `formal_sync_open=false` until final approval

## Decision Status

Suggested statuses:

- `draft_review`
- `blocked_missing_backup`
- `blocked_missing_permission`
- `blocked_stale_readonly_evidence`
- `blocked_sensitive_scan`
- `ready_for_human_approval`
- `approved_for_single_execution`
- `rejected`
- `expired`

## Safety Boundary

This phase is planning-only. It does not:

- add schema
- add backend routes
- write audit rows
- write orders or products
- call Naver
- open formal batch sync

## Result

The approval decision record can be designed in a later schema/API phase.
