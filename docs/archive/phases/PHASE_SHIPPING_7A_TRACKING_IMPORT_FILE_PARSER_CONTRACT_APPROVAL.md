# Phase Shipping-7A: Tracking Import File Parser Contract Approval

Purpose: approve the first local parser contract for logistics tracking return files.

Scope:

- File type remains `tracking_upload`.
- File format is `.xlsx`.
- The parser is preview only.
- The file binary is not persisted.
- Parsed rows are not written.
- Orders are not updated.
- Naver shipment writeback remains closed.

Required columns:

- `carrier`
- `tracking_number`
- at least one of `order_reference` or `product_order_reference`

Allowed optional columns:

- `logistics_inventory_code`
- `shipped_at`
- `operator_note`

Safety boundary:

- no Naver API call
- no logistics-provider API call
- no `orders` write
- no `products` write
- no `SyncLog` write
- no `ApiCapabilityTestResult tested_success` write
- no raw response, token, Authorization, signature, client secret, buyer privacy, receiver privacy, full address, or zip code

Next phase: Shipping-7B implements a mock parser route.
