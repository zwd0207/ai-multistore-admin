# T10 Luna R1 - Use the Terra Inquiry Contract

## Status

Gate B is blocked. Commit `8269a2c` improved read-only copy but did not connect the Terra contract to the frontend adapter.

## Purpose

Make the saved real inquiry and its optional order/logistics context actually render on the ordinary customer-service page.

## Ownership

- `src/services/adapters.js`
- `src/pages/CustomerService.jsx`
- Directly related frontend tests only

## Required Fixes

1. Update `adaptCustomerInquiry()` to consume the stable backend fields:
   - `inquiry_id`, `source`, `category`, `inquiry_type`, `status`, `summary`
   - `created_at`, `updated_at`, `store_id`, `reply_enabled`, `reply_disabled_reason`
   - `order_context`
   - `logistics_context`
2. Map `order_context` into the existing frontend `relatedOrder` shape:
   - `order_no`, `product_order_no`, `product_name`, `order_status`
   - `warehouse_batch_no`, `warehouse_batch_status`, `warehouse_row_status`
3. Map `logistics_context` into `relatedOrder`:
   - `carrier`, `tracking_number_masked`, `shipment_status`, `shipped_at`
4. Display the backend-provided masked tracking number as-is. Do not mask it a second time and do not request a complete tracking number.
5. When one inquiry has no `order_context`, its detail view must clearly show `当前读取窗口暂无关联订单`. Do not label it as an error and do not imply a warehouse step is pending.
6. Respect `reply_enabled`. The saved PXG/Naver read-only inquiry must keep its reply button disabled and no reply request may be sent.
7. Preserve existing generic inquiry compatibility by supporting both the old and new field names.
8. Add a focused frontend contract test using one PXG/Naver read-only inquiry with order/logistics context and one without context.

## Verification

- Run the focused frontend contract test.
- Run the session security contract.
- Run the frontend build.
- The commander will perform authenticated desktop and mobile browser verification after integration.

## Return Only

`STATUS / BRANCH / COMMIT / BUILD / TESTS / CONTRACT_MAPPING / BLOCKER`

