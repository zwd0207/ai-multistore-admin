# Phase Shipping-1C: Logistics Inventory Mapping Schema Proposal

## Purpose

Propose the future schema for matching Naver order rows to logistics-provider inventory codes and manually maintained logistics stock.

This is a proposal only. It does not create tables or modify the database.

## Proposed Tables

### `logistics_inventory_mappings`

Purpose: map platform order item identity to logistics-provider inventory code.

Suggested fields:

- `id`
- `store_id`
- `platform`
- `match_product_name`
- `match_option_name`
- `normalized_product_name`
- `normalized_option_name`
- `platform_product_id_hash`
- `platform_option_id_hash`
- `internal_sku`
- `logistics_inventory_code`
- `logistics_provider_name`
- `match_priority`
- `is_active`
- `mapping_version`
- `created_by_actor_hash`
- `updated_by_actor_hash`
- `created_at`
- `updated_at`

First-stage matching should use `normalized_product_name + normalized_option_name`. Future matching may prefer platform product id hash, option id hash, internal SKU, or explicit manual override.

### `logistics_inventory_items`

Purpose: manually maintain the logistics-provider inventory code and current stock.

Suggested fields:

- `id`
- `store_id`
- `platform`
- `logistics_inventory_code`
- `logistics_provider_name`
- `current_stock_quantity`
- `stock_status`
- `last_manual_checked_at`
- `last_manual_updated_by_actor_hash`
- `note`
- `is_active`
- `created_at`
- `updated_at`

The first version should be manual. It should not introduce purchase, warehouse, supplier, or automated logistics-provider API integration yet.

### `shipping_download_batches`

Purpose: record each local unshipped-order download/read action.

Suggested fields:

- `id`
- `store_id`
- `platform`
- `download_type`
- `source_window_from`
- `source_window_to`
- `candidate_count`
- `matched_count`
- `unmatched_count`
- `status`
- `created_by_actor_hash`
- `audit_correlation_id`
- `created_at`

This record should not store raw Naver response bodies.

### `shipping_export_batches`

Purpose: record each generated logistics-provider file.

Suggested fields:

- `id`
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

`file_type` should be generic enough for:

- `shipping_request`
- `tracking_upload`
- `inventory_table`
- `product_table`
- `future_file_type`

## Data Safety

The schema must not require:

- raw Naver responses
- tokens
- headers
- signatures
- full buyer privacy data
- detailed receiver address
- full platform identifiers when a safe hash is enough

Buyer and receiver information should only be introduced into export files when the user explicitly approves the operational need. Database storage should remain minimal and auditable.

## Acceptance Notes

- Proposal only.
- No migration.
- No database schema change.
- No local write.
- No real Naver API call.

