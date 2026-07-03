# Phase ERP-UX-1J - TechnicalDetails Safety Hardening Plan

## Summary

Phase ERP-UX-1J defines the safety hardening plan for Codex2 `TechnicalDetails`.

This phase is planning-only. It does not modify runtime frontend code, does not modify Codex1, does not call platform APIs, does not write local data, does not change database schema, and does not open formal Naver product or order sync.

The production goal is:

```text
Technical details may help administrators debug, but they must not accidentally expose platform secrets, raw responses, private identifiers, or buyer privacy.
```

## Current State

`src/components/common/TechnicalDetails.jsx` currently:

- renders a collapsed `<details>` block by default.
- accepts `items` and optional `children`.
- stringifies object values with `JSON.stringify`.
- does not apply label-based or value-based redaction.

This is acceptable only while every upstream payload is already sanitized. For production use, the component itself should add a last-line-of-defense safety layer.

## Current Usage Surface

Current call sites include:

- Dashboard.
- Orders.
- Products.
- Sales.
- API Capabilities.
- API Credentials.
- Logs.

These pages intentionally keep technical fields folded, including:

- backend status fields.
- preview metadata.
- safe hashes.
- sync and refresh diagnostics.
- capability details.
- order timeline metadata.
- log before/after summaries.

The next implementation must preserve administrator diagnostic value while preventing accidental leakage.

## Fields That Must Be Redacted

Labels matching these patterns should be blocked or replaced:

- `token`.
- `access_token`.
- `refresh_token`.
- `authorization`.
- `header`.
- `headers`.
- `signature`.
- `bcrypt`.
- `client_secret`.
- `secret`.
- `password`.
- `raw_response`.
- `rawResponse`.
- `raw_data` when it is not explicitly sanitized.
- `request_body`.
- `response_body`.
- `channel_no`.
- `productOrderId`.
- `orderId` when it is a full platform id.
- `external_product_id` when it is a full platform id.
- `buyer_name`.
- `buyer_phone`.
- `receiver_name`.
- `receiver_phone`.
- `address`.
- `zip_code`.
- `detailed_address`.

Recommended replacement:

```text
[已隐藏]
```

For explainability, the UI may show a short note:

```text
部分高级字段因包含敏感信息已隐藏。
```

## Value-Based Detection

The redaction layer should not rely only on labels.

Values should be redacted when they look like:

- bearer authorization values.
- long opaque tokens.
- JSON strings containing token/header/signature/secret/raw response keys.
- full phone numbers.
- full addresses.
- full platform order ids or product ids when the label suggests a platform identifier.
- request/response header objects.

The value scan should be conservative and avoid false confidence. When in doubt, hide the value and keep the label visible.

## Allowed Diagnostic Fields

The following can remain visible in folded technical details when sanitized:

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
- counts and booleans.
- safe status enums.
- safe changed field names.
- backup SHA-256.
- backup path, if it is local and does not contain secrets.

These fields are still not for main-page display; they are allowed only inside folded details or administrator diagnostics.

## Object And Children Handling

`TechnicalDetails` currently also renders arbitrary `children`.

The hardening implementation should:

- redact `items` automatically.
- expose a small helper for redacting JSON before rendering `children`.
- document that raw `<pre>{JSON.stringify(...)}</pre>` children must pass through the helper.
- update high-risk children call sites first, especially Logs before/after data and order preview diagnostics.

Do not try to parse and mutate arbitrary React children in the first implementation. Instead, provide an explicit helper and migrate known call sites.

## Proposed API

Recommended component API:

```jsx
<TechnicalDetails
  title="查看高级详情"
  description="..."
  items={items}
  redactionMode="strict"
/>
```

Recommended helper:

```js
redactTechnicalValue(label, value)
redactTechnicalObject(object)
```

Recommended default:

```text
strict
```

Optional future mode:

```text
diagnostic
```

`diagnostic` should still never show secrets, tokens, headers, signatures, raw responses, full private ids, full phone numbers, or full addresses.

## Implementation Order

Recommended next implementation phase:

```text
Phase ERP-UX-1K: TechnicalDetails safety hardening implementation
```

Implementation steps:

1. Add deny-list label matching inside `TechnicalDetails.jsx`.
2. Add value-based sensitive pattern checks.
3. Add `redactTechnicalObject`.
4. Update Logs JSON before/after details to use the helper.
5. Update Orders and Products diagnostic objects if they render raw objects as children.
6. Keep allowed safe fields visible.
7. Add static scan documentation and browser smoke check.

## Acceptance Criteria For 1K

The implementation should prove:

- `TechnicalDetails` still renders collapsed by default.
- safe fields still display.
- token-like labels are hidden.
- token-like values are hidden even under harmless labels.
- header/signature/client secret/raw response fields are hidden.
- buyer/receiver phone/address fields are hidden unless already masked and explicitly safe.
- JSON object rendering does not leak sensitive keys.
- Logs detail before/after JSON is still available when safe, but unsafe values are hidden.
- Dashboard, Orders, Products, Sales, API Capabilities, Credentials, and Logs still build.
- no mojibake appears.
- formal Naver product/order sync remains closed.

## Non-Goals

This plan does not:

- create a backend audit table.
- change Codex1 payloads.
- change database schema.
- call platform APIs.
- write local data.
- open formal sync.
- replace backend sanitization.

Frontend redaction is a last-line-of-defense guard, not a substitute for backend privacy and secret handling.

## Risk Notes

Potential risks:

- Over-redaction could hide useful admin diagnostics.
- Under-redaction could leak secrets or privacy.
- Children content is harder to protect than structured `items`.

Mitigation:

- Start strict.
- Keep explicit allow-list for known safe fields.
- Migrate high-risk child renderers to `redactTechnicalObject`.
- Document any intentional exception in the phase file and keep it inside folded details only.
