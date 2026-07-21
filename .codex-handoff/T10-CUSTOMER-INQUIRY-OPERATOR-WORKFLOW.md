# T10 Customer Inquiry Operator Workflow

> Execution order: Terra -> Commander gate -> Luna -> Commander browser gate -> Sol.

## Goal

Make the persisted real Naver inquiry for `pxg球包店 / Naver` visible in the ordinary customer-service workflow without enabling customer replies or any other real platform write.

## Global Boundaries

- Use the stable account displayed by `查看真实只读配置账号.cmd` for operator verification. Never print credentials or MFA secrets.
- The owner has accepted the current real-read data as correct. Do not repeat platform-read investigation unless a regression is found.
- Do not run another real persistence batch.
- Keep platform shipment writeback, customer sending, inventory/product changes, AI automation, scheduled sync, and all other platform writes disabled.
- Ordinary list responses must not expose complete recipient PII, full tracking numbers, credentials, raw Naver payloads, tokens, cookies, or signatures.
- Keep changes narrowly scoped to customer-inquiry visibility and operator usability.

## Phase A - Terra: Stable Backend Contract

**Model:** GPT-5.6 Terra

**Purpose:** Make locally persisted PXG/Naver inquiry records available through the ordinary customer-service API contract.

**Primary ownership:**

- `backend/app/api/v1/endpoints/customer_inquiries.py`
- `backend/app/services/customer_inquiry_service.py`
- `backend/app/services/pxg_naver_readonly_persistence_service.py`
- Backend schemas and verification scripts directly required by this contract

**Required behavior:**

1. `GET /api/v1/customer-inquiries` returns authorized generic inquiries plus the saved PXG/Naver read-only inquiry for the assigned store.
2. Normalize both sources into one stable frontend contract with source, inquiry id, category/type, status, cleaned summary, created/updated time, store id, and optional order/logistics context.
3. Missing orders or logistics are a valid empty state, not an API failure.
4. Enforce valid session, MFA, store assignment, and read permission. Cross-store requests return 403.
5. Keep reply/send endpoints disabled for the read-only Naver source and reject direct requests server-side.
6. List and error responses remain privacy-safe and contain no complete recipient data or raw platform payload.
7. Preserve existing generic inquiry behavior and avoid duplicate rows on repeated reads.

**Verification:**

- Add focused tests for aggregation, store isolation, empty order/logistics context, deduplication, privacy-safe output, and disabled replies.
- Run focused customer-inquiry tests, production-session verification, and `verify_all.py`.
- Commit only after all tests pass.

**Return only:**

`STATUS / BRANCH / COMMIT / TESTS / CONTRACT_FIELDS / BLOCKER`

## Commander Gate A

The commander reviews the diff, runs the focused backend verification, confirms no real write path opened, and fast-forwards the accepted Terra commit into integration. Luna does not start before this gate passes.

## Phase B - Luna: Ordinary Operator UI

**Model:** GPT-5.6 Luna

**Purpose:** Make the customer-service page understandable and useful to a normal operator using the stable Terra contract.

**Primary ownership:**

- `src/pages/CustomerService.jsx`
- `src/services/backendApi.js`
- `src/services/dataProvider.js`
- `src/services/adapters.js`
- Directly related frontend tests and styles only

**Required behavior:**

1. Remove all corrupted/mojibake Chinese text from the customer-service page.
2. Display the saved real inquiry through the Terra contract.
3. Show store, source platform, inquiry type, cleaned customer question summary, status, and last update time clearly.
4. When no related order exists, show `当前读取窗口暂无关联订单` as a normal information state.
5. When order/logistics context exists, show order number, product/specification, business status, warehouse batch state, masked carrier/tracking information, and latest logistics state.
6. Keep reply/send controls visibly disabled for real read-only inquiries, with concise operator copy explaining that sending is not enabled.
7. Preserve session failure, forbidden, loading, empty, and error states. Ensure desktop and 390px mobile layouts do not overlap.
8. Do not add marketing copy, technical API terminology, or explanatory capability cards.

**Verification:**

- Run frontend tests and build.
- Browser-check login, customer inquiry visibility, empty-order state, disabled reply state, desktop, and 390px mobile.
- Commit only after checks pass.

**Return only:**

`STATUS / BRANCH / COMMIT / BUILD / TESTS / DESKTOP / MOBILE / BLOCKER`

## Commander Gate B

The commander integrates Luna, starts the local isolated services, and verifies the real inquiry with the fixed local configuration-admin account. The commander confirms that logout/login does not lose locally persisted inquiry state and that no platform write control is active.

## Phase C - Sol: Final Boundary Review

**Model:** GPT-5.6 Sol

**Purpose:** Perform one narrow final acceptance review after Terra and Luna are integrated. Do not implement ordinary fixes unless a release-blocking boundary flaw requires it.

**Review scope:**

1. A normal operator can find and understand the saved real inquiry without technical knowledge.
2. Missing order/logistics data is represented honestly and does not look like a system error.
3. Sessions, MFA, store scope, permissions, privacy masking, and read-only reply restrictions remain fail-closed.
4. No real platform write, customer send, new persistence batch, scheduled sync, or AI automation has been enabled.
5. No credentials, full recipient PII, full tracking values, or raw Naver payloads appear in UI, APIs, logs, or errors.

**Return only:**

`STATUS passed|blocked / OPERATOR_USABILITY / SECURITY / PRIVACY / WRITE_BOUNDARY / BLOCKER / NEXT`

