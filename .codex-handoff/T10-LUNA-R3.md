# T10 Luna R3 - Mobile Operator Layout

## Status

Commander Gate B browser verification passed the runtime workflow but blocked final acceptance at the 390px mobile layout.

## Purpose

Fix only the visible mobile layout defects on the customer-inquiry page. Do not change the backend contract, inquiry mapping, permissions, reply gates, or desktop behavior.

## Required Fixes

1. At 390px width, make the customer-inquiry filter controls fit inside the viewport. No select, search control, or action button may be clipped beyond the right edge.
2. Prevent the top account identity, role text, store selector, sync button, and logout control from colliding or overflowing at 390px.
3. Preserve the existing readable inquiry list. Horizontal scrolling may remain inside the table container, but it must not cause page-level horizontal overflow.
4. Preserve the real inquiry detail modal behavior. It must fit the viewport, scroll internally, show the no-related-order state, and keep reply disabled.
5. Keep all real platform writes, customer sending, AI automation, and additional persistence disabled.

## Verification

- Run `node scripts/customer-inquiry-operator-contract.test.mjs`.
- Run `npm.cmd run session:verify`.
- Run `npm.cmd run build`.
- Add or update a focused responsive contract check for the filter/header classes if practical.
- Do not claim Commander browser verification. Commander will repeat desktop and 390px Gate B after integration.

## Return Only

`STATUS / BRANCH / COMMIT / BUILD / TESTS / MOBILE_FIX / BLOCKER`
