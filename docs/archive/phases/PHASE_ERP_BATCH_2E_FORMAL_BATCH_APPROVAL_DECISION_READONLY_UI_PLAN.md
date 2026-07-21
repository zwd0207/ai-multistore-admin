# Phase ERP-Batch-2E: Formal Batch Approval Decision Readonly UI Plan

## Goal

Plan a readonly Codex2 UI surface for future formal batch approval decision records.

## Proposed UI

The UI should show a business-first decision summary:

- approval status
- store and platform
- batch type
- candidate count
- backup status
- permission status
- rollback readiness
- sensitive scan status
- readback requirement
- whether the approval is expired

## Technical Details

The following fields should remain folded:

- `decision_id`
- `readonly_evidence_id`
- `backup_manifest_id`
- `rollback_report_id`
- `operation_audit_correlation_id`
- `actor_id_hash`
- `field_whitelist_status`
- `duplicate_check_status`
- `formal_sync_open`

## Safety Boundary

This phase does not implement the UI yet. It is a UI plan only.

Future implementation must remain readonly until a separate write phase is explicitly approved.

## Result

The next UI implementation can add a decision summary panel without opening formal sync.
