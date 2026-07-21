# Phase ERP-Batch-1U: Batch Approval Audit Evidence UI Route Integration

Purpose: connect the Orders batch approval evidence panel to the local readonly audit-evidence route.

Implemented behavior:

- `dataProvider.checkBatchApprovalAuditEvidence(...)` calls the backend route in backend mode.
- Mock mode returns an equivalent readonly response without network platform calls.
- The Orders panel shows an "audit evidence" business card.
- Technical route details remain folded in `TechnicalDetails`.

Safety boundary:

- No audit row is written.
- No order or product is written.
- No SyncLog or tested-success row is written.
- Formal product/order batch sync remains closed.
