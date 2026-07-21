# Phase ERP-Batch-1I: Batch Approval UI Evidence Integration Plan

## Purpose

Plan the Codex2 approval evidence surface for future formal batch sync review. The UI must help operators understand what evidence exists and what still requires approval, without exposing technical gate fields as the primary message.

## Decisions

- Use the existing local readonly evidence normalizer as the source for product/order evidence display.
- Keep main UI business-first: evidence ready, manual approval required, backup/audit/rollback still required, formal sync still closed.
- Put `phase`, `sync_kind`, `would_create`, `would_update`, `would_refresh_only`, and safety flags in folded TechnicalDetails only.
- Do not add any execute button for product or order batch sync.

## Safety Boundary

- No Naver API call.
- No real sync.
- No product/order/SyncLog/tested-success/audit write.
- No formal product or order batch sync opening.
