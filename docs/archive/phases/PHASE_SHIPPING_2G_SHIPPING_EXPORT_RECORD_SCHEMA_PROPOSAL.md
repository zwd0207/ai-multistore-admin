# Phase Shipping-2G: Shipping Export Record Schema Proposal

## Purpose

Propose the future export-record shape before generating any real logistics-provider file.

## Proposed Future Tables

`shipping_export_batches`:

- `id`
- `store_id`
- `platform`
- `file_type`
- `file_format`
- `file_name`
- `file_path`
- `file_sha256`
- `row_count`
- `matched_row_count`
- `unmatched_row_count`
- `actor_id_hash`
- `audit_correlation_id`
- `export_status`
- `created_at`
- `updated_at`

`shipping_export_batch_rows`:

- `id`
- `export_batch_id`
- `store_id`
- `platform`
- `order_reference`
- `product_name`
- `option_name`
- `quantity`
- `logistics_inventory_code`
- `logistics_provider_name`
- `internal_sku`
- `platform_product_id_hash`
- `platform_option_id_hash`
- `row_status`
- `created_at`

## Boundary

This is a schema proposal only. No schema migration, export-record write, file creation, audit-row write, or platform write is performed.
