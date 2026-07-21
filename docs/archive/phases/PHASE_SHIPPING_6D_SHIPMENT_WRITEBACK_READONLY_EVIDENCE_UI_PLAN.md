# Phase Shipping-6D: Shipment writeback readonly evidence UI plan

Purpose: show shipment writeback readiness without offering a real writeback action.

UI behavior:

- Show matched order count.
- Show missing approval actions.
- Show Naver writeback as closed.
- Keep technical fields in `TechnicalDetails`.

Forbidden:

- No shipment writeback button.
- No Naver API call.
- No order status update.
- No platform write.
