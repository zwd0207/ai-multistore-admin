# Phase Naver-ERP-14J - Orders UI Timeline Readonly Display

## Summary

Phase 14J adds a read-only order status timeline section to the Codex2 Orders page for Naver orders.

This is a frontend display phase only. It does not call Naver, does not execute `real_sync=true`, does not write `orders`, does not insert `order_status_events`, does not modify Codex1 schema or APIs, and does not open formal Naver order sync.

## UI Behavior

The Orders detail panel now separates:

- current local order status snapshot.
- optional future status event history.
- refresh write gate plan.
- complete-field readonly preview.
- TechnicalDetails.

The main seller-facing area shows Chinese business text:

- current local order status.
- current delivery status.
- current claim status.
- latest order time.
- a timeline if safe status events are present.
- an empty state when no persisted status events are present.

When no events are available, the UI says the local system has not recorded status history yet. It does not imply the order never changed, and it does not imply timeline persistence, automatic refresh, or formal order sync is already active.

## Technical Details Boundary

The following fields are kept in the collapsed TechnicalDetails section:

- raw order status enum.
- raw delivery status enum.
- raw claim status enum.
- observed timestamp.
- source phase.
- source type.
- mapping version.
- dedupe key.
- safe order hashes when available.

The main page does not show raw responses, platform secrets, request headers, tokens, Authorization values, signatures, or bcrypt inputs.

## Mock Coverage

Mock Naver order data includes one safe read-only status event so the timeline renderer can be checked without backend writes or real platform calls.

Real backend data can render future `statusEvents`, `status_events`, `orderStatusEvents`, `order_status_events`, or timeline-event fields when they become available. If the real response does not contain event arrays, the UI falls back to the explicit empty state.

## Current Real Baseline

The real `order_status_events` table currently exists but has `0` rows after Phase 14I. Therefore the real Orders UI should show the current local snapshot and the no-history empty state until a separately approved future event-write phase creates safe rows.

## Safety Boundary

14J keeps these boundaries closed:

- no Naver API request.
- no local DB write.
- no order refresh write.
- no timeline event write.
- no platform write operation.
- no formal order sync.
- no raw response display.
- no token, Authorization, header, signature, bcrypt, or client secret display.

Future event persistence still requires a separately approved phase with readback, dedupe, sensitive-field scanning, and rollback handling.
