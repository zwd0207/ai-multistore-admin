# T10 Luna R2 - Runtime Contract Correction

## Status

Gate B is blocked. Commit `92f6176` contains runtime and state-detection defects despite a passing build.

## Required Fixes

1. Remove `replyEnabled`, `replyDisabledReason`, and `source` from `adaptStore()`. They reference undefined variables and can break store loading at runtime.
2. Keep those fields only inside `adaptCustomerInquiry()`.
3. Map `ticketNo` and `externalInquiryId` from `inquiry_id` when the legacy `external_inquiry_id` is absent.
4. Add an explicit `hasRelatedOrder` boolean in `adaptCustomerInquiry()` based on actual identifiers in `order_context` or legacy related-order data. Placeholder text such as `—` must never count as an order.
5. In `normalizeMessage()`, preserve an explicit boolean `row.hasRelatedOrder`; do not infer it from placeholder strings.
6. The table reply button must remain disabled while the global platform reply capability is closed. Use both the global gate and the row-level `replyEnabled`; do not show an enabled button that has no action.
7. Replace the static source-text test with a runtime test that imports and executes `adaptStore()` and `adaptCustomerInquiry()` using:
   - a read-only inquiry with order/logistics context;
   - a read-only inquiry without context;
   - a legacy generic inquiry;
   - a normal store object.
8. Assert the runtime results, including no exception from `adaptStore`, correct mapped identifiers/context, masked tracking preserved as-is, false reply state, and false `hasRelatedOrder` for the no-context row.

## Verification

- Run the runtime customer-inquiry contract test.
- Run session security verification.
- Run frontend build.
- Do not claim browser verification; Commander performs it after this commit is accepted.

## Return Only

`STATUS / BRANCH / COMMIT / BUILD / TESTS / RUNTIME_MAPPING / BLOCKER`

