# Phase ERP-Multistore-1S: User Invitation Readonly UI Walkthrough

Purpose: verify the Accounts-page user invitation readiness panel is usable in backend and mock modes.

Walkthrough expectations:

- Accounts opens in backend and mock modes.
- The user invitation readonly panel is visible.
- Main UI says invitation is readiness-only.
- Main UI does not imply real user invitation is open.
- Full login identifiers, tokens, secrets, headers, and signatures are not displayed.
- Technical fields remain folded in `TechnicalDetails`.

Result:

- The panel remains display-only.
- No user is created.
- No invitation is sent.
- No role or store membership is written.
