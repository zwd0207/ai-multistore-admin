# Phase ERP-Batch-1H: Readonly Evidence API Local Route Implementation

## Result

The local readonly evidence route is implemented as a safe normalizer for batch approval screens.

## Response Meaning

When successful, the route returns `readonly_evidence_api_ready` with normalized candidate counts, changed field names, duplicate-check status, whitelist status, business message, and next action.

## Boundaries

- Readonly only.
- No platform request.
- No database write.
- No formal sync opening.
- No raw response, token, header, signature, full platform id, or buyer privacy exposure.

This endpoint prepares approval UI evidence; it does not approve or execute sync.
