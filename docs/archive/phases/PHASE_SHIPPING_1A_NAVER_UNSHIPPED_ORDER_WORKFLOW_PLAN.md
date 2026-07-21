# Phase Shipping-1A: Naver Unshipped Order Workflow Plan

## Purpose

Define the first real landing workflow for local production v1.0: Naver unshipped order download, logistics inventory-code matching, logistics stock review, Excel export, download/export records, and audit evidence.

This is the first practical shipping-assistant feature. It is not the final system shape. The long-term architecture must still support Korean multi-store operations across Naver, Coupang, future platforms, customer service, product operations, inventory alerts, AI assistance, audit, backup, permissions, and recovery.

## Operator Workflow

1. The operator opens the Shipping Assistant workspace.
2. The operator selects a store. Every operation must carry `store_id`.
3. The system reads Naver unshipped-order candidates for the selected store.
4. The operator reviews order rows in business wording:
   - platform
   - store
   - order date
   - order status
   - product name
   - option name
   - quantity
   - match status
   - logistics inventory code
   - logistics current stock
5. The matching layer attempts to match by normalized `product_name + option_name`.
6. Matched rows can be exported to a logistics-provider request file.
7. Unmatched rows are shown as work items for manual mapping maintenance.
8. The export action must create a download/export record and audit evidence in a later implementation phase.
9. The operator can download the generated file and send it to the logistics provider.

## First-Stage Scope

The first stage should cover:

- Naver store unshipped order candidates.
- Matching by product name and option name.
- Manual logistics inventory-code mapping.
- Manual logistics current-stock maintenance.
- Export contract for a logistics-provider file.
- Download/export record design.
- Audit evidence design.

The first stage should not cover:

- Naver formal order batch sync.
- Naver platform shipment writeback.
- Tracking-number upload/writeback.
- Cancel, return, exchange, or claim platform writes.
- Coupang runtime integration.
- AI customer-service automation.
- Finance, settlement, or profit reporting.

## Unshipped Candidate Definition

The first local candidate set should include Naver orders whose safe local status is one of:

- `PAYED`
- `PLACE_PRODUCT_ORDER`
- `READY`
- `DELIVERY_READY`

The first local candidate set should exclude:

- `DISPATCHED`
- `DELIVERED`
- `CANCELED`
- cancel request rows
- return request rows
- exchange request rows
- mock/test rows unless an explicit mock walkthrough is running

Status names may be refined after another Naver readonly preview, but unknown statuses must be shown as review-needed instead of guessed.

## Required Boundaries

- `platform` must remain explicit and extensible: `naver`, `coupang`, `future_platform`.
- `store_id` must be present on order candidates, mapping rows, stock rows, export records, and audit rows.
- File import/export capability must be generic enough for future shipping request files, tracking upload files, inventory files, and product files.
- Matching starts with product name and option name, but the data model must leave room for platform product id hash, platform option id hash, internal SKU, logistics SKU, and manual override.
- Ordinary operator screens must hide route names, raw payloads, hashes, flags, and technical gate states.
- Admin screens may keep technical details, backup, restore, permission, and audit evidence.

## Acceptance Notes

- Planning only.
- No database schema change.
- No Codex2 runtime UI change.
- No real Naver API call.
- No local database write.
- No formal sync opened.

