# Phase Shipping-5E: Tracking-number import history UI

Purpose: show local tracking import history in the Shipping Assistant.

UI behavior:

- Show import time, source file name, row count, ready rows, duplicate rows, import status, and writeback state.
- Keep technical flags in `TechnicalDetails`.
- Keep ordinary operator view focused on business history.

Safety boundary:

- History route is read-only.
- `tracking_number_import_open=false`
- `shipment_writeback_called=false`
- `orders_updated=false`
- `real_api_called=false`
- `raw_response_saved=false`
- `privacy_fields_redacted=true`

Next recommended phase: Shipping-6A tracking-number to order matching readonly plan.
