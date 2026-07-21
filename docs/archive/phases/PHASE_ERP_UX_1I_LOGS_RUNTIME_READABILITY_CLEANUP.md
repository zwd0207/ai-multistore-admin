# Phase ERP-UX-1I - Logs Runtime Readability Cleanup

## Summary

Phase ERP-UX-1I applies the Logs and Audit readability plan to the Codex2 runtime Logs page.

This phase modifies Codex2 frontend display only. It does not modify Codex1, does not call platform APIs during validation, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Changes

- Added a top `审计可读性摘要` section for administrators.
- Reframed sync-related records as `同步记录` instead of requiring users to understand backend sync internals.
- Reframed operation logs as `操作记录`.
- Changed visible operation table columns to business-first language:
  - time.
  - business object.
  - action.
  - actor.
  - result.
  - risk.
  - summary.
  - next step.
- Added readable Chinese status/risk labels for mixed Chinese/Korean mock values.
- Moved internal operation details into folded `TechnicalDetails`.
- Updated the detail modal to answer:
  - what happened.
  - who acted.
  - what result/risk was observed.
  - what should happen next.
  - whether recovery evidence exists.

## Technical Field Boundary

Main visible Logs page no longer needs to show:

- `SyncLog`.
- internal log number.
- selected store id.
- raw status.
- raw risk level.
- IP address.
- device.
- source path.
- JSON before/after payloads.

Those details remain folded in administrator-only advanced details.

## Current Limitation

The page still uses mock operation logs for operation history, and backend sync records only when the backend data source is active.

Full production audit coverage is not claimed yet because the real `operation_audit_logs` schema and service are not live.

## Safety Boundary

This phase keeps the existing safety boundary:

- no Codex1 changes.
- no platform API calls.
- no local database writes.
- no schema changes.
- no restore actions.
- no product/order formal sync opening.
- no raw response, token, Authorization, header, signature, or client secret display.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.
- `git diff --check`.
- mock browser walkthrough of `/logs`.

Browser walkthrough should confirm:

- Logs page opens without white screen.
- `审计可读性摘要`, `操作记录`, and `高级日志与审计` are visible.
- Operation detail modal opens.
- JSON before/after payloads stay folded by default.
- No mojibake appears.
- No console errors appear.
- The page does not claim full production audit coverage or formal sync availability.
