# Phase ERP-UX-2A: Role-aware action visibility implementation

## Implementation

Codex2 Orders now reads the permission mock API through the data provider and displays a business-first Naver order action permissions panel.

The main page explains:

- the current role can view Naver orders when store scope and permission pass
- order refresh writes require administrator approval
- future writes require backup, readonly repeat, and audit evidence
- formal order batch sync remains closed
- platform shipment/cancel/return/exchange writes remain closed

## Technical Details Boundary

The main page does not show permission keys as the primary message. Technical details such as operation key, approval status, mock API flag, raw safety flags, write flags, and formal sync flags are kept inside `TechnicalDetails`.

## Safety Boundary

This phase does not call Naver, write local orders/products/SyncLog/tested-success records, create auth sessions, change schema, or open formal sync.
