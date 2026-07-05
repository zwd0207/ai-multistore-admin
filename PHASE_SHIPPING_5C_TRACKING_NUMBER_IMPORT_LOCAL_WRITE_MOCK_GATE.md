# Phase Shipping-5C: Tracking-number import local write mock gate

Purpose: validate whether parsed tracking rows are safe to record locally.

Gate requirements:

- `manual_approval=true`
- `parser_contract_acknowledged=true`
- `file_type=tracking_upload`
- `file_format=xlsx`
- safe optional `source_file_name`
- at least one order reference or product-order reference per row
- carrier and tracking number per row
- no buyer/receiver privacy, address, token, Authorization, headers, signature, client secret, or raw response

Passing the gate does not write the database. It only returns `tracking_import_local_write_gate_ready`.

Approved next step: Shipping-5D local import record write.
