# T24 Naver customer inquiry readonly contract

## Reuse decision

- Reuse the T14 encrypted inquiry store, 30-day retention, cleanup gate, store isolation, and local ingestion audit.
- Reuse the T15 `SyncCheckpoint` row as the only store/resource lease and the existing retry classification.
- Keep the legacy generic inquiry sync route closed. Do not write to the generic plaintext inquiry path.
- Do not add an endpoint, table, scheduler, sync log type, platform write, reply action, or AI action.

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
