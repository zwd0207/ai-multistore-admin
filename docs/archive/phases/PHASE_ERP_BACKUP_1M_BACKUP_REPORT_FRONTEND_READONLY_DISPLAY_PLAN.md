# Phase ERP-Backup-1M: Backup Report Frontend Readonly Display Plan

## Plan

Codex2 should show backup evidence in the Logs/Audit administrator area as a business-first readonly panel.

Main-page copy should show:

- backup count
- manifest count
- whether backup manifests and safety checks passed
- latest backup phase/status
- whether any backup needs administrator review
- clear wording that restore, delete, and cleanup actions require separate approval

Technical details may remain folded:

- readonly API routes
- safe counts
- abbreviated backup hash
- retention metadata
- backup helper safety booleans

## Boundary

No restore button, delete button, cleanup button, upload target, arbitrary path input, or write action should be added in this phase.
