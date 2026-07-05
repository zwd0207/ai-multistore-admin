# Phase Shipping-5A: Tracking-number import record schema approval plan

Purpose: approve a local record schema for logistics tracking-number imports.

Decision:

- Add import batch and import row records.
- Keep `store_id` and `platform` required.
- Keep `platform` extensible for `naver`, `coupang`, and `future_platform`.
- Store safe order references, logistics inventory code, carrier, tracking number, shipped time, row status, and audit correlation.
- Do not update `orders`.
- Do not call Naver shipment writeback.
- Do not save token, Authorization, headers, signature, client secret, raw response, buyer/receiver privacy, full address, or zip code.

Approved next step: Shipping-5B schema migration.
