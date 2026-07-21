# Phase Naver-Order-Batch-1C: Order Batch Readonly Evidence API Alignment

## Purpose

Align Naver order batch review evidence with the shared batch readonly evidence API shape, so product and order approval material can be displayed consistently.

## Implemented

- Extended backend verification so order batch evidence can be normalized through `/api/v1/batch/readonly-evidence`.
- Allowed only safe changed-field names such as order status and delivery status.
- Confirmed the normalized evidence keeps order writes, timeline writes, raw responses, and formal order sync closed.

## Safety Boundary

- No Naver API call.
- No order write.
- No timeline event write.
- No buyer privacy exposure.
- Formal order batch sync remains closed.
