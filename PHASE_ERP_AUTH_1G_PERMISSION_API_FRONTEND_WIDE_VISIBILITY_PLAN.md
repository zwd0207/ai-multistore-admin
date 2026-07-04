# Phase ERP-Auth-1G: Permission API frontend-wide visibility plan

## Purpose

Plan how the runtime permission mock API should expand from the Orders page to the rest of Codex2 without confusing non-technical users.

This phase is planning-only.

## Target Pages

- Dashboard
- Products
- Orders
- Sales
- Credentials / API status
- Logs / Audit
- Backups
- Settings

## Display Rules

Main pages should show business wording:

- can view
- requires administrator approval
- not available yet
- formal sync not open
- action needs backup and audit evidence

Main pages should not show permission keys such as `orders.refresh_batch_write`, skip reasons, actor hashes, or mock gate details. Those fields belong only in folded technical details.

## Safety Boundary

The plan does not add production authentication, user management, role assignment UI, schema changes, or platform API calls.
