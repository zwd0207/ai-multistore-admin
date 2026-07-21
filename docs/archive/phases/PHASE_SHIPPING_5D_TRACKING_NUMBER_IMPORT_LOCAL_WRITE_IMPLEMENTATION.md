# Phase Shipping-5D: Tracking-number import local write implementation

Purpose: record an approved logistics tracking-number import locally.

Allowed writes:

- one `shipping_tracking_import_batches` row
- one or more `shipping_tracking_import_rows`
- one safe `operation_audit_logs` row with `operation_phase='Shipping-5D'`

Forbidden actions:

- no Naver API call
- no logistics-provider API call
- no Naver shipment writeback
- no order status update
- no `products` write
- no `SyncLog` write
- no tested-success write
- no raw response or secret storage

This is local operator history, not formal shipment synchronization.
