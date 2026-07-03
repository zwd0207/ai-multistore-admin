# Phase ERP-UX-1F - Credentials and API Status Wording Cleanup

## Summary

Phase ERP-UX-1F cleans up API Credentials and API Capabilities wording for production usability.

This phase modifies Codex2 frontend display only. It does not modify Codex1, does not call platform APIs during validation, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Changes

- API Credentials now shows business-first connection cards:
  - connection material status.
  - authorization and permission status.
  - store connection status.
  - Naver product status.
  - formal sync boundary.
- API Capabilities now shows business-first platform status cards:
  - platform authorization.
  - seller account.
  - store connection.
  - product reading.
  - order reading.
  - formal batch sync protection.
- Naver error enums are translated into seller-facing Chinese messages:
  - IP allowlist issue.
  - invalid credential.
  - permission missing.
  - product API not available.
  - token authorization failed.
  - unknown forbidden response.
- Raw technical fields are kept inside folded `TechnicalDetails`.

## Hidden Technical Fields

Main pages should not directly expose:

- `ip_not_allowed`
- `token_auth_failed`
- `product_api_not_allowed`
- `permission_forbidden`
- `unknown_forbidden`
- `http_status`
- `safe_keyword_flags`
- `business_error_hint`
- `capability_scope`
- `path_kind`
- `credential_id`
- `channel_no`

Those fields may remain in folded technical details for administrators.

## Safety Boundary

The UI still states that:

- formal product batch sync is not open.
- formal order batch sync is not open.
- successful connection does not automatically open batch sync.
- platform tokens, temporary authorization, request headers, signatures, client secrets, and raw responses are not displayed.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.
- `git diff --check`.

Page checks should confirm:

- API Capabilities opens in mock mode.
- API Credentials wording is covered by the backend-source accounts route and production build.
- Main page copy uses Chinese business messages.
- Technical fields remain folded in `TechnicalDetails`.
- No page claims formal Naver product/order sync is open.
