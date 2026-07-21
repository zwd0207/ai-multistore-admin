# Phase ERP-Multistore-1P: User Invitation Readonly API Local Implementation

Purpose: expose a local readonly readiness endpoint for later admin UI work without creating users or sending invitations.

Implemented:

- Codex1 added `POST /api/v1/permissions/user-invitation/readonly-check`.
- Codex2 added `dataProvider.checkUserInvitationReadonly(...)` and a mock fallback shape.
- The route wraps the private invitation mock gate and returns business wording for ready, duplicate target user, unmasked login identifier, missing manual approval, and permission-blocked cases.

Safety:

- `invitation_sent=false`
- `users_written=false`
- `membership_written=false`
- `role_assignment_written=false`
- `real_auth_session_created=false`
- `real_database_written=false`
- `operation_audit_rows_written=false`
- `formal_sync_open=false`
- `platform_writes_enabled=false`

Still closed:

- Real login production use.
- Real invitation delivery.
- Real store membership assignment.
- Multi-user production operations.
