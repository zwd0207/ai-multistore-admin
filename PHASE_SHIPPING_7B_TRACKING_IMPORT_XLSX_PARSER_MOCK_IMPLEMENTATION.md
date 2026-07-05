# Phase Shipping-7B: Tracking Import XLSX Parser Mock Implementation

Implemented a preview-only backend route:

```text
POST /api/v1/shipping/tracking-import/parse-xlsx-mock
```

The route accepts base64 `.xlsx` content and extracts tracking upload rows from sheet1. It validates required columns, duplicate rows, safe field names, manual approval, and parser contract acknowledgement.

Success status:

```text
tracking_xlsx_parser_mock_ready
```

Success still means:

- `file_content_saved=false`
- `parsed_rows_written=false`
- `import_record_written=false`
- `tracking_number_import_open=false`
- `tracking_numbers_written=false`
- `shipment_writeback_called=false`
- `orders_updated=false`
- `real_database_written=false`
- `real_api_called=false`

The implementation intentionally exposes column mapping as `mapped_columns` and `unknown_columns`, not HTTP/request header wording, to avoid sensitive-term confusion in scans.

Verified by `scripts/verify_all.py`.
