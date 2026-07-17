# T24 Naver customer inquiry readonly contract

## Reuse decision

- Reuse the T14 encrypted inquiry store, 30-day retention, cleanup gate, store isolation, and local ingestion audit.
- Reuse the T15 `SyncCheckpoint` row as the only store/resource lease and the existing retry classification.
- Keep the legacy generic inquiry sync route closed. Do not write to the generic plaintext inquiry path.
- Do not add an endpoint, table, scheduler, second log system, platform write, reply action, or AI action. A privacy-safe activation marker may use the existing `SyncLog` table.

## Official request

- API documentation version: Naver Commerce API `current/2.82.0`.
- Request: `GET /external/v1/pay-user/inquiries`.
- Headers: `Authorization: Bearer <token>` and `Accept: application/json;charset=UTF-8`.
- Query: `page` 1..1,000,000, `size` 10..200, required `startSearchDate` and `endSearchDate` in `yyyy-MM-dd`, and optional string `answered=true|false`.
- Production page size is 200. The local refresh ceiling is 1,000 pages; reaching it fails closed rather than reporting partial success.
- The automatic window is the KST business date plus the preceding 29 calendar dates.
- Consecutive pages are separated by at least one second.

## Pagination and failures

The reader requires `totalPages`, `totalElements`, `first`, `last`, `number`, `size`, `numberOfElements`, `content`, and `empty`. It reads until `last=true`. Missing or contradictory metadata, duplicate pages, a changed total, malformed content, or the local page ceiling fails the complete refresh. No partial page is persisted.

- HTTP 400 is `naver_customer_inquiry_request_invalid` and is not retryable.
- HTTP 429 is `naver_customer_inquiry_rate_limit`; the current T15 retry schedule handles it and the same run never retries immediately.
- HTTP 5xx, timeout, and network failures are retryable through T15.
- HTTP 401/403 continues through the established Naver credential and permission classifier.
- `GNCP-GW-Trace-ID`, bounded `GNCP-GW-RateLimit-*` / `GNCP-GW-Quota-*`, and an optional bounded `Retry-After` may be retained as safe diagnostics. The implementation does not depend on `Retry-After` being present.

## Privacy and activation gate

Logs and errors may contain only store/resource scope, page and count values, HTTP status, safe error code and field names, bounded rate values, and a sanitized trace ID. They must never contain credentials, authorization headers, raw responses, inquiry content/title, customer identifiers, order identifiers, or product-order identifiers.

`naver.customer_inquiry_read.implemented_now` is true after offline contract verification. `safe_to_real_test` remains false until an operator approves one store, confirms the Naver application has the order-seller permission, waits for the existing 429 cooldown, and performs exactly one controlled readonly GET. Platform writes remain false.

The runtime is separately fail-closed. `NAVER_READONLY_INQUIRY_REAL_READ_ENABLED` defaults to `false`; enabling it requires a non-empty exact allowlist in `NAVER_READONLY_INQUIRY_APPROVED_STORE_IDS`. The legacy singular `NAVER_READONLY_INQUIRY_APPROVED_STORE_ID` remains compatible only when the plural list is absent or already contains that same ID; a conflicting legacy value fails startup rather than widening access. Duplicate, non-positive, unknown, inactive, non-Naver, or otherwise ineligible stores are rejected by configuration or the guarded activation step. A store outside the exact approved set remains blocked before checkpoint creation, credential lookup, token exchange, or network access.

Every persistent inquiry read also requires exactly one active `test_passed` credential for the same store, a configured channel number, and a latest matching successful `naver.customer_inquiry_read` real-readonly capability result with the confirmed `order_seller` permission. A newer failure supersedes an older success. Capability-result writers and data-commit fences serialize on the same credential row so an appended failure cannot pass behind an older success. The preparation marker binds all four resources to that credential ID. Inquiry commits and every order, product, or logistics page renew and conditionally fence the same store/resource lease, credential, and preparation marker before local data and cursor state commit. Revoked approval, a disabled automatic checkpoint, a lost lease, or credential rotation rolls back the pending page.

Legacy production stores must be prepared only after all old workers are stopped, while the lifecycle scheduler, automatic-read runtime, persistent inquiry gate, real API test gate, and every platform-write gate are closed. `scripts/prepare_t24_dual_store_automatic_read.py` accepts exactly two owner-approved store IDs and name hashes plus an explicit future activation time. It requires the effective runtime allowlist to equal those two IDs, a unique decryptable and verified credential, current cleanup/backup safety health, and a safe successful manual order/product baseline for each store. It creates only the existing four T15 checkpoints per store, gives orders a fresh 30-day overlap read, retains the per-store product baseline, and spaces the first eight runs by one minute from the activation time. The 30 daily order slices may complete across multiple bounded scheduler runs; `read_page_limit_reached` retains the cursor and enters `retry_wait` instead of blocking. The scheduler also refuses an unchanged prepared set whose first-run activation grace was missed, so a late backend start cannot collapse all eight tasks into one burst. An expired, changed, or partially consumed schedule fails closed. The script never calls Naver and is idempotent only while all prepared checkpoints and their existing-`SyncLog` markers remain pristine.
