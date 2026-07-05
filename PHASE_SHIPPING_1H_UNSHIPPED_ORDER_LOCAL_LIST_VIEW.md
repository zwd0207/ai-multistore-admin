# Phase Shipping-1H: Unshipped Order Local List View

## Purpose

Show a local unshipped Naver order candidate list inside the Shipping Assistant.

## Implemented

- Backend data source uses existing `dataProvider.getOrders(...)`.
- Mock data source uses clean local Shipping mock orders.
- Candidate status set starts with:

```text
PAYED
PLACE_PRODUCT_ORDER
READY
DELIVERY_READY
```

- Delivered, canceled, and after-sales/request states are excluded from the first shipping list.
- Candidate rows show:
  - order reference,
  - order time,
  - product name,
  - option name,
  - quantity,
  - order amount,
  - Chinese business status,
  - logistics inventory match state.

## Boundary

- Read-only local list only.
- No Naver API call.
- No local order write.
- No platform writeback.
- No formal order batch sync.

