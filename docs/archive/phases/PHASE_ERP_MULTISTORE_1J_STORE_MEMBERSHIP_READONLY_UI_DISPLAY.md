# Phase ERP-Multistore-1J: Store Membership Readonly UI Display

## Purpose

Display the store membership readonly check on the Accounts page in both backend and mock data-source modes.

## Implemented

- Added a shared Accounts panel for store membership readiness.
- Backend mode calls `POST /api/v1/permissions/store-membership/readonly-check`.
- Mock mode returns the same safe display shape locally.
- The main page shows Chinese business conclusions and keeps technical fields folded.

## Boundary

- No user creation.
- No membership write.
- No auth session creation.
- No business data write.
- No formal product/order sync opening.
