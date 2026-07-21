# Phase ERP-Multistore-1R: User Invitation Readonly UI Display

Purpose: implement the Accounts-page user invitation readiness panel in backend and mock data modes.

Implemented:

- Added `UserInvitationReadonlyPanel`.
- Mounted it in backend Accounts and mock Accounts pages.
- The panel calls `dataProvider.checkUserInvitationReadonly(...)`.
- The main UI shows only business conclusions: readiness, real invitation closed, selected store scope, and masked login display.
- Technical fields remain folded in `TechnicalDetails`.

Safety:

- No real invitation is sent.
- No user, session, role assignment, or store membership is created.
- No Naver API is called.
- No orders, products, SyncLog, tested-success rows, or audit rows are written.
