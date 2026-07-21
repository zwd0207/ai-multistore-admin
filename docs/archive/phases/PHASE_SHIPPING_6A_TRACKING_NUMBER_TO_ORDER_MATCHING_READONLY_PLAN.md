# Phase Shipping-6A: Tracking-number to order matching readonly plan

Purpose: define how tracking-number import rows can be compared with local orders before any shipment writeback.

Rules:

- Read local tracking import rows or safe parsed rows.
- Match by safe `order_reference` first.
- Keep `store_id` and `platform` required.
- Return matched, unmatched, and duplicate counts.
- Do not update `orders`.
- Do not call Naver.
- Do not call a logistics-provider API.
- Do not write audit rows in this readonly phase.

Approved next step: Shipping-6B mock gate.
