# Phase Shipping-8G: Shipment Writeback Evidence UI Runtime Walkthrough

Purpose: show the Shipping-8F dry-run gate evidence in the Shipping Assistant UI without opening Naver shipment writeback.

Implemented UI behavior:

- `/shipping` calls the read-only dry-run gate when a latest tracking import batch exists.
- The page shows a business-first `Naver 发货回填 dry-run 证据` section.
- Operators can manually re-check dry-run evidence when a latest tracking import batch exists.
- The main cards show dry-run candidate count, blocked order count, Naver call status, and platform-write status.
- Candidate rows show only local order id, safe hash, carrier, shipped time, and target status.
- Technical flags stay in `TechnicalDetails`.

Closed boundaries:

- no Naver API call,
- no Naver shipment writeback,
- no logistics-provider API call,
- no order insert,
- no product write,
- no SyncLog write,
- no capability `tested_success` write,
- no formal product/order batch sync opening.

Runtime expectations:

- backend mode renders the dry-run evidence panel from Codex1 route data,
- mock mode renders the same panel from safe mock evidence,
- page renders without white screen,
- no Unicode replacement marker,
- ordinary UI does not expose raw platform payloads or sensitive fields.
