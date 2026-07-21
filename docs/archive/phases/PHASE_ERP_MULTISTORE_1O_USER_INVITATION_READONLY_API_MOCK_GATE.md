# Phase ERP-Multistore-1O: User Invitation Readonly API Mock Gate

Purpose: prove the future user-invitation readonly API shape can be evaluated safely before any real user creation or invitation send.

Result:

- Uses the existing invitation mock gate rules.
- Requires safe user hash, safe login hash, masked login identifier, target stores, target role, manual approval, backup planning, audit planning, and membership-assignment planning.
- Blocks duplicate target users, unmasked login identifiers, missing approval, missing evidence planning, and sensitive markers.
- Keeps `users_written=false`, `membership_written=false`, `role_assignment_written=false`, `real_auth_session_created=false`, and `operation_audit_rows_written=false`.

Boundary:

- No real invite is sent.
- No user, role, session, or membership row is created.
- No Naver API is called.
- Formal product and order batch sync remain closed.
