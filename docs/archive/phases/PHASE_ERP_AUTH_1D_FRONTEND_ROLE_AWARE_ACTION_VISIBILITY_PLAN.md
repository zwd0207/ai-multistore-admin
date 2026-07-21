# Phase ERP-Auth-1D: Frontend Role-Aware Action Visibility Plan

ERP-Auth-1D plans how Codex2 should show role-aware actions to non-technical users.

## Scope

This phase is planning-only:

- No Codex2 runtime code change
- No backend public permission API
- No schema change
- No local data write
- No platform API call

## UI Rules

Main pages should not expose technical permission keys as primary text.

Business wording should be:

- "You can view this store."
- "This action requires administrator approval."
- "You do not have permission to perform this action."
- "This action is not available because formal sync is not open."

Technical fields such as role key, permission key, store scope, and gate skip reason should stay in folded advanced details only.

## Page Impact

- Dashboard: show whether the current user can view store summaries and whether sensitive work needs approval.
- Orders: hide or disable local write/refresh actions unless the role and approval gate allow them.
- Products: keep formal batch sync unavailable unless separately approved.
- Logs/Audit: show readonly audit access for auditor/admin/owner; hide write/delete/export controls.
- Credentials: allow only owner/admin paths to plan credential updates; still require separate approval.
- Backups: show reports broadly, but backup create/restore stays approval-gated.

## Next Stage

`Phase Naver-ERP-20A: Controlled order refresh batch with audit approval plan`
