# Phase Shipping-7D: Tracking Import Parser Local Record Integration Plan

The parser result is intentionally separate from the existing local tracking import write route.

Current state:

- Parser preview is complete.
- Local tracking import records already exist from Shipping-5D.
- The parser does not automatically call the local write route.

Future integration plan:

1. Human reviews parser preview rows.
2. The UI shows duplicate and blocked rows.
3. A separate approval phase maps parser rows into the existing local write gate.
4. Local write remains limited to `shipping_tracking_import_batches`, `shipping_tracking_import_rows`, and safe audit evidence.
5. Naver shipment writeback remains a future separately approved phase.

This phase does not modify database schema.
