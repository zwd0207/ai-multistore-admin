# Phase Shipping-7C: Tracking Import Parser UI Upload Shell

Codex2 Shipping Assistant now includes a preview-only upload shell for logistics tracking `.xlsx` files.

Operator flow:

1. Select a local `.xlsx` tracking return file.
2. Click preview.
3. Review normalized rows, carrier, tracking number, and row status.
4. Continue to a future separately approved local import-record phase.

The UI does not:

- save the file,
- write parsed rows,
- update local orders,
- call Naver,
- call a logistics-provider API,
- open shipment writeback.

Technical boundary flags remain inside `TechnicalDetails`; the normal operator view stays focused on business status and row review.
