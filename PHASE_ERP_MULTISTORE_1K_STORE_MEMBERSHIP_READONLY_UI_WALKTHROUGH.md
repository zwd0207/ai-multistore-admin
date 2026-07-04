# Phase ERP-Multistore-1K: Store Membership Readonly UI Walkthrough

## Purpose

Confirm that the Accounts page can show the store-membership readonly check in a business-friendly way before any real user invitation or membership assignment is opened.

## Scope

- Codex2 UI walkthrough only.
- No Codex1 schema change.
- No user creation.
- No role assignment.
- No `erp_store_memberships` write.
- No platform API call.

## Walkthrough Expectations

- The Accounts page renders without a white screen in backend and mock data-source modes.
- The main card explains the current membership readiness result in Chinese business wording.
- The page says real write is not open.
- Technical details remain folded under the diagnostics section.
- The page does not imply production login, real membership assignment, or large-scale multi-store operation is available.

## Safety Boundary

The panel may call the readonly membership readiness API, but it must keep:

```text
membership_written=false
real_auth_session_created=false
real_database_written=false
orders_written=false
products_written=false
formal_sync_open=false
```

## Result

This phase is a walkthrough and documentation phase. It does not modify runtime behavior by itself.
