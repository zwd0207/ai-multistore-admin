# Phase ERP-Multistore-1T: User Invitation Readonly UI Production Wording Cleanup

Purpose: make the Accounts user invitation readonly panel easier for non-technical operators to understand.

Implemented behavior:

- Main UI wording is clear Chinese business wording.
- The page states that real invitations are not open.
- The page states that no user, login session, role assignment, or store membership is written.
- Masked login identifiers are allowed; full identifiers remain hidden.
- Technical flags remain folded in `TechnicalDetails`.

Safety boundary:

- No real invitation is sent.
- No user is created.
- No role or store membership is written.
- No platform API is called.
