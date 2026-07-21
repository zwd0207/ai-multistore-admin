# Phase Shipping-1E: Logistics Export Excel Contract Plan

## Purpose

Define the first export contract for a logistics-provider file generated from unshipped Naver order candidates and logistics inventory-code mappings.

This phase is contract planning only. It does not generate files yet.

## File Type Model

The export layer should not be hardcoded as one Excel-only feature. It should support a generic file contract:

- `file_type=shipping_request`
- `file_format=xlsx`
- future `file_type=tracking_upload`
- future `file_type=inventory_table`
- future `file_type=product_table`
- future `file_format=csv`

The first practical output can be `.xlsx` because the user needs a file that can be sent directly to a logistics provider.

## First Shipping Request Columns

Recommended first columns:

- platform
- store name
- order date
- safe order reference
- product name
- option name
- quantity
- logistics inventory code
- logistics provider name
- logistics current stock
- match status
- handling note

Optional columns that require explicit user approval:

- receiver name
- receiver phone
- receiver address

The database should not store full receiver privacy data by default. If the logistics provider requires receiver information inside the exported file, it should be treated as a separate operator-approved export boundary with audit evidence.

## Export Record

A later implementation should create an export record with:

- `store_id`
- `platform`
- `file_type`
- `file_format`
- `row_count`
- `matched_row_count`
- `unmatched_row_count`
- `file_name`
- `file_hash`
- `generated_by_actor_hash`
- `audit_correlation_id`
- `created_at`

The export record should not store raw platform responses or secret values.

## Audit Requirements

The export action should eventually write audit evidence for:

- who generated the file,
- which store was used,
- which file type was generated,
- how many rows were exported,
- whether receiver privacy columns were included,
- which approval or operator action allowed privacy export if applicable,
- the generated file hash.

## Acceptance Notes

- Planning only.
- No file generated.
- No database schema change.
- No local database write.
- No real Naver API call.
- No formal order sync opened.

