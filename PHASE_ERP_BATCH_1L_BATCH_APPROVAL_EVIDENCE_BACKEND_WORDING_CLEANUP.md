# Phase ERP-Batch-1L: Batch Approval Evidence Backend Wording Cleanup

## Purpose

Make backend batch approval evidence messages safe for direct business display if they reach the frontend main page.

## Implemented

- Replaced English default readonly evidence wording with Chinese business messages.
- Kept the batch evidence API as a normalizer only.
- Added regression coverage so the backend does not fall back to the old English default text.

## Safety Boundary

- No platform API call.
- No product/order/SyncLog/tested-success/audit write.
- No schema change.
- Formal product and order batch sync remain closed.
