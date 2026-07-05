# Phase Shipping-1D: Naver Unshipped Order Readonly Candidate Check

## Purpose

Check whether the current local Naver order data can support a first unshipped-order candidate list without calling Naver and without writing local data.

This phase intentionally uses local readonly inspection only. It does not run a real Naver API request and does not open formal order sync.

## Readonly Check Performed

Scope:

```text
store_id=8
platform=naver
database=backend/codex1.db
write_mode=false
real_api_called=false
```

Observed local order counts:

```text
store 8 / naver / naver_real_order_sync / PAYED: 1
store 8 / naver / naver_real_order_sync / DELIVERED: 3
store 8 / naver / mock_sync / paid: 3
```

Unshipped candidate status set for the first workflow:

```text
PAYED
PLACE_PRODUCT_ORDER
READY
DELIVERY_READY
```

Observed local unshipped candidate count:

```text
PAYED: 1
```

Delivered rows are not shipping-download candidates.

## Field Observation

The current `orders` table has business fields such as:

- `store_id`
- `platform`
- `external_order_id`
- `buyer_name`
- `buyer_masked_phone`
- `product_name`
- `quantity`
- `order_amount`
- `currency`
- `order_status`
- `paid_at`
- `ordered_at`
- `source_type`
- `last_synced_at`
- `raw_data`

The current table does not have a standalone `option_name` column. For real Naver local rows, sanitized metadata can include `option_name`, but the shipping workflow should not depend on parsing raw response data. The proposed logistics mapping schema should provide explicit product-name and option-name fields for matching.

## Result

The local data is enough to plan a first unshipped candidate list and mapping workflow, but not enough to claim that the full shipping assistant is implemented.

Next implementation should:

- expose a business-first local candidate list,
- exclude delivered/canceled/claim rows,
- separate real rows from mock rows,
- use `product_name + option_name` matching,
- keep raw technical fields folded,
- avoid any Naver shipment write.

## Acceptance Notes

- No real Naver API call.
- No database write.
- No SyncLog write.
- No tested-success write.
- No schema change.
- No Codex2 runtime UI change.
- Formal Naver order sync remains closed.
