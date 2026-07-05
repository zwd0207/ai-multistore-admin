# Phase Shipping-1B: Shipping Assistant UI Simplification Plan

## Purpose

Define a simple operator-facing UI direction for the first landing feature while preserving the administrator and technical areas needed for long-term production.

The operator should not need to understand API capabilities, sync gates, route names, raw technical details, or backend evidence panels to complete daily shipping work.

## Recommended Primary Navigation

For the first local production workflow, the ordinary operator workspace should prioritize:

1. Shipping Assistant
2. Unshipped Orders
3. Inventory Mapping
4. Logistics Stock
5. Export Records
6. Operation Records

These sections can be implemented as separate pages or as tabs inside one Shipping Assistant workspace. The first implementation should prefer a compact workflow view over many disconnected technical pages.

## Shipping Assistant View

The main screen should show:

- store selector
- unshipped order count
- matched count
- unmatched count
- insufficient logistics stock count
- last download time
- last export time
- export-ready table
- unmatched mapping tasks

Main table columns should stay business-first:

- order date
- product name
- option name
- quantity
- logistics inventory code
- logistics stock
- match status
- handling note

## Folded Or Admin-Only Areas

The following areas should be folded into administrator pages or hidden from ordinary operators during the first landing workflow:

- API Capabilities
- raw TechnicalDetails panels
- batch sync gates
- formal product/order sync approval panels
- backup and restore technical controls
- permission and role technical details
- audit internals
- AI/Coupang/customer-center placeholders
- raw route names and boolean guardrail flags

They should remain available to admins because the system still needs safety, audit, backup, restore, and expansion controls.

## Business Wording Rules

Use business wording such as:

- "Naver unshipped orders are ready for review."
- "Some rows need inventory-code mapping."
- "This export can be sent to the logistics provider."
- "This action only creates a local file and audit record."

Avoid ordinary-operator wording such as:

- `real_sync`
- `tested_success`
- `guardrail`
- `route`
- `raw_data`
- `store_id`
- `credential_id`
- `external_product_order_id_hash`

Technical values may stay inside admin-only details where needed.

## Acceptance Notes

- Planning only.
- No Codex2 runtime UI change in this phase.
- No backend route change.
- No real Naver API call.
- No local database write.

