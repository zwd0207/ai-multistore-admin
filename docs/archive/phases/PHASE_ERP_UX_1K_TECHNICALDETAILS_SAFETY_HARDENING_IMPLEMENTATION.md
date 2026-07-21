# Phase ERP-UX-1K - TechnicalDetails Safety Hardening Implementation

## Summary

Phase ERP-UX-1K implements frontend safety hardening for Codex2 `TechnicalDetails`.

This phase modifies Codex2 frontend runtime code only. It does not modify Codex1, does not call platform APIs during validation, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

## Changes

- `TechnicalDetails` now applies strict redaction by default.
- Added exported helper utilities:
  - `TECHNICAL_REDACTED_VALUE`.
  - `redactTechnicalValue(label, value)`.
  - `redactTechnicalObject(object)`.
- Added label-based redaction for sensitive fields.
- Added value-based redaction for token-like or authorization-like values.
- Added recursive object and array redaction.
- Added a visible folded-detail note when one or more advanced fields are hidden.
- Updated Logs detail before/after JSON rendering to pass through `redactTechnicalObject`.

## Redacted By Default

The frontend redacts labels and values related to:

- tokens.
- Authorization.
- request or response headers.
- signatures and bcrypt inputs.
- client secrets, passwords, and secrets.
- raw platform responses.
- raw request or response bodies.
- full channel numbers.
- full platform order/product identifiers when not already safe.
- buyer and receiver names.
- buyer and receiver phones.
- addresses and zip codes.
- long opaque token-like strings.

## Still Allowed In Folded Details

The following diagnostic fields remain visible when sanitized:

- `error_code`.
- `http_status`.
- `business_error_hint`.
- `safe_keyword_flags`.
- `capability_scope`.
- `path_kind`.
- `store_id`.
- `credential_id`.
- `real_preview`.
- `real_sync`.
- `mapping_version`.
- `source_phase`.
- `safe_hash`.
- `dedupe_key`.
- counts.
- booleans.
- safe status fields.
- backup SHA-256 and local backup path.

These fields are still intended only for folded administrator details, not main seller-facing cards.

## Current Limitations

- Arbitrary React `children` are not automatically transformed.
- Known high-risk JSON children in Logs now use `redactTechnicalObject`.
- Future child renderers that output JSON should also use `redactTechnicalObject`.
- This is a frontend last-line-of-defense layer. Backend sanitization remains required.

## Verification Expectations

Implementation should pass:

- production build.
- mock build.
- encoding scan.
- `git diff --check`.
- mock browser smoke check.

Browser smoke check should confirm:

- `/logs` opens.
- `TechnicalDetails` remains folded by default.
- Logs detail before/after JSON remains folded by default.
- sensitive sample fields are redacted if present.
- no mojibake appears.
- no console errors appear.
- formal Naver product/order sync remains closed.

## Safety Boundary

This phase does not:

- modify Codex1.
- call Naver, Coupang, or any platform API.
- write products, orders, SyncLog, audit rows, or backup records.
- change schema.
- change backend contracts.
- open product/order formal sync.
