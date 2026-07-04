# Phase ERP-Batch-1T: Batch Approval Audit Evidence UI Route Integration Plan

Purpose: plan how the Orders batch approval evidence panel should consume the local readonly audit-evidence route.

Planned route:

```text
POST /api/v1/batch/approval-audit-evidence
```

UI boundary:

- The main Orders page may show business wording that audit evidence is ready for manual review.
- Technical fields such as phase, route path, required actions, and write flags stay folded.
- The UI must not write audit rows, orders, products, SyncLog, or tested-success rows.
- The UI must not imply formal product or order batch sync is open.

This phase is a plan for a readonly UI integration only.
